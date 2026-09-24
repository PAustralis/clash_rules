#!/usr/bin/env python3
"""final_config.yaml 的结构完整性校验。

mihomo -t 只校验语法；本脚本补上 mihomo 不会报错的引用完整性问题：
  - rules 的目标策略是否存在（策略组名写错时 mihomo 会静默不匹配）
  - RULE-SET 引用的规则集是否已定义
  - 策略组的 use / proxies 引用是否存在
  - dns 里 rule-set:xxx 引用的规则集是否已定义
  - 订阅占位符是否被替换、URL 是否为空（Secrets 漏配时能拦住）

用法：python3 validate_config.py [配置文件，默认 final_config.yaml]
"""

import sys

import yaml

BUILTIN_POLICIES = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE", "GLOBAL"}
RULE_FLAGS = {"no-resolve", "src"}
PLACEHOLDERS = ("GLaDOS_URL", "TAG_URL", "Mojie_URL")


def top_level_fields(rule):
    """按顶层逗号切分一条规则，忽略括号内的逗号。"""
    fields, current, depth = [], "", 0
    for ch in rule:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            fields.append(current)
            current = ""
        else:
            current += ch
    fields.append(current)
    return [f.strip() for f in fields]


def rule_target(parts):
    """取出规则末尾的目标策略，跳过 no-resolve 这类修饰符。"""
    for field in reversed(parts[1:]):
        if field and field not in RULE_FLAGS:
            return field
    return ""


def collect_dns_ruleset_refs(dns):
    """收集 dns 段里所有 rule-set:xxx 引用。"""
    refs = set()
    for key in dns.get("nameserver-policy") or {}:
        for token in str(key).split(","):
            token = token.strip()
            if token.startswith("rule-set:"):
                refs.update(n.strip() for n in token[len("rule-set:"):].split(",") if n.strip())
    for item in dns.get("fake-ip-filter") or []:
        if isinstance(item, str) and item.startswith("rule-set:"):
            refs.update(n.strip() for n in item[len("rule-set:"):].split(",") if n.strip())
    return refs


def validate(path):
    text = open(path, encoding="utf-8").read()
    cfg = yaml.safe_load(text) or {}
    errors = []

    groups = [g["name"] for g in cfg.get("proxy-groups") or []]
    if len(groups) != len(set(groups)):
        errors.append("proxy-groups 里有重名策略组")
    policies = set(groups) | BUILTIN_POLICIES

    rule_providers = set(cfg.get("rule-providers") or {})
    proxy_providers = set(cfg.get("proxy-providers") or {})
    proxies = {p["name"] for p in cfg.get("proxies") or []}

    for group in cfg.get("proxy-groups") or []:
        name = group["name"]
        if group.get("include-all") and group.get("use"):
            errors.append(f"策略组 {name} 同时写了 include-all 和 use")
        for provider in group.get("use") or []:
            if provider not in proxy_providers:
                errors.append(f"策略组 {name} 的 use 引用了不存在的订阅源 {provider}")
        for proxy in group.get("proxies") or []:
            if proxy not in policies and proxy not in proxies:
                errors.append(f"策略组 {name} 的 proxies 引用了不存在的节点/组 {proxy}")

    rules = cfg.get("rules") or []
    for index, rule in enumerate(rules):
        parts = top_level_fields(str(rule))
        if not parts or not parts[0]:
            errors.append(f"rules[{index}] 是空规则")
            continue
        if parts[0] == "RULE-SET" and len(parts) > 1 and parts[1] not in rule_providers:
            errors.append(f"rules[{index}] 引用了未定义的规则集 {parts[1]}")
        target = rule_target(parts)
        if target and target not in policies and target not in proxies:
            errors.append(f"rules[{index}] 的目标策略 {target!r} 不存在")
        if parts[0] == "MATCH" and index != len(rules) - 1:
            errors.append(f"rules[{index}] MATCH 不在最后一条")

    for name in sorted(collect_dns_ruleset_refs(cfg.get("dns") or {})):
        if name not in rule_providers:
            errors.append(f"dns 段引用了未定义的规则集 {name}")

    for name, provider in (cfg.get("proxy-providers") or {}).items():
        url = str(provider.get("url", ""))
        if not url.startswith(("http://", "https://")):
            errors.append(f"订阅源 {name} 的 url 无效（Secrets 是否配置齐全？）")
    for placeholder in PLACEHOLDERS:
        if placeholder in text:
            errors.append(f"占位符 {placeholder} 没有被替换（检查仓库 Secrets）")

    return errors, len(groups), len(rule_providers), len(rules)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "final_config.yaml"
    errors, group_count, provider_count, rule_count = validate(path)
    if errors:
        print("配置校验不通过：", file=sys.stderr)
        for error in errors:
            print("  - " + error, file=sys.stderr)
        return 1
    print(f"配置校验通过：{group_count} 个策略组 / {provider_count} 个规则集 / {rule_count} 条规则")
    return 0


if __name__ == "__main__":
    sys.exit(main())
