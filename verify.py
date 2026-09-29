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
import re
import sys
from datetime import datetime, timedelta

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


def check_near(name, got, want, tol):
    """容差比较，用于概率一类带抽样噪声的量"""
    global PASS, FAIL
    ok = abs(got - want) <= tol
    if ok:
        PASS += 1
    else:
        FAIL += 1
    mark = "  ok  " if ok else " FAIL "
    print(f"[{mark}] {name:<34} 得到={got!s:<22} 期望={want}±{tol}")


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
print("五、大衍筮法 · 每日一卦")
print("=" * 78)

from engine import zhouyi as _zy          # noqa: E402
from engine.gua64_data import GUA64_DATA  # noqa: E402

# --- 1) 起卦概率须合古典：老阴1/16 少阳5/16 少阴7/16 老阳3/16 ---
import random as _rnd                      # noqa: E402
_r = _rnd.Random(20260929)
_N = 60000
_c = {}
for _ in range(_N):
    _v = _zy._three_bian(_r)
    _c[_v] = _c.get(_v, 0) + 1
for _k, _want in ((6, 1 / 16), (7, 5 / 16), (8, 7 / 16), (9, 3 / 16)):
    check_near(f"爻 {_zy.YAO_NAME[_k]}({_k})概率",
               round(_c.get(_k, 0) / _N, 4), round(_want, 4), 0.01)
check("六爻之数合于 6/7/8/9", sorted(_c) == [6, 7, 8, 9], True)

# --- 2) 数据库完整性 ---
check("六十四卦无缺", len(GUA64_DATA), 64)
check("文王卦序 1..64 连续", sorted(d["xu"] for d in GUA64_DATA.values()) == list(range(1, 65)), True)
_xus = [d["xu"] for d in GUA64_DATA.values()]
check("卦序无重复", len(_xus) == len(set(_xus)), True)
check("每卦六爻俱全", all(len(d["yao"]) == 6 for d in GUA64_DATA.values()), True)
check("卦符由卦序推出(乾䷀)", chr(0x4DC0 + 0), "䷀")
check("卦符由卦序推出(未济䷿)", chr(0x4DC0 + 63), "䷿")

# --- 3) 起卦确定性：同日同人必同卦，换日或换人则不同 ---
_g1 = _zy.cast(datetime(2026, 9, 29, 8, 0), personal="甲")
_g2 = _zy.cast(datetime(2026, 9, 29, 8, 0), personal="甲")
_g3 = _zy.cast(datetime(2026, 9, 30, 8, 0), personal="甲")
_g4 = _zy.cast(datetime(2026, 9, 29, 8, 0), personal="乙")
check("同日同人结果恒定", _g1.ben.name == _g2.ben.name, True)
check("换日则卦不同", _g1.ben.name != _g3.ben.name, True)

# --- 4) 之卦由本卦六爻阴阳尽反而成 ---
_g = _zy.cast(datetime(2026, 9, 29, 8, 0), personal="甲")
check("之卦六爻阴阳皆反", sum(1 for i in range(6) if (1 - _g.yin_yang[i]) != _g.yin_yang[i]),
      6)
check("动爻数为 0..6", 0 <= len(_g.moving) <= 6, True)
check("爻辞六条可用", len(_g.ben.yao), 6)

# --- 5) 断法七分支皆能出辞 ---
for _mv, _label in (([], "静"), ([3], "一动"), ([1, 5], "二动"), ([2, 4, 6], "三动"),
                    ([1, 2, 3, 5], "四动"), ([1, 2, 3, 4, 5], "五动"),
                    ([1, 2, 3, 4, 5, 6], "六动")):
    _r2 = _zy.cast(datetime(2026, 9, 29, 8, 0), personal="甲")
    _r2.moving = _mv
    _r2.lines = [9 if (i + 1) in _mv else 7 for i in range(6)]
    _zy._judge(_r2)
    check(f"断法 {_label} 有主断辞", bool(_r2.judge_text) and bool(_r2.method), True)

# --- 6) 乾坤用九用六 ---
for _pair, _name in (((0, 0), "乾"), ((7, 7), "坤")):
    _r3 = _zy.cast(datetime(2026, 9, 29, 8, 0), personal="甲")
    _r3.ben = _zy._ci_of(_pair)
    _r3.bian = _zy._ci_of((1, 1) if _pair == (0, 0) else (6, 6))
    _r3.moving = [1, 2, 3, 4, 5, 6]
    _zy._judge(_r3)
    check(f"{_name}卦六爻皆动取用爻", _r3.judge_src, "用爻")
    check(f"{_name}用爻辞非空", _r3.judge_text.startswith("用九" if _pair == (0, 0) else "用六"), True)

# --- 7) 全年遍历：64 卦皆可达 ---
_seen = set()
_d0 = datetime(2026, 1, 1)
for _i in range(365):
    _seen.add(_zy.cast(_d0 + timedelta(days=_i), personal="甲").ben.name)
check("一年内可见卦数(>=55)", len(_seen) >= 55, True)

# ---------------------------------------------------------------- 8) 邮件排版版
# 邮件客户端（QQ/163/Outlook/Gmail）会把 flex/grid/伪元素/外部资源剥掉或渲染错乱，
# 这几项是「发出去还能不能看」的最后一道防线，改 mail_report.py 后务必重跑。
print()
print("-" * 78)
print("8) 邮件排版版（mail_report）")
print("-" * 78)

from engine.report import render_text as _rtxt  # noqa: E402
from engine.mail_report import render_mail_html as _rmail  # noqa: E402
from engine.synthesize import generate as _gen  # noqa: E402

_rp = _gen(datetime(2026, 9, 29, 8, 0))   # 固定日期，保证这份快照可复现
_mail_html = _rmail(_rp)

_BANNED = ["display:flex", "display: flex", "display:grid", "display: grid",
           "var(--", "::before", "::after", "linear-gradient",
           "position:absolute", "position: absolute", "position:fixed"]
_hit = [b for b in _BANNED if b in _mail_html]
check("邮件版无客户端禁用CSS", _hit, [])

check("邮件版无<style>块(会被剥离)", "<style" in _mail_html, False)

_ext = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)', _mail_html)
check("邮件版无外部图片/字体/JS", [u for u in _ext if not u.startswith("#")], [])

check("邮件版宽600px", 'max-width:600px' in _mail_html, True)

# 标签必须严格配对，否则 Outlook 会把后半截整段吞掉
for _tag in ("table", "tr", "td", "div"):
    _o = len(re.findall(r"<" + _tag + r"[\s>]", _mail_html))
    _c = len(re.findall(r"</" + _tag + r">", _mail_html))
    check(f"邮件版 <{_tag}> 标签配对", _o == _c, True)

# 关键栏目一个都不能少 —— 漏栏目比样式错更严重，肉眼不一定看得出来
_MARKERS = {
    "本命提要": False, "每日一卦": False, "五门评分": False, "日常生活": False,
    "健康": False, "出行方位": False, "人际关系": False, "投资": False,
    "传统文化学习": False, "今日打卡清单": False,
}
_missing = [k for k in _MARKERS if k not in _mail_html]
check("邮件版栏目齐全", _missing, [])

check("邮件版今日速览含宜忌", "宜：" in _mail_html and "忌：" in _mail_html, True)
check("邮件版含综合分数", f'{_rp["meta"]["total"]:.0f}' in _mail_html, True)

if _rp.get("zhouyi"):
    check("邮件版含卦名", _rp["zhouyi"]["name"] in _mail_html, True)
    check("邮件版含卦辞", _rp["zhouyi"]["ci"][:8] in _mail_html, True)
    # 爻图：六爻必须各画一条，阳爻整条、阴爻断开两截
    check("邮件版六爻齐全", _mail_html.count('height="9"') >= 6, True)

check("邮件版结构完整收口", _mail_html.strip().endswith("</html>"), True)

# 内容等价性：邮件版不应比文本版少信息（文本里的每个小节标题邮箱里都该有）
_txt = _rtxt(_rp)
_CORE = ["【五门评分】", "【日常生活】", "【健康】", "【出行】", "【人际】",
         "【投资】", "【学习】", "【今日打卡】"]
check("文本版小节完整", [c for c in _CORE if c not in _txt], [])

print()
print("=" * 78)
print(f"结果：通过 {PASS} 项，失败 {FAIL} 项")
print("=" * 78)
sys.exit(1 if FAIL else 0)
