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

.disclaim{margin-top:22px;padding:14px 16px;border:1px dashed var(--line);border-radius:12px;
  font-size:12.4px;line-height:1.7;color:#8c8478;background:#fdfbf6}
.foot{margin-top:14px;text-align:center;font-size:12px;color:#a09889}
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

    btc = inv.get("btc", {})
    btc_html = (f'<div style="font-size:13.5px;font-weight:700;margin-bottom:6px;color:#3f3a33">'
                f'{_e(btc.get("headline", ""))}</div>{_tips(btc.get("lines", []))}')

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
                   f'■ BTC 复盘</div>{btc_html}'
                   f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 6px">'
                   f'■ 数字资产（{_e(inv["exchange"].upper())}）</div>{_tips(inv["crypto"])}'
                   f'<div style="font-size:13px;color:var(--gold);font-weight:700;margin:14px 0 6px">'
                   f'■ 彩票娱乐</div>{_tips(inv["lottery"])}{lot_html}')
    body.append(_sec("财", "投资 · 彩票 · 数字资产", invest_body, inv["score"]))

    body.append(_sec("学", "传统文化学习",
                     f'<div style="font-size:15px;font-weight:600;margin-bottom:10px;color:#3f3a33">'
                     f'{_e(st["headline"])}</div>{_tips(st["plan"])}', st["score"]))

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
    btc = r["invest"].get("btc", {})
    if btc.get("ok"):
        L.append(f"  · BTC 复盘：{btc['headline']}")
        for t in btc.get("lines", []):
            L.append(f"      {t}")
    else:
        for t in btc.get("lines", [])[:2]:
            L.append(f"  · {t}")
    for t in r["invest"]["crypto"]:
        L.append(f"  · {t}")
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
    for t in r["study"]["plan"]:
        L.append(f"  · {t}")
    L.append("")
    L.append("【今日打卡】")
    for c in r["checklist"]:
        L.append(f"  ☐ {c['task']}")
    L.append("")
    L.append(r["disclaimer"])
    return "\n".join(L)


def save_report(r: Dict, out_dir: str = OUT_DIR,
                date: datetime = None) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    date = date or r["target"] if "target" in r else datetime.now()
    stamp = (date.strftime("%Y-%m-%d") if isinstance(date, datetime)
             else str(date))
    html_path = os.path.join(out_dir, f"destiny-{stamp}.html")
    txt_path = os.path.join(out_dir, f"destiny-{stamp}.txt")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(r))
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(render_text(r))
    return {"html": html_path, "txt": txt_path}
