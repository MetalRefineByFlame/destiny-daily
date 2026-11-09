#!/usr/bin/env bash
# 一键部署：把本地修复推送到 GitHub 仓库并校验生效
#
# 用法（在项目目录下打开 Git Bash）：
#   bash scripts/deploy.sh
#   → 屏幕提示时粘贴 fine-grained PAT（输入不回显），回车即可
#
# 也可预先设置环境变量：
#   GITHUB_TOKEN=github_pat_xxx bash scripts/deploy.sh
#
# PAT 要求（fine-grained，只选 MetalRefineByFlame/destiny-daily 这一个仓库）：
#   Contents  : Read and write     ← 推送代码/台账
#   Workflows : Read and write     ← 修改 .github/workflows/* 必需，缺了会 403
set -u
cd "$(dirname "$0")/.." || exit 1

# 2026-11-09 三条调整（黄历 / 健康 / 投资）+ 隐私改造的精确清单。
# 【重要】绝不能加 data/lottery_picks.json：本地台账含「复算补录」标记，
# 推上去会覆盖云端真实推送记录。也不要用 push_github.py --all-changed。
FILES=(
  engine/almanac.py
  engine/therapy.py
  engine/astock.py
  engine/wool.py
  engine/market.py
  engine/synthesize.py
  engine/report.py
  engine/mail_report.py
  verify.py
  README.md
  .github/workflows/daily-destiny.yml
  scripts/make_profile.py
  scripts/deploy.sh
  .gitignore
)

TOK="${GITHUB_TOKEN:-}"
if [ -z "$TOK" ]; then
  printf '请粘贴 GitHub fine-grained PAT（输入不回显，回车确认）：'
  read -rs TOK
  echo
fi
if [ -z "$TOK" ]; then
  echo '未提供令牌，已取消。'
  exit 1
fi

PY=''
for p in 'C:/Users/江/.workbuddy/binaries/python/versions/3.13.12/python.exe' python3 python; do
  if [ -x "$p" ] || command -v "$p" >/dev/null 2>&1; then PY="$p"; break; fi
done
if [ -z "$PY" ]; then
  echo '找不到 python，请先安装或在 PATH 中提供。'
  exit 1
fi

echo "--- 推送中（${#FILES[@]} 个文件） ---"
if ! GITHUB_TOKEN="$TOK" "$PY" -B scripts/push_github.py "${FILES[@]}"; then
  echo
  echo '推送失败。常见原因：'
  echo '  1) 令牌缺 Workflows: Read and write（改工作流文件会 403）'
  echo '  2) 令牌缺 Contents: Read and write'
  echo '  3) 令牌已过期，或没有这个仓库的权限'
  exit 1
fi

echo
echo '--- 校验仓库 ---'
"$PY" -B - <<'PYEOF'
import base64
import json
import urllib.request

UA = {"User-Agent": "destiny-deploy", "Accept": "application/vnd.github+json"}
BASE = "/repos/MetalRefineByFlame/destiny-daily"


def get(path):
    req = urllib.request.Request("https://api.github.com" + path, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())


def raw(path):
    d = get(BASE + "/contents/" + path + "?ref=main")
    return base64.b64decode(d["content"]).decode("utf-8")


def mark(hit, label):
    print(("[OK]   " if hit else "[未生效] ") + label)
    return hit


ok = True
names = [x["name"] for x in get(BASE + "/contents/engine?ref=main")]
for f in ("almanac.py", "therapy.py", "astock.py"):
    ok = mark(f in names, "engine/" + f) and ok

wf = raw(".github/workflows/daily-destiny.yml")
ok = mark("DESTINY_CONSTITUTION" in wf, "工作流注入体质 Secret") and ok
ok = mark("行情数据源自检" in wf, "工作流含行情数据源自检") and ok
ok = mark("回写彩票台账" in wf, "工作流保留台账回写") and ok

ok = mark("隐私：体质档案走 Secret" in raw("README.md"), "README 隐私说明") and ok

# 反向确认：个人健康描述没有被写进公开代码
th = raw("engine/therapy.py")
ok = mark(all(w not in th for w in ("齿痕舌", "月牙", "清水鼻涕")),
          "公开代码不含个人健康描述") and ok

print()
print("结论：" + ("三条调整 + 隐私改造已上线；请确认 Secrets 已配置 DESTINY_CONSTITUTION。"
                 if ok else "仍有文件未更新，请把上面的输出发给 WorkBuddy。"))
PYEOF
