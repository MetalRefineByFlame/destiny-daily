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
    "传统文化学习": False, "每日一句经典": False, "今日黄历": False,
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
         "【投资】", "【学习】", "【每日一句经典 ·"]
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

# ---------------------------------------------------------------- 投资：A股复盘 + 仅 BTC 观察清单
print()
print("-" * 78)
print("11) 投资（A股复盘 + BTC 观察清单；平台活动薅羊毛已删除）")
print("-" * 78)

from engine import wool as _wo, market as _mk, astock as _ak  # noqa: E402
from engine.mail_report import _astock_mail as _astock_mail  # noqa: E402

# --- 打卡清单必须彻底消失（2026-10-03 江公子要求移除）---
check("报告不再有 checklist 字段", "checklist" in _rp, False)
check("三版均无「打卡清单 / 今日打卡」字样",
      [n for n, s in (("文本", _txt), ("浏览器", _rhtml), ("邮件", _mail_html))
       if ("打卡清单" in s or "今日打卡" in s)], [])

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

# --- 薅羊毛必须彻底删除（2026-11-09 江公子要求）---
check("模块不再有 WOOL 通道库", hasattr(_wo, "WOOL"), False)
check("模块不再有 SAFETY 防坑清单", hasattr(_wo, "SAFETY"), False)
check("模块不再有 pick_wool", hasattr(_wo, "pick_wool"), False)
check("模块不再有 wool_advice", hasattr(_wo, "wool_advice"), False)
_iv_src = ""
for _f_ in ("engine/wool.py", "engine/report.py", "engine/mail_report.py"):
    with open(_f_, encoding="utf-8") as _fh:
        _iv_src += _fh.read()
check("源码不再出现「薅羊毛」", "薅羊毛" in _iv_src, False)
check("源码不再出现「平台活动」", "平台活动" in _iv_src, False)
check("源码不再出现「常青通道」", "常青通道" in _iv_src, False)
check("源码不再出现「怎么薅」", "怎么薅" in _iv_src, False)
check("assets 只剩观察清单与免责",
      set(_rp["invest"]["assets"]), {"watch", "disclaimer"})

# --- 观察清单只保留 BTC ---
_wl = _wo.watch_rows(offline=True)
check("离线时优雅降级", _wl["ok"], False)
check("观察清单仅 1 条", len(_wl["rows"]), 1)
check("唯一标的为 BTC", _wl["rows"][0]["name"], "BTC")
check("WATCHLIST 只含 BTCUSDT", [w[0] for w in _wo.WATCHLIST], ["BTCUSDT"])
check("BTC 有定位与观察理由",
      bool(_wl["rows"][0]["role"]) and bool(_wl["rows"][0]["why"]), True)
check("未取到时无价格字段", [r["name"] for r in _wl["rows"]
                             if r.get("ok") and "price_txt" not in r], [])
check("旧标的已从行情映射移除",
      [k for k in _mk.GECKO_IDS if k != "BTCUSDT"], [])
check("CoinGecko 覆盖唯一标的", "BTCUSDT" in _mk.GECKO_IDS, True)
check("Coinbase 覆盖唯一标的", "BTCUSDT" in _mk.COINBASE_PAIRS, True)
# 即便 profile 里残留旧 watchlist 配置，也必须被强制收敛为 BTC
_wl2 = _wo.watch_rows(["ETHUSDT", "XRPUSDT"], offline=True)
check("旧配置不会带回其它标的",
      [r["name"] for r in _wl2["rows"]], ["BTC"])

# --- A股复盘：解析层用桩数据做确定性校验（不联网）---
from datetime import timezone as _tz  # noqa: E402
_CST8 = _tz(timedelta(hours=8))
_TS_CLOSE = int(datetime(2026, 11, 6, 15, 0, tzinfo=_CST8).timestamp())
_EM_IX = {"data": {"diff": [
    {"f2": 3665.94, "f3": 0.46, "f6": 455320337484.4, "f12": "000001",
     "f14": "上证指数", "f124": _TS_CLOSE},
    {"f2": 11206.24, "f3": -0.27, "f6": 554147164007.0, "f12": "399001",
     "f14": "深证成指", "f124": _TS_CLOSE},
    {"f2": 2478.94, "f3": 0.56, "f6": 286534110973.7, "f12": "399006",
     "f14": "创业板指", "f124": _TS_CLOSE},
    {"f2": 1261.95, "f3": 0.70, "f6": 46392877279.8, "f12": "000688",
     "f14": "科创50", "f124": _TS_CLOSE},
    {"f2": 4064.17, "f3": 0.24, "f6": 263147204587.8, "f12": "000300",
     "f14": "沪深300", "f124": _TS_CLOSE}]}}
_EM_BR = {"data": {"diff": [{"f104": 1107, "f105": 1147, "f106": 103}]}}
_EM_UP = {"data": {"diff": [{"f3": 5.04, "f14": "卫浴电器"},
                            {"f3": 4.85, "f14": "印制电路板"}]}}
_EM_DN = {"data": {"diff": [{"f3": -2.73, "f14": "宠物食品"}]}}
_orig_gj, _orig_get = _ak._get_json, _ak._get


def _em_stub(url, headers=None, timeout=8):
    if "f104" in url:
        return _EM_BR
    if "clist" in url:
        return _EM_UP if "po=1" in url else _EM_DN
    return _EM_IX


_ak._get_json = _em_stub
try:
    _em = _ak._eastmoney()
finally:
    _ak._get_json = _orig_gj
check("东财五大指数解析", len(_em["indices"]), 5)
check("东财指数点位正确", _em["indices"][0]["close"], 3665.94)
check("东财成交额换算为亿元", _em["indices"][0]["amount_yi"], 4553.2)
check("东财收盘时间戳判为收盘复盘", _em["session"], "收盘复盘")
check("东财数据日期取自数据源", _em["date"], "2026-11-06")
check("东财涨跌家数齐备", _em["breadth"], {"up": 1107, "down": 1147, "flat": 103})
check("东财领涨板块解析", len(_em["sectors_up"]), 2)
check("东财领跌板块解析", len(_em["sectors_down"]), 1)
check("东财客观小结非空", bool(_ak._summary(_em)), True)

# 12:00 的盘中数据不能被说成收盘复盘
_TS_MID = int(datetime(2026, 11, 9, 12, 0, tzinfo=_CST8).timestamp())
_EM_MID = {"data": {"diff": [dict(_EM_IX["data"]["diff"][0], f124=_TS_MID)]}}
_ak._get_json = lambda u, headers=None, timeout=8: _EM_MID if "f124" in u else _EM_BR
try:
    _mid = _ak._eastmoney()
finally:
    _ak._get_json = _orig_gj
check("盘中快照如实标注", _mid["session"], "盘中快照")

# 腾讯 / 新浪 / Yahoo 的解析也各测一次，确保备用源不是摆设
_tx = ('v_s_sh000001="1~上证指数~000001~3665.94~16.76~0.46~'
       '280353411~45532034~~642438.43~ZS~";')
_txr = _ak._text_indices(_tx, "v_s_", sina=False)
check("腾讯简版行情解析", len(_txr), 1)
check("腾讯成交额换算为亿元", _txr[0]["amount_yi"], 4553.2)
_sn = 'var hq_str_s_sh000001="上证指数,3665.9448,16.7674,0.46,2803534,45532034";'
_snr = _ak._text_indices(_sn, "hq_str_s_", sina=True)
check("新浪简版行情解析", len(_snr), 1)
check("新浪涨跌幅解析", _snr[0]["chg"], 0.46)
_YH = {"chart": {"result": [{"timestamp": [100, 200],
                             "indicators": {"quote": [{"close": [100.0, 101.5]}]}}]}}
_ak._get_json = lambda u, headers=None, timeout=8: _YH
try:
    _yh = _ak._yahoo()
finally:
    _ak._get_json = _orig_gj
check("Yahoo 日线涨跌幅计算", round(_yh["indices"][0]["chg"], 2), 1.5)
check("Yahoo 境外源标记", _yh["source"], "Yahoo Finance")

# 全源不可达：必须明说，不得伪装成「尚未公布」
def _boom(*a, **k):
    raise OSError("all down")


_ak._get_json, _ak._get = _boom, _boom
_ak.reset_cache()
try:
    _fail = _ak.fetch(offline=False, use_cache=False)
finally:
    _ak._get_json, _ak._get = _orig_gj, _orig_get
    _ak.reset_cache()
check("全源不可达 reason", _fail["reason"], "unreachable")
check("不可达时不做复盘", _fail["ok"] and bool(_fail["indices"]), False)
check("不可达文案不含「尚未公布」",
      "尚未公布" in "\n".join(_ak.render_astock_text(_fail)), False)
check("不可达文案明确标数据源不可达",
      "行情数据获取失败（数据源不可达）" in "\n".join(_ak.render_astock_text(_fail)), True)
check("离线模式单独标注", _ak.fetch(offline=True)["reason"], "offline")

# 涨红跌绿（A股习惯）+ 邮件版 table 安全
_fake = {"ok": True, "source": "桩数据", "session": "收盘复盘",
         "as_of": "2026-11-06 15:00", "date": "2026-11-06",
         "indices": [{"name": "上证指数", "close": 3600.0, "chg": 1.25,
                      "amount_yi": 4500.0},
                     {"name": "创业板指", "close": 2400.0, "chg": -0.80,
                      "amount_yi": 2600.0}],
         "breadth": {"up": 3000, "down": 1500, "flat": 100},
         "sectors_up": [{"name": "卫浴电器", "chg": 5.04}],
         "sectors_down": [{"name": "宠物食品", "chg": -2.73}],
         "disclaimer": "仅供复盘", "summary": "", "error": "", "reason": ""}
_am = _astock_mail(_fake)
check("A股涨用红色", "#b03030" in _am, True)
check("A股跌用绿色", "#1f7a52" in _am, True)
check("A股邮件用 table 渲染", _am.count("<table") >= 1, True)
check("A股邮件无禁用 CSS",
      [b for b in ("display:flex", "display: grid", "var(--",
                   "linear-gradient") if b in _am], [])
check("A股邮件标签配对",
      all(_am.count("<" + t + " ") + _am.count("<" + t + ">")
          == _am.count("</" + t + ">") for t in ("table", "tr", "td", "div")),
      True)

# --- 行情层：多源 fallback + 熔断 ---
check("价格源不少于3个", len(_mk.PRICE_SRC) >= 3, True)
check("日线源不少于3个", len(_mk.SERIES_SRC) >= 3, True)
check("CoinGecko 覆盖全部默认标的",
      [s for s, *_ in _wo.WATCHLIST if s not in _mk.GECKO_IDS], [])
check("A股复盘备用源共 4 个", len(_ak.SOURCES), 4)
check("A股复盘含境外源 Yahoo",
      any(n == "yahoo" for n, _ in _ak.SOURCES), True)
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

# --- 三版渲染：旧内容删干净 + 新栏目齐全 ---
_as = _rp["invest"].get("assets") or {}
check("报告已带 assets 字段", bool(_as), True)
check("报告已带 astock 字段", bool(_rp["invest"].get("astock")), True)
_BANNED = ("薅羊毛", "平台活动", "常青通道", "怎么薅", "前往官网",
           "Launchpool", "HODLer", "Megadrop", "双币投资", "防坑提醒")
for _nm, _s in (("文本", _txt), ("浏览器", _rhtml), ("邮件", _mail_html)):
    check(f"{_nm}版含 A股复盘栏", "A股复盘" in _s, True)
    check(f"{_nm}版含 BTC 观察清单", "BTC 观察清单" in _s, True)
    check(f"{_nm}版无已删推广内容", [k for k in _BANNED if k in _s], [])
    check(f"{_nm}版无旧标的",
          [k for k in ("ETH", "SOL", "BNB", "XRP") if k in _s], [])
check("邮件版带新栏目名", "投资 · A股复盘 · 数字资产 · 彩票" in _mail_html, True)
# 行情未取到时，邮件里必须如实说明，不能默默留空
check("离线时邮件标注未取到", "未取到" in _mail_html, True)
check("保留仓位纪律段", "仓位与账户纪律" in _mail_html, True)
check("离线模式 A股不伪装成已复盘", "离线模式" in _mail_html, True)

# --- 观察清单表格在邮件里必须是 table（不能退化成 div+flex） ---
_wpos = _mail_html.find("BTC 观察清单")
_wm = _mail_html[_wpos:_wpos + 2500] if _wpos >= 0 else ""
check("观察清单用 table 渲染", _wm.count("<table") >= 1, True)
check("观察清单无禁用 CSS",
      [b for b in ("display:flex", "display: grid", "var(--",
                   "linear-gradient") if b in _wm], [])

# --- 彩票回溯核对（对奖规则 + 台账记账，全程离线） ---
from engine import lottery_result as _lr          # noqa: E402

_SSQ_DRAW = {"front": [1, 2, 3, 4, 5, 6], "back": [7]}
check("双色球 6+1 判一等奖",
      _lr.settle("双色球", [1, 2, 3, 4, 5, 6], [7], _SSQ_DRAW)["level"], "一等奖")
check("双色球 5+1 判三等奖",
      _lr.settle("双色球", [1, 2, 3, 4, 5, 9], [7], _SSQ_DRAW)["level"], "三等奖")
check("双色球 2+1 判六等奖",
      _lr.settle("双色球", [1, 2, 31, 32, 33, 34], [7], _SSQ_DRAW)["level"], "六等奖")
check("双色球 2+0 判未中奖",
      _lr.settle("双色球", [1, 2, 31, 32, 33, 34], [9], _SSQ_DRAW)["level"], "未中奖")
_DLT_DRAW = {"front": [1, 2, 3, 4, 5], "back": [6, 7]}
check("大乐透 5+2 判一等奖",
      _lr.settle("大乐透", [1, 2, 3, 4, 5], [6, 7], _DLT_DRAW)["level"], "一等奖")
check("大乐透 3+0 判八等奖",
      _lr.settle("大乐透", [1, 2, 3, 32, 33], [11, 12], _DLT_DRAW)["level"], "八等奖")
check("大乐透 2+0 判九等奖",
      _lr.settle("大乐透", [1, 2, 31, 32, 33], [11, 12], _DLT_DRAW)["level"], "九等奖")
_KL8_DRAW = {"front": list(range(1, 21)), "back": []}
check("快乐8 中10 判一等奖",
      _lr.settle("快乐8", list(range(1, 11)), [], _KL8_DRAW)["level"], "一等奖")
check("快乐8 中6 判五等奖",
      _lr.settle("快乐8", list(range(1, 7)), [], _KL8_DRAW)["level"], "五等奖")
check("快乐8 中0 判未中奖",
      _lr.settle("快乐8", list(range(31, 41)), [], _KL8_DRAW)["level"], "未中奖")

# 台账：用临时文件，避免污染真实 data/lottery_picks.json
_real_log = _lr.LOG_PATH
_TODAY = datetime(2026, 9, 29, 8, 0)
_tmp_log = os.path.join(_tmpf.gettempdir(), "_destiny_picks_verify.json")
try:
    _lr.LOG_PATH = _tmp_log
    if os.path.exists(_tmp_log):
        os.remove(_tmp_log)
    _lr.record_from_block(_TODAY, {"skip": True, "score": 40.0, "picks": []})
    check("停买日不记账", os.path.exists(_tmp_log), False)
    _lr.record_from_block(_TODAY, {"skip": False, "score": 61.0,
                                   "picks": [{"game": "双色球",
                                              "front": [1, 2, 3, 4, 5, 6],
                                              "back": [7]}]})
    check("推荐日已记账", os.path.exists(_tmp_log), True)
    _rec = json.load(open(_tmp_log, encoding="utf-8"))
    check("台账记录号码完整", _rec[_TODAY.strftime("%Y-%m-%d")]["front"],
          [1, 2, 3, 4, 5, 6])
    # 离线回溯：保留条目但不抓开奖（结果留空，标注「待公布」）
    _rv = _lr.review(_TODAY + timedelta(days=1), offline=True)
    check("离线回溯不报错", isinstance(_rv, dict) and "items" in _rv, True)
    check("离线回溯不出开奖结果", [x for x in _rv["items"] if x.get("result")], [])
    # 台账缺失时按当日盘面确定性复算，结果必须与当日实际推送一致
    # （10-16 实推快乐8 07 12 27 36 49 52 62 63 66 70；profile 变更时需同步更新此期望）
    _rc = _lr._recompute_pick(datetime(2026, 10, 16, 8, 0))
    check("台账缺失可复算出号码", bool(_rc and _rc.get("front")), True)
    check("复算号码与当日实推一致", _rc.get("front") if _rc else None,
          [7, 12, 27, 36, 49, 52, 62, 63, 66, 70])
finally:
    _lr.LOG_PATH = _real_log
    if os.path.exists(_tmp_log):
        os.remove(_tmp_log)

# ---- 数据源容错：官方站按 IP 属地 403，必须能回落备用源 ----
# 背景：2026-10-26 云端早报把 10-25 已开奖的快乐8 显示成「尚未公布」，
# 根因是 cwl.gov.cn 对境外出口（GitHub Actions）一律 403，取数失败被当成未公布。
# 下面几条断言钉死：备用源可解析、官方挂掉会回落、全挂时文案必须说「取数失败」。
_XML_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<xml>
   <row expect="2026284" opencode="05,06,07,09,11,16,18,22,29,34,36,39,41,50,52,53,58,62,69,78" opentime="2026-10-25 21:30:00" updatetime="2026-10-25 21:55:46"/>
   <row expect="26122" opencode="01,02,04,17,19,30|09" opentime="2026-10-25 21:15:00" updatetime="2026-10-25 21:20:21"/>
</xml>"""
_orig_text = _lr._http_text
lr_had = hasattr(_lr, "_500")
try:
    _lr._http_text = lambda *a, **k: _XML_SAMPLE
    _k5 = _lr._500("快乐8", 5) if lr_had else []
    _s5 = _lr._500("双色球", 5) if lr_had else []
finally:
    _lr._http_text = _orig_text
check("备用源·快乐8 取到开奖日期", _k5[0]["date"] if _k5 else None, "2026-10-25")
check("备用源·快乐8 号码 20 个", len(_k5[0]["front"]) if _k5 else 0, 20)
check("备用源·双色球按 | 拆分前后区",
      (_s5[0]["front"], _s5[0]["back"]) if _s5 else None,
      ([1, 2, 4, 17, 19, 30], [9]))

_orig_cwl, _orig_dlt, _orig_500 = _lr._cwl, _lr._dlt, _lr._500
try:
    _lr._cwl = lambda *a, **k: []          # 模拟境外：官方接口 403 → 空
    _lr._dlt = lambda *a, **k: []
    _lr._500 = lambda g, c: [{"date": "2026-10-25", "issue": "2026284",
                              "front": [5, 6, 7], "back": []}]
    _fb = _lr.fetch_draws("快乐8")
    check("官方源不可达时回落备用源", bool(_fb), True)
    check("回落来源标记为 500", _lr._FETCH_STATE.get("快乐8", {}).get("source"), "500")

    # 全部源都挂掉：必须标记 unreachable，不能伪装成「官方未公布」
    _lr._500 = lambda g, c: []
    _tmp_log3 = os.path.join(_tmpf.gettempdir(), "_destiny_picks_verify3.json")
    _lr.LOG_PATH = _tmp_log3
    with open(_tmp_log3, "w", encoding="utf-8") as _f:
        json.dump({"2026-10-25": {"game": "快乐8", "back": [],
                                  "front": list(range(1, 11)),
                                  "score": 50.0}}, _f, ensure_ascii=False)
    _rv3 = _lr.review(datetime(2026, 10, 26, 8, 0))
    check("全源不可达·标记为取数失败",
          _rv3["items"][0].get("result_reason"), "unreachable")
    check("全源不可达·note 不得说「尚未公布」",
          "尚未公布" in _rv3["note"], False)
    os.remove(_tmp_log3)
finally:
    _lr._cwl, _lr._dlt, _lr._500 = _orig_cwl, _orig_dlt, _orig_500
    _lr.LOG_PATH = _real_log

# ---- 行为规范：有推荐→次日早报必带核对；无推荐→早报无任何相关信息 ----
_orig_review, _orig_record = _lr.review, _lr.record_from_block
_tmp_log2 = os.path.join(_tmpf.gettempdir(), "_destiny_picks_verify2.json")
try:
    # 场景A：回溯窗口内均建议停买（无号可核）→ 三版都不出现「往期推荐核对」
    _lr.review = lambda *a, **k: {"ok": False, "items": [],
                                  "note": "（最近 7 天均建议停买，无号码可核对）"}
    _lr.record_from_block = lambda *a, **k: None
    _rpA = _gen(datetime(2026, 9, 30, 8, 0), offline=True)
    check("无推荐·文本版无核对段", "往期推荐核对" in _rtxt(_rpA), False)
    check("无推荐·浏览器版无核对段", "往期推荐核对" in _rhtm(_rpA), False)
    check("无推荐·邮件版无核对段", "往期推荐核对" in _rmail(_rpA), False)

    # 场景B：昨日有推荐且开奖已公布 → 当日早报必须带昨日号码与中奖结果
    _lr.review, _lr.record_from_block = _orig_review, _orig_record
    _draw = {"date": "2026-09-28", "issue": "2026098",
             "front": [1, 2, 3, 11, 12, 13, 21, 22, 23, 31,
                       32, 33, 41, 42, 43, 51, 52, 53, 61, 62],
             "back": []}
    _lr.LOG_PATH = _tmp_log2
    with open(_tmp_log2, "w", encoding="utf-8") as _f:
        json.dump({"2026-09-27": {
            "game": "快乐8", "front": list(range(21, 31)), "back": [],
            "score": 60.0,
            "result": _lr.settle("快乐8", list(range(21, 31)), [], _draw)},
            "2026-09-28": {
            "game": "快乐8", "front": list(range(1, 11)), "back": [],
            "score": 62.0,
            "result": _lr.settle("快乐8", list(range(1, 11)), [], _draw)}},
            _f, ensure_ascii=False)
    _rpB = _gen(datetime(2026, 9, 29, 8, 0), offline=True)
    _tB = _rtxt(_rpB)
    check("有推荐·次日文本版带核对段", "往期推荐核对" in _tB, True)
    check("有推荐·核对段含昨日号码",
          "01 02 03 04 05 06 07 08 09 10" in _tB, True)
    check("有推荐·核对段含命中结果", "未中奖（命中 3）" in _tB, True)
    check("只展示最近一天·前日号码不出现",
          "21 22 23 24 25 26 27 28 29 30" in _tB, False)
    check("有推荐·次日浏览器版带核对段", "往期推荐核对" in _rhtm(_rpB), True)
    check("有推荐·次日邮件版带核对段", "往期推荐核对" in _rmail(_rpB), True)
finally:
    _lr.review, _lr.record_from_block = _orig_review, _orig_record
    _lr.LOG_PATH = _real_log
    if os.path.exists(_tmp_log2):
        os.remove(_tmp_log2)

# ---------------------------------------------------------------- 9) 今日黄历
print()
print("-" * 78)
print("9) 今日黄历历注（宜忌 / 四离四绝 / 杨公忌 / 神诞）")
print("-" * 78)

from engine.almanac import almanac_of as _al, _si_map  # noqa: E402


def _sp_names(al):
    return [x["name"] for x in al["special"]]


def _dt_names(al):
    return [x["name"] for x in al["deities"]]


_a0203 = _al(datetime(2026, 2, 3, 8, 0))
check("四绝·立春前一日", any("四绝" in n and "立春" in n
                        for n in _sp_names(_a0203)), True)
_a0319 = _al(datetime(2026, 3, 19, 8, 0))
check("四离·春分前一日", any("四离" in n and "春分" in n
                        for n in _sp_names(_a0319)), True)
_a1106 = _al(datetime(2026, 11, 6, 8, 0))
check("四绝·立冬前一日", any("四绝" in n and "立冬" in n
                        for n in _sp_names(_a1106)), True)
check("四绝日标记为大忌", _a1106["warning_level"], 2)
_a1221 = _al(datetime(2026, 12, 21, 8, 0))
check("四离·冬至前一日", any("四离" in n and "冬至" in n
                        for n in _sp_names(_a1221)), True)
check("2026 年四离四绝共八日",
      len([k for k in _si_map(2026) if k.year == 2026]), 8)

_a1109 = _al(datetime(2026, 11, 9, 8, 0))
check("平日不误报四离四绝",
      any("四离" in n or "四绝" in n for n in _sp_names(_a1109)), False)
check("建除·亥月亥日为建日", _a1109["jianchu"], "建")
check("喜神方位按日干取", _a1109["xishen"], "正南（离）")
check("宜忌均非空", bool(_a1109["yi"]) and bool(_a1109["ji"]), True)
check("彭祖百忌含干支两条",
      "丁不剃头" in _a1109["pengzu"] and "亥不嫁娶" in _a1109["pengzu"], True)

_a0301 = _al(datetime(2026, 3, 1, 8, 0))
check("杨公十三忌·正月十三", "杨公十三忌" in _sp_names(_a0301), True)
_a0406 = _al(datetime(2026, 4, 6, 8, 0))
check("神圣日·二月十九观音圣诞",
      any("观世音菩萨圣诞" in n for n in _dt_names(_a0406)), True)
_a0216 = _al(datetime(2026, 2, 16, 8, 0))
check("除夕按次日春节判定",
      any("除夕" in n for n in _dt_names(_a0216)), True)
_a0910 = _al(datetime(2026, 9, 10, 8, 0))
check("月小·地藏诞顺延廿九",
      any("地藏王菩萨圣诞" in n for n in _dt_names(_a0910)), True)
check("民岁腊·十月初一不重复",
      len([n for n in _dt_names(_a1109) if "民岁腊" in n]), 1)

# --- 三端渲染 + 邮件主题兼容（TXT 首行格式不得被新增栏目挤掉） ---
_rA = _gen(datetime(2026, 11, 9, 8, 0), offline=True)
for _nm, _s in (("文本", _rtxt(_rA)), ("浏览器", _rhtm(_rA)),
                ("邮件", _rmail(_rA))):
    check(f"{_nm}版含今日黄历栏", "今日黄历" in _s, True)
    check(f"{_nm}版含宜忌", ("宜：" in _s) or ("宜 · 今日所喜" in _s), True)
    check(f"{_nm}版含彭祖百忌", "彭祖百忌" in _s, True)
_tA = _rtxt(_rA)
check("文本版含忌日提醒", "【忌】十恶大败日" in _tA, True)
check("文本版含神诞提醒", "民岁腊" in _tA, True)
check("文本版含近日提醒", "近日提醒" in _tA, True)
_first = _tA.splitlines()[0]
check("文本首行仍为日期+干支（主题依赖）",
      bool(re.match(r"^\d{4}年\d{2}月\d{2}日", _first)) and "丁亥日" in _first,
      True)
from notify_mail import derive_subject as _ds  # noqa: E402
_pth = os.path.join(_tmpf.mkdtemp(), "almanac.txt")
with open(_pth, "w", encoding="utf-8") as _f:
    _f.write(_tA)
check("邮件主题仍可解析出干支日", "丁亥日" in _ds(_pth), True)
os.remove(_pth)

# --- 健康版块改版：删力量训练 / 增肌营养，改体质食疗 + 穴位拍拉（2026-11-09） ---
from engine import therapy as _th  # noqa: E402

_hA = _rA["health"]
check("健康字段已无训练/营养", ("training" in _hA or "nutrition" in _hA), False)
check("打卡已无力量/蛋白项",
      ("力量训练" in _hA["checkin"] or "蛋白达标" in _hA["checkin"]), False)
check("打卡改为食疗/穴位/忌生冷",
      all(k in _hA["checkin"] for k in ("今日食疗", "穴位拍拉", "忌生冷")), True)
check("体质辨识与调理方向存在",
      bool(_hA["constitution"]) and bool(_hA["direction"]), True)
check("当前调理锚定四神汤", "四神汤" in _hA["current_regimen"], True)
check("体质依据不少于三条", len(_hA["basis"]) >= 3, True)
check("食疗/穴位/忌口/常规功课均非空",
      all([_hA["diet_items"], _hA["avoid"], _hA["acu_items"],
           _hA["routine"], _hA["qigong"]]), True)

for _nm, _s in (("文本", _tA), ("浏览器", _rhtm(_rA)), ("邮件", _rmail(_rA))):
    check(f"{_nm}版含今日食疗", "今日食疗" in _s, True)
    check(f"{_nm}版含穴位拍拉", "穴位拍拉" in _s, True)
    check(f"{_nm}版含饮食宜忌", "饮食宜忌" in _s, True)
    check(f"{_nm}版含四神汤", "四神汤" in _s, True)
    check(f"{_nm}版含医疗免责", "非医疗诊断" in _s, True)
    check(f"{_nm}版已删力量训练",
          ("力量训练" in _s or "营养补给" in _s or "蛋白达标" in _s), False)

_d0 = datetime(2026, 11, 9, 8, 0)
_plans = [_th.therapy_of(_d0 + timedelta(days=k))["diet"]["name"] for k in range(8)]
check("食疗 8 日轮转不重样", len(set(_plans)), 8)
check("同日食疗结果确定不变",
      _th.therapy_of(_d0)["diet"]["name"], _th.therapy_of(_d0)["diet"]["name"])
check("每方都以四神汤为底",
      all(_th.CORE_DECOCTION in p["items"][0] for p in [_th.therapy_of(_d0 + timedelta(days=k))["diet"]
                                                        for k in range(8)]), True)
check("每方都有服法与暂停条件",
      all(p["dose"] and p["care"] for p in _th.DIET_PLANS), True)
check("穴位拍拉共 3 组", len(_th.ACU_GROUPS), 3)
check("穴位组含迎香/足三里/太冲",
      all(any(k in g["name"] + "".join(g["points"]) for g in _th.ACU_GROUPS)
          for k in ("迎香", "足三里", "太冲")), True)
check("11 月给出冬季提示", "冬三月" in _th.therapy_of(_d0)["season_note"], True)
check("5 月给出夏季提示",
      "夏月" in _th.therapy_of(datetime(2026, 5, 6, 8, 0))["season_note"], True)
check("五行提示按脏腑联动",
      "肺" in _th.therapy_of(_d0, focus_wx="金")["wx_note"], True)
check("免责说明含面诊提示", "面诊" in _th.DISCLAIMER, True)

# --- 隐私：公开仓库不含个人体质资料，档案只从 Secret 注入（2026-11-09） ---
# 下面这个词表是「反向检查用的命中词」，不是任何人的体质档案；
# 真实档案在 GitHub Secret DESTINY_CONSTITUTION，本地值文件已被 .gitignore 挡住。
_PRIV_WORDS = ("齿痕舌", "晨起舌苔发白", "清水鼻涕", "指甲竖纹", "月牙",
               "脾虚湿盛", "肺脾气虚", "肝血不足", "白苔齿痕", "甲象")
_th_src = open(os.path.join("engine", "therapy.py"), encoding="utf-8").read()
_mk_src = open(os.path.join("scripts", "make_profile.py"), encoding="utf-8").read()
_ex_src = open(os.path.join("data", "profile.example.json"), encoding="utf-8").read()
check("公开调理模块不含个人健康描述",
      [w for w in _PRIV_WORDS if w in _th_src], [])
check("公开档案生成器与模板不含个人健康描述",
      [w for w in _PRIV_WORDS if w in _mk_src + _ex_src], [])
check("默认体质档案为通用版", "通用调理" in _th.CONSTITUTION["label"], True)
check("默认档案不作个体辨识",
      "不作个体辨识" in "".join(_th.CONSTITUTION["basis"]), True)

# 注入测试一律使用中性假数据，真实体质绝不写进公开验证脚本
_fake = {"label": "测试体质A", "direction": "测试方向B",
         "basis": ["测试依据1", "测试依据2"], "current_regimen": "测试底方C"}
_a1 = _th.therapy_of(_d0, focus_wx="土", profile={"constitution": _fake})
_a2 = _th.therapy_of(_d0, focus_wx="土")
check("Secret 档案覆盖体质标签", _a1["constitution"], "测试体质A")
check("Secret 档案覆盖调理方向", _a1["direction"], "测试方向B")
check("Secret 档案覆盖依据条数", len(_a1["basis"]), 2)
check("Secret 档案覆盖当前调理", _a1["current_regimen"], "测试底方C")
check("Secret 注入不改变食疗轮转", _a1["diet"], _a2["diet"])
check("Secret 注入不改变穴位组", _a1["acupoint"], _a2["acupoint"])
check("Secret 注入不改变忌口与免责",
      (_a1["avoid"], _a1["disclaimer"]), (_a2["avoid"], _a2["disclaimer"]))
check("未注入时优雅降级为通用版", "通用调理" in _a2["constitution"], True)

# 完整覆盖包（DESTINY_THERAPY）：可把个性化食疗/穴位文案也放进 Secret
_pack = {
    "core_decoction": "测试底方X",
    "diet_plans": [{"name": "测试方Y", "items": ["测试做法"],
                    "for": "测试对症", "dose": "测试服法", "care": "测试注意"}],
    "avoid": ["测试忌口"],
    "acu_groups": [{"name": "测试穴位组", "points": ["测试穴"], "method": ["测试手法"]}],
    "routine": ["测试功课"], "timing": ["测试时辰"],
    "season": {"冬": "测试冬季提示"}, "wx_note": {"土": "测试五行提示"},
    "disclaimer": "测试免责", "evil_key": "应被忽略",
}
_a3 = _th.therapy_of(_d0, focus_wx="土", profile={"therapy": _pack})
check("覆盖包替换底方", _a3["diet"]["items"][0], "测试底方X")
check("覆盖包替换食疗", _a3["diet"]["name"], "测试方Y")
check("覆盖包替换穴位", _a3["acupoint"]["name"], "测试穴位组")
check("覆盖包替换忌口", _a3["avoid"], ["测试忌口"])
check("覆盖包替换功课", _a3["routine"], ["测试功课"])
check("覆盖包替换季节提示", _a3["season_note"], "测试冬季提示")
check("覆盖包替换五行提示", _a3["wx_note"], "测试五行提示")
check("覆盖包替换免责", _a3["disclaimer"], "测试免责")
check("覆盖包忽略未知键",
      set(_th._overrides({"therapy": _pack})) <= _th._OVERRIDE_KEYS, True)
check("覆盖包字段为空时回退默认",
      _th.therapy_of(_d0, profile={"therapy": {"diet_plans": []}})["diet"]["name"],
      _a2["diet"]["name"])

# make_profile.py 的 Secret 解析
import subprocess as _sp  # noqa: E402
_cmd = [sys.executable, "-B", "scripts/make_profile.py", "--print"]
_o1 = _sp.run(_cmd, capture_output=True, text=True, encoding="utf-8",
              env=dict(os.environ, DESTINY_CONSTITUTION=json.dumps(_fake, ensure_ascii=False)))
check("make_profile 解析 Secret 成功", _o1.returncode, 0)
check("make_profile 写入 constitution 段",
      json.loads(_o1.stdout).get("constitution", {}).get("label"), "测试体质A")
_o2 = _sp.run(_cmd, capture_output=True, text=True, encoding="utf-8",
              env=dict(os.environ, DESTINY_CONSTITUTION="{不是json"))
check("非法 Secret 显式报错不静默降级",
      (_o2.returncode != 0 and "不是合法 JSON" in (_o2.stderr + _o2.stdout)), True)
_o3 = _sp.run(_cmd, capture_output=True, text=True, encoding="utf-8",
              env=dict(os.environ, DESTINY_THERAPY=json.dumps({"avoid": ["测试忌口"]})))
check("make_profile 支持完整覆盖包 Secret",
      json.loads(_o3.stdout).get("therapy", {}).get("avoid"), ["测试忌口"])

# 工作流与忽略规则
_wf = open(os.path.join(".github", "workflows", "daily-destiny.yml"), encoding="utf-8").read()
check("工作流注入体质 Secret", "secrets.DESTINY_CONSTITUTION" in _wf, True)
check("工作流注入调理覆盖 Secret", "secrets.DESTINY_THERAPY" in _wf, True)
check("缺 Secret 时有可见 warning", "::warning::未配置 DESTINY_CONSTITUTION" in _wf, True)
_seg = _wf.split("::warning::未配置 DESTINY_CONSTITUTION")[1][:200]
check("缺 Secret 不阻断发信", "exit 1" in _seg, False)
_gi = open(".gitignore", encoding="utf-8").read()
check("本地私有 Secret 值文件被忽略", "data/*.local.json" in _gi, True)

print()
print("=" * 78)
print(f"结果：通过 {PASS} 项，失败 {FAIL} 项")
print("=" * 78)
sys.exit(1 if FAIL else 0)
