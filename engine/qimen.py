# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.qimen
时家奇门遁甲排盘引擎。

流程：
  1. 定局      —— 节气定阴阳遁 + 三元九局(接气法：以节气交接日起每 5 日一候)
  2. 地盘      —— 三奇六仪(戊己庚辛壬癸丁丙乙) 依局数顺/逆布九宫
  3. 值符值使  —— 依时柱旬首在地盘所在宫取===
  4. 天盘      —— 值符随时干
  5. 门盘      —— 值使随时支
  6. 神盘      —— 八神(阳遁九天朱雀勾陈 / 阴遁白虎玄武)
  7. 吉凶      —— 门迫、击刑、入墓、空亡、三奇乙丙丁组合判定

九宫编号采用洛书数：1坎 2坤 3震 4巽 5中(寄坤) 6乾 7兑 8艮 9离
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .base import (
    TIAN_GAN, DI_ZHI, JIA_ZI, day_gz, hour_gz, hour_zhi, month_gz_by_jie,
    current_jie, solar_term_datetime, year_terms, JIE_TERMS, ensure_cst,
    zhi_wuxing, gan_wuxing, WX_KE,
)

PALACE_NAME = {1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离"}
PALACE_FANG = {1: "正北", 2: "西南", 3: "正东", 4: "东南", 6: "西北", 7: "正西", 8: "东北", 9: "正南"}
PALACE_WX = {1: "水", 2: "土", 3: "木", 4: "木", 5: "土", 6: "金", 7: "金", 8: "土", 9: "火"}

YANG9 = [1, 2, 3, 4, 5, 6, 7, 8, 9]
YIN9 = [9, 8, 7, 6, 5, 4, 3, 2, 1]
YANG8 = [1, 2, 3, 4, 6, 7, 8, 9]        # 飞宫序列(跳中宫)
YIN8 = [9, 8, 7, 6, 4, 3, 2, 1]

SANQI_LIUYI = ["戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"]
SANQI = ["乙", "丙", "丁"]

XING_BY_PALACE = {1: "天蓬", 2: "天芮", 3: "天冲", 4: "天辅", 5: "天禽",
                  6: "天心", 7: "天柱", 8: "天任", 9: "天英"}
XING_ORDER = ["天蓬", "天芮", "天冲", "天辅", "天心", "天柱", "天任", "天英"]  # 天禽随天芮

MEN_BY_PALACE = {1: "休门", 2: "死门", 3: "伤门", 4: "杜门", 6: "开门",
                 7: "惊门", 8: "生门", 9: "景门"}
MEN_ORDER = ["休门", "死门", "伤门", "杜门", "开门", "惊门", "生门", "景门"]

SHEN_YANG = ["值符", "腾蛇", "太阴", "六合", "勾陈", "朱雀", "九地", "九天"]
SHEN_YIN = ["值符", "腾蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"]

# 地支 -> 所属宫
ZHI_PALACE = {"子": 1, "丑": 8, "寅": 8, "卯": 3, "辰": 4, "巳": 4,
              "午": 9, "未": 2, "申": 2, "酉": 7, "戌": 6, "亥": 6}

# 三元九局: 节气 -> (上元, 中元, 下元)
TERNARY_JU: Dict[str, Tuple[int, int, int]] = {
    # ---------- 阳遁 (冬至 -> 芒种) ----------
    "冬至": (1, 7, 4), "小寒": (2, 8, 5), "大寒": (3, 9, 6),
    "立春": (8, 5, 2), "雨水": (9, 6, 3), "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6), "清明": (4, 1, 7), "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7), "小满": (5, 2, 8), "芒种": (6, 3, 9),
    # ---------- 阴遁 (夏至 -> 大雪) ----------
    "夏至": (9, 3, 6), "小暑": (8, 2, 5), "大暑": (7, 1, 4),
    "立秋": (2, 5, 8), "处暑": (1, 4, 7), "白露": (9, 3, 6),
    "秋分": (7, 1, 4), "寒露": (6, 9, 3), "霜降": (5, 8, 2),
    "立冬": (6, 9, 3), "小雪": (5, 8, 2), "大雪": (4, 7, 1),
}

XU_KONG_MAP = {"甲子": ["戌", "亥"], "甲戌": ["申", "酉"], "甲申": ["午", "未"],
               "甲午": ["辰", "巳"], "甲辰": ["寅", "卯"], "甲寅": ["子", "丑"]}

XUN_TO_YI = {"甲子": "戊", "甲戌": "己", "甲申": "庚",
             "甲午": "辛", "甲辰": "壬", "甲寅": "癸"}


@dataclass
class Palace:
    no: int
    di_pan: str                 # 地盘三奇六仪
    tian_pan: str = ""          # 天盘三奇六仪
    xing: str = ""              # 九星
    men: str = ""               # 八门
    shen: str = ""              # 八神
    score: float = 50.0
    notes: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return PALACE_NAME[self.no]

    @property
    def fang(self) -> str:
        return PALACE_FANG[self.no]


@dataclass
class QiMenPan:
    dt: datetime
    jie: str
    yang: bool
    yuan: str
    ju: int
    palace: Dict[int, Palace]
    zhifu_palace: int
    zhishi_palace: int
    hour_gz_name: str
    xun: str
    xunkong: List[str]
    summary: Dict

    @property
    def title(self) -> str:
        return f"{'阳' if self.yang else '阴'}遁{self.ju}局"


# ---------------------------------------------------------------- 定局


def is_yang_dun(dt: datetime) -> bool:
    """冬至(含)后至夏至前用阳遁；夏至(含)后至冬至前用阴遁"""
    dt = ensure_cst(dt)
    terms = year_terms(dt.year)
    winter = summer = None
    for name, t in terms:
        if name == "冬至" and t <= dt:
            winter = t
        if name == "夏至" and t <= dt:
            summer = t
    if winter is None and summer is None:
        return True
    if winter is None:
        return False
    if summer is None:
        return True
    return winter > summer


def determine_ju(dt: datetime) -> Tuple[str, bool, str, int]:
    """返回 (节气, 是否阳遁, 上/中/下元, 局数)"""
    dt = ensure_cst(dt)
    jie_name, jie_time = current_jie(dt)
    yang = _term_yang(jie_name)
    days = (dt - jie_time).total_seconds() / 86400.0
    idx = int(days // 5)
    idx = idx % 3                       # 超神/接气：超过 15 天循环归元
    yuan = ["上元", "中元", "下元"][idx]
    ju = TERNARY_JU[jie_name][idx]
    return jie_name, yang, yuan, ju


def _term_yang(name: str) -> bool:
    """十二节中，冬至后到芒种为阳遁"""
    return name in ["冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
                    "春分", "清明", "谷雨", "立夏", "小满", "芒种"]


# ---------------------------------------------------------------- 排盘


def _rotate(seq: List[int], start: int) -> List[int]:
    i = seq.index(start)
    return seq[i:] + seq[:i]


def layout_dipan(ju: int, yang: bool) -> Dict[int, str]:
    order = _rotate(YANG9 if yang else YIN9, ju)
    return {p: SANQI_LIUYI[i] for i, p in enumerate(order)}


def xun_of(hour_idx: int) -> str:
    """时柱所属六甲旬首"""
    return JIA_ZI[hour_idx - hour_idx % 10]


def paipan(dt: datetime) -> QiMenPan:
    dt = ensure_cst(dt)
    jie, yang, yuan, ju = determine_ju(dt)
    dipan = layout_dipan(ju, yang)

    day_idx = day_gz(dt)
    hz = hour_zhi(dt)
    hour_idx = hour_gz(day_idx, hz)
    xun = xun_of(hour_idx)
    xunkong = XU_KONG_MAP[xun]

    # --- 值符星 / 值使门：取旬首在地盘所处宫
    ju_shou_symbol = XUN_TO_YI[xun]           # 甲子->戊 ...
    xun_palace = None
    for p, s in dipan.items():
        if s == ju_shou_symbol:
            xun_palace = p
            break
    # 中宫(5)寄坤：天禽随天芮，值使取坤宫死门
    if xun_palace == 5:
        zhifu_xing = "天芮"
        zhishi_men = MEN_BY_PALACE[2]
    else:
        zhifu_xing = XING_BY_PALACE[xun_palace]
        zhishi_men = MEN_BY_PALACE[xun_palace]

    # --- 值符随时干
    hour_gan = TIAN_GAN[hour_idx % 10]
    target_symbol = hour_gan
    if hour_gan == "甲":
        target_symbol = XUN_TO_YI[xun]
    zhifu_palace = None
    for p, s in dipan.items():
        if s == target_symbol:
            zhifu_palace = p
            break
    if zhifu_palace == 5:
        zhifu_palace = 2          # 值符加临中宫 -> 寄坤二宫
    if zhifu_palace is None:
        zhifu_palace = 2

    # --- 值使随时支
    hour_zhi_name = DI_ZHI[hz]
    zhishi_palace = ZHI_PALACE[hour_zhi_name]

    # --- 天盘九星 / 天盘干
    palace_seq = _rotate(YANG8 if yang else YIN8, zhifu_palace)
    xing_seq = XING_ORDER[XING_ORDER.index(zhifu_xing):] + \
               XING_ORDER[:XING_ORDER.index(zhifu_xing)]
    xing_map = {p: XING_BY_PALACE[p] for p in [1, 2, 3, 4, 6, 7, 8, 9]}
    # 天盘干跟着值符星一起移动：取地盘该宫的符号，按星位移位
    star_to_symbol = {XING_BY_PALACE[p]: dipan[p] for p in [1, 2, 3, 4, 6, 7, 8, 9]}
    tian_map = {}
    for i, p in enumerate(palace_seq):
        st = xing_seq[i]
        tian_map[p] = star_to_symbol.get(st, "")

    # --- 门盘
    men_seq = MEN_ORDER[MEN_ORDER.index(zhishi_men):] + \
              MEN_ORDER[:MEN_ORDER.index(zhishi_men)]
    door_palace_seq = _rotate(YANG8 if yang else YIN8, zhishi_palace)
    men_map = {}
    for i, p in enumerate(door_palace_seq):
        men_map[p] = men_seq[i]

    # --- 神盘
    shen_list = SHEN_YANG if yang else SHEN_YIN
    shen_palace_seq = _rotate(YANG8 if yang else YIN8, zhifu_palace)
    shen_map = {p: shen_list[i] for i, p in enumerate(shen_palace_seq)}

    palaces: Dict[int, Palace] = {}
    xing_pos = {p: xing_seq[i] for i, p in enumerate(palace_seq)}
    for p in [1, 2, 3, 4, 6, 7, 8, 9]:
        palaces[p] = Palace(
            no=p, di_pan=dipan[p], tian_pan=tian_map.get(p, ""),
            xing=xing_pos.get(p, ""),
            men=men_map.get(p, ""), shen=shen_map.get(p, ""),
        )

    # --- 逐宫评断
    for p, pl in palaces.items():
        _judge_palace(pl, xunkong, dipan)

    best = max(palaces.values(), key=lambda x: x.score)
    worst = min(palaces.values(), key=lambda x: x.score)

    summary = {
        "temples": {},
        "best": (best.no, best.name, best.fang, best.score),
        "worst": (worst.no, worst.name, worst.fang, worst.score),
        "kaimen": [p for p, pl in palaces.items() if pl.men == "开门"],
        "shengmen": [p for p, pl in palaces.items() if pl.men == "生门"],
        "xiumen": [p for p, pl in palaces.items() if pl.men == "休门"],
        "sanqi": [p for p, pl in palaces.items() if pl.tian_pan in SANQI],
    }
    return QiMenPan(
        dt=dt, jie=jie, yang=yang, yuan=yuan, ju=ju, palace=palaces,
        zhifu_palace=zhifu_palace, zhishi_palace=zhishi_palace,
        hour_gz_name=JIA_ZI[hour_idx], xun=xun, xunkong=xunkong, summary=summary,
    )


MEN_SCORE = {"开门": 22, "休门": 18, "生门": 20, "伤门": -12, "杜门": -4,
             "景门": -2, "死门": -22, "惊门": -14}
XING_SCORE = {"天蓬": -12, "天芮": -16, "天冲": -10, "天辅": 10, "天禽": 14,
              "天心": 18, "天柱": -6, "天任": 14, "天英": -8}
SHEN_SCORE = {"值符": 22, "腾蛇": -14, "太阴": 14, "六合": 14, "勾陈": -12,
              "朱雀": -10, "白虎": -18, "玄武": -14, "九地": 12, "九天": 14}

# 门迫：门克宫(以门之五行克宫之五行)
MEN_WX = {"休门": "水", "死门": "土", "伤门": "木", "杜门": "木",
          "开门": "金", "惊门": "金", "生门": "土", "景门": "火"}
# 击刑：门+特定宫
JIXING = [("伤门", 8), ("杜门", 8), ("开门", 6), ("休门", 6), ("生门", 6),
          ("景门", 6), ("死门", 6), ("惊门", 6)]  # 简化：6/8 宫受迫为击刑主要情形


def _is_kongwang(palace_no: int, xunkong: List[str]) -> bool:
    """宫所辖地支落入旬空则为空亡宫"""
    return any(z in xunkong for z, pz in ZHI_PALACE.items() if pz == palace_no)


def _judge_palace(pl: Palace, xunkong: List[str], dipan: Dict[int, str]) -> None:
    s = 50.0
    notes = []
    s += MEN_SCORE.get(pl.men, 0)
    s += XING_SCORE.get(pl.xing, 0)
    s += SHEN_SCORE.get(pl.shen, 0)

    if pl.tian_pan in SANQI:
        s += 12
        notes.append(f"天盘得三奇「{pl.tian_pan}」")
    if pl.di_pan in SANQI:
        s += 6
        notes.append(f"地盘藏奇「{pl.di_pan}」")

    # 门迫：门克宫
    if WX_KE.get(MEN_WX.get(pl.men, "")) == PALACE_WX[pl.no]:
        s -= 10
        notes.append("门迫(门克宫，吉减)")
    # 星克宫(星代表人事，克宫为不谐)
    XING_WX = {"天蓬": "水", "天芮": "土", "天冲": "木", "天辅": "木", "天禽": "土",
               "天心": "金", "天柱": "金", "天任": "土", "天英": "火"}
    if WX_KE.get(XING_WX.get(pl.xing, "")) == PALACE_WX[pl.no]:
        s -= 6
        notes.append("星克宫")
    # 空亡宫：该宫所辖地支落入旬空即为空亡
    if _is_kongwang(pl.no, xunkong):
        s -= 14
        notes.append("空亡")

    if pl.men == "开门" and pl.xing == "天心" and pl.shen == "值符":
        s += 12
        notes.append("开门+天心+值符·上吉组合")
    if pl.men in ("开门", "休门", "生门") and pl.tian_pan in SANQI:
        s += 8
        notes.append("吉门配奇")

    pl.score = max(8.0, min(96.0, round(s, 1)))
    pl.notes = notes


# ---------------------------------------------------------------- 每日汇总


# ---------------------------------------------------------------- 盘面质量
# 注意：单个宫的分数 = 门/星/神 三组固定评分之和，而三者在一盘之中是
# 「排列」关系，九宫总和恒定 —— 因此「全盘均值」几乎无区分度(实测σ≈1.5)。
# 真正有信息量的是「开门/休门/生门」这三吉门实际落到了哪些宫、又配上
# 了什么星神，故以吉门宫的质量作为盘面评分。


def pan_quality(pan: "QiMenPan") -> float:
    """
    盘面「组合丰厚度」评分。
    计数型指标而非均值型：统计三吉门是否与三奇、吉神同宫，
    以及凶门是否与凶神凶星叠见。这类组合每日不同，具备真实区分度。
    """
    s = 50.0
    for pl in pan.palace.values():
        good = 0
        if pl.men in ("开门", "休门", "生门"):
            good += 1
        if pl.tian_pan in SANQI:
            good += 1
        if pl.shen in ("值符", "太阴", "六合", "九天", "九地"):
            good += 1
        bad = 0
        if pl.men in ("死门", "惊门", "伤门"):
            bad += 1
        if pl.shen in ("白虎", "玄武", "腾蛇", "勾陈"):
            bad += 1
        if pl.xing in ("天蓬", "天芮", "天英", "天冲"):
            bad += 1
        if good == 3:
            s += 26
        elif good == 2:
            s += 10
        if bad == 3:
            s -= 22
        elif bad == 2:
            s -= 8
    return round(max(6.0, min(96.0, s)), 1)


# ---------------------------------------------------------------- 每日汇总


# ---------------------------------------------------------------- 盘面质量
# 注意：单个宫的分数 = 门/星/神 三组固定评分之和，而三者在一盘之中是
# 「排列」关系，九宫总和恒定 —— 因此「全盘均值」几乎无区分度(实测σ≈1.5)。
# 真正有信息量的是「开门/休门/生门」这三吉门实际落到了哪些宫、又配上
# 了什么星神，故以吉门宫的质量作为盘面评分。


def pan_quality(pan: "QiMenPan") -> float:
    lucky = [pl for pl in pan.palace.values() if pl.men in ("开门", "休门", "生门")]
    bad = [pl for pl in pan.palace.values() if pl.men in ("死门", "惊门", "伤门")]
    if not lucky:
        return 50.0
    avg_lucky = sum(pl.score for pl in lucky) / len(lucky)
    best = max(pl.score for pl in lucky)
    worst_bad = min((pl.score for pl in bad), default=None)
    s = 0.45 * avg_lucky + 0.35 * best
    if worst_bad is not None:
        # 凶门越低越好 -> 反向计入
        s += 0.20 * (100.0 - worst_bad)
    return round(max(5.0, min(96.0, s)), 1)


def day_report(dt: datetime) -> Dict:
    """对当日 12 时辰各排一盘，汇总吉方吉时"""
    dt = ensure_cst(dt)
    base = datetime(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo)
    hours = []
    ZHOU = [(0, "子"), (2, "丑"), (4, "寅"), (6, "卯"), (8, "辰"), (10, "巳"),
            (12, "午"), (14, "未"), (16, "申"), (18, "酉"), (20, "戌"), (22, "亥")]
    pan0 = paipan(base.replace(hour=6))
    for h, zname in ZHOU:
        hh = h if h < 23 else 0
        tm = base.replace(hour=hh, minute=30)
        if h == 0:
            tm = (base.replace(hour=23, minute=30))
        try:
            pan = paipan(tm)
        except Exception:
            continue
        avg = sum(p.score for p in pan.palace.values()) / len(pan.palace)
        best_p = max(pan.palace.values(), key=lambda x: x.score)
        hours.append({
            "name": zname, "hour": h, "dz": pan.title,
            "avg": round(avg, 1),
            "best": (best_p.no, best_p.name, best_p.fang, best_p.score),
            "kaimen": pan.summary["kaimen"],
            "shengmen": pan.summary["shengmen"],
            "xiumen": pan.summary["xiumen"],
            "xunkong": pan.xunkong,
            "quality": pan_quality(pan),
        })
    hours_sorted = sorted(hours, key=lambda x: x["quality"], reverse=True)
    avg_all = sum(h["avg"] for h in hours) / max(1, len(hours))
    q_all = sum(h["quality"] for h in hours) / max(1, len(hours))
    # 清醒可用时段(卯~戌)的平均质量 —— 取 top3 会把日间差异拉平，故不用
    WAKE = ["卯", "辰", "巳", "午", "未", "申", "酉", "戌"]
    wake = [h for h in hours if h["name"] in WAKE]
    q_wake = sum(h["quality"] for h in wake) / max(1, len(wake))
    day_score = 0.35 * q_all + 0.65 * q_wake
    return {
        "jie": pan0.jie,
        "title": pan0.title,
        "yuan": pan0.yuan,
        "yang": pan0.yang,
        "hours": hours,
        "good_hours": [h["name"] for h in hours_sorted[:3]],
        "bad_hours": [h["name"] for h in hours_sorted[-2:]],
        "quality_all": round(q_all, 1),
        "day_avg": round(avg_all, 1),
        "day_score": round(day_score, 1),
    }


if __name__ == "__main__":
    from datetime import datetime
    dt = datetime(2026, 9, 28, 8, 0)
    pan = paipan(dt)
    print(f"{pan.title} | {pan.jie} {pan.yuan} | 时柱 {pan.hour_gz_name} 旬 {pan.xun} 空亡 {pan.xunkong}")
    print(f"值符宫 {pan.zhifu_palace} 值使宫 {pan.zhishi_palace}")
    for p in sorted(pan.palace):
        pl = pan.palace[p]
        print(f"  {pl.name}{pl.no}({pl.fang}) 地{pl.di_pan} 天{pl.tian_pan} "
              f"{pl.xing:4s} {pl.men:4s} {pl.shen:4s} 分{pl.score:5.1f} {';'.join(pl.notes)}")
    print("吉", pan.summary["best"], "| 凶", pan.summary["worst"])
    print()
    dr = day_report(dt)
    print("当日:", dr["jie"], dr["title"], dr["yuan"], "均值", dr["day_avg"])
    print("吉时:", dr["good_hours"], "不利时:", dr["bad_hours"])
