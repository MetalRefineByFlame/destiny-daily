# -*- coding: utf-8 -*-
"""
彩票娱乐：今日可参与彩种判定 + 号码生成。

号码不是随机数，而是由当日盘面的「术数数源」加权抽出：
  日干支数 / 农历月日 / 奇门吉宫数 / 六壬三传地支 / 梅花卦先天数 / 用神河图数
再按「五行配数」（河图：1,6水 2,7火 3,8木 4,9金 5,0土）给候选号加权——
用神五行加码、忌神五行减码。抽取用固定种子，保证同一天多次运行号码一致。

定位说明：这是**娱乐**，不是预测。任何号码的中奖概率与机选完全相同。
系统的真实作用是「限额纪律」：月度预算、单日上限、超出即停。
"""
import random
from datetime import datetime
from typing import Dict, List, Optional

from .base import gz_index

# 河图五行配数（取个位；0 视为 10 属土）
HETU_WX = {1: "水", 6: "水", 2: "火", 7: "火",
           3: "木", 8: "木", 4: "金", 9: "金", 5: "土", 0: "土"}
WX_NUM = {"水": [1, 6], "火": [2, 7], "木": [3, 8], "金": [4, 9], "土": [5, 0]}

# 先天卦数：乾1 兑2 离3 震4 巽5 坎6 艮7 坤8
XIANTIAN = {"乾": 1, "兑": 2, "离": 3, "震": 4, "巽": 5, "坎": 6, "艮": 7, "坤": 8}

# 开奖日：Python weekday() Monday=0 … Sunday=6
DRAW_DAYS = {
    "双色球": {1, 3, 6},        # 周二、四、日
    "大乐透": {0, 2, 5},        # 周一、三、六
    "快乐8":  {0, 1, 2, 3, 4, 5, 6},   # 每日
}

SPEC = {
    "双色球": {"front": (33, 6), "back": (16, 1), "note": "红球 1-33 选 6，蓝球 1-16 选 1"},
    "大乐透": {"front": (35, 5), "back": (12, 2), "note": "前区 1-35 选 5，后区 1-12 选 2"},
    "快乐8":  {"front": (80, 10), "back": None, "note": "1-80 选 10（选十玩法）"},
}

# 彩种量级：大盘彩种(双色球/大乐透)头奖概率极低、需要更强的彩气支撑；
# 快乐8 玩法灵活、单注金额可控，作为弱彩气日的唯一选择。
BIG_GAMES = ("双色球", "大乐透")
SMALL_GAME = "快乐8"

# 决定「今日彩气」的权重：五门加权总分为主锚，财气十神修正为辅
W_FIVE_TOTAL = 0.62
W_CAI_ADJ = 0.38

# 低于此分直接给「今日不建议购买」，不出号码
DEFAULT_SKIP_THRESHOLD = 50.0


def wx_of(n: int) -> str:
    return HETU_WX.get(n % 10, "土")


def _pick(pool: List[int], weights: Dict[int, float], k: int, rng: random.Random) -> List[int]:
    """按权重无放回抽取 k 个，返回升序"""
    p = list(pool)
    w = [max(0.02, weights.get(n, 1.0)) for n in p]
    out: List[int] = []
    for _ in range(min(k, len(p))):
        tot = sum(w)
        r = rng.random() * tot
        acc = 0.0
        idx = len(w) - 1
        for i, wi in enumerate(w):
            acc += wi
            if r <= acc:
                idx = i
                break
        out.append(p[idx])
        p.pop(idx)
        w.pop(idx)
    return sorted(out)


def number_sources(ctx) -> List[int]:
    """从当日盘面采集数源（用于加权与说明）"""
    lr_day = ctx["lr_day"]
    lr = ctx["lr"]
    mh = ctx["mh"]
    qm = ctx["qm_day"]
    bz = ctx["bz"]
    lu = ctx["lu"]

    src: List[int] = []
    dg = gz_index(lr_day["gz"])
    src += [dg % 10 or 10, dg % 12 or 12]      # 日干数、日支数
    src += [lu.month, lu.day]                   # 农历月、日
    # 奇门：取全日 quality 最髙时辰的吉宫（洛书宫号 1-9）
    try:
        best_h = max(qm["hours"], key=lambda x: x["quality"])
        src.append(int(best_h["best"][0]))
    except Exception:      # noqa: BLE001
        pass
    src += [(c % 12) + 1 for c in lr.chuan]     # 六壬三传地支
    src += [mh.upper + 1, mh.lower + 1]         # 梅花本卦上下卦先天数
    for w in (bz.yong_shen_wx or [])[:2]:       # 用神河图数
        src += WX_NUM.get(w, [])
    return [s for s in src if s]


def build_weights(hi: int, src: List[int], yong: List[str], ji: List[str]) -> Dict[int, float]:
    w: Dict[int, float] = {}
    for n in range(1, hi + 1):
        v = 1.0
        x = wx_of(n)
        if x in yong:
            v *= 2.2
        elif x in (ji or []):
            v *= 0.6
        for s in src:
            if n == s:
                v += 1.5
            elif abs(n - s) <= 2:
                v += 0.8
            elif n % 10 == s % 10:
                v += 0.6
        w[n] = v
    return w


def gen_numbers(ctx, game: str) -> Dict:
    spec = SPEC[game]
    src = number_sources(ctx)
    bz = ctx["bz"]
    yong = list(bz.yong_shen_wx or [])[:2]
    ji = list(bz.ji_shen_wx or [])
    seed = ctx["target"].toordinal() * 7919 + sum(src) * 31
    rng = random.Random(seed)

    front_hi, front_k = spec["front"]
    wf = build_weights(front_hi, src, yong, ji)
    front = _pick(list(range(1, front_hi + 1)), wf, front_k, rng)

    back = []
    if spec["back"]:
        back_hi, back_k = spec["back"]
        wb = build_weights(back_hi, src, yong, ji)
        back = _pick(list(range(1, back_hi + 1)), wb, back_k, rng)

    return {"front": front, "back": back, "note": spec["note"], "src": src}


def cai_adj(ten_god: str) -> float:
    """流日十神对彩气的修正量（相对 50 中值的偏移）"""
    return {
        "偏财": 18.0, "正财": 12.0,          # 财星当令，横财之象
        "食神": 5.0, "伤官": 3.0,            # 食伤生财
        "比肩": 0.0, "劫财": -4.0,           # 比劫夺财
        "正印": -6.0, "偏印": -6.0,          # 印星克食伤，财源被制
        "七杀": -14.0, "正官": -12.0,        # 官杀克身，主破耗
    }.get(ten_god, 0.0)


def lottery_score(five_total: float, ten_god: str) -> float:
    """
    今日彩气分 = 五门加权总分(主锚) + 财气十神修正(辅助)。
    五门总分为校准后的分布值（μ≈50 σ≈13），故 50 即"中性"。
    """
    raw = five_total * W_FIVE_TOTAL + (50.0 + cai_adj(ten_god)) * W_CAI_ADJ
    return round(max(5.0, min(96.0, raw)), 1)


def pick_one_game(target: datetime, score: float, skip_at: float) -> Dict:
    """
    同一天只选一个彩种。
    规则：
      1) score < skip_at  -> 不出号码，直接「今日不建议购买」
      2) 彩气偏强(>=64) 且当日有大盘彩种开奖 -> 取大盘彩种（搏一等奖需气盛）
      3) 否则 -> 取快乐8（每日开奖、玩法灵活、单注可控）
    返回的 always 字段含未选中彩种的原因，便于报告说明。
    """
    wd = target.weekday()
    open_games = [g for g, days in DRAW_DAYS.items() if wd in days]

    if score < skip_at:
        return {"game": None, "skip": True, "score": score, "open_games": open_games}

    big = [g for g in BIG_GAMES if g in open_games]
    chosen = big[0] if (score >= 64 and big) else SMALL_GAME
    if chosen not in open_games:          # 兜底
        chosen = open_games[0] if open_games else None
    if chosen is None:
        return {"game": None, "skip": True, "score": score, "open_games": []}

    reason = ("彩气偏强，取大盘彩种搏高奖池" if chosen in BIG_GAMES
              else "彩气中性，取快乐8 玩法灵活、单注可控")
    return {"game": chosen, "skip": False, "score": score,
            "open_games": open_games, "reason": reason}


def lottery_block(ctx, five_total: float, ten_god: str,
                  budget: int = 100, skip_at: float = DEFAULT_SKIP_THRESHOLD,
                  one_game: bool = True) -> Dict:
    score = lottery_score(five_total, ten_god)
    decision = pick_one_game(ctx["target"], score, skip_at)
    daily_cap = max(2, budget // 20)

    picks: List[Dict] = []
    if not decision["skip"]:
        n = gen_numbers(ctx, decision["game"])
        picks.append({
            "game": decision["game"],
            "draw_today": True,
            "spec": SPEC[decision["game"]]["note"],
            "reason": decision["reason"],
            "score": score,
            **n,
        })

    lt = 4 if score >= 76 else 3 if score >= 64 else 2 if score >= 50 else 1 if score >= 41 else 0
    return {
        "score": score,
        "skip": decision["skip"],
        "skip_threshold": skip_at,
        "chosen": decision["game"],
        "chosen_reason": decision.get("reason", ""),
        "open_games": decision["open_games"],
        "level": ["极弱", "偏弱", "一般", "尚可", "较旺"][lt],
        "picks": picks,
        "daily_cap": daily_cap,
        "budget": budget,
        "one_game_per_day": one_game,
        "disclaimer": "号码由当日盘面数源加权生成，属娱乐玩法，中奖概率与机选完全相同，"
                      "不构成任何收益预期。月度预算 ¥%d，单日上限 ¥%d，超出即停。" % (budget, daily_cap),
    }
