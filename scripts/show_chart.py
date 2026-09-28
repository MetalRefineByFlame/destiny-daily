# -*- coding: utf-8 -*-
"""
打印本命盘（读本地 data/profile.json，该文件不入公开仓库）。

用法：
    python scripts/show_chart.py
    python scripts/show_chart.py --now 2026-09-28     # 指定"当前"基准日
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.base import true_solar_time            # noqa: E402
from engine.bazi import analyze                    # noqa: E402


def main() -> int:
    now = datetime.now()
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a.startswith("--now"):
            val = a.split("=", 1)[-1] if "=" in a else (
                args[i + 1] if i + 1 < len(args) else "")
            if val:
                now = datetime.strptime(val, "%Y-%m-%d")

    path = os.path.join(ROOT, "data", "profile.json")
    try:
        with open(path, encoding="utf-8") as f:
            p = json.load(f)
    except OSError:
        raise SystemExit(f"[error] 找不到 {path}。先跑：python scripts/make_profile.py --force")

    if not p.get("birth_place_confirmed"):
        print("⚠ 当前档案的出生数据仍是模板占位值，下面结果无实际意义。")

    b = p["birth"]
    birth = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"])
    lon = float(p.get("birth_longitude", 120.0))
    tst = true_solar_time(birth, lon)

    r = analyze(birth, longitude=lon, now=now, male=(p.get("gender", "male") == "male"))

    print("=" * 60)
    print(f"{p.get('name', '本人')} 本命盘（{p.get('gender', '-')}）"
          f"  出生 {birth:%Y-%m-%d %H:%M}  经度 {lon}°E")
    print(f"真太阳时 {tst:%H:%M:%S}    当前基准日 {now:%Y-%m-%d}")
    print("=" * 60)
    print("        年      月      日      时")
    print("     " + "  ".join(f"{r.pillars[k].name}" for k in "年月日时"))
    print("     " + "  ".join(f"{r.pillars[k].ten_god}" for k in "年月日时"))
    print("     " + "  ".join(f"{r.pillars[k].nayin}" for k in "年月日时"))
    print("-" * 60)
    print(f"日主      {r.day_master}")
    print(f"强弱      {r.strength:.1f}  {r.strength_label}")
    print(f"格局      {r.pattern}")
    if getattr(r, "pattern_detail", ""):
        print(f"          {r.pattern_detail}")
    print(f"用神      {'、'.join(r.yong_shen_wx)}   喜 {'、'.join(r.xi_shen_wx)}"
          f"   忌 {'、'.join(r.ji_shen_wx)}")
    print(f"起运      {r.qiyun_date:%Y-%m-%d}")
    print("大运      " + " → ".join(
        (f"[{d.name}]" if r.current_dayun and d.name == r.current_dayun.name else d.name)
        for d in r.dayun))
    if r.current_dayun:
        print(f"当前大运  {r.current_dayun.name}（{r.current_dayun.ten_god}）"
              f" {r.current_dayun.start_age}–{r.current_dayun.end_age} 岁")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
