# -*- coding: utf-8 -*-
"""把本地文件推送到 GitHub 仓库（REST API 方式）。

为什么不用 git push：
    本机 git.exe 的出网常被拦（表现为连接超时/被重置），而 HTTPS 的 REST 调用正常。
    Contents API 一次 PUT 一个文件，天然绕开 git 协议层面的问题。

用法：
    export GITHUB_TOKEN=github_pat_xxx
    python scripts/push_github.py <文件1> [文件2 ...]
    python scripts/push_github.py --all-changed        # 推送 git status 里的改动项

环境变量：
    GITHUB_TOKEN   必填。fine-grained PAT；改 .github/workflows/* 需要
                   「Workflows: Read and write」权限，否则上传会 403
    GITHUB_OWNER   默认 MetalRefineByFlame
    GITHUB_REPO    默认 destiny-daily
    GITHUB_BRANCH  默认 main
    COMMIT_MSG     自定义提交信息

说明：PUT 时带上文件的 blob sha 表示「更新已有文件」，不带 sha 表示「新建」。
脚本会自动向服务端查询 sha，因此新增和改动走同一条路径。
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

OWNER = os.environ.get("GITHUB_OWNER", "MetalRefineByFlame")
REPO = os.environ.get("GITHUB_REPO", "destiny-daily")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")


def _req(method: str, path: str, payload=None):
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        raise SystemExit("[error] 未设置环境变量 GITHUB_TOKEN")
    url = f"https://api.github.com{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "destiny-daily-push")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"[error] HTTP {e.code} {method} {path}\n{body[:600]}")


def get_sha(rel: str):
    """返回远端文件的 sha；文件不存在返回 None。"""
    path = f"/repos/{OWNER}/{REPO}/contents/{urllib.parse.quote(rel)}?ref={BRANCH}"
    try:
        return _req("GET", path).get("sha")
    except SystemExit as e:
        msg = str(e)
        if "HTTP 404" in msg:
            return None
        raise


def push_one(rel: str, msg: str) -> bool:
    try:
        with open(rel, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError as e:
        print(f"[skip] {rel}: {e}")
        return False

    payload = {
        "message": msg,
        "content": b64,
        "branch": BRANCH,
    }
    sha = get_sha(rel)
    if sha:
        payload["sha"] = sha
        action = "更新"
    else:
        action = "新增"

    res = _req("PUT", f"/repos/{OWNER}/{REPO}/contents/{urllib.parse.quote(rel)}", payload)
    commit = res.get("commit", {}).get("sha", "")[:8]
    size = res.get("content", {}).get("size", 0)
    print(f"[{action}] {rel:<42} {size:>7} 字节  commit={commit}")
    return True


def delete_one(rel: str, msg: str) -> bool:
    """删除远端文件（本地已删掉的模块，云端也要跟着删，否则仓库里留着死代码）。"""
    sha = get_sha(rel)
    if not sha:
        print(f"[skip] {rel:<42} 远端本来就没有")
        return True
    _req("DELETE", f"/repos/{OWNER}/{REPO}/contents/{urllib.parse.quote(rel)}",
         {"message": msg, "sha": sha, "branch": BRANCH})
    print(f"[删除] {rel:<42} 已从 {BRANCH} 移除")
    return True


def changed_files() -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # 形如 " M path" / "?? path" / "R  old -> new"
        rest = line[3:].strip()
        if "->" in rest:
            rest = rest.split("->", 1)[1].strip()
        files.append(rest.strip('"'))
    return files


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    # --delete a.py b.py：同步删除远端文件（本地删掉的模块要一起清掉）
    if args[0] == "--delete":
        files = args[1:]
        if not files:
            print("[error] --delete 后面要跟文件路径")
            return 1
        msg = os.environ.get("COMMIT_MSG") or f"删除 {len(files)} 个文件"
        print(f"[info] 目标 {OWNER}/{REPO}@{BRANCH}")
        print(f"[info] 提交信息：{msg}\n")
        ok = sum(1 for f in files if delete_one(f.replace("\\", "/"), msg))
        print(f"\n完成：删除 {ok}/{len(files)} 个")
        return 0 if ok == len(files) else 1

    if args[0] == "--all-changed":
        files = changed_files()
        if not files:
            print("[info] 没有待推送的改动")
            return 0
        print(f"[info] 从 git status 取到 {len(files)} 个改动项")
    else:
        files = args

    msg = os.environ.get("COMMIT_MSG") or (
        f"更新 {len(files)} 个文件（destiny-daily 本地推送）")
    print(f"[info] 目标 {OWNER}/{REPO}@{BRANCH}")
    print(f"[info] 提交信息：{msg}\n")

    ok = sum(1 for f in files if push_one(f.replace("\\", "/"), msg))
    print(f"\n完成：{ok}/{len(files)} 个文件")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    raise SystemExit(main())
