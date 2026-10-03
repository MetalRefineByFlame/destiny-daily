# -*- coding: utf-8 -*-
"""
观察清单的行情抓取：多源 fallback。

**为什么要多源？**
单一数据源在这个场景里不可靠：
- 币安（api.binance.com / data-api.binance.vision）**屏蔽美国 IP**，
  而每日报告跑在 GitHub Actions（美国机房）上 —— 实测抓不到。
- 国内网络又访问不到 CoinGecko / Coinbase。
两边各有各的盲区，所以按「CoinGecko → Coinbase → 币安」依次尝试，
任一源成功即返回；全挂则优雅降级（报告保留清单与观察理由，注明行情未取到）。

设计原则
--------
1. **联网失败绝不中断报告**。行情只是这一栏的补充，抓不到就降级。
2. **只输出客观事实，不做价位预测**。现价、24h 变动、相对 MA30 偏离、
   近 30 日区间分位、年化波动率都是事实；「目标价」「还会涨吗」不给。
3. **熔断**：某个源试穿后在本轮内直接跳过，避免 N 标的 × M 源 × 重试 的空等。
"""
import json
import os
import time
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional

TIMEOUT = 8

# 每个源的熔断状态：试穿一次后本轮内不再重试
_DOWN: Dict[str, bool] = {}

_CACHE: Dict = {"ts": 0.0, "data": None}
CACHE_TTL = 300     # 秒。批量生成多天报告时避免重复联网

# ---------------------------------------------------------------- 标的映射

GECKO_IDS = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "XRPUSDT": "ripple",
}
# Coinbase 无 BNB 现货；缺失的标的该源直接跳过
COINBASE_PAIRS = {
    "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD", "SOLUSDT": "SOL-USD",
    "XRPUSDT": "XRP-USD",
}


def reset_breaker() -> None:
    """测试用：清掉熔断状态与缓存。"""
    _DOWN.clear()
    _CACHE["ts"], _CACHE["data"] = 0.0, None


def _down(name: str) -> bool:
    return _DOWN.get(name, False)


def _mark_down(name: str) -> None:
    _DOWN[name] = True


def _get_json(url: str, headers: Optional[Dict] = None, timeout: int = TIMEOUT):
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _try(name: str, fn):
    """执行某源的一次抓取；失败则熔断该源。"""
    if _down(name):
        raise RuntimeError(f"{name} 已熔断")
    try:
        return fn()
    except Exception as e:                  # noqa: BLE001
        _mark_down(name)
        raise RuntimeError(f"{name} 不可达：{repr(e)[:80]}") from e


def _gecko_headers() -> Dict:
    k = os.environ.get("COINGECKO_KEY", "").strip()
    return {"x-cg-demo-api-key": k} if k else {}


def _vol(closes: List[float]) -> float:
    """近 30 日日收益标准差的年化（百分数）。"""
    rets = [(closes[i] / closes[i - 1] - 1)
            for i in range(max(1, len(closes) - 30), len(closes))]
    if not rets:
        return 0.0
    mu = sum(rets) / len(rets)
    return (sum((x - mu) ** 2 for x in rets) / len(rets)) ** 0.5 * (365 ** 0.5) * 100


def _stats_from_series(closes: List[float]) -> Optional[Dict]:
    if len(closes) < 8:
        return None
    win = closes[-30:] if len(closes) >= 30 else closes
    return {"ma30": sum(win) / len(win), "hi30": max(win), "lo30": min(win),
            "vol30d_annual": _vol(closes)}


# ---------------------------------------------------------------- 各源实现

def gecko_prices(symbols: List[str]) -> Dict[str, Dict]:
    """一次请求拿全部标的的现价与 24h 变动。"""
    ids = ",".join(GECKO_IDS[s] for s in symbols if s in GECKO_IDS)
    if not ids:
        return {}
    url = ("https://api.coingecko.com/api/v3/coins/markets"
           f"?vs_currency=usd&ids={ids}&price_change_percentage=24h")
    arr = _try("coingecko", lambda: _get_json(url, _gecko_headers()))
    rev = {v: k for k, v in GECKO_IDS.items()}
    out = {}
    for c in arr if isinstance(arr, list) else []:
        sym = rev.get(c.get("id"))
        if not sym:
            continue
        try:
            out[sym] = {
                "price": float(c["current_price"]),
                "chg": float(c.get("price_change_percentage_24h") or 0.0),
                "high": float(c.get("high_24h") or c["current_price"]),
                "low": float(c.get("low_24h") or c["current_price"]),
            }
        except (TypeError, ValueError, KeyError):
            continue
    return out


def gecko_series(sym: str) -> Optional[Dict]:
    gid = GECKO_IDS.get(sym)
    if not gid:
        return None
    url = (f"https://api.coingecko.com/api/v3/coins/{gid}/market_chart"
           "?vs_currency=usd&days=30&interval=daily")
    d = _try("coingecko", lambda: _get_json(url, _gecko_headers()))
    closes = [float(p[1]) for p in d.get("prices", []) if len(p) >= 2]
    return _stats_from_series(closes)


def coinbase_prices(symbols: List[str]) -> Dict[str, Dict]:
    """逐个标的取 24h 统计（Coinbase 无批量接口）。"""
    out = {}
    for s in symbols:
        pair = COINBASE_PAIRS.get(s)
        if not pair:
            continue
        try:
            d = _try("coinbase", lambda: _get_json(
                f"https://api.exchange.coinbase.com/products/{pair}/stats"))
            last, op = float(d["last"]), float(d.get("open") or d["last"])
            out[s] = {
                "price": last,
                "chg": (last - op) / op * 100 if op else 0.0,
                "high": float(d.get("high") or last),
                "low": float(d.get("low") or last),
            }
        except Exception:                   # noqa: BLE001
            continue
    return out


def coinbase_series(sym: str) -> Optional[Dict]:
    pair = COINBASE_PAIRS.get(sym)
    if not pair:
        return None
    d = _try("coinbase", lambda: _get_json(
        f"https://api.exchange.coinbase.com/products/{pair}/candles"
        "?granularity=86400"))
    if not isinstance(d, list) or not d:
        return None
    # 返回按时间倒序：[time, low, high, open, close, volume]
    rows = sorted((r for r in d if len(r) >= 5), key=lambda r: r[0])
    closes = [float(r[4]) for r in rows]
    return _stats_from_series(closes)


BINANCE_BASES = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
]


def binance_prices(symbols: List[str]) -> Dict[str, Dict]:
    """币安全市场 24h 快照（一次请求）。美国 IP 通常被拒，故排在最后。"""
    want = set(symbols)
    out: Dict[str, Dict] = {}

    def go():
        arr = None
        last = None
        for base in BINANCE_BASES:
            try:
                arr = _get_json(base + "/api/v3/ticker/24hr")
                break
            except Exception as e:          # noqa: BLE001
                last = e
        if arr is None:
            raise last or RuntimeError("no binance source")
        for t in arr if isinstance(arr, list) else []:
            s = t.get("symbol")
            if s in want:
                try:
                    out[s] = {"price": float(t["lastPrice"]),
                              "chg": float(t["priceChangePercent"]),
                              "high": float(t["highPrice"]),
                              "low": float(t["lowPrice"])}
                except (TypeError, ValueError, KeyError):
                    continue
        return out

    try:
        return _try("binance", go)
    except Exception:                       # noqa: BLE001
        return {}


def binance_series(sym: str) -> Optional[Dict]:
    def go():
        last = None
        for base in BINANCE_BASES:
            try:
                k = _get_json(
                    base + f"/api/v3/klines?symbol={sym}&interval=1d&limit=31")
                return [float(x[4]) for x in k]
            except Exception as e:          # noqa: BLE001
                last = e
        raise last or RuntimeError("no binance source")
    try:
        return _stats_from_series(_try("binance", go))
    except Exception:                       # noqa: BLE001
        return None


# ---------------------------------------------------------------- 组装

PRICE_SRC = [("coingecko", gecko_prices), ("coinbase", coinbase_prices),
             ("binance", binance_prices)]
SERIES_SRC = [("coingecko", gecko_series), ("coinbase", coinbase_series),
              ("binance", binance_series)]


def build_watch(symbols: List[str], use_cache: bool = True) -> Dict:
    """
    组装观察清单行。返回 {ok, rows, ts, source, error}。

    rows[sym] = {price, chg, high24h, low24h, ma30, hi30, lo30,
                 ma30_dev, pos30, vol}
    全为客观量，不含方向性判断。抓取失败时 rows 为空，由上层降级处理。
    """
    now = time.time()
    if use_cache and _CACHE["data"] is not None and now - _CACHE["ts"] < CACHE_TTL:
        if set(symbols) <= set(_CACHE["data"].get("rows", {})):
            return _CACHE["data"]

    used = []
    tickers: Dict[str, Dict] = {}
    for name, fn in PRICE_SRC:
        try:
            tickers = fn(symbols)
        except Exception:                   # noqa: BLE001
            tickers = {}
        if tickers:
            used.append(name)
            break
    if not tickers:
        res = {"ok": False, "rows": {}, "ts": "", "source": "",
               "error": "所有行情源均不可达"}
        _CACHE["ts"], _CACHE["data"] = now, res
        return res

    series_src = None
    rows: Dict[str, Dict] = {}
    for s in symbols:
        t = tickers.get(s)
        if not t:
            continue
        st = None
        for name, fn in SERIES_SRC:
            try:
                st = fn(s)
            except Exception:               # noqa: BLE001
                st = None
            if st:
                series_src = name
                break
        row = {"sym": s, "price": t["price"], "chg": t["chg"],
               "high24h": t["high"], "low24h": t["low"]}
        if st:
            p = t["price"]
            row.update({"ma30": st["ma30"], "hi30": st["hi30"],
                        "lo30": st["lo30"], "vol": st["vol30d_annual"]})
            row["ma30_dev"] = ((p - st["ma30"]) / st["ma30"] * 100) if st["ma30"] else None
            span = st["hi30"] - st["lo30"]
            row["pos30"] = ((p - st["lo30"]) / span * 100) if span > 0 else None
        rows[s] = row

    res = {"ok": bool(rows), "rows": rows,
           "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "source": "+".join(used + ([series_src] if series_src else [])),
           "error": "" if rows else "日线数据未取到"}
    _CACHE["ts"], _CACHE["data"] = now, res
    return res


if __name__ == "__main__":
    SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    w = build_watch(SYMS)
    print("ok =", w["ok"], "| 源:", w.get("source") or "-", "|", w.get("error", ""))
    for s in SYMS:
        v = w.get("rows", {}).get(s)
        if not v:
            print(f"  {s:<9} 未取到")
            continue
        dev = v.get("ma30_dev")
        pos = v.get("pos30")
        print(f"  {s:<9} {v['price']:>12,.2f}  {v['chg']:+6.2f}%  "
              f"MA30偏离 {'-' if dev is None else format(dev, '+.1f')}%  "
              f"30日分位 {'-' if pos is None else format(pos, '.0f')}%")
