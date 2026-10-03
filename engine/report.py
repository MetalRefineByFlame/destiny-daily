# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.report
把 synthesize 生成的结构化 dict 渲染为：
  1) 自包含的 HTML 报告（宣纸风、响应式、可打印）
  2) 纯摘要文本（用于邮件正文 / 控制台）
"""

from __future__ import annotations

import html
import os
from datetime import datetime
from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "output")

SCORE_COLOR = [
    "#8a6d3b",  # 低调 - 土褐
    "#8a6d3b",
    "#3d6b5a",  # 平顺 - 青
    "#2f6b4f",  # 吉
    "#b03030",  # 上吉 - 朱砂
]


def _e(s) -> str:
    return html.escape(str(s) if s is not None else "")


def _tier_of(score: float) -> int:
    for i, th in enumerate([41, 50, 64, 76]):
        if score < th:
            return i
    return 4


# ---------------------------------------------------------------- CSS

CSS = """
:root{
  --paper:#faf7f0; --paper2:#ffffff; --ink:#25221e; --ink2:#5d574e;
  --line:#e3dccd; --zhu:#b03030; --qing:#3d6b5a; --gold:#8a6d3b;
  --shadow:0 1px 3px rgba(60,50,30,.07),0 8px 24px rgba(60,50,30,.05);
}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased}
.wrap{max-width:820px;margin:0 auto;padding:28px 18px 60px}

/* ---------- 头部 ---------- */
.hero{background:linear-gradient(160deg,#fffdf8,#f5efe2);border:1px solid var(--line);
  border-radius:18px;padding:26px 26px 22px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.hero::before{content:"";position:absolute;right:-40px;top:-40px;width:180px;height:180px;
  border-radius:50%;background:radial-gradient(circle,rgba(176,48,48,.07),transparent 70%)}
.brand{font-size:12px;letter-spacing:.28em;color:var(--gold);text-transform:none}
.hero h1{margin:6px 0 2px;font-size:26px;font-weight:700;letter-spacing:.02em}
.sub{color:var(--ink2);font-size:13.5px}
.hero-row{display:flex;align-items:center;gap:24px;margin-top:18px;flex-wrap:wrap}
.ring{flex:0 0 108px;width:108px;height:108px;border-radius:50%;display:flex;
  flex-direction:column;align-items:center;justify-content:center;font-weight:700;
  border:5px solid;background:#fff}
.ring .num{font-size:32px;line-height:1}
.ring .lbl{font-size:12px;font-weight:600;margin-top:3px;letter-spacing:.1em}
.chips{display:flex;flex-wrap:wrap;gap:8px;flex:1}
.chip{background:#fff;border:1px solid var(--line);border-radius:999px;
  padding:5px 13px;font-size:13px;color:var(--ink2)}
.chip b{color:var(--ink);font-weight:600}

/* ---------- 分区 ---------- */
.section{margin-top:22px;background:var(--paper2);border:1px solid var(--line);
  border-radius:16px;padding:20px 22px;box-shadow:var(--shadow)}
.sec-h{display:flex;align-items:center;gap:10px;margin-bottom:14px;
  padding-bottom:10px;border-bottom:1px dashed var(--line)}
.sec-h .ico{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;
  justify-content:center;background:#f6f1e6;font-size:15px}
.sec-h h2{margin:0;font-size:17px;font-weight:700;letter-spacing:.02em}
.sec-h .sc{margin-left:auto;font-size:13px;font-weight:700;padding:3px 11px;
  border-radius:999px;background:#f6f1e6;color:var(--ink2)}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
@media(max-width:640px){.grid2{grid-template-columns:1fr}}

/* ---------- 六亲 ---------- */
.rels{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
.rel{border:1px solid var(--line);border-radius:10px;padding:11px 13px;background:#fffdf8}
.rel.on{border-color:var(--zhu);background:#fff6f4}
.rel .rh{display:flex;align-items:center;gap:7px;margin-bottom:5px}
.rel .who{font-weight:700;font-size:14.5px}
.rel .star{font-size:11.5px;color:var(--ink2);border:1px solid var(--line);
  border-radius:999px;padding:1px 8px;background:#fff}
.rel .st{margin-left:auto;font-size:11.5px;font-weight:700;color:var(--zhu)}
.rel .ad{font-size:13px;color:#4a443c;line-height:1.65}

/* ---------- 号码球 ---------- */
.balls{display:flex;flex-wrap:wrap;gap:6px;margin:7px 0 3px;align-items:center}
.ball{width:29px;height:29px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:12.5px;font-weight:700;background:var(--zhu);color:#fff}
.ball.b{background:#2f5d8a}
.sep{color:var(--ink2);font-size:12px;margin:0 3px}
.lot{border:1px solid var(--line);border-radius:10px;padding:11px 13px;margin-top:9px;background:#fffdf8}
.lot .lt{font-weight:700;font-size:14px;margin-bottom:2px}
.lot .lv{font-size:12px;color:var(--zhu);font-weight:700}
.lot .ln{font-size:11.5px;color:var(--ink2);margin-top:5px}
.lot.skip{background:#f7f8f6;border-color:#c9cfc6;border-style:dashed}
.lot.skip .lt{color:#6b7280}
.lot.skip .lv{color:#8a8f86}

/* ---------- 五门评分 ---------- */
.five{display:grid;gap:10px}
.bar{display:grid;grid-template-columns:84px 1fr 44px;align-items:center;gap:10px}
.bar .nm{font-size:13.5px;color:var(--ink2)}
.track{height:9px;border-radius:999px;background:#efe9dc;overflow:hidden}
.fill{height:100%;border-radius:999px;transition:width .4s}
.bar .v{font-size:13px;font-weight:700;text-align:right}
.bar .sm{grid-column:1/-1;font-size:12px;color:#8c8478;margin:-4px 0 2px 94px}

/* ---------- 列表 ---------- */
ul.tips{margin:0;padding:0;list-style:none}
ul.tips li{position:relative;padding:5px 0 5px 20px;font-size:14.2px;color:var(--ink)}
ul.tips li::before{content:"";position:absolute;left:5px;top:14px;width:6px;height:6px;
  border-radius:50%;background:var(--gold)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:14px}
.kv dt{color:var(--ink2);white-space:nowrap}
.kv dd{margin:0;font-weight:600}

.yi-ji{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:12px}
.yi-ji .box{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:#fdfbf6}
.yi-ji h4{margin:0 0 6px;font-size:13px;letter-spacing:.1em}
.yi-ji .y{color:var(--qing)} .yi-ji .j{color:var(--zhu)}
.yi-ji p{margin:3px 0;font-size:13.5px}

/* ---------- 打卡 ---------- */
.checks{display:grid;gap:9px}
.chk{display:flex;align-items:center;gap:11px;padding:11px 13px;border:1px solid var(--line);
  border-radius:11px;background:#fdfbf6}
.chk .boxf{width:19px;height:19px;border:2px solid #c9bfa6;border-radius:5px;flex:0 0 auto}
.chk .t{flex:1;font-size:14px}
.chk .tag{font-size:11.5px;color:var(--ink2);border:1px solid var(--line);
  border-radius:6px;padding:1px 7px;background:#fff}

/* ---------- 投资警示 ---------- */
.risk{background:#fdf3f1;border:1px solid #e8cfc9;border-left:4px solid var(--zhu);
  border-radius:10px;padding:11px 14px;font-size:13.2px;color:#7c3b32;margin:12px 0}
.risk b{color:var(--zhu)}

/* ---------- 每日一卦 ---------- */
.gua-top{display:flex;align-items:center;gap:16px;padding:14px 16px;
  background:linear-gradient(155deg,#fffdf7,#f6f0e3);border:1px solid var(--line);
  border-radius:13px;margin-bottom:14px}
.gua-sym{font-size:52px;line-height:1;flex:0 0 auto;color:#5a4a2a}
.gua-top .gm{font-size:21px;font-weight:700;letter-spacing:.04em}
.gua-top .gx{font-size:12.5px;color:var(--ink2);margin-top:3px}
.gua-top .gtags{margin-top:6px;display:flex;flex-wrap:wrap;gap:6px}
.gua-top .gtags span{font-size:11.5px;border:1px solid var(--line);border-radius:999px;
  padding:1px 9px;background:#fff;color:var(--ink2)}
.tend{margin-left:auto;flex:0 0 auto;text-align:center;padding:6px 14px;border-radius:10px;
  background:#fff;border:1px solid var(--line)}
.tend .tt{font-size:19px;font-weight:700;line-height:1.2}
.tend .tl{font-size:11px;color:var(--ink2);margin-top:2px}

.yaotu{display:grid;gap:7px;margin:12px 0}
.yl{display:grid;grid-template-columns:64px 1fr;align-items:center;gap:12px}
.yl .bar{display:grid;grid-template-columns:1fr 1fr;gap:7px;height:11px}
.yl .bar i{border-radius:2px;background:#3b3630;display:block}
.yl .bar.yin i{background:#fff;border:1.5px solid #b7ad98}
.yl .bar.dong i{background:var(--zhu);box-shadow:0 0 0 2px rgba(176,48,48,.18)}
.yl .bar.yin.dong i{background:#fff;border-color:var(--zhu);
  box-shadow:0 0 0 2px rgba(176,48,48,.18)}
.yl .info{font-size:12.6px;color:#5d574e;line-height:1.6}
.yl .info b{color:var(--ink)}
.yl .info .dn{color:var(--zhu);font-weight:700}
.yl .info .txt{color:#7c7367}
.judge{background:#fdfbf6;border:1px solid var(--line);border-left:4px solid var(--gold);
  border-radius:10px;padding:12px 15px;margin:12px 0}
.judge .jh{font-size:12.5px;color:var(--gold);font-weight:700;letter-spacing:.06em}
.judge .jm{font-size:12.6px;color:var(--ink2);margin:2px 0 7px}
.judge .jt{font-size:15px;font-weight:600;color:#332e28;line-height:1.75}
.jd-what{font-size:12.4px;color:#8c8478;margin-top:7px;line-height:1.65}

.jing{border:1px solid var(--line);border-radius:11px;padding:13px 15px;background:#fffdf8;
  margin-top:11px}
.jing h5{margin:0 0 7px;font-size:12.5px;letter-spacing:.1em;color:var(--qing);font-weight:700}
.jing .orig{font-size:14.6px;color:#332e28;line-height:1.85}
.jing .bai{font-size:13.2px;color:#7c7367;line-height:1.75;margin-top:5px}
.jing.bai-bg .orig{font-size:15px;letter-spacing:.02em}

.gua-rel{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px;margin-top:11px}
.gcard{border:1px solid var(--line);border-radius:10px;padding:9px 12px;background:#fffdf8}
.gcard .lb{font-size:11.5px;color:var(--ink2);letter-spacing:.06em}
.gcard .nm{font-size:14.5px;font-weight:700}
.gcard .nm .sym{font-size:17px;color:#5a4a2a;margin-right:5px}
.gcard .note{font-size:11.8px;color:#8c8478;margin-top:2px;line-height:1.55}

.studybox{margin-top:12px;border:1px dashed var(--line);border-radius:11px;
  padding:12px 15px;background:#fdfbf6}
.studybox h5{margin:0 0 8px;font-size:12.5px;letter-spacing:.1em;color:var(--gold);font-weight:700}
.studybox .line{font-size:13.4px;line-height:1.8;color:#4a443c}
.studybox .line .pos{display:inline-block;min-width:34px;color:var(--zhu);font-weight:700}
.studybox .quote{font-size:13.2px;color:#332e28;margin-top:9px;padding:9px 12px;
  background:#fff;border:1px solid var(--line);border-radius:8px;line-height:1.8}

.disclaim{margin-top:22px;padding:14px 16px;border:1px dashed var(--line);border-radius:12px;
  font-size:12.4px;line-height:1.7;color:#8c8478;background:#fdfbf6}
.foot{margin-top:14px;text-align:center;font-size:12px;color:#a09889}

/* ---------- 每日一句经典 ---------- */
.cls{padding:2px 0}
.cls-h{display:flex;align-items:center;gap:8px;margin-bottom:11px}
.cls-badge{display:inline-block;padding:2px 10px;border-radius:20px;
  background:#f3ece0;color:#8a6d3b;font-size:11.8px;font-weight:700;letter-spacing:.04em}
.cls-gz{margin-left:auto;font-size:11.6px;color:#a09889}
.cls-quote{margin:0;padding:15px 18px;background:#fbf7ee;border-left:3px solid var(--zhu);
  border-radius:0 10px 10px 0}
.cls-q{font-size:16.8px;line-height:2;color:#332e28;font-weight:600;letter-spacing:.02em}
.cls-src{margin-top:9px;font-size:12.3px;color:#96897a;text-align:right}
.cls-zh{margin:12px 0 0;font-size:13.6px;line-height:1.9;color:#5f574c}
.cls-note{margin-top:11px;padding:10px 14px;background:#f6f9f4;border:1px solid #e3eadd;
  border-radius:9px;font-size:13.4px;line-height:1.8;color:#4a5a42}
.cls-why{margin-top:10px;font-size:11.7px;color:#a09889;line-height:1.7}

/* ---------- 数字资产：平台活动 + 观察清单 ---------- */
.wadv{font-size:12.9px;color:#4a443c;background:#f3f8f8;border:1px dashed #cbe0e0;
  border-radius:9px;padding:9px 13px;line-height:1.72;margin-bottom:12px}
.wool{display:grid;gap:11px}
.wcard{border:1px solid var(--line);border-left:3px solid var(--qing);
  border-radius:10px;padding:11px 14px;background:#fffdf8}
.wcard.warn{border-left-color:var(--zhu)}
.wch{display:flex;align-items:baseline;gap:8px;margin-bottom:7px;flex-wrap:wrap}
.wch .wn{font-size:13.7px;font-weight:700;color:#332e28}
.wch .wk{font-size:10.5px;color:#fff;background:var(--qing);border-radius:3px;
  padding:1px 6px;letter-spacing:.02em}
.wcard.warn .wch .wk{background:var(--zhu)}
.wch .ws{margin-left:auto;font-size:11px;color:#b9963f;letter-spacing:.06em}
.wrow{display:grid;grid-template-columns:52px 1fr;gap:5px 10px;font-size:12.5px;
  line-height:1.68}
.wrow .k{color:#8c8478;font-weight:600}
.wrow .v{color:#4a443c}
.wrow .v.risk{color:#a4532f}
.wcard.warn .wrow .v.risk{color:#b0402f;font-weight:600}
.wlink{display:inline-block;margin-top:8px;font-size:12px;color:var(--qing);
  text-decoration:none;border-bottom:1px dotted var(--qing)}
.wglance{display:grid;gap:6px;margin-top:12px;padding-top:10px;
  border-top:1px dashed var(--line)}
.wg{font-size:12.3px;color:#5c544b;line-height:1.62}
.wg .n{color:#332e28;font-weight:600}
.wg .o{color:#8c8478}
.wtable{width:100%;border-collapse:collapse;font-size:12.4px;margin-top:2px}
.wtable th{text-align:left;font-weight:600;color:#8c8478;font-size:11.4px;
  padding:4px 6px;border-bottom:1px solid var(--line);white-space:nowrap}
.wtable td{padding:7px 6px;border-bottom:1px dotted #efe9dc;color:#4a443c;
  vertical-align:top;line-height:1.6}
.wtable td.nm{font-weight:700;color:#332e28;white-space:nowrap}
.wtable .role{display:block;font-weight:400;font-size:11px;color:#8c8478;
  margin-top:2px}
.wtable .why{display:block;font-size:11.3px;color:#8c8478;margin-top:3px}
.wtable .up{color:#c0392b;font-weight:600}
.wtable .dn{color:#1f8a5b;font-weight:600}
.wtable .na{color:#b0a795}
.wfoot{font-size:11.3px;color:#a09889;margin-top:10px;line-height:1.72}

/* ---------- 今日一课（系统学习路线） ---------- */
.lesson{border:1px solid var(--line);border-radius:11px;background:#fffdf8;overflow:hidden}
.lsn-top{display:flex;align-items:center;gap:9px;padding:9px 15px;background:#f3ece0;
  border-bottom:1px solid var(--line)}
.lsn-track{font-size:12.6px;font-weight:700;color:#8a6d3b;letter-spacing:.02em}
.lsn-prog{margin-left:auto;font-size:11.4px;color:#96897a}
.lsn-body{padding:12px 15px}
.lsn-title{font-size:15.2px;font-weight:700;color:#332e28;line-height:1.6;margin-bottom:8px}
.lsn-quote{margin:0 0 10px;padding:9px 13px;background:#fbf7ee;border-left:3px solid var(--qing);
  border-radius:0 8px 8px 0;font-size:13.6px;color:#4a5a42;line-height:1.85}
.lsn-prac{margin-top:10px;padding:10px 13px;background:#f6f9f4;border:1px solid #e3eadd;
  border-radius:9px;font-size:13.4px;color:#4a5a42;line-height:1.8}
.lsn-links{margin-top:11px;display:flex;gap:8px;flex-wrap:wrap}
.lsn-link{display:inline-block;padding:5px 13px;border-radius:18px;font-size:12.2px;
  text-decoration:none;border:1px solid var(--line);background:#fff;color:#3d6b5a}
.lsn-link:hover{background:#3d6b5a;color:#fff}
"""


# ---------------------------------------------------------------- 组件


def _ring(score: float, grade: str) -> str:
    c = SCORE_COLOR[_tier_of(score)]
    return (f'<div class="ring" style="border-color:{c};color:{c}">'
            f'<div class="num">{score:.0f}</div>'
            f'<div class="lbl">{_e(grade)}</div></div>')


def _bars(items: List[Dict]) -> str:
    out = ['<div class="five">']
    for it in items:
        s = it["score"]
        c = SCORE_COLOR[_tier_of(s)]
        out.append(
            f'<div class="bar"><span class="nm">{_e(it["name"])}</span>'
            f'<span class="track"><span class="fill" style="width:{min(100, s):.0f}%;background:{c}"></span></span>'
            f'<span class="v" style="color:{c}">{s:.0f}</span>'
            f'<span class="sm">{_e(it.get("summary", ""))}</span></div>')
    out.append("</div>")
    return "".join(out)


def _tips(items) -> str:
    if not items:
        return ""
    return ("<ul class='tips'>" +
            "".join(f"<li>{_e(t)}</li>" for t in items) + "</ul>")


def _sec(icon: str, title: str, body: str, score=None) -> str:
    sc = f'<span class="sc">{score:.0f}</span>' if score is not None else ""
    return (f'<div class="section"><div class="sec-h"><span class="ico">{icon}</span>'
            f'<h2>{_e(title)}</h2>{sc}</div>{body}</div>')


# ---------------------------------------------------------------- 每日一卦

YAO_NAME = {6: "老阴", 7: "少阳", 8: "少阴", 9: "老阳"}
TEND_COLOR = {"顺": "#2f6b4f", "平": "#3d6b5a", "警": "#b03030"}


def _gua_section(z: Dict) -> str:
    """每日一卦栏目 —— 与本命提要并列，不并入五门评分"""
    if not z:
        return ""

    # --- 头部 ---
    tags = "".join(f"<span>{_e(t)}</span>" for t in z.get("tags", []))
    tc = TEND_COLOR.get(z.get("tendency"), "#3d6b5a")
    head = (
        f'<div class="gua-top">'
        f'<div class="gua-sym">{z["symbol"]}</div>'
        f'<div><div class="gm">{_e(z["name"])}</div>'
        f'<div class="gx">第{z["xu"]}卦　上{z["upper"]}　下{z["lower"]}</div>'
        f'<div class="gtags">{tags}</div></div>'
        f'<div class="tend"><div class="tt" style="color:{tc}">{_e(z["tendency"])}</div>'
        f'<div class="tl">{_e(z["tend_note"])}</div></div></div>')

    # --- 六爻爻图（自上而下：上爻在顶）---
    yaotu = ['<div class="yaotu">']
    for y in reversed(z["yao_study"]):
        yang = z["yin_yang"][y["pos"] - 1] == 1
        cls = "bar" + (" yin" if not yang else "")
        if y["dong"]:
            cls += " dong"
        bar = (f'<span class="{cls}">'
               + ("<i></i><i></i>" if yang else "<i></i><i></i>")
               + "</span>")
        dong = ('　<span class="dn">动爻</span>' if y["dong"] else "")
        yaotu.append(
            f'<div class="yl">{bar}'
            f'<div class="info"><b>{y["pos"]}爻</b>　{_e(y["name"])}'
            f'　{y["dewei"]}{dong}'
            f'<br><span class="txt">{_e(y["text"])}</span></div></div>')
    yaotu.append("</div>")
    yaotu = "".join(yaotu)

    # --- 主断 ---
    judge = (
        f'<div class="judge"><div class="jh">占　断</div>'
        f'<div class="jm">{_e(z["method"])}　·　主断取「{_e(z["judge_src"])}」</div>'
        f'<div class="jt">{_e(z["judge_text"])}</div>'
        f'<div class="jd-what">倾向依断辞用语推定，示人以势，非定命之辞。</div></div>')

    # --- 具体分析 + 本命呼应 ---
    ana = _tips(list(z.get("analysis", [])) + list(z.get("benming", [])))

    # --- 经文 ---
    jing = (
        f'<div class="jing"><h5>卦　辞</h5>'
        f'<div class="orig">{_e(z["ci"])}</div>'
        f'<div class="bai">{_e(z["ci_bai"])}</div></div>'
        f'<div class="jing bai-bg"><h5>大象传（象曰）</h5>'
        f'<div class="orig">{_e(z["xiang"])}</div>'
        f'<div class="bai">{_e(z["xg_bai"])}</div></div>'
        f'<div class="jing"><h5>核心义理</h5>'
        f'<div class="orig" style="font-size:14px;line-height:1.9">{_e(z["yi"])}</div></div>'
        f'<div class="jing"><h5>今日之用</h5>'
        f'<div class="orig" style="font-size:14px;line-height:1.9">{_e(z["yong"])}</div></div>')

    # --- 关系卦 ---
    rels = ['<div class="gua-rel">']
    b = z.get("bian")
    if b:
        rels.append(f'<div class="gcard"><div class="lb">之卦（变卦）</div>'
                    f'<div class="nm"><span class="sym">{b["symbol"]}</span>{_e(b["name"])}</div>'
                    f'<div class="note">事态走向。{_e(b["ci"])}</div></div>')
    h = z.get("hu")
    if h:
        rels.append(f'<div class="gcard"><div class="lb">互卦</div>'
                    f'<div class="nm"><span class="sym">{h["symbol"]}</span>{_e(h["name"])}</div>'
                    f'<div class="note">二三五四爻相叠，看事情内在的过程肌理。</div></div>')
    for key, lb, note in (("cuo", "错卦（旁通）", "阴阳尽反 —— 换个立场看同一件事。"),
                          ("zong", "综卦（覆卦）", "上下颠倒 —— 反过来看同一件事。")):
        g = z.get(key)
        if g:
            rels.append(f'<div class="gcard"><div class="lb">{lb}</div>'
                        f'<div class="nm"><span class="sym">{g["symbol"]}</span>{_e(g["name"])}</div>'
                        f'<div class="note">{_e(note)}</div></div>')
    rels.append("</div>")
    rels = "".join(rels)

    # --- 学习：爻位通则 ---
    lines = []
    for y in z["yao_study"]:
        mark = '　<span style="color:var(--zhu);font-weight:700">（今日动爻）</span>' if y["dong"] else ""
        lines.append(
            f'<div class="line"><span class="pos">{y["pos"]}爻</span>{_e(y["wei"])}{mark}</div>')
    study = (f'<div class="studybox"><h5>爻　位　通　则</h5>' + "".join(lines) + "</div>")

    return head + yaotu + judge + _jing_notice(z) + rels + ana + jing + study


def _jing_notice(z: Dict) -> str:
    """起卦法说明"""
    mv = z.get("moving", [])
    cnt = len(mv)
    if cnt == 0:
        note = "六爻皆静，卦象稳定，以本卦卦辞为主体，不动处以守常。"
    else:
        pos = "、".join(f"{p}爻" for p in mv)
        note = f"第 {pos} 动，阳极阴生、阴极阳生，是为变机所在；本卦言其体，之卦言其用。"
    return (f'<div class="jd-what" style="margin:10px 0 0">'
            f'起卦：大衍之数五十，其用四十有九，三变成爻，十八变成卦。{_e(note)}</div>')


# ---------------------------------------------------------------- 每日一句经典


def _lesson_section(c: Dict) -> str:
    """浏览器版「今日一课」——系统学习路线的当日小节，附讲解/原文链接。"""
    if not c:
        return ""
    top = (f'<div class="lsn-top"><span class="lsn-track">{_e(c["track"])}</span>'
           f'<span class="lsn-prog">第 {c["no"]}/{c["total"]} 节　'
           f'总进度 {c["global_no"]}/{c["global_total"]}</span></div>')
    body = [f'<div class="lsn-body"><div class="lsn-title">{_e(c["title"])}</div>']
    if c.get("points"):
        body.append(_tips(c["points"]))
    if c.get("quote"):
        body.append(f'<div class="lsn-quote">{_e(c["quote"])}</div>')
    if c.get("practice"):
        body.append(f'<div class="lsn-prac"><b>今日练习　</b>{_e(c["practice"])}</div>')
    links = c.get("links") or []
    if links:
        body.append('<div class="lsn-links">' + "".join(
            f'<a class="lsn-link" href="{_e(l["url"])}" target="_blank" '
            f'rel="noopener">{_e(l["label"])} →</a>' for l in links) + "</div>")
    body.append("</div>")
    return f'<div class="lesson">{top}{"".join(body)}</div>'


def _wool_card(w: Dict) -> str:
    """一条羊毛通道的完整卡片。"""
    warn = w.get("stars", 3) <= 1 or "高风险" in w.get("kind", "")
    rows = [("门槛", w["need"], False), ("怎么薅", w["how"], False),
            ("拿到什么", w["gain"], False), ("注意", w["risk"], True)]
    body = "".join(
        f'<div class="k">{k}</div><div class="v{" risk" if r else ""}">{_e(v)}</div>'
        for k, v, r in rows)
    return (
        f'<div class="wcard{" warn" if warn else ""}">'
        f'<div class="wch"><span class="wn">{_e(w["name"])}</span>'
        f'<span class="wk">{_e(w["kind"])}</span>'
        f'<span class="ws">{"★" * w["stars"]}{"☆" * (5 - w["stars"])}</span></div>'
        f'<div class="wrow">{body}</div>'
        f'<a class="wlink" href="{_e(w["link"])}" target="_blank">'
        f'前往官网查看当期活动 ↗</a></div>')


def _watch_table(watch: Dict) -> str:
    """观察清单表格。行情未取到时仍列出标的与观察理由。"""
    rows = []
    for r in watch.get("rows", []):
        if r.get("ok"):
            cls = "up" if r["chg"] >= 0 else "dn"
            price = f'{r["price_txt"]}'
            chg = f'<span class="{cls}">{r["chg"]:+.2f}%</span>'
            state = r.get("note", "")
        else:
            price = '<span class="na">未取到</span>'
            chg = '<span class="na">—</span>'
            state = "行情接口不可达，本条仅列清单与观察理由。"
        rows.append(
            f'<tr><td class="nm">{_e(r["name"])}'
            f'<span class="role">{_e(r.get("role", ""))}</span></td>'
            f'<td>{price}</td><td>{chg}</td>'
            f'<td>{_e(state)}<span class="why">{_e(r.get("why", ""))}</span></td></tr>')
    if not rows:
        return '<div class="wfoot">观察清单未取到。</div>'
    return (f'<table class="wtable"><thead><tr><th>标的</th><th>现价</th>'
            f'<th>24h</th><th>客观状态 / 观察理由</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def _assets_section(inv: Dict) -> str:
    """浏览器版「数字资产」：今日适配建议 + 重点通道 + 速览 + 观察清单 + 防坑。"""
    a = inv.get("assets")
    if not a:
        return _tips(inv.get("crypto", []))
    head = f'<div class="wadv">{_e(a["advice"])}</div>'
    cards = f'<div class="wool">{"".join(_wool_card(w) for w in a["focus"])}</div>'
    glance = "".join(
        f'<div class="wg"><span class="n">{_e(w["name"])}</span>'
        f'　<span class="o">{_e(w["one"])}</span></div>' for w in a["glance"])
    glance = (f'<div class="wglance">{glance}'
              f'<div class="wg o">常青通道库共 {a["total"]} 项，每日轮换推送。</div></div>')
    watch = _watch_table(a["watch"])
    w = a["watch"]
    ts = (f'　行情时间 {_e(w.get("ts", ""))}'
          + (f'（数据源 {_e(w.get("source", ""))}）' if w.get("source") else "")
          ) if w.get("ok") else ""
    return (head + cards + glance
            + f'<div class="wfoot">{_e(a["disclaimer"])}{ts}</div>'
            + watch
            + _tips(["防坑：" + s for s in a["safety"]][:4]))


def _classic_section(c: Dict) -> str:
    """浏览器版「每日一句经典」。"""
    if not c:
        return '<div class="cls-zh">今日经典未取到，不影响术数内容。</div>'
    head = (f'<div class="cls-h"><span class="cls-badge">{_e(c["theme"])}</span>'
            f'<span class="cls-gz">{_e(c.get("day_gz", ""))}日'
            f'　日干属{_e(c.get("wuxing", ""))}</span></div>')
    quote = (f'<div class="cls-quote"><div class="cls-q">{_e(c["text"])}</div>'
             f'<div class="cls-src">—— {_e(c["book"])}·{_e(c["chapter"])}</div></div>')
    zh = f'<div class="cls-zh"><b>白话　</b>{_e(c["zh"])}</div>'
    note = f'<div class="cls-note"><b>今日提点　</b>{_e(c["note"])}</div>'
    why = f'<div class="cls-why">{_e(c["why"])}</div>'
    return f'<div class="cls">{head}{quote}{zh}{note}{why}</div>'


# ---------------------------------------------------------------- 主渲染


def render_html(r: Dict) -> str:
    m, d = r["meta"], r["destiny"]
    g, tr, he, soc, inv, st = (r["general"], r["travel"], r["health"],
                               r["social"], r["invest"], r["study"])

    # --- 命盘
    sizhu_html = "".join(
        f'<div style="text-align:center"><div style="font-size:19px;font-weight:700">'
        f'{_e(n)}</div><div style="font-size:12px;color:#8c8478">{_e(t)}</div>'
        f'<div style="font-size:11px;color:#a09889">{_e(ny)}</div></div>'
        for n, t, ny in zip(d["sizhu"], d["sizhu_ten"], d["sizhu_nayin"]))
    stars = "; ".join(f"{k}柱：{'、'.join(v)}" for k, v in d["stars"].items() if v)

    dest = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;
                padding:12px;background:#fdfbf6;border:1px solid var(--line);
                border-radius:12px;margin-bottom:14px">{sizhu_html}</div>
    <dl class="kv">
      <dt>日主</dt><dd>{_e(d['day_master'])}水 · {_e(d['strength_label'])}（{d['strength']}）</dd>
      <dt>格局</dt><dd>{_e(d['pattern'])}</dd>
      <dt>取用</dt><dd>用神 {_e(d['yong'])}　忌神 {_e(d['ji'])}</dd>
      <dt>大运 / 流年</dt><dd>{_e(d['dayun'])}　{_e(d['liunian'])}年</dd>
    </dl>
    """
    if stars:
        dest += f'<div style="font-size:12.6px;color:#8c8478;margin-top:10px">神煞：{_e(stars)}</div>'

    # --- 宜忌
    yj = f"""<div class="yi-ji">
      <div class="box"><h4 class="y">宜</h4>{''.join(f'<p>· {_e(x)}</p>' for x in g['yi'])}</div>
      <div class="box"><h4 class="j">忌</h4>{''.join(f'<p>· {_e(x)}</p>' for x in g['ji'])}</div>
    </div>"""

    body = []
    body.append(
        f'<div class="hero"><div class="brand">五 术 日 课</div>'
        f'<h1>{_e(m["date_str"])} · {_e(m["weekday"])}</h1>'
        f'<div class="sub">{_e(m["lunar_full"])}　|　{m["day_gz"]}日（{_e(m["day_nayin"])}）　|　'
        f'节气：{_e(m["jieqi"])}</div>'
        f'<div class="hero-row">{_ring(m["total"], m["grade"])}'
        f'<div class="chips">'
        f'<span class="chip">本命 <b>{_e(d["day_master"])}水 · {_e(d["pattern"])}</b></span>'
        f'<span class="chip">用神 <b>{_e(d["yong"])}</b></span>'
        f'<span class="chip">大运 <b>{_e(d["dayun"].split("（")[0])}</b></span>'
        f'<span class="chip">流年 <b>{_e(d["liunian"])}</b></span>'
        f'</div></div></div>')

    body.append(_sec("盘", "本命提要", dest))
    if r.get("zhouyi"):
        body.append(_sec("卦", "每日一卦 · 大衍筮法", _gua_section(r["zhouyi"])))
    body.append(_sec("五", "五门评分", _bars(r["five"])))
    body.append(_sec("常", "日常生活",
                     f'<div style="font-size:15px;font-weight:600;margin-bottom:10px;'
                     f'color:#3f3a33">{_e(g["headline"])}</div>'
                     f'{_tips(g["tips"])}{yj}', g["score"]))

    health_body = (
        f'<div style="font-size:15px;font-weight:600;margin-bottom:10px;color:#3f3a33">'
        f'{_e(he["headline"])}</div>'
        f'<div style="font-size:13.4px;color:#7c7367;margin-bottom:12px">'
        f'{_e("　".join(he["organ_tips"]))}</div>'
        f'<div class="grid2">'
        f'<div><div style="font-size:13px;color:var(--qing);font-weight:700;margin-bottom:6px">'
        f'■ 力量训练</div>{_tips(he["training"])}</div>'
        f'<div><div style="font-size:13px;color:var(--qing);font-weight:700;margin-bottom:6px">'
        f'■ 八部金刚功</div>{_tips(he["qigong"])}</div></div>'
        f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 6px">'
        f'■ 营养补给</div>{_tips(he["nutrition"])}')
    body.append(_sec("健", "健康 · 健身 · 金刚功", health_body, he["score"]))

    car = r.get("career")
    if car:
        career_body = (f'<div style="font-size:15px;font-weight:600;margin-bottom:10px;color:#3f3a33">'
                       f'{_e(car["advice_headline"])}</div>{_tips(car["notes"])}'
                       f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 6px">'
                       f'■ 今日行动</div>{_tips(car["actions"])}')
        body.append(_sec("业", "事业 · 客户 · 融资", career_body, car["score"]))

    body.append(_sec("行", "出行方位",
                     f'<div style="font-size:15px;font-weight:600;margin-bottom:10px;color:#3f3a33">'
                     f'{_e(tr["headline"])}</div>{_tips(tr["tips"])}', tr["score"]))

    rel_cards = "".join(
        f'<div class="rel{" on" if x["on_duty"] else ""}">'
        f'<div class="rh"><span class="who">{_e(x["who"])}</span>'
        f'<span class="star">{_e(x["star"])}</span>'
        f'<span class="st">{_e(x["state"])}</span></div>'
        f'<div class="ad">{_e(x["advice"])}</div></div>'
        for x in soc.get("relations", []))
    social_body = (f'<div style="font-size:15px;font-weight:600;margin-bottom:10px;color:#3f3a33">'
                   f'{_e(soc["headline"])}</div>{_tips(soc["tips"])}'
                   f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 8px">'
                   f'■ 六亲分论（今日十神：{_e(soc["today_star"])}）</div>'
                   f'<div class="rels">{rel_cards}</div>')
    body.append(_sec("缘", "人际关系", social_body, soc["score"]))

    ld = inv.get("lottery_detail") or {}
    lot_html = ""
    if ld.get("skip"):
        # 低于建议线：明确「今日不建议购买」，不出号码
        lot_html = (f'<div class="lot skip"><div class="lt">今日不建议购买'
                    f'<span class="lv" style="margin-left:8px">'
                    f'彩气 {ld.get("score", 0):.0f} / 建议线 {ld.get("skip_threshold", 50):.0f}</span></div>'
                    f'<div class="ln">五门加权总分偏低，术数层面无支撑。'
                    f'今日停买一天，额度留到彩气旺日再用。</div></div>')
    else:
        for p in ld.get("picks", []):
            front = "".join(f'<span class="ball">{n}</span>' for n in p["front"])
            back = ""
            if p.get("back"):
                back = ('<span class="sep">+</span>'
                        + "".join(f'<span class="ball b">{n}</span>' for n in p["back"]))
            lot_html += (f'<div class="lot"><div class="lt">{_e(p["game"])}'
                         f'<span class="lv" style="margin-left:8px">'
                         f'今日唯一推荐 · 彩气 {ld.get("score", 0):.0f}</span></div>'
                         f'<div class="balls">{front}{back}</div>'
                         f'<div class="ln">{_e(p.get("note", ""))}　|　'
                         f'选种依据：{_e(p.get("reason", ""))}</div></div>')
        others = [g for g in ld.get("open_games", []) if g != ld.get("chosen")]
        if others:
            lot_html += (f'<div style="font-size:12.5px;color:var(--ink2);margin-top:8px">'
                         f'当日其他开奖彩种（今日不碰）：'
                         f'{"、".join(_e(x) for x in others)}</div>')

    invest_body = (f'<div class="risk"><b>⚠ 风险提示</b>　{_e(inv["risk_banner"])}</div>'
                   f'<div style="font-size:15px;font-weight:600;margin:10px 0;color:#3f3a33">'
                   f'{_e(inv["headline"])}</div>{_tips(inv["notes"])}'
                   f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 6px">'
                   f'■ 数字资产（{_e(inv["exchange"].upper())}）· 平台活动薅羊毛</div>'
                   f'{_assets_section(inv)}'
                   f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 6px">'
                   f'■ 仓位与账户纪律</div>{_tips(inv["crypto"])}'
                   f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 6px">'
                   f'■ 彩票娱乐</div>{_tips(inv["lottery"])}{lot_html}')
    body.append(_sec("财", "投资 · 彩票 · 数字资产", invest_body, inv["score"]))

    body.append(_sec("学", "传统文化学习 · 今日一课",
                     f'<div style="font-size:15px;font-weight:600;margin-bottom:10px;color:#3f3a33">'
                     f'{_e(st["headline"])}</div>'
                     f'{_lesson_section(st.get("lesson"))}{_tips(st["plan"])}',
                     st["score"]))

    if r.get("classic"):
        body.append(_sec("典", "每日一句经典", _classic_section(r["classic"])))

    checks = "".join(
        f'<div class="chk"><span class="boxf"></span><span class="t">{_e(c["task"])}</span>'
        f'<span class="tag">{_e(c["tag"])}</span></div>' for c in r["checklist"])
    body.append(_sec("记", "今日打卡清单", f'<div class="checks">{checks}</div>'))

    body.append(f'<div class="disclaim">{_e(r["disclaimer"])}</div>')
    body.append(f'<div class="foot">destiny-daily v1.0 · 生成于 {_e(m["generated_at"])}</div>')

    return (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_e(m["date_str"])} 每日运势 · {_e(m["grade"])}</title>'
            f'<style>{CSS}</style></head><body><div class="wrap">'
            + "".join(body) + "</div></body></html>")


# ---------------------------------------------------------------- 文本摘要


def render_text(r: Dict) -> str:
    m, d = r["meta"], r["destiny"]
    L = []
    L.append(f"{m['date_str']} {m['weekday']}　{m['lunar_full']}　{m['day_gz']}日")
    L.append(f"综合运势 {m['total']:.0f} 分（{m['grade']}）　节气：{m['jieqi']}")
    L.append("")
    if r.get("zhouyi"):
        z = r["zhouyi"]
        L.append(f"【每日一卦】{z['symbol']} {z['name']}（第{z['xu']}卦）　"
                 f"上{z['upper']}　下{z['lower']}　倾向：{z['tendency']}")
        for i in range(5, -1, -1):
            y = z["yao_study"][i]
            yang = z["yin_yang"][i] == 1
            sym = "━━━" if yang else "━　━"
            L.append(f"    {sym}  {y['pos']}爻 {y['name']}"
                     f"{' ←动' if y['dong'] else ''}　{y['text']}")
        L.append(f"  卦辞：{z['ci']}")
        L.append(f"  大象：{z['xiang']}")
        if z.get("bian"):
            L.append(f"  之卦：{z['bian']['symbol']} {z['bian']['name']}　{z['bian']['ci']}")
        L.append(f"  断法：{z['method']}")
        L.append(f"  主断：{z['judge_src']}　{z['judge_text']}")
        for x in z["analysis"]:
            L.append(f"  · {x}")
        for x in z["benming"]:
            L.append(f"  ◈ {x}")
        L.append(f"  义理：{z['yi']}")
        L.append(f"  日用：{z['yong']}")
        L.append("")
    L.append("【五门评分】")
    for p in r["five"]:
        L.append(f"  {p['name']:<6} {p['score']:.0f}　{p['summary']}")
    L.append("")
    L.append(f"【日常生活】{r['general']['headline']}")
    for t in r["general"]["tips"]:
        L.append(f"  · {t}")
    L.append(f"  宜：{'、'.join(r['general']['yi'])}")
    L.append(f"  忌：{'、'.join(r['general']['ji'])}")
    L.append("")
    L.append(f"【健康】{r['health']['headline']}")
    L.append(f"  脏腑：{r['health']['organ']}")
    for t in r["health"]["training"]:
        L.append(f"  · {t}")
    for t in r["health"]["qigong"]:
        L.append(f"  · {t}")
    L.append("")
    L.append(f"【出行】{r['travel']['headline']}")
    for t in r["travel"]["tips"]:
        L.append(f"  · {t}")
    L.append("")
    car = r.get("career")
    if car:
        L.append(f"【事业】{car['headline']}")
        L.append(f"  {car['advice_headline']}")
        for t in car["notes"]:
            L.append(f"  · {t}")
        for t in car["actions"]:
            L.append(f"  - {t}")
        L.append("")
    L.append(f"【人际】{r['social']['headline']}　（今日十神：{r['social']['today_star']}）")
    for t in r["social"]["tips"][:4]:
        L.append(f"  · {t}")
    for x in r["social"].get("relations", []):
        L.append(f"  【{x['who']}】{x['state']}　{x['advice']}")
    L.append("")
    L.append(f"【投资】{r['invest']['headline']}")
    for t in r["invest"]["notes"][:3]:
        L.append(f"  · {t}")
    _as = r["invest"].get("assets") or {}
    if _as:
        L.append(f"  ■ 数字资产（{r['invest']['exchange'].upper()}）· 平台活动薅羊毛")
        L.append(f"  · 今日适配：{_as['advice']}")
        for w in _as["focus"]:
            L.append(f"  · 【{w['name']}】{w['kind']} {'★' * w['stars']}"
                     f"{'☆' * (5 - w['stars'])}")
            for k, v in (("门槛", w["need"]), ("怎么薅", w["how"]),
                         ("拿到什么", w["gain"]), ("注意", w["risk"])):
                L.append(f"      {k}：{v}")
            L.append(f"      官网：{w['link']}")
        L.append("  · 速览：" + "；".join(
            f"{w['name']}（{w['one']}）" for w in _as["glance"]))
        L.append(f"  · 观察清单：{'、'.join(x['name'] for x in _as['watch']['rows'])}")
        for x in _as["watch"]["rows"]:
            if x.get("ok"):
                L.append(f"      {x['name']:<4} {x['price_txt']:>12}  "
                         f"{x['chg']:+6.2f}%  {x['note']}")
        if _as["watch"].get("ok"):
            L.append(f"      行情时间 {_as['watch'].get('ts', '')}"
                     f"（数据源 {_as['watch'].get('source', '')}）")
        L.append("  · 防坑：" + "　".join(_as["safety"][:3]))
    L.append("  ■ 仓位与账户纪律")
    for t in r["invest"]["crypto"]:
        L.append(f"  · {t}")
    L.append("  ■ 彩票娱乐")
    ld = r["invest"].get("lottery_detail") or {}
    for t in r["invest"]["lottery"]:
        L.append(f"  · {t}")
    if ld.get("skip"):
        L.append(f"  · 【今日不建议购买】彩气 {ld.get('score', 0):.0f} "
                 f"< 建议线 {ld.get('skip_threshold', 50):.0f}，不出号码")
    else:
        for p in ld.get("picks", []):
            nums = " ".join(f"{n:02d}" for n in p["front"])
            if p.get("back"):
                nums += "  +  " + " ".join(f"{n:02d}" for n in p["back"])
            L.append(f"  · {p['game']}（今日唯一推荐）{p['note']}")
            L.append(f"      号码：{nums}")
            L.append(f"      选种依据：{p.get('reason', '')}")
        others = [g for g in ld.get("open_games", []) if g != ld.get("chosen")]
        if others:
            L.append(f"      当日其他开奖彩种（今日不碰）：{'、'.join(others)}")
    L.append(f"  {r['invest']['risk_banner']}")
    L.append("")
    L.append(f"【学习】{r['study']['headline']}")
    les = r["study"].get("lesson")
    if les:
        L.append(f"  ▍今日一课：{les['title']}")
        L.append(f"    {les['track']}（第 {les['no']}/{les['total']} 节，"
                 f"总进度 {les['global_no']}/{les['global_total']}）")
        for p in les.get("points", []):
            L.append(f"    · {p}")
        if les.get("quote"):
            L.append(f"    【原文】{les['quote']}")
        if les.get("practice"):
            L.append(f"    【今日练习】{les['practice']}")
        for l in les.get("links", []):
            L.append(f"    【{l['label']}】{l['url']}")
    for t in r["study"]["plan"]:
        L.append(f"  · {t}")
    L.append("")
    if r.get("classic"):
        try:
            from .classic import render_classic_text as _rct
            L.append(_rct(r["classic"]))
            L.append("")
        except Exception:        # noqa: BLE001
            pass
    L.append("【今日打卡】")
    for c in r["checklist"]:
        L.append(f"  ☐ {c['task']}")
    L.append("")
    L.append(r["disclaimer"])
    return "\n".join(L)


def save_report(r: Dict, out_dir: str = OUT_DIR,
                date: datetime = None) -> Dict[str, str]:
    """产出三份：
        .html       完整报告，宣纸风、带 grid/flex，浏览器里看最好
        .mail.html  邮件专用版，table 布局 + 全内联样式（见 engine.mail_report）
        .txt        纯文本摘要，用于邮件降级正文 / 控制台
    """
    os.makedirs(out_dir, exist_ok=True)
    date = date or r["target"] if "target" in r else datetime.now()
    stamp = (date.strftime("%Y-%m-%d") if isinstance(date, datetime)
             else str(date))
    html_path = os.path.join(out_dir, f"destiny-{stamp}.html")
    mail_path = os.path.join(out_dir, f"destiny-{stamp}.mail.html")
    txt_path = os.path.join(out_dir, f"destiny-{stamp}.txt")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(r))
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(render_text(r))
    # 邮件版做延迟导入 + 兜底：mail_report 反向依赖本模块的色板，
    # 顶层互相 import 会形成循环，这里在函数内部取用最省事。
    # 即便某天它出问题，也不影响上面两份主产物。
    try:
        from .mail_report import render_mail_html as _render_mail
        with open(mail_path, "w", encoding="utf-8") as f:
            f.write(_render_mail(r))
    except Exception as e:        # noqa: BLE001
        print(f"[warn] 邮件版 HTML 生成失败，已跳过：{e}")
    return {"html": html_path, "mail": mail_path, "txt": txt_path}
