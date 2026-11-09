# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.wool
「数字资产观察清单」—— 现只保留 BTC 一条。

文件名沿革
----------
早期本模块还包含一套交易所活动推广内容库（14 项，每日轮换深度展开），
2026-11-09 江公子要求整块删除，观察清单也收敛为仅 BTC。
文件名 wool.py 保留不改，是为了让 GitHub Contents API 推送时只需覆盖、
不需要处理「删文件」这一步；内容已与那套推广条目无关。

设计取舍
--------
* 只输出客观量：现价、24h 变动、相对 MA30 偏离、近 30 日区间分位、
  年化波动率。**不给目标价、不做买卖推荐**，是「清单」不是「推荐」。
* 价格必须当日新鲜，所以联网；失败时降级为「只列标的与观察理由」，
  如实注明行情未取到，绝不中断整份报告。
* 行情多源 fallback + 熔断在 engine/market.py，本模块只负责组装。
"""
from datetime import datetime
from typing import Dict, List, Optional

from . import market

# (交易对, 显示名, 定位, 观察理由 —— 静态，不随行情变)
WATCHLIST: List[tuple] = [
    ("BTCUSDT", "BTC", "唯一观察标的",
     "只作为加密市场的基准尺子观察：看它的波动与位置，不给买卖结论、不做价位预测。"),
]


# ---------------------------------------------------------------- 组装

def _fmt_price(p: float) -> str:
    """BTC 按量级显示整数。"""
    if p >= 1000:
        return f"{p:,.0f}"
    if p >= 10:
        return f"{p:,.2f}"
    if p >= 1:
        return f"{p:,.3f}"
    return f"{p:,.4f}"


def _row_note(row: Dict) -> str:
    """把客观量翻译成一句话状态描述。只描述，不判断方向。"""
    bits = []
    dev = row.get("ma30_dev")
    if dev is not None:
        bits.append(f"较 MA30 {'高' if dev >= 0 else '低'} {abs(dev):.1f}%")
    pos = row.get("pos30")
    if pos is not None:
        bits.append(f"处近 30 日区间 {pos:.0f}% 分位")
    v = row.get("vol")
    if v is not None:
        bits.append(f"年化波动 {v:.0f}%")
    return "，".join(bits) + "。" if bits else "日线数据未取到。"


def watch_rows(symbols: Optional[List[str]] = None,
               offline: bool = False) -> Dict:
    """取观察清单行情。失败或 offline 时降级：仍返回清单，只是没有价格。

    无论 profile 里配了什么 watchlist，本版一律收敛为 BTC ——
    这是 2026-11-09 的明确要求，避免旧配置把 ETH/SOL/BNB/XRP 带回来。
    """
    symbols = ["BTCUSDT"]
    meta = {w[0]: w for w in WATCHLIST}
    snap = ({"ok": False, "rows": {}, "ts": "", "source": "", "error": "offline"}
            if offline else market.build_watch(symbols))
    rows = []
    for s in symbols:
        sym, name, role, why = meta.get(s, (s, s, "", ""))
        q = snap.get("rows", {}).get(s)
        row = {"sym": sym, "name": name, "role": role, "why": why,
               "ok": bool(q)}
        if q:
            row.update({"price": q["price"], "chg": q["chg"],
                        "ma30_dev": q.get("ma30_dev"), "pos30": q.get("pos30"),
                        "vol": q.get("vol")})
            row["note"] = _row_note(q)
            row["price_txt"] = _fmt_price(q["price"])
        rows.append(row)
    return {"ok": snap.get("ok", False), "rows": rows,
            "ts": snap.get("ts", ""), "source": snap.get("source", ""),
            "error": snap.get("error", "")}


DISCLAIMER = ("以上为公开行情的客观量化描述，不构成投资建议；"
              "加密资产波动剧烈，可能损失全部本金。")


def build(target: datetime, cai_score: float,
          symbols: Optional[List[str]] = None,
          offline: bool = False) -> Dict:
    """组装数字资产栏目（只剩观察清单；参数保留以兼容既有调用）。"""
    try:
        watch = watch_rows(symbols, offline=offline)
    except Exception as e:                  # noqa: BLE001
        watch = {"ok": False, "rows": [
            {"sym": s, "name": nm, "role": rl, "why": why, "ok": False}
            for s, nm, rl, why in WATCHLIST], "ts": "", "source": "",
            "error": repr(e)[:120]}
    return {"watch": watch, "disclaimer": DISCLAIMER}


if __name__ == "__main__":
    b = build(datetime(2026, 11, 9, 8, 0), 60.0, offline=True)
    print(f"\n观察清单（ok={b['watch']['ok']} {b['watch'].get('error','')}）")
    for r in b["watch"]["rows"]:
        if r["ok"]:
            print(f"  {r['name']:<5} {r['price_txt']:>12}  {r['chg']:+6.2f}%  {r['note']}")
        else:
            print(f"  {r['name']:<5} 行情未取到 —— {r['why'][:30]}")
