# 离线可用：把早 8 点推送搬到云端

## 问题根源

现在的定时任务记在 `LocalAutomationScheduler`（见 `%USERPROFILE%\.workbuddy\logs\automation.log`），
它跑在**你本机**的 WorkBuddy 里。电脑关机 → 调度进程本身不存在 → 任务不可能触发。
这不是配置问题，是本地调度的结构性限制，改参数救不了。

要"人不在公司也能 8 点收到"，**代码必须搬到一个始终在线的地方**。

---

## 方案对比

| 方案 | 可靠性 | 费用 | 代码改动 | 门槛 |
|---|---|---|---|---|
| **A. Cloudflare Cron → GitHub Actions**（推荐） | 高 | ¥0 | 极小（原生 Python 直接跑） | CF 账号 + GitHub PAT |
| B. Cloudflare Workers 直接跑 Python | 高 | $5/月 | 大（10ms CPU 不够，且须重写网络层） | 需付费套餐 |
| C. GitHub Actions 原生 cron | **低** | ¥0 | 极小 | 已知平台故障 |
| D. 轻量云服务器 + cron | 最高 | ¥24/月起 | 几乎为零 | 需购买、实名、运维 |
| E. BIOS RTC 定时开机 | 中 | ¥0 | 无 | 须插电 + 主板支持 + 公司政策风险 |

**为什么不选 C**：社区自 2026-08-26 起大量报告 Actions 的 `schedule` 触发器延迟 3–10 小时甚至完全不触发，
而同样的 workflow 用 `workflow_dispatch` 手动触发秒起，证明是调度器本身的问题。

**为什么不选 B**：免费套餐 Cron 触发的 Worker 只有 **10ms CPU 时间**。本项目的农历模块要迭代求根算朔日和
24 节气，严重超时。付费版（$5/月）才有 30s——既然要花钱，不如直接上方案 D。

**推荐 A 的原因**：CF Cron 可靠 + GitHub Actions 跑原生 Python 零移植 + 完全免费，
恰好避开两边的短板。社区推荐的标准做法。

---

## 隐私设计（仓库是公开的，务必理解这一节）

出生年月日时、出生地经度、收件邮箱、姓名，**一律不进仓库**。做法：

| 文件 | 是否入库 | 内容 |
|---|---|---|
| `data/profile.example.json` | ✅ 入库 | 全是占位值（1990-01-01 12:00 / 东经 120.00） |
| `data/profile.json` | ❌ gitignore | 真实档案，本地由脚本生成；云端由 Secrets 现场生成 |
| `output/` | ❌ gitignore | 每日报告，含个人化内容 |

注入链路：

```
GitHub Secrets (DESTINY_* / MAIL_TO / SMTP_*)
        │  scripts/make_profile.py --force
        ▼
   data/profile.json（运行时生成，用完即弃）
        │  daily_run.py
        ▼
   报告 → SMTP 发信
```

本机要重建档案：

```bash
set DESTINY_NAME=江公子
set DESTINY_GENDER=male
set DESTINY_BIRTH=1980-07-17 09:28
set DESTINY_LONGITUDE=119.30
set DESTINY_CITY=福州
set DESTINY_EMAIL=你的邮箱@qq.com
python scripts/make_profile.py --force
```

> ⚠ 仍有一处需要你自己权衡：`verify.py` 第三节写死了本命盘的期望值（四柱 / 强弱 / 起运 / 大运序列）。
> 它只在本地检测到真实档案时才运行，但常量本身在公开代码里。若介意，删掉该节即可，其余 18 项校验不受影响。

---

## 费用：长期 ¥0/月

| 环节 | 套餐 | 收费 | 我们的用量 | 结论 |
|---|---|---|---|---|
| GitHub 仓库 | Free（Public） | ¥0 | 1 个公开仓库 | **公开仓库的 Actions 分钟数不限量**（所有套餐都如此） |
| GitHub Actions | Free | ¥0 | 每天 1 次、约 1–2 分钟（标准 2 核 Linux runner） | 不计费。仅当改用**私有**仓库时才计入 2000 分钟/月免费额度 |
| Cloudflare Workers | Free | ¥0 | 每天 1 次 cron 触发 | 免费套餐 10 万次请求/日、每账号 5 个 Cron Trigger，我们只用 1 个，离限额差五个数量级 |
| QQ 邮箱 SMTP | — | ¥0 | 每天 1 封 | QQ 邮箱自带，免费 |

**唯一需要留意的两件事**：

1. **GitHub PAT 有有效期**（fine-grained 最长 1 年）。到期后 CF 触发会静默失败 → 不再推送。
   建议设 1 年，并在手机日历里加一条「换 destiny-daily 的 GitHub token」提醒（到期前一周）。
   换的时候只需在 Cloudflare 的 Worker 变量里更新 `GITHUB_TOKEN`，不用重跑部署。
2. **App 密码/授权码失效**：QQ 邮箱若改密码或关闭 SMTP 服务，授权码会失效。
   现象是每天收到一封 `[失败]` 告警邮件——看到就重开 SMTP 服务拿新码，替换 `SMTP_PASS` 即可。

不会自动扣费的情况：本方案没有任何「超出免费额度自动转付费」的入口，
CF 与 GitHub 免费套餐超限时是**拒绝服务**而不是扣款。

---

## 凭据去哪找（附精确路径）

### GitHub 用户名

登录 github.com，右上角头像 → **Settings**，或地址栏就是 `github.com/<用户名>`。
用户名是 `<用户名>`，不是邮箱、不是昵称。

### GitHub Personal Access Token

> 顺序很重要：**先建空仓库，再生成 token**（fine-grained token 必须绑定到具体仓库）。

**第 1 步 · 建空仓库**（网页右上角 `+` → New repository）

- Repository name：`destiny-daily`
- 选 **Public**
- **不要**勾 Add a README file / Add .gitignore / Choose a license（保持完全空白，否则推送会冲突）
- 点 Create repository

**第 2 步 · 生成 token**

右上角头像 → **Settings** → 左侧栏最下方 **Developer settings**
→ **Personal access tokens** → **Fine-grained tokens** → **Generate new token**

| 字段 | 填什么 |
|---|---|
| Token name | `destiny-daily-scheduler` |
| Expiration | 建议 **1 年**（Custom，最长 366 天） |
| Repository access | **Only select repositories** → 选 `destiny-daily` |
| Permissions → Actions | **Read and write** |
| Permissions → Secrets | **Read and write** |
| Permissions → Contents | **Read and write** |
| Permissions → Metadata | Read-only（默认，不用动） |

点 Generate token，**只显示一次**，立刻复制（`github_pat_` 开头的一长串）。

### Cloudflare Account ID

登录 dash.cloudflare.com → 左侧 **Workers & Pages** → 右侧栏最下方就能看到 **Account ID**（32 位十六进制）。
或者进任意域名 → **Overview** 页右下角 API 区也有。

### Cloudflare API Token

右上角头像 → **My Profile** → 左侧 **API Tokens** → **Create Token**
→ 找到模板 **Edit Cloudflare Workers** → Use template

- Account Resources：选你的账号（Include → 你的账号名）
- Zone Resources：保持默认（这个 token 不需要改 DNS）
- 其余不动 → **Continue to summary** → **Create Token**

同样只显示一次，复制保存。

> 这个 token 的权限是「编辑 Workers 脚本」，碰不到你的域名解析和证书，也碰不到 ResumeForge 的 Pages。
> 真不放心，部署完可以在 API Tokens 页面把它删掉，Worker 照常跑。

---

## 方案 A 部署步骤

```
Cloudflare Cron (UTC 00:00, 可靠)
        │  HTTP POST /dispatches
        ▼
GitHub Actions runner (ubuntu + Python 3.12)
        │  python daily_run.py
        ▼
SMTP 发信 → 你的邮箱
```

### 第 1 步：建 GitHub 仓库并推送

```bash
cd D:/WorkBuddy/2026-09-28-13-14-40/destiny-daily
git init
git add .
git commit -m "五术日课：每日运势"
git remote add origin https://github.com/<你的用户名>/destiny-daily.git
git push -u origin main
```

仓库设 **Public**（公开仓库的 Actions 分钟数不限量，且不会因 60 天无活动自动停用定时任务）。

推送前自查，确认没有敏感文件被带上：

```bash
git status --short                 # 不应出现 data/profile.json 或 output/
git ls-files | grep -E "profile.json|output/"   # 应为空
```

### 第 2 步：拿 GitHub Personal Access Token

GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens**
→ Generate new token

- Repository access：**只选** `destiny-daily`
- Permissions → Actions：**Read and write**
- Metadata：Read-only（默认）

生成后复制保存（只显示一次）。

### 第 3 步：部署触发 Worker

```bash
cd cloudflare
npm i -g wrangler          # 已有可跳过
wrangler login

wrangler secret put GITHUB_TOKEN     # 粘贴第 2 步的 token
wrangler secret put GITHUB_OWNER     # 例：jianggongzi
wrangler secret put GITHUB_REPO      # 例：destiny-daily

wrangler deploy
```

### 第 4 步：立刻验证（不要等到明早）

部署成功后 wrangler 会给出 Worker 地址，手动打一次：

```bash
curl -X POST https://destiny-daily-scheduler.<你的子域>.workers.dev/trigger
```

去 GitHub 仓库的 Actions 页看是否出现一条新运行记录。**这一步必须做**——
真实触发生效一次，才说明整条链路通了。

### 第 5 步：配 GitHub Secrets

仓库 → Settings → Secrets and variables → Actions → New repository secret，逐个添加：

| Name | Value | 说明 |
|---|---|---|
| `DESTINY_NAME` | 江公子 | 报告抬头称呼 |
| `DESTINY_GENDER` | `male` | male / female |
| `DESTINY_BIRTH` | `1980-07-17 09:28` | 公历出生时刻，24 小时制 |
| `DESTINY_LONGITUDE` | `119.30` | 出生地东经度数 |
| `DESTINY_CITY` | 福州 | 仅展示用，可省 |
| `SMTP_HOST` | `smtp.qq.com` | QQ 邮箱 |
| `SMTP_PORT` | `465` | SSL 端口 |
| `SMTP_USER` | `你的邮箱@qq.com` | |
| `SMTP_PASS` | （16 位字母） | **SMTP 授权码**，不是 QQ 登录密码 |
| `MAIL_TO` | `你的邮箱@qq.com` | 可填多个，逗号分隔 |

QQ 邮箱授权码获取：QQ 邮箱网页版 → 设置 → 账户 → POP3/SMTP 服务 → 开启 → 发短信 → 得到授权码。

前 4 项缺失会导致 workflow 在「校验必要 Secrets」一步直接红叉报错，不会静默产出一份错报告。

### 第 6 步：本地先验证 SMTP（可选但推荐）

```bash
cd D:/WorkBuddy/2026-09-28-13-14-40/destiny-daily
set SMTP_HOST=smtp.qq.com
set SMTP_PORT=465
set SMTP_USER=你的邮箱@qq.com
set SMTP_PASS=你的授权码
set MAIL_TO=你的邮箱@qq.com
python daily_run.py
python notify_mail.py output/destiny-<今天>.txt output/destiny-<今天>.html
```

本机就能确认 SMTP 是否通，不必等 Actions。
先跑 `python notify_mail.py ... --dry-run` 可只看主题和收件人不真发。

---

## 时间对照

Cron 一律 **UTC**：

| 你想收到 | Cron 表达式 |
|---|---|
| 北京时间 08:00 | `0 0 * * *` |
| 北京时间 07:30 | `30 23 * * *`（前一天） |

夏令时无需处理，中国不实行夏令时，全年固定 UTC+8。

已在两个位置做了时区保护：

1. `daily_run.py` 默认按 **UTC+8** 判定"今天"，不依赖 runner 的系统时区（`--tz-offset` 可覆盖）
2. Workflow 设置 `TZ: Asia/Shanghai` + `DESTINY_TZ_OFFSET: '8'`

实测边界全部正确：UTC 23:59→09-29、00:00→09-29、15:59→09-28、16:00→09-29。

---

## 失败保护

- **Secrets 缺失**会在第一步红叉并列出缺哪个，避免产出基于占位生日的错报告
- **BTC 行情抓取失败**会优雅降级（报告注明"行情未取到"），不会让整轮任务失败
- **报告生成失败**会发一封标题带 `[失败]` 的告警邮件，不会静默无声
- 想要更保险的监控：在 Worker 里加一道"9:00 还没收到成功回调就告警"的逻辑

## 部署完成后

把本机那条 `每日运势早报（五术日课）` 自动化任务暂停，避免重复收到两封：

```python
automation_update(mode="update", id="ad2a1880-6dbe-4440-b660-d2b7189ac2b7", status="PAUSED")
```
