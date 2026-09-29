# -*- coding: utf-8 -*-
"""destiny-daily :: engine.mail_report —— 邮件专用 HTML 渲染。

为什么不直接复用 engine/report.py 的那份 HTML？
    那份用了 flex / grid / CSS 变量 / ::before 伪元素 —— 浏览器里好看，
    但主流邮件客户端会把它们过滤掉或渲染错乱：
        · QQ 邮箱 / 163：过滤部分选择器，grid 塌成一列堆叠
        · Outlook（Word 排版引擎）：完全不支持 flex / grid
        · Gmail：早年直接删掉整个 <style>，现在仍会过滤不少属性
    邮件必须退回「table 布局 + 全部内联样式」的老写法，才能所见即所得。

本模块的硬约束（后续改动请一并遵守）：
    1. 只用 <table> 布局，不用 div + flex / grid
    2. 每个视觉样式写成 style="..." 内联属性，不依赖 <style> 选择器
    3. 底色同时写 bgcolor="" 和 style="background:..."，照顾 Outlook
    4. 不用伪元素、不用 CSS 变量、不用 linear-gradient
    5. 宽度固定 600px，外层居中（移动端收发最稳）
    6. 不引外部字体、图片、JS —— 邮件里外链基本都会被拦

内容与原 HTML 报告逐一对应，另在头部加了「今日速览」，
手机上一屏内就能看到今天最要紧的几件事。
"""

from __future__ import annotations

import html as _html
from typing import Dict, List

from .report import SCORE_COLOR, _tier_of, TEND_COLOR

# ---------------------------------------------------------------- 色板
PAPER = "#f4efe6"        # 外层宣纸底
CARD = "#ffffff"         # 卡片
SOFT = "#fdfbf6"         # 卡片内浅底
SOFT2 = "#f7f2e6"        # 强调底
INK = "#2b2721"          # 主文字
INK2 = "#6f685c"         # 次要文字
INK3 = "#948c7e"         # 辅助说明
LINE = "#e6dfd1"         # 描边
ZHU = "#b03030"          # 朱砂
QING = "#3d6b5a"         # 青
GOLD = "#8a6d3b"         # 金褐

FONT = ("-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB',"
        "'Microsoft YaHei','Segoe UI',Helvetica,Arial,sans-serif")

SYM_FONT = ("'Apple Symbols','Segoe UI Symbol','Noto Sans Symbols',"
            "'PingFang SC','Microsoft YaHei',serif")

WIDTH = 600


def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")


# ---------------------------------------------------------------- 通用零件


def _f(size: int, color: str = INK, weight: str = "normal",
       lh: float = 1.75, extra: str = "") -> str:
    """生成一个 font 内联样式串。"""
    return (f"font-family:{FONT};font-size:{size}px;color:{color};"
            f"font-weight:{weight};line-height:{lh};margin:0;padding:0;{extra}")


def _sp(h: int) -> str:
    """占位空行（邮件里 br 的间距不可控，用固定高度 td 更稳）。"""
    return f'<tr><td height="{h}" style="font-size:1px;line-height:1px">&nbsp;</td></tr>'


def _card(inner: str, bg: str = CARD) -> str:
    """一张卡片。"""
    return (
        f'<tr><td style="padding:0 18px">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{bg}" '
        f'style="background:{bg};border:1px solid {LINE};border-radius:14px;'
        f'border-collapse:separate">'
        f'<tr><td style="padding:18px 20px">{inner}</td></tr>'
        f'</table></td></tr>')


def _sec_head(icon: str, title: str, score=None) -> str:
    """栏目头：图标 + 标题 + 右上分数。"""
    sc = ""
    if score is not None:
        c = SCORE_COLOR[_tier_of(score)]
        sc = (f'<td width="52" align="right" valign="middle">'
              f'<span style="{_f(13, c, "700", 1)}display:inline-block;'
              f'padding:2px 10px;border:1px solid {LINE};border-radius:999px;'
              f'background:{SOFT}">{score:.0f}</span></td>')
    return (
        f'<tr><td style="padding-bottom:12px">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr>'
        f'<td width="30" valign="middle">'
        f'<span style="{_f(15, INK, "700", 1)}display:inline-block;width:28px;height:28px;'
        f'line-height:28px;text-align:center;background:{SOFT2};border-radius:8px">'
        f'{_e(icon)}</span></td>'
        f'<td valign="middle" style="padding-left:8px">'
        f'<span style="{_f(17, INK, "700", 1.3)}letter-spacing:.02em">{_e(title)}</span></td>'
        f'{sc}'
        f'</tr></table></td></tr>')


def _sec(icon: str, title: str, inner: str, score=None) -> str:
    """一个完整栏目（含栏间距）。"""
    return (_card(_sec_head(icon, title, score) + f"<tr><td>{inner}</td></tr>")
            + _sp(14))


def _lead(text: str, color: str = "#3f3a33") -> str:
    """栏目导语（加粗的一句总结）。"""
    return (f'<div style="{_f(15, color, "600", 1.6)}margin-bottom:10px">'
            f'{_e(text)}</div>')


def _sub(text: str, color: str = GOLD) -> str:
    """二级小标题。"""
    return (f'<div style="{_f(13, color, "700", 1.5)}margin:14px 0 6px">'
            f'{_e(text)}</div>')


def _tips(items, size: int = 14) -> str:
    """要点列表。不用 <ul>（邮件里 list-style 各端不一致），手搓表格。"""
    if not items:
        return ""
    rows = []
    for t in items:
        rows.append(
            f'<tr><td width="16" valign="top" style="padding:4px 0;'
            f'{_f(size, GOLD, "700", 1.7)}">&#8226;</td>'
            f'<td valign="top" style="padding:4px 0;{_f(size, INK, "normal", 1.7)}">'
            f'{_e(t)}</td></tr>')
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            + "".join(rows) + "</table>")


def _note(text: str, size: float = 12.5, color: str = INK3) -> str:
    return f'<div style="{_f(size, color, "normal", 1.65)}margin-top:8px">{_e(text)}</div>'


# ---------------------------------------------------------------- 今日速览


def _glance(r: Dict) -> str:
    """今日速览 —— 手机上一屏看完重点。"""
    m, g, he = r["meta"], r["general"], r["health"]
    c = SCORE_COLOR[_tier_of(m["total"])]

    picks = []
    ld = r["invest"].get("lottery_detail") or {}
    if ld.get("skip"):
        picks.append(("彩", "今日停买", f'彩气 {ld.get("score", 0):.0f}，低于建议线'))
    elif ld.get("picks"):
        p = ld["picks"][0]
        nums = " ".join(f"{n:02d}" for n in p["front"])
        if p.get("back"):
            nums += " + " + " ".join(f"{n:02d}" for n in p["back"])
        picks.append(("财", p["game"], nums))

    z = r.get("zhouyi")
    if z:
        picks.append(("卦", f'{z["symbol"]} {z["name"]}', f'倾向：{z["tendency"]}'))
    car = r.get("career")
    if car:
        picks.append(("业", "事业指数 " + str(int(car["score"])), car.get("line", "")))

    rows = []
    for tag, head, detail in picks:
        rows.append(
            f'<tr>'
            f'<td width="26" valign="middle" style="padding:6px 0">'
            f'<span style="{_f(11, "#fff", "700", 1)}display:inline-block;width:22px;'
            f'height:22px;line-height:22px;text-align:center;background:{QING};'
            f'border-radius:6px">{_e(tag)}</span></td>'
            f'<td valign="middle" style="padding:6px 0 6px 8px">'
            f'<span style="{_f(13.5, INK, "700", 1.5)}">{_e(head)}</span>'
            f'<span style="{_f(12.5, INK2, "normal", 1.5)}">　{_e(detail)}</span></td>'
            f'</tr>')

    inner = (
        f'<tr><td>'
        f'<div style="{_f(14, INK, "600", 1.6)}margin-bottom:8px">'
        f'{_e(g["headline"])}</div>'
        f'<div style="{_f(13, INK2, "normal", 1.6)}">宜：{_e("、".join(g["yi"]))}'
        f'<br>忌：{_e("、".join(g["ji"]))}</div>'
        f'</td></tr>'
        + _sp(10)
        + f'<tr><td><table width="100%" cellpadding="0" cellspacing="0" border="0">'
        + "".join(rows) + "</table></td></tr>")

    return _card(inner, SOFT)


# ---------------------------------------------------------------- Hero


def _hero(r: Dict) -> str:
    m, d = r["meta"], r["destiny"]
    c = SCORE_COLOR[_tier_of(m["total"])]

    chips = [
        ("本命", f'{d["day_master"]}水 · {d["pattern"]}'),
        ("用神", d["yong"]),
        ("大运", d["dayun"].split("（")[0]),
        ("流年", d["liunian"]),
    ]
    chip_html = "".join(
        f'<span style="{_f(12.5, INK2, "normal", 1)}display:inline-block;'
        f'margin:0 6px 6px 0;padding:4px 11px;background:{CARD};border:1px solid {LINE};'
        f'border-radius:999px">{_e(k)} <b style="color:{INK};font-weight:600">'
        f'{_e(v)}</b></span>' for k, v in chips)

    return (
        f'<tr><td bgcolor="{SOFT2}" style="background:{SOFT2};padding:24px 22px 20px;'
        f'border:1px solid {LINE};border-radius:16px">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td colspan="2" style="{_f(11, GOLD, "normal", 1)}letter-spacing:.3em">'
        f'WU SHU RI KE &#183; 五 术 日 课</td></tr>'
        f'<tr><td colspan="2" style="padding-top:7px;'
        f'{_f(24, INK, "700", 1.3)}letter-spacing:.02em">'
        f'{_e(m["date_str"])}　{_e(m["weekday"])}</td></tr>'
        f'<tr><td colspan="2" style="padding-top:5px;{_f(12.5, INK2, "normal", 1.6)}">'
        f'{_e(m["lunar_full"])}　|　{_e(m["day_gz"])}日'
        f'（{_e(m["day_nayin"])}）　|　节气：{_e(m["jieqi"])}</td></tr>'
        + _sp(16)
        + f'<tr>'
        f'<td width="96" valign="middle">'
        f'<table width="88" cellpadding="0" cellspacing="0" border="0" bgcolor="{CARD}" '
        f'style="background:{CARD};border:4px solid {c};border-radius:50%">'
        f'<tr><td height="80" align="center" valign="middle">'
        f'<div style="{_f(30, c, "700", 1)}">{m["total"]:.0f}</div>'
        f'<div style="{_f(11.5, c, "700", 1.4)}letter-spacing:.08em">'
        f'{_e(m["grade"])}</div></td></tr></table></td>'
        f'<td valign="middle" style="padding-left:6px">{chip_html}</td>'
        f'</tr></table></td></tr>' + _sp(14))


# ---------------------------------------------------------------- 本命提要


def _destiny(r: Dict) -> str:
    d = r["destiny"]
    cols = "".join(
        f'<td align="center" style="padding:10px 4px">'
        f'<div style="{_f(17, INK, "700", 1.3)}">{_e(n)}</div>'
        f'<div style="{_f(11.5, INK3, "normal", 1.5)}">{_e(t)}</div>'
        f'<div style="{_f(10.5, INK3, "normal", 1.5)}">{_e(ny)}</div></td>'
        for n, t, ny in zip(d["sizhu"], d["sizhu_ten"], d["sizhu_nayin"]))

    kv = [
        ("日　主", f'{d["day_master"]}水 · {d["strength_label"]}（{d["strength"]}）'),
        ("格　局", d["pattern"]),
        ("取　用", f'用神 {d["yong"]}　忌神 {d["ji"]}'),
        ("大运 / 流年", f'{d["dayun"]}　{d["liunian"]}年'),
    ]
    kv_html = "".join(
        f'<tr><td width="70" valign="top" style="padding:3px 0;'
        f'{_f(13, INK2, "normal", 1.7)}white-space:nowrap">{_e(k)}</td>'
        f'<td valign="top" style="padding:3px 0;{_f(13, INK, "600", 1.7)}">'
        f'{_e(v)}</td></tr>' for k, v in kv)

    inner = (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SOFT}" '
        f'style="background:{SOFT};border:1px solid {LINE};border-radius:11px;'
        f'border-collapse:separate">{cols}</table>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin-top:12px">{kv_html}</table>')

    stars = "; ".join(f"{k}柱：{'、'.join(v)}" for k, v in d["stars"].items() if v)
    if stars:
        inner += _note("神煞：" + stars)
    return _sec("盘", "本命提要", inner)


# ---------------------------------------------------------------- 每日一卦


def _yao_line(yang: bool, dong: bool) -> str:
    """一条爻线。阴爻断开两截，全部用表格实现。"""
    if yang:
        bg = ZHU if dong else "#3b3630"
        return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
                f'<tr><td height="9" bgcolor="{bg}" style="background:{bg};'
                f'font-size:1px;line-height:1px;border-radius:2px">&nbsp;</td></tr></table>')
    bd = ZHU if dong else "#bfb59e"
    bg = CARD
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>'
            f'<td width="42%" height="9" bgcolor="{bg}" style="background:{bg};'
            f'border:1px solid {bd};font-size:1px;line-height:1px;border-radius:2px">&nbsp;</td>'
            f'<td width="16%" style="font-size:1px;line-height:1px">&nbsp;</td>'
            f'<td width="42%" height="9" bgcolor="{bg}" style="background:{bg};'
            f'border:1px solid {bd};font-size:1px;line-height:1px;border-radius:2px">&nbsp;</td>'
            f'</tr></table>')


def _gua(r: Dict) -> str:
    z = r["zhouyi"]
    tc = TEND_COLOR.get(z.get("tendency"), QING)

    tags = "".join(
        f'<span style="{_f(11.5, INK2, "normal", 1)}display:inline-block;'
        f'margin:0 5px 5px 0;padding:2px 9px;background:{CARD};border:1px solid {LINE};'
        f'border-radius:999px">{_e(t)}</span>' for t in z.get("tags", []))

    head = (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SOFT2}" '
        f'style="background:{SOFT2};border:1px solid {LINE};border-radius:12px;'
        f'border-collapse:separate;margin-bottom:12px">'
        f'<tr>'
        f'<td width="60" align="center" valign="middle" style="padding:12px 8px">'
        f'<div style="font-family:{SYM_FONT};font-size:42px;line-height:1;color:#5a4a2a">'
        f'{_e(z["symbol"])}</div></td>'
        f'<td valign="middle" style="padding:12px 4px">'
        f'<div style="{_f(19, INK, "700", 1.35)}letter-spacing:.03em">'
        f'{_e(z["name"])}</div>'
        f'<div style="{_f(12, INK2, "normal", 1.5)}margin-top:2px">'
        f'第{z["xu"]}卦　上{_e(z["upper"])}　下{_e(z["lower"])}</div>'
        f'<div style="margin-top:5px">{tags}</div></td>'
        f'<td width="70" align="center" valign="middle" style="padding:12px 8px">'
        f'<table cellpadding="0" cellspacing="0" border="0" bgcolor="{CARD}" '
        f'style="background:{CARD};border:1px solid {LINE};border-radius:10px">'
        f'<tr><td align="center" style="padding:5px 10px">'
        f'<div style="{_f(18, tc, "700", 1.2)}">{_e(z["tendency"])}</div>'
        f'<div style="{_f(10.5, INK2, "normal", 1.4)}margin-top:1px">'
        f'{_e(z["tend_note"])}</div></td></tr></table></td>'
        f'</tr></table>')

    yt = [f'<table width="100%" cellpadding="0" cellspacing="0" border="0">']
    for y in reversed(z["yao_study"]):
        yang = z["yin_yang"][y["pos"] - 1] == 1
        dong = ('　<span style="color:' + ZHU + ';font-weight:700">动爻</span>'
                if y["dong"] else "")
        yt.append(
            f'<tr>'
            f'<td width="82" valign="middle" style="padding:4px 0">'
            f'{_yao_line(yang, y["dong"])}</td>'
            f'<td valign="middle" style="padding:4px 0 4px 12px">'
            f'<div style="{_f(12.5, INK, "normal", 1.6)}">'
            f'<b style="font-weight:700">{y["pos"]}爻</b>　{_e(y["name"])}'
            f'　{_e(y["dewei"])}{dong}</div>'
            f'<div style="{_f(12, "#7c7367", "normal", 1.6)}">{_e(y["text"])}</div></td>'
            f'</tr>')
    yt.append("</table>")
    yaotu = "".join(yt)

    mv = z.get("moving", [])
    if not mv:
        jn = "六爻皆静，卦象稳定，以本卦卦辞为主体，不动处以守常。"
    else:
        pos = "、".join(f"{p}爻" for p in mv)
        jn = f"第 {pos} 动，阳极阴生、阴极阳生，是为变机所在；本卦言其体，之卦言其用。"
    notice = (f'<div style="{_f(12.2, INK3, "normal", 1.65)}margin:10px 0 0">'
              f'起卦：大衍之数五十，其用四十有九，三变成爻，十八变成卦。'
              f'{_e(jn)}</div>')

    judge = (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SOFT}" '
        f'style="background:{SOFT};border:1px solid {LINE};border-left:4px solid {GOLD};'
        f'border-radius:9px;border-collapse:separate;margin:12px 0">'
        f'<tr><td style="padding:11px 14px">'
        f'<div style="{_f(11.5, GOLD, "700", 1)}letter-spacing:.08em">占　断</div>'
        f'<div style="{_f(12, INK2, "normal", 1.6)}margin:3px 0 6px">'
        f'{_e(z["method"])}　·　主断取「{_e(z["judge_src"])}」</div>'
        f'<div style="{_f(14.5, "#332e28", "600", 1.8)}">{_e(z["judge_text"])}</div>'
        f'</td></tr></table>')

    def _jing(label: str, orig: str, bai: str = "", color: str = QING) -> str:
        b = (f'<div style="{_f(12.8, "#7c7367", "normal", 1.75)}margin-top:5px">'
             f'{_e(bai)}</div>') if bai else ""
        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{SOFT}" style="background:{SOFT};border:1px solid {LINE};'
            f'border-radius:10px;border-collapse:separate;margin-top:9px">'
            f'<tr><td style="padding:11px 13px">'
            f'<div style="{_f(12, color, "700", 1)}letter-spacing:.1em">'
            f'{_e(label)}</div>'
            f'<div style="{_f(14, "#332e28", "normal", 1.85)}margin-top:5px">'
            f'{_e(orig)}</div>{b}</td></tr></table>')

    jings = (
        _jing("卦　辞", z["ci"], z["ci_bai"])
        + _jing("大象传（象曰）", z["xiang"], z["xg_bai"])
        + _jing("核心义理", z["yi"], "", GOLD)
        + _jing("今日之用", z["yong"], "", GOLD))

    rels = [f'<table width="100%" cellpadding="0" cellspacing="0" border="0">']
    items = []
    if z.get("bian"):
        items.append(("之卦（变卦）", z["bian"]["symbol"], z["bian"]["name"],
                      "事态走向。" + z["bian"]["ci"]))
    if z.get("hu"):
        items.append(("互卦", z["hu"]["symbol"], z["hu"]["name"],
                      "二三五四爻相叠，看事情内在的过程肌理。"))
    if z.get("cuo"):
        items.append(("错卦（旁通）", z["cuo"]["symbol"], z["cuo"]["name"],
                      "阴阳尽反 —— 换个立场看同一件事。"))
    if z.get("zong"):
        items.append(("综卦（覆卦）", z["zong"]["symbol"], z["zong"]["name"],
                      "上下颠倒 —— 反过来看同一件事。"))
    row: List[str] = []
    for i, (lb, sym, nm, note) in enumerate(items):
        cell = (
            f'<td width="50%" valign="top" style="padding:4px">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{SOFT}" style="background:{SOFT};border:1px solid {LINE};'
            f'border-radius:9px;border-collapse:separate">'
            f'<tr><td style="padding:8px 11px">'
            f'<div style="{_f(11, INK2, "normal", 1)}letter-spacing:.05em">{_e(lb)}</div>'
            f'<div style="{_f(14, INK, "700", 1.5)}margin-top:2px">'
            f'<span style="font-family:{SYM_FONT};font-size:16px;color:#5a4a2a;'
            f'margin-right:5px">{_e(sym)}</span>{_e(nm)}</div>'
            f'<div style="{_f(11.5, INK3, "normal", 1.55)}margin-top:3px">{_e(note)}</div>'
            f'</td></tr></table></td>')
        row.append(cell)
        if len(row) == 2 or i == len(items) - 1:
            if len(row) == 1:
                row.append('<td width="50%" style="padding:4px">&nbsp;</td>')
            rels.append("<tr>" + "".join(row) + "</tr>")
            row = []
    rels.append("</table>")

    ana = _tips(list(z.get("analysis", [])) + list(z.get("benming", [])), 13.5)

    lines = "".join(
        f'<tr><td width="32" valign="top" style="padding:2px 0;'
        f'{_f(13, ZHU, "700", 1.8)}">{y["pos"]}爻</td>'
        f'<td valign="top" style="padding:2px 0;{_f(13, "#4a443c", "normal", 1.8)}">'
        f'{_e(y["wei"])}'
        f'{("　<b style=\'color:" + ZHU + ";font-weight:700\'>(今日动爻)</b>") if y["dong"] else ""}'
        f'</td></tr>' for y in z["yao_study"])
    study = (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SOFT}" '
        f'style="background:{SOFT};border:1px dashed {LINE};border-radius:10px;'
        f'border-collapse:separate;margin-top:12px">'
        f'<tr><td style="padding:11px 14px">'
        f'<div style="{_f(12, GOLD, "700", 1)}letter-spacing:.1em;margin-bottom:6px">'
        f'爻　位　通　则</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">{lines}</table>'
        f'</td></tr></table>')

    return _sec("卦", "每日一卦 · 大衍筮法",
                head + yaotu + judge + notice + "".join(rels) + ana
                + jings + study)


# ---------------------------------------------------------------- 五门评分


def _bars(items: List[Dict]) -> str:
    out = [f'<table width="100%" cellpadding="0" cellspacing="0" border="0">']
    for it in items:
        s = it["score"]
        c = SCORE_COLOR[_tier_of(s)]
        w = int(max(0, min(100, s)))
        out.append(
            f'<tr>'
            f'<td width="72" valign="middle" style="padding:5px 0;'
            f'{_f(13, INK2, "normal", 1.6)}">{_e(it["name"])}</td>'
            f'<td valign="middle" style="padding:5px 8px">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="#efe9dc" style="background:#efe9dc;border-radius:999px">'
            f'<tr><td height="8" style="font-size:1px;line-height:1px">'
            f'<table width="{w}%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{c}" style="background:{c};border-radius:999px">'
            f'<tr><td height="8" style="font-size:1px;line-height:1px">&nbsp;</td></tr>'
            f'</table></td></tr></table></td>'
            f'<td width="30" valign="middle" align="right" style="padding:5px 0;'
            f'{_f(13, c, "700", 1.6)}">{s:.0f}</td>'
            f'</tr>'
            f'<tr><td colspan="3" style="padding:0 0 4px 72px;'
            f'{_f(11.8, INK3, "normal", 1.55)}">{_e(it.get("summary", ""))}</td></tr>')
    out.append("</table>")
    return "".join(out)


# ---------------------------------------------------------------- 生活 / 健康等


def _yi_ji(g: Dict) -> str:
    def box(title: str, items, color: str) -> str:
        ps = "".join(
            f'<div style="{_f(13, INK, "normal", 1.7)}">&#183; {_e(x)}</div>'
            for x in items)
        return (
            f'<td width="50%" valign="top" style="padding:5px">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{SOFT}" style="background:{SOFT};border:1px solid {LINE};'
            f'border-radius:11px;border-collapse:separate">'
            f'<tr><td style="padding:10px 13px">'
            f'<div style="{_f(12.5, color, "700", 1)}letter-spacing:.1em;margin-bottom:4px">'
            f'{_e(title)}</div>{ps}</td></tr></table></td>')
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin-top:12px"><tr>'
            + box("宜", g["yi"], QING) + box("忌", g["ji"], ZHU)
            + "</tr></table>")


def _ball(n, blue: bool = False) -> str:
    bg = "#2f5d8a" if blue else ZHU
    return (f'<span style="{_f(12.5, "#fff", "700", 1)}display:inline-block;'
            f'width:27px;height:27px;line-height:27px;text-align:center;'
            f'background:{bg};border-radius:50%;margin:0 3px 5px 0">'
            f'{n:02d}</span>')


def _lottery(inv: Dict) -> str:
    ld = inv.get("lottery_detail") or {}
    if ld.get("skip"):
        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="#f5f6f3" style="background:#f5f6f3;border:1px dashed #c9cfc6;'
            f'border-radius:10px;border-collapse:separate;margin-top:9px">'
            f'<tr><td style="padding:12px 14px">'
            f'<div style="{_f(14, "#6b7280", "700", 1.5)}">今日不建议购买'
            f'<span style="{_f(11.5, "#8a8f86", "700", 1.5)}margin-left:8px">'
            f'彩气 {ld.get("score", 0):.0f} / 建议线 {ld.get("skip_threshold", 50):.0f}'
            f'</span></div>'
            f'<div style="{_f(12, INK2, "normal", 1.65)}margin-top:5px">'
            f'五门加权总分偏低，术数层面无支撑。今日停买一天，额度留到彩气旺日再用。'
            f'</div></td></tr></table>')

    out = ""
    for p in ld.get("picks", []):
        balls = "".join(_ball(n) for n in p["front"])
        if p.get("back"):
            balls += (f'<span style="{_f(12, INK2, "normal", 1)}margin:0 4px">+</span>'
                      + "".join(_ball(n, True) for n in p["back"]))
        out += (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{SOFT}" style="background:{SOFT};border:1px solid {LINE};'
            f'border-radius:10px;border-collapse:separate;margin-top:9px">'
            f'<tr><td style="padding:12px 14px">'
            f'<div style="{_f(14, INK, "700", 1.5)}">{_e(p["game"])}'
            f'<span style="{_f(11.5, ZHU, "700", 1.5)}margin-left:8px">'
            f'今日唯一推荐 · 彩气 {ld.get("score", 0):.0f}</span></div>'
            f'<div style="margin:8px 0 6px">{balls}</div>'
            f'<div style="{_f(11.5, INK3, "normal", 1.6)}">'
            f'{_e(p.get("note", ""))}　|　选种依据：{_e(p.get("reason", ""))}</div>'
            f'</td></tr></table>')
    others = [x for x in ld.get("open_games", []) if x != ld.get("chosen")]
    if others:
        out += _note("当日其他开奖彩种（今日不碰）：" + "、".join(others))
    return out


def _rel_cards(soc: Dict) -> str:
    cards = [f'<table width="100%" cellpadding="0" cellspacing="0" border="0">']
    rels = soc.get("relations", [])
    row: List[str] = []
    for i, x in enumerate(rels):
        bg = "#fff6f4" if x["on_duty"] else SOFT
        bd = ZHU if x["on_duty"] else LINE
        cell = (
            f'<td width="50%" valign="top" style="padding:4px">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{bg}" style="background:{bg};border:1px solid {bd};'
            f'border-radius:10px;border-collapse:separate">'
            f'<tr><td style="padding:9px 12px">'
            f'<div style="{_f(13.5, INK, "700", 1.4)}">{_e(x["who"])}'
            f'<span style="{_f(10.5, INK2, "normal", 1)}display:inline-block;margin-left:6px;'
            f'padding:1px 7px;border:1px solid {LINE};border-radius:999px;background:{CARD}">'
            f'{_e(x["star"])}</span>'
            f'<span style="{_f(11, ZHU, "700", 1.4)}margin-left:6px">{_e(x["state"])}</span>'
            f'</div>'
            f'<div style="{_f(12.5, "#4a443c", "normal", 1.65)}margin-top:4px">'
            f'{_e(x["advice"])}</div></td></tr></table></td>')
        row.append(cell)
        if len(row) == 2 or i == len(rels) - 1:
            if len(row) == 1:
                row.append('<td width="50%" style="padding:4px">&nbsp;</td>')
            cards.append("<tr>" + "".join(row) + "</tr>")
            row = []
    cards.append("</table>")
    return "".join(cards)


def _checks(r: Dict) -> str:
    rows = "".join(
        f'<tr>'
        f'<td width="26" valign="middle" style="padding:6px 0">'
        f'<span style="{_f(13, INK, "normal", 1)}display:inline-block;width:17px;height:17px;'
        f'line-height:17px;text-align:center;border:2px solid #c9bfa6;border-radius:5px">'
        f'&nbsp;</span></td>'
        f'<td valign="middle" style="padding:6px 0 6px 8px;'
        f'{_f(13.5, INK, "normal", 1.6)}">{_e(c["task"])}</td>'
        f'<td width="44" align="right" valign="middle" style="padding:6px 0">'
        f'<span style="{_f(10.5, INK2, "normal", 1)}display:inline-block;padding:1px 7px;'
        f'border:1px solid {LINE};border-radius:6px;background:{CARD}">'
        f'{_e(c["tag"])}</span></td>'
        f'</tr>' for c in r["checklist"])
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>')


# ---------------------------------------------------------------- 主渲染


def render_mail_html(r: Dict) -> str:
    m = r["meta"]
    d = r["destiny"]
    g, tr, he, soc, inv, st = (r["general"], r["travel"], r["health"],
                               r["social"], r["invest"], r["study"])

    body = [_hero(r), _glance(r), _sp(14), _destiny(r)]
    if r.get("zhouyi"):
        body.append(_gua(r))
    body.append(_sec("五", "五门评分", _bars(r["five"])))

    body.append(_sec("常", "日常生活",
                     _lead(g["headline"]) + _tips(g["tips"]) + _yi_ji(g),
                     g["score"]))

    health = (
        _lead(he["headline"])
        + f'<div style="{_f(12.8, "#7c7367", "normal", 1.65)}margin-bottom:12px">'
        + _e("　".join(he["organ_tips"])) + "</div>"
        + f'<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td width="50%" valign="top" style="padding-right:7px">'
        f'<div style="{_f(12.5, QING, "700", 1.5)}margin-bottom:5px">■ 力量训练</div>'
        f'{_tips(he["training"], 13.5)}</td>'
        f'<td width="50%" valign="top" style="padding-left:7px">'
        f'<div style="{_f(12.5, QING, "700", 1.5)}margin-bottom:5px">■ 八部金刚功</div>'
        f'{_tips(he["qigong"], 13.5)}</td></tr></table>'
        + _sub("■ 营养补给") + _tips(he["nutrition"], 13.5))
    body.append(_sec("健", "健康 · 健身 · 金刚功", health, he["score"]))

    car = r.get("career")
    if car:
        body.append(_sec("业", "事业 · 客户 · 融资",
                         _lead(car["advice_headline"]) + _tips(car["notes"])
                         + _sub("■ 今日行动") + _tips(car["actions"]),
                         car["score"]))

    body.append(_sec("行", "出行方位",
                     _lead(tr["headline"]) + _tips(tr["tips"]), tr["score"]))

    social = (_lead(soc["headline"]) + _tips(soc["tips"])
              + _sub(f'■ 六亲分论（今日十神：{soc["today_star"]}）')
              + _rel_cards(soc))
    body.append(_sec("缘", "人际关系", social, soc["score"]))

    btc = inv.get("btc", {})
    invest = (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#fdf3f1" '
        f'style="background:#fdf3f1;border:1px solid #e8cfc9;border-left:4px solid {ZHU};'
        f'border-radius:9px;border-collapse:separate">'
        f'<tr><td style="padding:10px 13px;{_f(12.8, "#7c3b32", "normal", 1.65)}">'
        f'<b style="color:{ZHU};font-weight:700">&#9888; 风险提示</b>　'
        f'{_e(inv["risk_banner"])}</td></tr></table>'
        + f'<div style="{_f(14.5, "#3f3a33", "600", 1.7)}margin:12px 0 10px">'
        + _e(inv["headline"]) + "</div>"
        + _tips(inv["notes"])
        + _sub("■ BTC 复盘")
        + f'<div style="{_f(13.2, "#3f3a33", "700", 1.6)}margin-bottom:5px">'
        + _e(btc.get("headline", "")) + "</div>" + _tips(btc.get("lines", []), 13.2)
        + _sub(f'■ 数字资产（{inv["exchange"].upper()}）')
        + _tips(inv["crypto"], 13.2)
        + _sub("■ 彩票娱乐")
        + _tips(inv["lottery"], 13.2)
        + _lottery(inv))
    body.append(_sec("财", "投资 · 彩票 · 数字资产", invest, inv["score"]))

    body.append(_sec("学", "传统文化学习",
                     _lead(st["headline"]) + _tips(st["plan"]), st["score"]))
    body.append(_sec("记", "今日打卡清单", _checks(r)))

    foot = ('<tr><td style="padding:0 18px">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SOFT}" '
            f'style="background:{SOFT};border:1px dashed {LINE};border-radius:12px;'
            f'border-collapse:separate">'
            f'<tr><td style="padding:13px 15px;{_f(12, INK3, "normal", 1.7)}">'
            f'{_e(r["disclaimer"])}</td></tr></table></td></tr>'
            + _sp(12)
            + f'<tr><td align="center" style="{_f(11.5, "#a89f90", "normal", 1.6)}">'
            f'destiny-daily &#183; 生成于 {_e(m["generated_at"])}</td></tr>'
            + _sp(24))

    return (
        f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="format-detection" content="telephone=no,date=no,address=no,email=no">'
        f'<title>{_e(m["date_str"])} 每日运势 · {_e(m["grade"])}</title></head>'
        f'<body style="margin:0;padding:0;background:{PAPER}">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAPER}" '
        f'style="background:{PAPER}"><tr><td align="center" style="padding:16px 8px">'
        f'<table width="{WIDTH}" cellpadding="0" cellspacing="0" border="0" '
        f'style="width:100%;max-width:{WIDTH}px;border-collapse:collapse">'
        + "".join(body) + foot
        + "</table></td></tr></table></body></html>")
