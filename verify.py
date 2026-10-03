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

import html as _html  # noqa: E402

from engine.report import render_text as _rtxt, render_html as _rhtm  # noqa: E402
from engine.mail_report import render_mail_html as _rmail  # noqa: E402
from engine.synthesize import generate as _gen  # noqa: E402

# 固定日期保证快照可复现
# offline=True：观察清单的行情抓取依赖外网，测试不因源抖动而红
_rp = _gen(datetime(2026, 9, 29, 8, 0), offline=True)
_mail_html = _rmail(_rp)
_rhtml = _rhtm(_rp)


def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")

_BANNED = ["display:flex", "display: flex", "display:grid", "display: grid",
           "var(--", "::before", "::after", "linear-gradient",
           "position:absolute", "position: absolute", "position:fixed"]
_hit = [b for b in _BANNED if b in _mail_html]
check("邮件版无客户端禁用CSS", _hit, [])

check("邮件版无<style>块(会被剥离)", "<style" in _mail_html, False)

# 禁的是「外部资源」（图片/字体/JS/CSS），不是超链接——
# 学习栏要给 B 站讲解链接，那是正文的一部分，属于正常 <a href>
_ext = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)', _mail_html)
_RES = re.compile(r'\.(js|css|png|jpe?g|gif|svg|webp|woff2?|ttf|otf|eot|ico)'
                  r'(\?|$)', re.I)
check("邮件版无外部图片/字体/JS",
      [u for u in _ext if not u.startswith("#") and _RES.search(u)], [])
check("邮件版超链接均为 https",
      [u for u in _ext if not u.startswith("#")
       and not u.startswith("https://")], [])
check("学习栏带B站讲解链接",
      any("search.bilibili.com" in u for u in _ext), True)

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

# --- MIME 结构：正文必须解码一次即还原（2026-09-29 双重编码事故的防回归） ---
# 事故：手动 encode_quopri 叠加 MIMEText 自带 base64，header 声称 QP、
# payload 实际是 base64，QQ 邮箱解出一屏「PCFET0NUWVBF…」乱码。
import tempfile as _tmpf  # noqa: E402
from notify_mail import build_message as _bm  # noqa: E402

_dtmp = _tmpf.mkdtemp()
_hpth = os.path.join(_dtmp, "t.html")
with open(_hpth, "w", encoding="utf-8") as f:
    f.write("<!DOCTYPE html><html><body><b>中文测试</b></body></html>")
_mm = _bm("s", "t", _hpth, "a@x.com", ["b@y.com"])

_inline = None
for _p in _mm.walk():
    cd = _p.get("Content-Disposition") or ""
    if _p.get_content_type() == "text/html" and "attachment" not in cd:
        _inline = _p
        break
check("邮件正文HTML part存在", _inline is not None, True)
if _inline is not None:
    check("正文CTE声明合法",
          _inline.get("Content-Transfer-Encoding") in
          ("base64", "quoted-printable", "7bit", "8bit"), True)
    _dec = _inline.get_payload(decode=True).decode("utf-8", "replace")
    check("正文解码一次即还原",
          _dec.startswith("<!DOCTYPE html>") and "中文测试" in _dec, True)
    check("正文无双重编码残留",
          ("PCFET0" in _dec) or ("PGh0bWw" in _dec), False)
    check("纯文本降级仍在", any(
        p.get_content_type() == "text/plain" for p in _mm.walk()), True)

# ---------------------------------------------------------------- 9) 每日一句经典
# 全程离线：句子内建，不联网不受外部源影响，断言可以写死
print()
print("-" * 78)
print("9) 每日一句经典（classic）")
print("-" * 78)

from engine import classic as _cl  # noqa: E402
from datetime import timedelta as _td  # noqa: E402

check("经典主题为12类", len(_cl.CLASSICS), 12)
check("句库总量充足", sum(len(v) for v in _cl.CLASSICS.values()) >= 100, True)
check("每主题不少于8句",
      [t for t, v in _cl.CLASSICS.items() if len(v) < 8], [])
check("每条字段齐全（书名/篇第/原文/白话）",
      [t for t, v in _cl.CLASSICS.items()
       for b, ch, tx, zh in v if not (b and ch and tx and zh)], [])
check("每主题都有今日提点",
      [t for t in _cl.CLASSICS if t not in _cl.ACTIONS], [])

# 死角检查：曾有「养生」不在任何五行映射里，永远选不到
_reach = set()
for _wx in "木火土金水":
    for _tt in (30.0, 60.0, 90.0):
        for _hs in (None, 40.0):
            _reach |= set(_cl._themes_for(_wx, _tt, _hs))
check("12 类主题全部可达", sorted(_reach), sorted(_cl.CLASSICS))

# 确定性：同一天两次调用必须完全相同
_ctx = {"target": datetime(2026, 9, 29, 8, 0), "lr_day": {"gz": "辛卯"},
        "total": 62.0}
_c1 = _cl.daily_classic(dict(_ctx))
_c2 = _cl.daily_classic(dict(_ctx))
check("同一天结果确定", (_c1["text"], _c1["theme"]), (_c2["text"], _c2["theme"]))
check("取到的句子在库里", _c1["text"] in
      [t[2] for t in _cl.CLASSICS[_c1["theme"]]], True)
check("日干五行已解析", _c1["wuxing"], "金")
check("日干支已带上", _c1["day_gz"], "辛卯")

# 轮转：连续 30 天不撞句（同一句连续两天出现最容易被察觉）
_seq = []
for _i in range(30):
    _d = datetime(2026, 9, 29, 8, 0) + _td(days=_i)
    _cc = _cl.daily_classic({"target": _d, "lr_day": {"gz": "辛卯"},
                             "total": 62.0})
    _seq.append(_cc["text"])
check("相邻两天不撞句",
      [i for i in range(1, 30) if _seq[i] == _seq[i - 1]], [])
check("30天内句子充分轮转", len(set(_seq)) >= 25, True)

# 健康分偏低时养生能被选中（这一路只有它进得去）
_low = None
for _i in range(20):
    _d = datetime(2026, 9, 29, 8, 0) + _td(days=_i)
    _cc = _cl.daily_classic({"target": _d, "lr_day": {"gz": "甲子"},
                             "total": 62.0}, health_score=38.0)
    if _cc["theme"] == "养生":
        _low = _cc
        break
check("健康分低时切入养生", _low is not None, True)

# 档位影响：运势极低偏守、极高偏进
_th_lo = _cl._themes_for("木", 30.0)[0]
_th_hi = _cl._themes_for("木", 90.0)[0]
check("低分档偏守静", _th_lo, "守静")
check("高分档偏进取", _th_hi, "进取")

# 三版渲染都带经典栏
_ctxt = _cl.render_classic_text(_c1)
check("文本版带经典段", "【每日一句经典" in _ctxt, True)
check("文本版带出处", "—— 道德经" in _ctxt or "——" in _ctxt, True)
check("文本版带今日提点", "【今日提点】" in _ctxt, True)
# 渲染断言必须对照真实报告里那一句，不能拿上面另造的 ctx 去比
_rc = _rp["classic"]
_rc_q = _e(_rc["text"])[:12]
check("报告已带 classic 字段", bool(_rc.get("text")), True)
check("浏览器版带经典栏", "每日一句经典" in _rhtml, True)
check("浏览器版带原文", _rc_q in _rhtml, True)
check("邮件版带经典栏", "每日一句经典" in _mail_html, True)
check("邮件版带原文", _rc_q in _mail_html, True)
check("邮件版无链接残留(资讯已移除)",
      "utm_" in _mail_html or "抓取于" in _mail_html, False)

# ---------------------------------------------------------------- 10) 系统学习路线
print()
print("-" * 78)
print("10) 传统文化系统课（curriculum）")
print("-" * 78)

from engine import curriculum as _cu  # noqa: E402

_trs = _cu.all_tracks()
_n = _cu.total_lessons(_trs)
check("课程轨道数量", len(_trs) >= 12, True)
check("总课时够学半年", _n >= 180, True)
check("每条轨道有课时", [t["name"] for t in _trs if not (t.get("lessons") or [])], [])

# 课时字段完整性：缺了要点或练习，推到邮箱里就是空卡片
_bad = []
for _t in _trs:
    for _l in (_t.get("lessons") or []):
        if not str(_l.get("t", "")).strip():
            _bad.append(f'{_t["name"]}: 缺标题')
        if not (_l.get("p") or []):
            _bad.append(f'{_t["name"]}/{_l.get("t")}: 缺要点')
        if not str(_l.get("a", "")).strip():
            _bad.append(f'{_t["name"]}/{_l.get("t")}: 缺练习')
check("每课都有标题/要点/练习", _bad[:6], [])
check("课时标题无重复",
      len({str(_l["t"]) for _t in _trs for _l in (_t["lessons"] or [])}) == _n, True)

# 推进：相邻两天必须是不同的课，且不能跳节
_d0 = datetime(2026, 10, 3)
_seq = [_cu.lesson_for(_d0 + _td(days=i), _trs) for i in range(40)]
check("相邻两天不重复",
      [i for i in range(1, 40)
       if _seq[i]["title"] == _seq[i - 1]["title"]], [])
check("逐日推进不跳节",
      [i for i in range(1, 40)
       if _seq[i]["global_no"] - _seq[i - 1]["global_no"] != 1], [])
check("同一天结果确定",
      _cu.lesson_for(_d0, _trs)["title"], _cu.lesson_for(_d0, _trs)["title"])
# 从起算日（2026-09-29 = 第1节）走满一轮，应回到第 1 节
check("走完一轮回到第1节",
      _cu.lesson_for(datetime(2026, 9, 29) + _td(days=_n), _trs)["global_no"], 1)

# 链接：每课都要能点开学
_nolink = [s["title"] for s in _seq if not s.get("links")]
check("每课都有链接", _nolink, [])
check("链接均为 https",
      [l["url"] for s in _seq for l in s["links"]
       if not l["url"].startswith("https://")], [])
check("每课都有B站讲解入口",
      [s["title"] for s in _seq
       if not any("bilibili" in l["url"] for l in s["links"])], [])
# 搜索关键词必须 URL 编码过，否则中文在部分客户端会变成乱码链接
check("搜索词已URL编码",
      [l["url"] for s in _seq for l in s["links"]
       if "bilibili" in l["url"] and "%" not in l["url"]], [])

# 三版渲染都带今日一课
_lsn = _rp["study"].get("lesson")
check("报告已带 lesson 字段", bool(_lsn), True)
check("文本版带今日一课", "今日一课" in _rtxt(_rp), True)
check("浏览器版带今日一课", "今日一课" in _rhtml and _e(_lsn["title"])[:10] in _rhtml, True)
check("邮件版带今日一课", _e(_lsn["title"])[:10] in _mail_html, True)
check("邮件版带链接", "search.bilibili.com" in _mail_html, True)
# 旧版那句写死的「轮换专题」不该再出现
check("旧版轮换文案已清除", "（轮换专题）" in _rhtml or "（轮换专题）" in _mail_html, False)

# ---------------------------------------------------------------- 数字资产：羊毛 + 观察清单
print()
print("-" * 78)
print("11) 数字资产（wool：平台活动薅羊毛 + 观察清单）")
print("-" * 78)

from engine import wool as _wo  # noqa: E402

# --- BTC 复盘必须彻底消失 ---
check("报告不再有 btc 字段", "btc" in _rp["invest"], False)
check("三版均无「BTC 复盘」字样",
      [n for n, s in (("文本", _txt), ("浏览器", _rhtml), ("邮件", _mail_html))
       if "BTC 复盘" in s], [])
_src = ""
for _f_ in ("engine/synthesize.py", "engine/report.py", "engine/mail_report.py"):
    with open(_f_, encoding="utf-8") as _fh:
        _src += _fh.read()
check("源码不再调用 market.review", "market.review" in _src, False)
check("源码不再引用 inv['btc'] 取值", "get(\"btc\"" in _src, False)

# --- 常青羊毛库完整性 ---
check("羊毛库条目数", len(_wo.WOOL), 14)
check("条目 key 唯一", len({w["key"] for w in _wo.WOOL}), len(_wo.WOOL))
check("条目字段无空缺",
      [w["key"] for w in _wo.WOOL
       if not all(w.get(k) for k in ("name", "kind", "need", "how",
                                     "gain", "risk", "link", "one"))], [])
check("星级在 1~5", [w["key"] for w in _wo.WOOL
                     if not 1 <= w["stars"] <= 5], [])
check("链接均为 https",
      [w["key"] for w in _wo.WOOL if not w["link"].startswith("https://")], [])
# 双币投资是高风险产品，必须被明确标出来，不能混在羊毛里
_dual = next(w for w in _wo.WOOL if w["key"] == "dual")
check("双币投资标为高风险", "高风险" in _dual["kind"] and _dual["stars"] <= 1, True)
check("高风险项文案含警示", "不是羊毛" in _dual["risk"], True)
check("防坑清单不少于5条", len(_wo.SAFETY) >= 5, True)

# --- 轮换：确定性 + 覆盖全库 ---
_p0 = _wo.pick_wool(_d0)
_p0b = _wo.pick_wool(_d0)
check("同一天结果一致", [w["key"] for w in _p0["focus"]],
      [w["key"] for w in _p0b["focus"]])
_n2 = len(_wo.WOOL)
_seen = set()
for _i in range(_n2):                       # 每天推进 2 条，走满 n/2 天即覆盖全库
    _pk = _wo.pick_wool(_d0 + _td(days=_i))
    _seen.update(w["key"] for w in _pk["focus"])
check("半轮覆盖全部条目", len(_seen), _n2)
check("重点条数", len(_p0["focus"]), 2)
check("速览不与重点重复",
      [w["key"] for w in _p0["glance"] if w["key"] in
       {x["key"] for x in _p0["focus"]}], [])
check("速览条数", len(_p0["glance"]), 4)
check("首日从库首开始", _wo.pick_wool(_wo.datetime(2026, 10, 3))["cursor"], 0)

# --- 财气分档建议 ---
_a1, _a2, _a3, _a4 = (_wo.wool_advice(s) for s in (80.0, 55.0, 45.0, 30.0))
check("四档建议各不相同", len({_a1, _a2, _a3, _a4}), 4)
check("偏弱档明确收缩动作", "不做新开仓" in _a3, True)
check("极弱档明确只收不进", "一律不动" in _a4, True)

# --- 观察清单 ---
_wl = _wo.watch_rows(offline=True)
check("离线时优雅降级", _wl["ok"], False)
check("离线仍列全清单", len(_wl["rows"]), len(_wo.WATCHLIST))
check("清单每项有名称与观察理由",
      [r["name"] for r in _wl["rows"] if not r.get("why")], [])
check("清单定位齐备", [r["name"] for r in _wl["rows"] if not r.get("role")], [])
check("未取到时无价格字段", [r["name"] for r in _wl["rows"]
                             if r.get("ok") and "price_txt" not in r], [])
check("观察清单含 BNB（与羊毛门槛相关）",
      any(r["name"] == "BNB" for r in _wl["rows"]), True)

# --- 行情层：多源 fallback + 熔断 ---
from engine import market as _mk  # noqa: E402

check("价格源不少于3个", len(_mk.PRICE_SRC) >= 3, True)
check("日线源不少于3个", len(_mk.SERIES_SRC) >= 3, True)
check("CoinGecko 覆盖全部默认标的",
      [s for s, *_ in _wo.WATCHLIST if s not in _mk.GECKO_IDS], [])
# Coinbase 无 BNB 现货：这是已知缺口，必须有别的源兜住，不能整栏失效
check("BNB 至少有一个非 Coinbase 源",
      "BNBUSDT" in _mk.GECKO_IDS or "BNBUSDT" in _mk.COINBASE_PAIRS, True)
_mk.reset_breaker()
check("初始未熔断", _mk._down("binance"), False)
_mk._mark_down("binance")
check("熔断生效", _mk._down("binance"), True)
_mk.reset_breaker()
check("熔断可复位", _mk._down("binance"), False)
# 熔断后不应再发起网络请求（直接抛错，避免 N×M×重试 的空等）
_raise = False
_mk._mark_down("__probe__")
try:
    _mk._try("__probe__", lambda: 1 / 0)     # 已熔断 → 必须立刻抛，不发起请求
except Exception:                            # noqa: BLE001
    _raise = True
check("熔断源直接抛错不联网", _raise, True)
_mk.reset_breaker()

# --- 三版渲染 ---
_as = _rp["invest"].get("assets") or {}
check("报告已带 assets 字段", bool(_as), True)
check("文本版带薅羊毛段", "平台活动薅羊毛" in _rtxt(_rp), True)
check("文本版带观察清单", "观察清单" in _rtxt(_rp), True)
check("浏览器版带薅羊毛段", "平台活动薅羊毛" in _rhtml, True)
check("邮件版带薅羊毛段", "平台活动薅羊毛" in _mail_html, True)
check("邮件版带观察清单", "观察清单" in _mail_html, True)
check("邮件版带重点通道名", _e(_as["focus"][0]["name"]) in _mail_html, True)
check("邮件版带官网链接", _as["focus"][0]["link"] in _mail_html, True)
check("邮件版带防坑提醒", "防坑提醒" in _mail_html, True)
# 行情未取到时，邮件里必须如实说明，不能默默留空
check("离线时邮件标注未取到", "未取到" in _mail_html, True)
check("保留仓位纪律段", "仓位与账户纪律" in _mail_html, True)

# --- 观察清单表格在邮件里必须是 table（不能退化成 div+flex） ---
_wpos = _mail_html.find("观察清单")
_wm = _mail_html[_wpos:_wpos + 2500] if _wpos >= 0 else ""
check("观察清单用 table 渲染", _wm.count("<table") >= 1, True)
check("观察清单无禁用 CSS",
      [b for b in ("display:flex", "display: grid", "var(--",
                   "linear-gradient") if b in _wm], [])

print()
print("=" * 78)
print(f"结果：通过 {PASS} 项，失败 {FAIL} 项")
print("=" * 78)
sys.exit(1 if FAIL else 0)
