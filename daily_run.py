# -*- coding: utf-8 -*-
"""
destiny-daily :: 每日运势跑批入口

用法：
    python daily_run.py                    # 生成今天
    python daily_run.py 2026-10-01         # 生成指定日
    python daily_run.py --days 7           # 连续生成 7 天
    python daily_run.py --text             # 仅输出文本摘要到 stdout
    python daily_run.py --stdout-text      # 生成文件的同时把摘要打到 stdout(供邮件正文)
    python daily_run.py --tz-offset 8      # 按 UTC+8 判定"今天"（云端部署必用）

时区说明（云端部署必读）：
    CI runner 的系统时区通常是 UTC。若直接用 datetime.now()，
    在 UTC 机器上取到的是 UTC 日期，与目标时区可能差一天。
    本脚本默认按 **UTC+8（北京时间）** 判定"今天"，可用 --tz-offset 覆盖，
    也可设环境变量 DESTINY_TZ_OFFSET。
    显式传入 YYYY-MM-DD 时，时区参数不生效。

产出：
    output/destiny-YYYY-MM-DD.html   完整报告（浏览器打开/打印）
    output/destiny-YYYY-MM-DD.txt    纯文本摘要（邮件正文）
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.base import ensure_cst          # noqa: E402
from engine.synthesize import generate, load_profile   # noqa: E402
from engine.report import save_report, render_text, OUT_DIR  # noqa: E402

DEFAULT_TZ_OFFSET = 8.0      # 北京时间 UTC+8


def today_in_tz(offset: float = DEFAULT_TZ_OFFSET) -> datetime:
    """按目标时区（默认 UTC+8）返回当前日历日，避免 CI runner 的 UTC 时区导致跨日错位。"""
    utc_now = datetime.now(timezone.utc)
    local = utc_now + timedelta(hours=offset)
    return datetime(local.year, local.month, local.day, 8, 0)


def run_one(day: datetime, text_only: bool = False,
            print_text: bool = False) -> dict:
    day = ensure_cst(day)
    prof = load_profile()
    r = generate(day, prof)
    if text_only:
        print(render_text(r))
        return r
    paths = save_report(r, OUT_DIR, day)
    print(f"[OK] {day.strftime('%Y-%m-%d')} 运势 {r['meta']['total']:.0f} 分"
          f"（{r['meta']['grade']}）")
    print(f"     HTML  -> {paths['html']}")
    print(f"     邮件版 -> {paths['mail']}")
    print(f"     TXT   -> {paths['txt']}")
    if print_text:
        print("\n-----8<-----")
        print(render_text(r))
    return r


def main() -> int:
    args = [a for a in sys.argv[1:]]
    text_only = "--text" in args
    print_text = "--stdout-text" in args
    days = 1
    target = None
    tz_offset = float(os.environ.get("DESTINY_TZ_OFFSET", DEFAULT_TZ_OFFSET))

    for a in args:
        if a.startswith("--days"):
            days = int(a.split("=", 1)[-1]) if "=" in a else 1
        elif a.startswith("--tz-offset"):
            tz_offset = float(a.split("=", 1)[-1])
        elif a.startswith("--") or "=" in a:
            continue
        else:
            try:
                target = datetime.strptime(a, "%Y-%m-%d")
            except ValueError:
                pass

    base = target or today_in_tz(tz_offset)
    print(f"[tz] 按 UTC{tz_offset:+g} 判定今日 -> {base.strftime('%Y-%m-%d')}")
    for i in range(max(1, days)):
        run_one(base + timedelta(days=i), text_only=text_only, print_text=print_text)
        if i < days - 1:
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
