# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.astock
「A股复盘」—— 市场事实层，独立于术数推算。

为什么单独一层
--------------
早报 08:00 发出，A 股尚未开盘，所以「复盘」指的是**最近一个交易日的收盘**；
若在非标准时刻重跑，数据源带回来的可能是盘中快照，必须如实标注是收盘还是盘中，
不能把 12:00 的盘中价说成「昨日收盘」。数据日期一律取自数据源自带的时间戳，
不用「今天减一天」去猜（周一早上抓到的是上周五，节假日更要靠数据源）。

数据源与 IP 属地（2026-11-09 实测）
----------------------------------
境内可达：东方财富 push2（指数/成交额/涨跌家数/行业板块，信息最全）、
          腾讯 qt.gtimg.cn、新浪 hq.sinajs.cn（后两者只有指数，GBK 文本）。
境外可达：Yahoo Finance chart API —— Yahoo 自 2021-11-01 起对**中国大陆**
          整体停用，但明确声明「其它全球地区不受影响」，正好补 GitHub Actions
          美国节点的盲区（与 lottery_result 的备用源是同一套思路）。
按「东财 → 腾讯 → 新浪 → Yahoo」依次尝试，任一源成功即返回；
全挂时返回 ok=False + reason="unreachable"，渲染端必须显示
「行情数据获取失败（数据源不可达）」，**绝不降级成「尚未公布」**。

风险立场
--------
只陈述已发生的客观事实（点位、涨跌幅、成交额、家数、板块），
不预测方向、不给点位目标、不推荐个股；涨跌配色遵循 A 股习惯：涨红跌绿。
联网失败绝不中断整份报告。
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

CST = timezone(timedelta(hours=8), "Asia/Shanghai")
TIMEOUT = 8

# 五大指数：(东财 secid, 名称, 腾讯代码, 新浪代码, Yahoo 代码)
INDEXES = [
    ("1.000001", "上证指数", "s_sh000001", "s_sh000001", "000001.SS"),
    ("0.399001", "深证成指", "s_sz399001", "s_sz399001", "399001.SZ"),
    ("0.399006", "创业板指", "s_sz399006", "s_sz399006", "399006.SZ"),
    ("1.000688", "科创50", "s_sh000688", "s_sh000688", "000688.SS"),
    ("1.000300", "沪深300", "s_sh000300", "s_sh000300", "000300.SS"),
]
EM_SECIDS = ",".join(x[0] for x in INDEXES)
EM_BASE = "https://push2.eastmoney.com/api/qt"

DISCLAIMER = ("行情为公开数据源快照，仅供复盘记录，不构成投资建议；"
              "指数与板块口径以数据源公告为准，成交额单位已换算为亿元。")

_CACHE: Dict = {"ts": 0.0, "data": None}
CACHE_TTL = 300


def reset_cache() -> None:
    """测试用：清掉本轮缓存。"""
    _CACHE["ts"], _CACHE["data"] = 0.0, None


def _get(url: str, headers: Optional[Dict] = None, timeout: int = TIMEOUT) -> bytes:
    h = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get_json(url: str, headers: Optional[Dict] = None,
              timeout: int = TIMEOUT):
    return json.loads(_get(url, headers, timeout).decode("utf-8"))


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return f if f == f else None        # 排除 NaN
    except (TypeError, ValueError):
        return None


def _blank(reason: str = "", error: str = "") -> Dict:
    return {"ok": False, "reason": reason, "error": error,
            "source": "", "as_of": "", "date": "", "session": "",
            "indices": [], "breadth": None, "sectors_up": [],
            "sectors_down": [], "summary": "", "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------- 东方财富（信息最全）

def _eastmoney() -> Dict:
    url = (f"{EM_BASE}/ulist.np/get?fltt=2&secids={EM_SECIDS}"
           "&fields=f2,f3,f6,f12,f13,f14,f124")
    d = _get_json(url)
    diff = ((d.get("data") or {}).get("diff") or [])
    if not diff:
        raise RuntimeError("东财指数返回为空")
    byname = {}
    stamps = []
    for x in diff:
        p, c = _num(x.get("f2")), _num(x.get("f3"))
        if p is None or c is None:
            continue
        amt = _num(x.get("f6"))
        byname[str(x.get("f14", ""))] = {
            "name": str(x.get("f14", "")), "code": str(x.get("f12", "")),
            "close": p, "chg": c,
            "amount_yi": round(amt / 1e8, 1) if amt is not None else None,
        }
        if _num(x.get("f124")):
            stamps.append(int(x["f124"]))
    order = [x[1] for x in INDEXES]
    indices = [byname[n] for n in order if n in byname]
    if not indices:
        raise RuntimeError("东财指数形态校验未通过")

    a = _blank()
    a["ok"], a["source"] = True, "东方财富"
    a["indices"] = indices
    if stamps:
        dt = datetime.fromtimestamp(max(stamps), CST)
        a["as_of"] = dt.strftime("%Y-%m-%d %H:%M")
        a["date"] = dt.strftime("%Y-%m-%d")
        a["session"] = "收盘复盘" if (dt.hour, dt.minute) >= (15, 0) else "盘中快照"

    # 以下三项为增量信息，失败不影响整栏成立
    try:
        b = _get_json(f"{EM_BASE}/ulist.np/get?fltt=2&secids=1.000001"
                      "&fields=f104,f105,f106")
        row = ((b.get("data") or {}).get("diff") or [{}])[0]
        up, dn, fl = (_num(row.get("f104")), _num(row.get("f105")),
                      _num(row.get("f106")))
        if None not in (up, dn, fl):
            a["breadth"] = {"up": int(up), "down": int(dn), "flat": int(fl)}
    except Exception:       # noqa: BLE001
        pass
    for po, key in ((1, "sectors_up"), (0, "sectors_down")):
        try:
            s = _get_json(f"{EM_BASE}/clist/get?pn=1&pz=3&po={po}&np=1"
                          "&fltt=2&fid=f3&fs=m:90+t:2&fields=f3,f14")
            rows = ((s.get("data") or {}).get("diff") or [])
            a[key] = [{"name": str(x["f14"]), "chg": float(x["f3"])}
                      for x in rows if _num(x.get("f3")) is not None
                      and str(x.get("f14", ""))][:3]
        except Exception:   # noqa: BLE001
            pass
    return a


# ---------------------------------------------------------------- 腾讯 / 新浪（GBK 文本，仅指数）

def _text_indices(raw: str, prefix: str, sina: bool) -> List[Dict]:
    """解析 s_sh000001 系列简版行情：现价、涨跌幅、成交额（万元）。"""
    out: Dict[str, Dict] = {}
    for line in raw.splitlines():
        line = line.strip().rstrip(";")
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.replace("var ", "").strip()
        if not key.startswith(prefix):
            continue
        val = val.strip().strip('"')
        f = val.split("~") if not sina else val.split(",")
        try:
            if sina:                       # 名称,现价,涨跌额,涨跌幅,量,额(万元)
                nm, p, c, amt = f[0], f[1], f[3], f[5]
            else:                          # 1~名称~代码~现价~涨跌额~涨跌幅~量~额(万元)~…
                nm, p, c, amt = f[1], f[3], f[5], f[7]
            pv, cv, av = _num(p), _num(c), _num(amt)
            if None in (pv, cv):
                continue
            out[nm] = {"name": nm, "code": "", "close": pv, "chg": cv,
                       "amount_yi": round(av / 1e4, 1) if av is not None else None}
        except (IndexError, ValueError):
            continue
    return [out[n] for n in (x[1] for x in INDEXES) if n in out]


def _tencent() -> Dict:
    q = ",".join(x[2] for x in INDEXES)
    raw = _get(f"https://qt.gtimg.cn/q={q}").decode("gbk", "ignore")
    indices = _text_indices(raw, "v_s_", sina=False)
    if not indices:
        raise RuntimeError("腾讯行情解析为空")
    a = _blank()
    a.update({"ok": True, "source": "腾讯财经", "indices": indices,
              "session": "最近收盘", "as_of": "", "date": ""})
    return a


def _sina() -> Dict:
    q = ",".join(x[3] for x in INDEXES)
    raw = _get(f"https://hq.sinajs.cn/list={q}",
               {"Referer": "https://finance.sina.com.cn/"}).decode("gbk", "ignore")
    indices = _text_indices(raw, "hq_str_s_", sina=True)
    if not indices:
        raise RuntimeError("新浪行情解析为空")
    a = _blank()
    a.update({"ok": True, "source": "新浪财经", "indices": indices,
              "session": "最近收盘", "as_of": "", "date": ""})
    return a


# ---------------------------------------------------------------- Yahoo（境外节点备用）

def _yahoo() -> Dict:
    """Yahoo 在大陆整体停用但在境外可用；只取三大指数的日线收盘。"""
    indices: List[Dict] = []
    stamps = []
    for secid, name, _t, _s, ysym in INDEXES[:3]:
        try:
            d = _get_json("https://query1.finance.yahoo.com/v8/finance/chart/"
                          f"{ysym}?range=5d&interval=1d", timeout=6)
            res = (d.get("chart") or {}).get("result") or [{}]
            r = res[0]
            ts = r.get("timestamp") or []
            closes = ((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
            pairs = [(t, c) for t, c in zip(ts, closes) if _num(c) is not None]
            if len(pairs) < 2:
                continue
            (t1, c1), (t2, c2) = pairs[-2], pairs[-1]
            indices.append({"name": name, "code": secid.split(".")[-1],
                            "close": float(c2),
                            "chg": (float(c2) / float(c1) - 1) * 100 if c1 else 0.0,
                            "amount_yi": None})
            stamps.append(int(t2))
        except Exception:   # noqa: BLE001
            continue
    if not indices:
        raise RuntimeError("Yahoo 日线解析为空")
    a = _blank()
    a.update({"ok": True, "source": "Yahoo Finance", "indices": indices,
              "session": "收盘复盘"})
    if stamps:
        dt = datetime.fromtimestamp(max(stamps), CST)
        a["as_of"] = dt.strftime("%Y-%m-%d")
        a["date"] = dt.strftime("%Y-%m-%d")
    return a


SOURCES = [("eastmoney", _eastmoney), ("tencent", _tencent),
           ("sina", _sina), ("yahoo", _yahoo)]


# ---------------------------------------------------------------- 小结与主入口

def _summary(a: Dict) -> str:
    ix = a["indices"]
    if not ix:
        return ""
    head = "、".join(f"{x['name']} {x['close']:,.2f}（{x['chg']:+.2f}%）"
                    for x in ix[:2])
    amt = [x for x in ix[:2] if x.get("amount_yi") is not None]
    if amt:
        head += "；成交额 " + " / ".join(f"{x['name']} {x['amount_yi']:,.0f} 亿"
                                    for x in amt)
    b = a.get("breadth")
    if b:
        head += f"；涨 {b['up']} / 跌 {b['down']} / 平 {b['flat']} 家"
    if a.get("sectors_up"):
        head += "；领涨 " + "、".join(f"{x['name']} {x['chg']:+.2f}%"
                                  for x in a["sectors_up"][:2])
    if a.get("sectors_down"):
        head += "；领跌 " + "、".join(f"{x['name']} {x['chg']:+.2f}%"
                                  for x in a["sectors_down"][:2])
    return head + "。"


def fetch(offline: bool = False, use_cache: bool = True) -> Dict:
    """抓最近一次 A 股行情；任何异常都被吞掉，返回可渲染的降级结构。"""
    if offline:
        a = _blank(reason="offline")
        a["session"] = "离线模式"
        return a
    now = time.time()
    if (use_cache and _CACHE["data"] is not None
            and now - _CACHE["ts"] < CACHE_TTL):
        return _CACHE["data"]

    errors = []
    a = _blank()
    for name, fn in SOURCES:
        try:
            cand = fn()
            if cand.get("ok") and cand.get("indices"):
                a = cand
                break
        except Exception as e:              # noqa: BLE001
            errors.append(f"{name}: {repr(e)[:70]}")
    if not a["ok"]:
        a = _blank(reason="unreachable", error="；".join(errors))
    else:
        a["error"] = "；".join(errors)
        a["summary"] = _summary(a)
    _CACHE["ts"], _CACHE["data"] = now, a
    return a


def render_astock_text(a: Dict) -> List[str]:
    """纯文本版 / 调试用。"""
    L: List[str] = []
    label = a.get("session") or "复盘"
    L.append(f"【A股复盘 · {label}】")
    if not a.get("ok"):
        if a.get("reason") == "offline":
            L.append("  · 离线模式：本次未抓取 A 股行情。")
        else:
            L.append("  · 行情数据获取失败（数据源不可达）：东方财富 / 腾讯 / 新浪 / Yahoo 均未取到。")
        return L
    stamp = a.get("as_of") or a.get("date") or "数据源未提供时间戳"
    L.append(f"  · {a.get('session') or '复盘'}　数据：{stamp}　来源 {a['source']}")
    for x in a["indices"]:
        amt = f"　成交额 {x['amount_yi']:,.0f} 亿" if x.get("amount_yi") is not None else ""
        L.append(f"  · {x['name']:<6} {x['close']:>10,.2f}　{x['chg']:+6.2f}%{amt}")
    b = a.get("breadth")
    if b:
        L.append(f"  · 市场宽度：涨 {b['up']} / 跌 {b['down']} / 平 {b['flat']} 家")
    if a.get("sectors_up"):
        L.append("  · 领涨行业：" + "、".join(
            f"{x['name']} {x['chg']:+.2f}%" for x in a["sectors_up"]))
    if a.get("sectors_down"):
        L.append("  · 领跌行业：" + "、".join(
            f"{x['name']} {x['chg']:+.2f}%" for x in a["sectors_down"]))
    L.append(f"  · 注：{a['disclaimer']}")
    return L


if __name__ == "__main__":  # pragma: no cover
    import sys
    a = fetch(offline="--offline" in sys.argv)
    print("=" * 74)
    print("ok", a["ok"], "| source", a["source"], "| session", a["session"],
          "| as_of", a["as_of"], "| reason", a["reason"])
    print("\n".join(render_astock_text(a)))
