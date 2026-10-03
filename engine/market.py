# -*- coding: utf-8 -*-
"""
币安公开行情抓取：观察清单用。

数据源：币安公开数据镜像 https://data-api.binance.vision （无需 API Key）。
主站 api.binance.com 在部分网络下不可达，故用此镜像并保留多个备用。

设计原则
--------
1. **联网失败必须优雅降级**。每日 08:00 的定时任务不该因为行情接口抖动而中断整份报告，
   抓不到数据时返回 ok=False，报告保留清单本身（名称 + 观察理由）并标注「行情未取到」。
2. **只输出客观事实，不做价位预测**。现价、24h 变动、相对均线偏离、区间分位、波动率是事实；
   「目标价」「涨到多少」不是本系统能给出的，也不给。
3. 不做技术面解读与买卖倾向 —— 这是「清单」而非「推荐」。
"""
import json
import time
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional

FALLBACKS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]
TIMEOUT = 6

_CACHE: Dict = {"ts": 0.0, "data": None}
CACHE_TTL = 300     # 秒。批量生成多天报告时避免重复联网（否则 N 天 = N×symbols 次请求，极慢）

# 熔断：一旦把所有备用源都试穿，本次进程内的后续请求直接放弃，不再逐个重试。
# 否则「网络不通」场景下会出现 5 个标的 × 6 个源 × 2 次重试 × 超时 的长时间空等。
_DOWN = {"yes": False, "why": ""}


def reset_breaker() -> None:
    """测试用：清掉熔断状态与缓存。"""
    _DOWN["yes"], _DOWN["why"] = False, ""
    _CACHE["ts"], _CACHE["data"] = 0.0, None


def _get(url: str, timeout: int = TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _try_get(path: str, retries: int = 2):
    """依次尝试各数据源，每个源重试 retries 次。网络抖动常见，单次失败不代表不可用。"""
    if _DOWN["yes"]:
        raise RuntimeError(_DOWN["why"] or "行情源在本轮内已判定不可达（熔断）")
    last = None
    for base in FALLBACKS:
        for _ in range(retries):
            try:
                return _get(base + path)
            except Exception as e:      # noqa: BLE001
                last = e
    _DOWN["yes"] = True
    _DOWN["why"] = f"全部 {len(FALLBACKS)} 个行情源不可达：{repr(last)[:80]}"
    raise _DOWN["why"]


def fetch_tickers(symbols: List[str]) -> Dict[str, Dict]:
    """一次请求拿全部 24h 行情（不带 symbol 参数即返回全市场数组）。失败返回 {}。"""
    try:
        arr = _try_get("/api/v3/ticker/24hr")
    except Exception:                   # noqa: BLE001
        return {}
    want = set(symbols)
    out: Dict[str, Dict] = {}
    for t in arr if isinstance(arr, list) else []:
        s = t.get("symbol")
        if s in want:
            try:
                out[s] = {
                    "price": float(t["lastPrice"]),
                    "chg": float(t["priceChangePercent"]),
                    "high": float(t["highPrice"]),
                    "low": float(t["lowPrice"]),
                    "quote_vol": float(t.get("quoteVolume", 0)),
                }
            except (TypeError, ValueError, KeyError):
                continue
    return out


def daily_stats(symbol: str, limit: int = 31) -> Optional[Dict]:
    """日线统计：MA7 / MA30 / 近30日高低 / 年化波动率。失败返回 None。"""
    try:
        klines = _try_get(f"/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}")
    except Exception:                   # noqa: BLE001
        return None
    try:
        closes = [float(k[4]) for k in klines]
    except (TypeError, ValueError, IndexError):
        return None
    if len(closes) < 8:
        return None

    def ma(n: int) -> float:
        return sum(closes[-n:]) / n if len(closes) >= n else 0.0

    win = closes[-30:] if len(closes) >= 30 else closes
    hi, lo = max(win), min(win)
    rets = [(closes[i] / closes[i - 1] - 1)
            for i in range(max(1, len(closes) - 30), len(closes))]
    mu = sum(rets) / len(rets) if rets else 0.0
    vol = (sum((x - mu) ** 2 for x in rets) / len(rets)) ** 0.5 if rets else 0.0
    return {
        "ma7": ma(7),
        "ma30": ma(30),
        "hi30": hi,
        "lo30": lo,
        "vol30d_annual": vol * (365 ** 0.5) * 100,
        "closes": closes[-10:],
    }


def build_watch(symbols: List[str], use_cache: bool = True) -> Dict:
    """
    组装观察清单行。返回 {ok, rows, ts, error}。

    rows 每行 = {sym, price, chg, ma30_dev, pos30, vol, ma7, ma30, hi30, lo30}
    全部为客观量，不含任何方向性判断。
    """
    now = time.time()
    if use_cache and _CACHE["data"] is not None and now - _CACHE["ts"] < CACHE_TTL:
        if set(symbols) <= set(_CACHE["data"].get("rows", {})):
            return _CACHE["data"]

    tickers = fetch_tickers(symbols)
    if not tickers:
        res = {"ok": False, "rows": {}, "ts": "", "error": "行情接口不可达"}
        _CACHE["ts"], _CACHE["data"] = now, res
        return res

    rows: Dict[str, Dict] = {}
    for s in symbols:
        st = daily_stats(s)
        t = tickers.get(s)
        if not t:
            continue
        row = {"sym": s, "price": t["price"], "chg": t["chg"],
               "high24h": t["high"], "low24h": t["low"]}
        if st:
            p = t["price"]
            row["ma7"] = st["ma7"]
            row["ma30"] = st["ma30"]
            row["hi30"] = st["hi30"]
            row["lo30"] = st["lo30"]
            row["vol"] = st["vol30d_annual"]
            row["ma30_dev"] = ((p - st["ma30"]) / st["ma30"] * 100) if st["ma30"] else None
            span = st["hi30"] - st["lo30"]
            row["pos30"] = ((p - st["lo30"]) / span * 100) if span > 0 else None
        rows[s] = row

    res = {"ok": bool(rows), "rows": rows,
           "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "error": "" if rows else "日线数据未取到"}
    _CACHE["ts"], _CACHE["data"] = now, res
    return res


if __name__ == "__main__":
    w = build_watch(["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"])
    print("ok =", w["ok"], w.get("ts", ""), w.get("error", ""))
    for k, v in w.get("rows", {}).items():
        print(f"  {k:<9} {v['price']:>12,.2f}  {v['chg']:+6.2f}%  "
              f"MA30偏离 {v.get('ma30_dev') if v.get('ma30_dev') is None else round(v['ma30_dev'],1)}%  "
              f"30日分位 {'-' if v.get('pos30') is None else round(v['pos30'])}%")
