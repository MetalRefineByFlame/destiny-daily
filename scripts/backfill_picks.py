# -*- coding: utf-8 -*-
"""
回填台账：把 output/ 下历史报告中「已经推送过」的彩票号码补记进
data/lottery_picks.json，使回溯核对功能对历史推荐同样生效。

解析的是最终 TXT 报告正文，因此记录的号码与实际推送给用户的完全一致。

用法：
    python scripts/backfill_picks.py                        # 扫描 output/ 下全部报告
    python scripts/backfill_picks.py 2026-10-07             # 只处理指定日期的报告
    python scripts/backfill_picks.py 2026-10-11 2026-10-16  # 区间确定性复算回填
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import lottery_result        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output")

GAMES = ("双色球", "大乐透", "快乐8")


def parse_one(path: str):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    date_s = ""
    score = 0.0
    game = ""
    nums = ""
    for i, ln in enumerate(lines):
        m = re.match(r"^(\d{4})年(\d{2})月(\d{2})日", ln)
        if m:
            date_s = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = re.search(r"今日彩气\s*([\d.]+)", ln)
        if m:
            score = float(m.group(1))
        if "（今日唯一推荐）" in ln:
            for g in GAMES:
                if g in ln:
                    game = g
                    break
        m = re.match(r"^\s*号码：(.+)$", ln)
        if m:
            nums = m.group(1)

    if not (date_s and game and nums):
        return None

    if "  +  " in nums:
        a, b = nums.split("  +  ")
    elif " + " in nums:
        a, b = nums.split(" + ")
    else:
        a, b = nums, ""
    front = [int(x) for x in re.findall(r"\d+", a)]
    back = [int(x) for x in re.findall(r"\d+", b)]
    return date_s, game, front, back, score


def recompute_range(a: str, b: str) -> int:
    """
    按区间**确定性复算**推荐号码并记账。

    用途：某段时间没在本地跑过报告（例如云端 CI 生成、本地没落盘），
    但号码本身由「日期 + 盘面数源」固定种子决定，重算结果与当日实际推送一致。
    """
    from datetime import timedelta

    from engine.synthesize import generate, load_profile

    prof = load_profile()
    d = datetime.strptime(a, "%Y-%m-%d")
    end = datetime.strptime(b, "%Y-%m-%d")
    n = 0
    while d <= end:
        r = generate(d.replace(hour=8), prof, offline=True)
        ld = r["invest"].get("lottery_detail") or {}
        if ld.get("skip") or not ld.get("picks"):
            print(f"[skip] {d:%Y-%m-%d} 当日建议停买，无号码")
        else:
            p = ld["picks"][0]
            lottery_result.record_pick(d, p["game"], p["front"],
                                       p.get("back") or [],
                                       ld.get("score", 0.0), recomputed=True)
            print(f"[ok] {d:%Y-%m-%d}  {p['game']}  "
                  + " ".join(f"{x:02d}" for x in p["front"])
                  + (("  +  " + " ".join(f"{x:02d}" for x in p["back"]))
                     if p.get("back") else "")
                  + f"   (彩气 {ld.get('score', 0):.0f})")
            n += 1
        d += timedelta(days=1)
    print(f"[done] 复算回填 {n} 条")
    return n


def main() -> int:
    only = None
    rng: list[str] = []
    for a in sys.argv[1:]:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", a):
            rng.append(a)
    if len(rng) == 2:                       # 两个日期 → 区间复算回填
        recompute_range(rng[0], rng[1])
        return 0
    if rng:                                 # 一个日期 → 只处理该日的报告
        only = rng[0]
    files = sorted(
        os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
        if f.startswith("destiny-") and f.endswith(".txt")
    )
    n = 0
    for p in files:
        r = parse_one(p)
        if not r:
            continue
        date_s, game, front, back, score = r
        if only and date_s != only:
            continue
        try:
            day = datetime.strptime(date_s, "%Y-%m-%d")
        except ValueError:
            continue
        lottery_result.record_pick(day, game, front, back, score)
        print(f"[ok] {date_s}  {game}  "
              + " ".join(f"{x:02d}" for x in front)
              + (("  +  " + " ".join(f"{x:02d}" for x in back)) if back else "")
              + f"   (彩气 {score:.0f})")
        n += 1
    print(f"[done] 回填 {n} 条 -> {lottery_result.LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
