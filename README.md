# clash_rules

自用 Clash / Mihomo 规则仓库:**push 即生效** —— Action 用 `mihomo -t` 校验,通过后才把最终配置 PATCH 到 gist,
路由器上的 OpenClash 从 gist 拉取。

## 文件

| 文件 | 作用 |
| --- | --- |
| `Rules.yaml` | 主配置模板;`GLaDOS_URL` / `TAG_URL` / `Mojie_URL` 三个占位符由 Action 用 Secrets 替换 |
| `no-fake-ip.yaml` | 强制真实解析的域名清单,由 `dns.fake-ip-filter` 的 `rule-set:NoFakeIP` 引用 |
| `Openrouter.yaml` / `AIHubMix.yaml` | 自维护的 classical 规则集 |
| `.github/workflows/update_gist.yml` | 结构校验 + `mihomo -t` + 更新 gist |

## 为什么要 no-fake-ip.yaml

DSH(Harness)的网页抓取会拒绝解析到非公网 IP 的地址(fake-ip 段 `198.18.0.0/16` 会被拒),
所以"我会去抓、又不在 `fake-ip-filter` 里"的域名要单独列出来拿真实 IP。普通浏览不需要 —— 走假 IP 一样通。

- `behavior: domain` 的规则集只认精确域名和 `+.` 前缀;**通配符(`*.lan`、`stun.*.*`)必须写在 `Rules.yaml` 本体里**。
- 清单改动后内核会在下次启动或 `interval`(86400s)到期时重抓;想立刻生效:
  `rm /etc/openclash/rule_provider/nofakeip.yaml && /etc/init.d/openclash restart`。

## 更新流程

1. 改 `Rules.yaml` 或清单文件,push 到 `main`。
2. Action 自动校验 → 通过才更新 gist(不通过不会污染线上配置)。
3. 路由器更新订阅:
   ```sh
   sh /usr/share/openclash/openclash.sh 'Sub'
   /etc/init.d/openclash restart
   ```

## 本地自检(推之前)

```sh
python3 -c "import yaml;yaml.safe_load(open('Rules.yaml',encoding='utf-8'))"        # YAML 可解析
# 结构校验(与 Action 同一个脚本):把三个占位符换成假值即可直接跑
python3 .github/scripts/validate_config.py final_config.yaml
```

## 注意

- 仓库里**不放订阅链接**:占位符在 Action 里被替换,只有 gist 里才有真实地址。
- 规则集走 `github.com/<owner>/<repo>/raw/...`(不用 jsdelivr,避免分支缓存滞后)。
  OpenClash 的 `github_address_mod`(GitHub 加速)会把 provider URL 前缀成 jsdelivr 并拼坏别的 URL,
  本项目在路由器上已把该项清空。
