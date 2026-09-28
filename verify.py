# -*- coding: utf-8 -*-
"""
术数基础层回归测试。

设计原则（血泪教训）：
  日柱锚点校验是唯一能抓到「整体平移 N 天」类 bug 的手段。
  仅做「日干支连续性」测试是不够的 —— 连续性对整体平移完全免疫，
  2026-09 那次日柱差 1 天的致命 bug 就是这样逃过自检的。

运行：python verify.py
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, ".")

from engine.base import (  # noqa: E402
    day_gz, year_gz_by_lichun, month_gz_by_jie, hour_gz, hour_zhi,
    gz_index, JIA_ZI, solar_term_datetime, true_solar_time, ensure_cst,
)
from engine.bazi import analyze  # noqa: E402
from engine.lunar import lunar_info  # noqa: E402

PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    ok = got == want
    if ok:
        PASS += 1
    else:
        FAIL += 1
    mark = "  ok  " if ok else " FAIL "
    print(f"[{mark}] {name:<34} 得到={got!s:<22} 期望={want}")


def gz(dt):
    return JIA_ZI[day_gz(dt)]


def load_birth():
    """
    取本命数据。仓库是公开的，真实出生数据只存在于本地的 data/profile.json
    （已 gitignore）或环境变量 DESTINY_BIRTH / DESTINY_LONGITUDE 中。
    两者都没有时返回 None —— 第三节整节跳过，不算失败。
    """
    env_b = os.environ.get("DESTINY_BIRTH", "").strip()
    env_l = os.environ.get("DESTINY_LONGITUDE", "").strip()
    if env_b:
        import re
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})[ T]+(\d{1,2}):(\d{2})", env_b)
        if m:
            return (datetime(*[int(m.group(i)) for i in range(1, 6)]),
                    float(env_l) if env_l else 120.0)
    try:
        with open(os.path.join("data", "profile.json"), encoding="utf-8") as f:
            p = json.load(f)
        if p.get("birth_place_confirmed") and p.get("birth"):
            b = p["birth"]
            return (datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"]),
                    float(p.get("birth_longitude", 120.0)))
    except OSError:
        pass
    return None


print("=" * 78)
print("一、日柱绝对锚点（可抓整体平移类 bug，务必保留）")
print("=" * 78)
# 1949-10-01 甲子日、2000-01-01 戊午日、2024-02-10 甲辰日 均为公开可核基准
check("1949-10-01 日柱", gz(datetime(1949, 10, 1, 12, 0)), "甲子")
check("2000-01-01 日柱", gz(datetime(2000, 1, 1, 12, 0)), "戊午")
check("2024-02-10 日柱(甲辰年春节)", gz(datetime(2024, 2, 10, 12, 0)), "甲辰")
check("1980-07-17 日柱(锚点)", gz(datetime(1980, 7, 17, 12, 0)), "辛卯")
check("2026-09-28 日柱", gz(datetime(2026, 9, 28, 12, 0)), "乙巳")
check("1980-01-01 日柱", gz(datetime(1980, 1, 1, 12, 0)), "癸酉")
check("2026-02-17 日柱(丙午年春节)", gz(datetime(2026, 2, 17, 12, 0)), "壬戌")

print()
print("=" * 78)
print("二、日干支连续性（辅助，不能替代锚点）")
print("=" * 78)
prev, bad = None, 0
for i in range(1000):
    x = day_gz(datetime(2025, 1, 1) + __import__("datetime").timedelta(days=i))
    if prev is not None and x != (prev + 1) % 60:
        bad += 1
    prev = x
check("连续 1000 天日干支递增", bad, 0)

print()
print("=" * 78)
print("三、本命四柱（需本地真实数据，未注入则整节跳过）")
print("=" * 78)
_birth = load_birth()
if _birth is None:
    print("[  --  ] 未找到本命数据（data/profile.json 或 DESTINY_BIRTH），跳过本节。")
    print("        公开仓库不含真实出生数据，属预期行为。")
else:
    BIRTH, LON = _birth
    tst = true_solar_time(BIRTH, LON)
    check("真太阳时", tst.strftime("%H:%M:%S"), "09:19:24")
    yg = year_gz_by_lichun(BIRTH)
    mg = month_gz_by_jie(BIRTH)
    dg = day_gz(BIRTH)
    hg = hour_gz(dg, hour_zhi(tst))
    check("年柱", JIA_ZI[yg], "庚申")
    check("月柱", JIA_ZI[mg], "癸未")
    check("日柱", JIA_ZI[dg], "辛卯")
    check("时柱", JIA_ZI[hg], "癸巳")

    r = analyze(BIRTH, longitude=LON, now=datetime(2026, 9, 28, 15, 0))
    check("日主", r.day_master, "辛")
    check("强弱", round(r.strength, 1), 67.6)
    check("强弱分级", r.strength_label, "身旺")
    check("用神", "".join(r.yong_shen_wx[:2]), "火水")
    check("起运", r.qiyun_date.strftime("%Y-%m-%d"), "1987-08-26")
    check("大运序列", " ".join(d.name for d in r.dayun[:5]), "甲申 乙酉 丙戌 丁亥 戊子")
    check("当前大运", r.current_dayun.name if r.current_dayun else None, "丁亥")

print()
print("=" * 78)
print("四、节气精度（Meeus 算法，容差 ±2 分钟）")
print("=" * 78)
TERMS = [
    (1980, "立春", "1980-02-05 00:04"),
    (1980, "小暑", "1980-07-07 07:14"),
    (1980, "立秋", "1980-08-07 17:00"),
    (2026, "立春", None),
    (2026, "冬至", None),
]
for y, n, want in TERMS:
    got = solar_term_datetime(y, n).strftime("%Y-%m-%d %H:%M")
    if want:
        check(f"{y} {n}", got, want)
    else:
        print(f"[  --  ] {y} {n:<32} {got}")

print()
print("=" * 78)
print("五、农历（天文算法，无本地数据包）")
print("=" * 78)
_lu1 = lunar_info(datetime(2026, 2, 17, 12, 0))
_lu2 = lunar_info(datetime(2023, 3, 22, 12, 0))
_lu3 = lunar_info(datetime(2026, 9, 25, 12, 0))
check("2026-02-17 春节(丙午正月初一)",
      f"{_lu1.gz_year}年{_lu1.suishi_name}月初一" if _lu1.day == 1 else _lu1.label,
      "丙午年正月初一")
check("2023-03-22 闰二月初一",
      f"{_lu2.gz_year}年闰{_lu2.suishi_name}月初一" if _lu2.day == 1 else _lu2.label,
      "癸卯年闰二月初一")
check("2023-03-22 确为闰月", _lu2.leap, True)
check("2026-09-25 中秋(八月十五)",
      f"{_lu3.gz_year}年{_lu3.suishi_name}月十五" if _lu3.day == 15 else _lu3.label,
      "丙午年八月十五")

print()
print("=" * 78)
print(f"结果：通过 {PASS} 项，失败 {FAIL} 项")
print("=" * 78)
sys.exit(1 if FAIL else 0)
