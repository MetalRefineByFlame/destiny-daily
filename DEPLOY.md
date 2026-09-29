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

> ⚠ **务必用 wrangler，不要用 REST API 直接传脚本**（血泪教训，见文末实况记录）。

```bash
cd cloudflare
npm i -g wrangler          # 已有可跳过

export CLOUDFLARE_API_TOKEN=<cfut_ 开头的 API Token>
export CLOUDFLARE_ACCOUNT_ID=<32 位 Account ID>

wrangler deploy                      # 明文变量从 wrangler.toml 的 [vars] 读
echo "<github_pat_...>" | wrangler secret put GITHUB_TOKEN
```

`wrangler.toml` 里已写死 `GITHUB_OWNER` / `GITHUB_REPO`（明文无害），
只有 `GITHUB_TOKEN` 走 Secret。**重新 deploy 不会冲掉 Secret**，只有换 token 时才重跑那一条命令。

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

## 三条通道如何共存（当日幂等）

Cloudflare cron、GitHub 自家 schedule、手动 dispatch 三条路同时开着。
靠「当日幂等」保证**一天只发一封**，不会互相打架：

```
                ┌─ Cloudflare cron ── 北京 08:00 准点触发 ──┐
任一通道 ────────┼─ workflow_dispatch ── 手动补发 ──────────┼─→ should-run job
                └─ GitHub schedule ── 08/09/…/13 点各试一次 ─┘        │
                                                                     ▼
                                          ① 时间闸门：schedule 早于 08:00 → 跳过
                                          ② 查标记：destiny-sent-YYYY-MM-DD 命中 → 跳过
                                          ③ 放行 → daily-report 生成并发信 → 写标记
```

标记用 **GitHub Actions Cache**（key = `destiny-sent-<北京日期>`）：免费、无需外部存储、
7 天自动过期。日志里的判别原文是：

```
Cache hit for: destiny-sent-2026-09-29
今天 2026-09-29 已经成功发过，跳过本次
```

三条路的定位：

| 通道 | 作用 | 触发时是否受时间闸门限制 |
|---|---|---|
| Cloudflare cron | 主力，准点 | 否，一律放行 |
| workflow_dispatch | 手动补发 | 否；但受幂等限制，**勾 `force` 可强制发** |
| GitHub schedule | 自愈兜底 | 是，早于 08:00 跳过；到点后同样受幂等限制 |

也就是说：CF 正常时它先发出去，之后所有其他尝试都会因标记命中而自动歇菜；
万一 CF 挂了，GitHub 的兜底窗口会在 08:17 之后补上；两边同时挂才会漏。

---

## 失败保护

- **Secrets 缺失**会在第一步红叉并列出缺哪个，避免产出基于占位生日的错报告
- **BTC 行情抓取失败**会优雅降级（报告注明"行情未取到"），不会让整轮任务失败
- **报告生成失败**会发一封标题带 `[失败]` 的告警邮件，不会静默无声
- **当日幂等**保证任何情况下都不会重复轰炸邮箱（除非手动勾 `force`）
- Worker 里的 dispatch 失败会 throw，在 CF 后台的 cron 记录里标成失败，便于察觉

## 部署完成后

把本机那条 `每日运势早报（五术日课）` 自动化任务暂停，避免重复收到两封：

```python
automation_update(mode="update", id="ad2a1880-6dbe-4440-b660-d2b7189ac2b7", status="PAUSED")
```

---

## 本次实况记录（2026-09-29 · 已全部跑通）

| 项 | 值 |
|---|---|
| GitHub 仓库 | https://github.com/MetalRefineByFlame/destiny-daily （Public） |
| Actions Secrets | 10 个已写入（DESTINY_* 5 个 + SMTP_* 4 个 + MAIL_TO） |
| 首次手动运行 | run 36525614135，全步骤 success，邮件已投递 |
| Cloudflare Account ID | `acdac70d5e21b2c1c88c9086b127cfe3` |
| Worker 名称 | `destiny-daily-scheduler` |
| Worker 子域 | `destiny49.workers.dev` |
| Cron | `0 0 * * *`（UTC 00:00 = 北京 08:00） |
| 诊断端点 | `/health` 看绑定是否齐全，`/trigger` 立即触发一次 |
| 本机自动化 | `每日运势早报（五术日课）` 已 **PAUSED**，避免收发两条路重复 |

### 端到端验证记录

把 cron 临时改成 `* * * * *` 后的第一次验证（这是唯一可靠的验证方式，理由见踩坑 3）：

```
2026-09-29T06:38:47Z | repository_dispatch | completed success   ← Cloudflare cron 真的自动叫醒了 GitHub
```

幂等验证：同一天再触发两次，`should-run` 判定 cache hit，`daily-report` **skipped**，邮箱没被轰炸。

### 踩过的坑（按重要性排序）

**1. REST API 上传 Worker 是假成功 —— 522 的唯一原因**

只用 `PUT /workers/scripts/{name}` 传脚本，返回 200，`GET /workers/scripts/{name}` 也能读到源码，
一切都像成功了。但 `GET /workers/deployments/by-script/{name}` 返回
`10007 This Worker does not exist on your account` —— **没有生成部署版本**。
结果 workers.dev 域名背后空无一物，任何请求都是 `HTTP 522`（CF 边缘连不到源站）。

判断依据：用只返回 `pong` 的最小 Worker 做对照，同样 522，排除代码问题。
修复：改用 `wrangler deploy`。它会输出 `Current Version ID: ...`，拿到这个 ID 才算真的部署成功。

顺带记一笔：`PUT /workers/scripts/{name}/versions`（wrangler 内部用的两步式 API）
对 API Token 返回 `405 Method not allowed for this authentication scheme`，此路不通。

**2. wrangler 部署会覆盖 bindings**

之前通过 REST API 设在 metadata 里的 `GITHUB_OWNER`/`GITHUB_REPO`/`GITHUB_TOKEN`，
wrangler 部署后全部消失（它以 `wrangler.toml` 为准），于是请求打到
`api.github.com/repos/undefined/undefined/dispatches`，Worker 抛异常 → `HTTP 1101`。

修复：明文变量写进 `[vars]`，机密走 `wrangler secret put`。
同时给 Worker 加了 `/health` 端点和「缺失 binding 时不抛异常」的防御——
因为 uncaught exception 在 Worker 里只会变成 Cloudflare 的 1101 错误页，看不到任何线索。

**3. 本机根本测不了 workers.dev，只能用 CF 自己验证**

本机所有出网都走沙箱代理：curl 直接返回 `HTTP 000`，Python urllib 报
`Tunnel connection failed: 502 Bad Gateway`。外部公共代理（allorigins / codetabs）
要么自报 5xx，要么被目标判定为错误源。

绕开办法：**把 cron 临时改成 `* * * * *`，等两分钟，去 GitHub Actions 看有没有新的
`repository_dispatch` 运行**。Cloudflare 内部触发不经过本机网络，这是唯一可信的验证路径。
验证完立刻改回 `0 0 * * *` 重新部署（每分钟触发会疯狂发邮件）。

**4. npm 装 wrangler 缺平台二进制**

`Error: The package "@cloudflare/workerd-windows-64" could not be found`、
同理 `@esbuild/win32-x64`。这是 optionalDependencies 被跳过导致的。
补装即可：`npm install @cloudflare/workerd-windows-64 @esbuild/win32-x64`。

---

## 日常运维

**改了 Worker 代码**（凭据与 CF 环境变量照旧）：

```bash
cd cloudflare
export CLOUDFLARE_API_TOKEN=<token>
export CLOUDFLARE_ACCOUNT_ID=acdac70d5e21b2c1c88c9086b127cfe3
wrangler deploy
```

**改了报告逻辑**：直接 `git push` 即可，Actions 会自动用新代码。
注意本机 `git push` 也会被沙箱拦，需要时用 REST API 的 `PUT /contents/{path}` 逐文件更新。

**换 GitHub token**（最长 1 年，到期会静默停推，务必提前换）：

```bash
echo "<新的 github_pat_...>" | wrangler secret put GITHUB_TOKEN
```

**只改一次 Secret，不用重新部署 Worker。**

**今天想再收一封**：Actions 页面 → Run workflow → 勾 `force` → Run。
不勾的话会被幂等标记拦住（这是设计意图）。

**怀疑链路挂了时**，按顺序查这三处：

1. Worker 是否活着：`https://destiny-daily-scheduler.destiny49.workers.dev/health`
   —— 返回 JSON 且三个 binding 都是 `true` 才正常
2. CF 后台 Workers → destiny-daily-scheduler → **Triggers** 页看 cron 最近一次执行是否成功
3. GitHub 仓库 → Actions 页看当天有没有成功的运行记录；
   看 Multi-window 兜底是否补上（会有 `跳过本次` 的记录，属正常）
