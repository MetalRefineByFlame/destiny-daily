# -*- coding: utf-8 -*-
"""手动触发每日运势工作流（workflow_dispatch）。

用法：
    export GITHUB_TOKEN=github_pat_xxx
    python scripts/trigger_action.py            # 正常触发
    python scripts/trigger_action.py --force    # 强制发送（忽略当日幂等标记）
    python scripts/trigger_action.py --wait     # 触发后轮询运行直至结束并打印结论

环境变量：
    GITHUB_TOKEN   必填，需要 Actions: Read and write 权限
    GITHUB_OWNER / GITHUB_REPO / GITHUB_BRANCH

为什么需要 --force：
    仓库开了「当日幂等」——同一天已成功发过就自动跳过。
    临时 DEBUG 或想当天补发一封时，必须勾上 force，否则会看到 decision=no 的跳过。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

OWNER = os.environ.get("GITHUB_OWNER", "MetalRefineByFlame")
REPO = os.environ.get("GITHUB_REPO", "destiny-daily")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")


def _req(method: str, path: str, payload=None):
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        raise SystemExit("[error] 未设置环境变量 GITHUB_TOKEN")
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "destiny-daily")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[error] HTTP {e.code} {method} {path}\n"
                         f"{e.read().decode('utf-8', 'replace')[:500]}")


def trigger(force: bool) -> None:
    _req("POST",
         f"/repos/{OWNER}/{REPO}/actions/workflows/daily-destiny.yml/dispatches",
         {"ref": BRANCH, "inputs": {"force": "true" if force else "false"}})
    print(f"[OK] 已触发 {OWNER}/{REPO}@{BRANCH}（force={force}）")


def latest_run():
    runs = _req("GET",
                f"/repos/{OWNER}/{REPO}/actions/workflows/daily-destiny.yml/"
                f"runs?per_page=1")["workflow_runs"]
    return runs[0] if runs else None


def wait_run(run_id: int, timeout: int = 300) -> None:
    print(f"[info] 等待 run {run_id} ...")
    waited = 0
    while waited < timeout:
        r = _req("GET", f"/repos/{OWNER}/{REPO}/actions/runs/{run_id}")
        status, concl = r.get("status"), r.get("conclusion")
        if status == "completed":
            print(f"\n[{'OK' if concl == 'success' else 'FAIL'}] "
                  f"运行结束：{concl}")
            jobs = _req("GET", f"/repos/{OWNER}/{REPO}/actions/runs/{run_id}/jobs")
            for j in jobs.get("jobs", []):
                print(f"    - {j['name']:<16} {j['conclusion']}")
            return
        print(f"    {status} ... ({waited}s)")
        time.sleep(10)
        waited += 10
    print(f"[warn] 超时 {timeout}s，去网页看："
          f"https://github.com/{OWNER}/{REPO}/actions/runs/{run_id}")


def main() -> int:
    args = sys.argv[1:]
    force = "--force" in args
    do_wait = "--wait" in args
    if not args or "-h" in args:
        print(__doc__)
        return 1

    before = latest_run()
    trigger(force)
    if not do_wait:
        print(f"[info] 查看进度：https://github.com/{OWNER}/{REPO}/actions")
        return 0

    time.sleep(12)
    run = latest_run()
    if not run or (before and run["id"] == before["id"]):
        print("[warn] 未捕捉到新 run，可能被平台调度延迟")
        return 1
    print(f"[info] run {run['id']} · {run['display_title']} · {run['html_url']}")
    wait_run(run["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
