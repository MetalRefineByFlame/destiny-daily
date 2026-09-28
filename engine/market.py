# -*- coding: utf-8 -*-
"""
BTC 行情快照与技术面复盘。

数据源：币安公开数据镜像 https://data-api.binance.vision （无需 API Key）。
主站 api.binance.com 与 CoinGecko / OKX 在部分网络下不可达，故用此镜像并保留多个备用。

设计原则
--------
1. **联网失败必须优雅降级**。每日 08:00 的定时任务不该因为行情接口抖动而中断整份报告，
   抓不到数据时返回 ok=False，报告只保留术数视角并明确标注「行情未取到」。
2. **只做客观技术面描述，不做价位预测**。均线排列、振幅、相对位置是事实；
   「目标价」「涨到多少」不是本系统能给出的，也不给。
3. 术数倾向只作为「文化视角的附加注脚」，与技术面分列，不混为一谈。
"""
import json
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional

BASE = "https://data-api.binance.vision"
FALLBACKS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
]
TIMEOUT = 8


def _get(url: str, timeout: int = TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _try_get(path: str, retries: int = 2):
    """依次尝试各数据源，每个源重试 retries 次。网络抖动常见，单次失败不代表不可用。"""
    last = None
    for base in FALLBACKS:
        for _ in range(retries):
            try:
                return _get(base + path)
            except Exception as e:      # noqa: BLE001
                last = e
    raise last if last else RuntimeError("no source")


_CACHE: Dict = {"ts": 0.0, "data": None}
CACHE_TTL = 300     # 秒。批量生成多天报告时避免重复联网（否则 N 天 = 2N 次请求，极慢）


def fetch_snapshot(symbol: str = "BTCUSDT", use_cache: bool = True) -> Dict:
    """抓取当前价、24h 变动与日线均线。失败返回 {'ok': False}。"""
    import time
    now = time.time()
    if use_cache and _CACHE["data"] is not None and now - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["data"]
    try:
        ticker = _try_get(f"/api/v3/ticker/24hr?symbol={symbol}")
        klines = _try_get(f"/api/v3/klines?symbol={symbol}&interval=1d&limit=61")
    except Exception as e:          # noqa: BLE001
        # 失败也短暂缓存，避免批量生成时反复等待超时
        _CACHE["ts"] = now
        _CACHE["data"] = {"ok": False, "error": repr(e)[:120]}
        return _CACHE["data"]

    price = float(ticker["lastPrice"])
    chg = float(ticker["priceChangePercent"])
    high = float(ticker["highPrice"])
    low = float(ticker["lowPrice"])
    closes = [float(k[4]) for k in klines]

    def ma(n: int) -> float:
        return sum(closes[-n:]) / n if len(closes) >= n else 0.0

    ma7, ma30, ma60 = ma(7), ma(30), ma(60)
    # 年化波动率：用近 30 日日收益标准差粗估
    rets = [(closes[i] / closes[i - 1] - 1) for i in range(len(closes) - 30, len(closes))]
    mu = sum(rets) / len(rets)
    vol = (sum((x - mu) ** 2 for x in rets) / len(rets)) ** 0.5
    _CACHE["ts"] = now
    _CACHE["data"] = {
        "ok": True,
        "symbol": symbol,
        "price": price,
        "chg24h": chg,
        "high24h": high,
        "low24h": low,
        "ma7": ma7, "ma30": ma30, "ma60": ma60,
        "amp24h": (high - low) / low * 100 if low else 0.0,
        "vol30d_annual": vol * (365 ** 0.5) * 100,
        "closes": closes[-10:],
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    return _CACHE["data"]


def review(snap: Dict, cai_score: float, yong_wx: str = "水") -> Dict:
    """生成复盘文案。snap['ok'] 为 False 时降级为纯术数版本。"""
    if not snap.get("ok"):
        return {
            "ok": False,
            "headline": "行情未取到（接口不可达）",
            "lines": [
                f"BTC 行情快照获取失败：{snap.get('error', '未知原因')}",
                "本条不影响其余板块；如需复盘请检查网络或稍后手动刷新。",
                f"术数视角：今日财气 {cai_score:.0f}，用神属「{yong_wx}」，"
                "仅作文化参考，不构成任何操作依据。",
            ],
            "trend": "未知",
        }

    p = snap["price"]
    ma7, ma30, ma60 = snap["ma7"], snap["ma30"], snap["ma60"]

    # --- 客观技术状态 ---
    if ma7 > ma30 > ma60:
        trend = "多头排列"
    elif ma7 < ma30 < ma60:
        trend = "空头排列"
    else:
        trend = "均线纠缠"

    pos = []
    for name, m in (("MA7", ma7), ("MA30", ma30), ("MA60", ma60)):
        if m:
            d = (p - m) / m * 100
            pos.append(f"{name} {'上方' if d >= 0 else '下方'} {abs(d):.1f}%")

    lines: List[str] = [
        f"BTC/USDT 现价 {p:,.0f}（24h {snap['chg24h']:+.2f}%），"
        f"24h 区间 {snap['low24h']:,.0f} ~ {snap['high24h']:,.0f}，振幅 {snap['amp24h']:.1f}%。",
        f"均线：MA7 {ma7:,.0f} / MA30 {ma30:,.0f} / MA60 {ma60:,.0f} —— {trend}。",
        "价格位置：" + "，".join(pos) + "。",
    ]

    # --- 结构解读（描述性，非预测） ---
    if trend == "多头排列" and p > ma30:
        read = "中期结构偏强，短期回调只要不破 MA30，结构本身未坏。"
    elif trend == "空头排列" and p < ma30:
        read = "中期结构偏弱，反弹至 MA30 附近易遇压，不宜视作趋势反转。"
    elif p > ma30:
        read = "价格仍在 MA30 上方，但均线未形成有序排列，属震荡偏强、方向未定。"
    else:
        read = "价格位于 MA30 下方，中期偏弱，宜等结构修复而非抢反弹。"
    lines.append(read)

    lines.append(
        f"近 30 日年化波动率约 {snap['vol30d_annual']:.0f}%"
        + ("——处于高波动区间，仓位应按最坏情形设定。" if snap["vol30d_annual"] > 60
           else "——波动温和，但仍高于绝大多数传统资产。")
    )

    # --- 术数视角（明确分列） ---
    t = 4 if cai_score >= 76 else 3 if cai_score >= 64 else 2 if cai_score >= 50 else 1 if cai_score >= 41 else 0
    shu = ["极弱", "偏弱", "一般", "尚可", "较旺"][t]
    lines.append(
        f"术数视角（文化参考，非操作依据）：今日财气{shu}（{cai_score:.0f}），用神属「{yong_wx}」。"
        "此栏只描述传统象义倾向，与上面的技术面互不印证、不可互相替代。"
    )
    lines.append(
        "纪律：单一标的 ≤ 总资金 15%，单笔亏损止损 ≤ 账户 2.5%；"
        "不加杠杆、不碰合约；任何决策以你自己的判断为准。"
    )

    return {
        "ok": True,
        "headline": f"BTC {p:,.0f}（24h {snap['chg24h']:+.2f}%）· {trend}",
        "lines": lines,
        "trend": trend,
        "price": p,
        "chg24h": snap["chg24h"],
    }


if __name__ == "__main__":
    s = fetch_snapshot()
    r = review(s, 60.0, "水")
    print(r["headline"])
    for x in r["lines"]:
        print("  ", x)
