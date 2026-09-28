# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.liuren
大六壬排课引擎。

流程：
  1. 月将      —— 依中气定太阳过宫(雨水后亥 / 春分后戌 … 大寒后子)
  2. 天地盘    —— 月将加占时，天盘顺布十二支
  3. 四课      —— 十干寄宫起干阳、干阴、支阳、支阴
  4. 三传      —— 九宗门：贼克(元首/重审)、比用(知一)、遥克(蒿矢/弹射)、
                  昴星、别责、八专、伏吟、返吟
  5. 天将      —— 贵人排十二天将(昼贵/夜贵；临阳方顺布、临阴方逆布)
  6. 六亲      —— 父母/子孙/官鬼/妻财/兄弟
  7. 判吉凶    —— 初乘吉将、递刑传入空亡等

地支一律用 0..11 索引：0子 1丑 2寅 3卯 4辰 5巳 6午 7未 8申 9酉 10戌 11亥
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .base import (
    TIAN_GAN, DI_ZHI, day_gz, hour_zhi, current_zhongqi, ZHONGQI_TERMS,
    solar_term_datetime, year_terms, ensure_cst, gan_wuxing, zhi_wuxing,
    GAN_YANG, WX_SHENG, WX_SHENG_BY, WX_KE, WX_KE_BY,
)

# ---------------------------------------------------------------- 常量表

# 月将神名
JIANG_NAME = ["神后", "大吉", "功曹", "太冲", "天罡", "太乙",
              "胜光", "小吉", "传送", "从魁", "河魁", "登明"]
JIANG_DESC = ["子", "丑", "寅", "卯", "辰", "巳",
              "午", "未", "申", "酉", "戌", "亥"]

# 中气 -> 月将地支索引(该中气之后启用)
ZHONGQI_JIANG = {
    "雨水": 11,   # 亥 登明
    "春分": 10,   # 戌 河魁
    "谷雨": 9,    # 酉 从魁
    "小满": 8,    # 申 传送
    "夏至": 7,    # 未 小吉
    "大暑": 6,    # 午 胜光
    "处暑": 5,    # 巳 太乙
    "秋分": 4,    # 辰 天罡
    "霜降": 3,    # 卯 太冲
    "小雪": 2,    # 寅 功曹
    "冬至": 1,    # 丑 大吉
    "大寒": 0,    # 子 神后
}

# 十干寄宫
GAN_JIGONG = {"甲": 2, "乙": 4, "丙": 5, "丁": 7, "戊": 5, "己": 7,
              "庚": 8, "辛": 10, "壬": 11, "癸": 1}

# 十二天将
TIANJIANG = ["贵人", "腾蛇", "朱雀", "六合", "勾陈", "青龙",
             "天空", "白虎", "太常", "玄武", "太阴", "天后"]

# 贵人起例：(昼贵, 夜贵) 地支索引
GUI_REN = {
    "甲": (7, 1),   # 牛羊：昼未 夜丑
    "乙": (0, 8),   # 鼠猴：昼子 夜申
    "丙": (11, 9),  # 猪鸡：昼亥 夜酉
    "丁": (11, 9),  # 猪鸡
    "戊": (1, 7),   # 牛羊：戊与甲反
    "己": (8, 0),   # 鼠猴：己与乙反
    "庚": (1, 7),   # 牛羊
    "辛": (2, 6),   # 虎马：昼寅 夜午
    "壬": (3, 5),   # 兔蛇：昼卯 夜巳
    "癸": (5, 3),   # 兔蛇：癸与壬反
}

JIANG_SCORE = {"贵人": 20, "腾蛇": -12, "朱雀": -6, "六合": 14, "勾陈": -10,
               "青龙": 18, "天空": -8, "白虎": -20, "太常": 10, "玄武": -14,
               "太阴": 12, "天后": 14}

KEYI = ["元首", "重审", "知一", "涉害", "遥克", "昴星", "别责", "八专", "伏吟", "返吟"]

# 日干五合(别责借用)
GAN_HE = {"甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛",
          "辛": "丙", "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊"}

LIUCHONG_ZHI = [(0, 6), (1, 7), (2, 8), (3, 9), (4, 10), (5, 11)]


@dataclass
class Ke:
    pos: str          # 干阳/干阴/支阳/支阴
    ben: int          # 本位地支索引
    shen: int         # 上神(天盘落此之支)
    jiang: str = ""   # 天将
    liuqin: str = ""
    relation: str = ""  # 贼/克/无


@dataclass
class LiuRenPan:
    dt: datetime
    jiang: int              # 月将支
    jiang_name: str
    zhanshi: int            # 占时支
    tianpan: Dict[int, int]  # 地盘支 -> 天盘支
    sike: List[Ke]
    chuan: List[int]        # 三传地支索引
    chuan_jiang: List[str]
    chuan_liuqin: List[str]
    keti: str
    keti_desc: str
    score: float
    notes: List[str] = field(default_factory=list)
    day_gan: str = ""
    day_zhi: int = 0


# ---------------------------------------------------------------- 起课


def get_yuejiang(dt: datetime) -> Tuple[int, str]:
    """依中气定月将"""
    dt = ensure_cst(dt)
    name, _ = current_zhongqi(dt)
    idx = ZHONGQI_JIANG[name]
    return idx, f"{JIANG_NAME[idx]}({DI_ZHI[idx]})"


def build_tianpan(jiang: int, zhanshi: int) -> Dict[int, int]:
    """月将加占时：天盘顺布"""
    return {z: (jiang + (z - zhanshi)) % 12 for z in range(12)}


def build_sike(day_gan: str, day_zhi: int, tianpan: Dict[int, int]) -> List[Ke]:
    ji = GAN_JIGONG[day_gan]
    gan_yang_shen = tianpan[ji]
    gan_yin_shen = tianpan[gan_yang_shen]
    zhi_yang_shen = tianpan[day_zhi]
    zhi_yin_shen = tianpan[zhi_yang_shen]
    return [
        Ke("干阳", ji, gan_yang_shen),
        Ke("干阴", gan_yang_shen, gan_yin_shen),
        Ke("支阳", day_zhi, zhi_yang_shen),
        Ke("支阴", zhi_yang_shen, zhi_yin_shen),
    ]


def _wx(z: int) -> str:
    return zhi_wuxing(DI_ZHI[z])


def _relation(ben: int, shen: int) -> str:
    """返回 '克'(上克下) / '贼'(下贼上) / ''"""
    bw, sw = _wx(ben), _wx(shen)
    if WX_KE.get(sw) == bw:
        return "克"     # 上神克本位
    if WX_KE.get(bw) == sw:
        return "贼"     # 本位克上神
    return ""


def _chong(z: int) -> int:
    return (z + 6) % 12


def find_chuan(sike: List[Ke], day_gan: str, day_zhi: int,
               tianpan: Dict[int, int]) -> Tuple[List[int], str, str]:
    """
    九宗门定三传。返回 (三传, 课体, 说明)
    """
    for k in sike:
        k.relation = _relation(k.ben, k.shen)

    dm_idx = TIAN_GAN.index(day_gan)
    dm_yang = GAN_YANG[dm_idx]
    dm_wx = gan_wuxing(day_gan)

    ke_list = [k for k in sike if k.relation == "克"]
    zei_list = [k for k in sike if k.relation == "贼"]
    # 「贼」(下贼上)优先于「克」(上克下)
    cands = zei_list if zei_list else ke_list
    kind = "贼" if zei_list else "克"

    # ---------- 1) 贼克法 ----------
    if len(cands) == 1:
        k = cands[0]
        label = "下贼上，事起于内" if zei_list else "上克下，事起于外"
        desc = f"{k.pos}课「{kind}」({label})，{DI_ZHI[k.ben]}上得{DI_ZHI[k.shen]}"
        return _extend(k.shen, tianpan), ("重审" if zei_list else "元首"), desc
    if len(cands) > 1:
        same = [k for k in cands if _is_same_yang(k.shen, dm_yang)]
        pick = same[0] if same else cands[0]
        keti = "知一" if len(same) == 1 else "涉害"
        desc = (f"四课多处{kind}，{'比用' if same else '涉害'}取{pick.pos}课："
                f"{DI_ZHI[pick.ben]}上{DI_ZHI[pick.shen]}")
        return _extend(pick.shen, tianpan), keti, desc

    # ---------- 2) 遥克法 ----------
    remote = _remote_ke(sike, day_gan, dm_wx)
    if remote:
        return _extend(remote[0], tianpan), remote[1], remote[2]

    # ---------- 3) 专用课体 ----------
    # 八专：日干寄宫与日支同位
    if GAN_JIGONG[day_gan] == day_zhi:
        first = sike[0].shen
        if dm_yang:
            chuan0 = (first + 3) % 12
            desc = "干支同位，阳日自干上神顺数三位发用"
        else:
            chuan0 = (sike[3].shen - 3) % 12
            desc = "干支同位，阴日自支阴神逆数三位发用"
        return [chuan0, first, first], "八专", desc

    # 别责：四课不全(干上神与支上神同源)，借日干之合发用
    if sike[0].shen == sike[2].shen:
        he = GAN_HE.get(day_gan)
        chuan0 = tianpan[GAN_JIGONG[he]]
        return [chuan0, sike[0].shen, sike[0].shen], "别责", \
            f"诸课不全，借日干之合「{he}」寄宫{DI_ZHI[GAN_JIGONG[he]]}发用"

    # 伏吟：月将与占时同位，天地盘俱静
    if all(tianpan[z] == z for z in range(12)):
        chuan0 = sike[0].shen if dm_yang else sike[2].shen
        other = sike[2].shen if dm_yang else sike[0].shen
        return [chuan0, other, chuan0], "伏吟", \
            f"天地盘俱伏，{'刚日干上' if dm_yang else '柔日支上'}神发用，宜静不宜动"

    # 返吟：月将与占时相冲，天地盘皆对冲
    if _is_fanyin(tianpan):
        chuan0 = sike[0].shen if dm_yang else sike[2].shen
        return [chuan0, _chong(chuan0), chuan0], "返吟", \
            "月将与占时相冲，天地盘皆动，事多反复，宜守成防变"

    # ---------- 4) 昴星 ----------
    if dm_yang:
        chuan0 = tianpan[9]
        return [chuan0, sike[0].shen, sike[2].shen], "昴星", "刚日昴星，取地盘酉上神发用"
    inv = {v: k for k, v in tianpan.items()}
    chuan0 = inv.get(9, 9)
    return [chuan0, sike[2].shen, sike[0].shen], "昴星", "柔日昴星，取天盘酉下神发用"


def _is_same_yang(zhi_idx: int, day_yang: bool) -> bool:
    """地支的阴阳与日干阴阳相比"""
    return (zhi_idx % 2 == 0) == day_yang


def _is_fanyin(tianpan: Dict[int, int]) -> bool:
    """月将与占时相冲 -> 天地盘十二支皆对冲"""
    return all(tianpan[z] == (z + 6) % 12 for z in range(12))


def _extend(chuan0: int, tianpan: Dict[int, int]) -> List[int]:
    mid = tianpan[chuan0]
    return [chuan0, mid, tianpan[mid]]


def _remote_ke(sike: List[Ke], day_gan: str, dm_wx: str):
    """遥克：四课无贼克，看日干与课上神遥相克"""
    for idx, k in enumerate(sike[1:], start=1):
        sw = _wx(k.shen)
        if WX_KE_BY.get(dm_wx) == sw:            # 上神克日干 -> 蒿矢
            return (k.shen, "遥克", f"蒿矢课：{DI_ZHI[k.shen]}遥克日干{day_gan}")
    for idx, k in enumerate(sike[1:], start=1):
        sw = _wx(k.shen)
        if WX_KE.get(dm_wx) == sw:              # 日干克上神 -> 弹射
            return (k.shen, "遥克", f"弹射课：日干{day_gan}遥克{DI_ZHI[k.shen]}")
    return None


# ---------------------------------------------------------------- 天将


def build_tianjiang(dt: datetime, day_gan: str, tianpan: Dict[int, int]
                    ) -> Dict[int, str]:
    """贵人排十二天将：临亥子丑寅卯辰顺布；临巳午未申酉戌逆布"""
    hour = ensure_cst(dt).hour
    day_time = 6 <= hour < 18
    day_gui, night_gui = GUI_REN[day_gan]
    gui_di = day_gui if day_time else night_gui
    # 贵人加临之地盘位置(天盘贵人所在的地盘支)
    inv = {v: k for k, v in tianpan.items()}
    place = inv.get(gui_di, gui_di)
    forward = place in [11, 0, 1, 2, 3, 4]    # 亥子丑寅卯辰 -> 顺
    result: Dict[int, str] = {}
    for i, name in enumerate(TIANJIANG):
        pos = (place + i) % 12 if forward else (place - i) % 12
        result[pos] = name
    return result


def _liuqin(day_gan: str, z: int) -> str:
    dm = gan_wuxing(day_gan)
    zw = _wx(z)
    if zw == WX_SHENG_BY[dm]:
        return "父母"
    if zw == WX_SHENG[dm]:
        return "子孙"
    if zw == WX_KE_BY[dm]:
        return "官鬼"
    if zw == WX_KE[dm]:
        return "妻财"
    return "兄弟"


# ---------------------------------------------------------------- 判吉凶


PROPITIOUS = ["贵人", "青龙", "六合", "太常", "太阴", "天后"]
DESTRUCTIVE = ["白虎", "玄武", "腾蛇", "勾陈", "天空", "朱雀"]


def judge(pan: LiuRenPan) -> Tuple[float, List[str]]:
    s = 50.0
    notes = []
    raw = 0.0
    weights = [1.0, 0.55, 0.3]
    for i, (ch, jg, lq) in enumerate(zip(pan.chuan, pan.chuan_jiang, pan.chuan_liuqin)):
        raw += JIANG_SCORE.get(jg, 0) * weights[i]
        pos = f"{['初','中','末'][i]}传{DI_ZHI[ch]}"
        notes.append(f"{pos}·{jg}·{lq}")
    s += 30 * math.tanh(raw / 45.0)

    if pan.chuan_jiang[0] in PROPITIOUS:
        s += 6
        notes.append("初传乘吉将，事主顺遂")
    elif pan.chuan_jiang[0] in DESTRUCTIVE:
        s -= 6
        notes.append("初传乘凶将，宜静守")

    if pan.chuan_liuqin[-1] == "妻财":
        s += 4
        notes.append("末传见妻财，收成有利")
    if pan.chuan_liuqin[-1] == "官鬼":
        s -= 4
        notes.append("末传见官鬼，收尾有压")
    if WX_KE.get(_wx(pan.chuan[0])) == _wx(pan.chuan[1]):
        s -= 4
        notes.append("初传克中传，多为波折后成")

    # 课体倾向修正
    TI_KETI = {"伏吟": -6, "返吟": -7, "八专": -3, "别责": -2,
               "昴星": -4, "知一": 0, "涉害": -1, "遥克": -2,
               "元首": 5, "重审": 1}
    adj = TI_KETI.get(pan.keti, 0)
    if adj:
        s += adj
        notes.append(f"{pan.keti}课体{'减' if adj < 0 else '加'}分")

    return max(12.0, min(92.0, round(s, 1))), notes


# ---------------------------------------------------------------- 主入口


def paipan(dt: datetime) -> LiuRenPan:
    dt = ensure_cst(dt)
    jiang, jiang_name = get_yuejiang(dt)
    zhanshi = hour_zhi(dt)
    tianpan = build_tianpan(jiang, zhanshi)

    day_idx = day_gz(dt)
    day_gan = TIAN_GAN[day_idx % 10]
    day_zhi = day_idx % 12

    sike = build_sike(day_gan, day_zhi, tianpan)
    chuan, keti, keti_desc = find_chuan(sike, day_gan, day_zhi, tianpan)

    tianjiang = build_tianjiang(dt, day_gan, tianpan)
    for k in sike:
        k.jiang = tianjiang.get(k.ben, "")
        k.liuqin = _liuqin(day_gan, k.shen)

    chuan_jiang = [tianjiang.get(c, "") for c in chuan]
    chuan_liuqin = [_liuqin(day_gan, c) for c in chuan]

    pan = LiuRenPan(
        dt=dt, jiang=jiang, jiang_name=jiang_name, zhanshi=zhanshi,
        tianpan=tianpan, sike=sike, chuan=chuan, chuan_jiang=chuan_jiang,
        chuan_liuqin=chuan_liuqin, keti=keti, keti_desc=keti_desc,
        score=50.0, day_gan=day_gan, day_zhi=day_zhi,
    )
    pan.score, pan.notes = judge(pan)
    return pan


if __name__ == "__main__":
    from datetime import datetime
    for t in [datetime(2026, 9, 28, 8, 0), datetime(2026, 9, 28, 22, 0)]:
        pan = paipan(t)
        print(f"\n=== {t} ===")
        print(f"月将 {pan.jiang_name} | 占时 {DI_ZHI[pan.zhanshi]} | 日 {pan.day_gan}{DI_ZHI[pan.day_zhi]}")
        print("天地盘:", " ".join(f"{DI_ZHI[z]}:{DI_ZHI[pan.tianpan[z]]}" for z in range(12)))
        for k in pan.sike:
            print(f"  {k.pos} 本位{DI_ZHI[k.ben]} 上神{DI_ZHI[k.shen]} {k.jiang} {k.liuqin} {k.relation or '-'}")
        print("三传:", " ".join(f"{DI_ZHI[c]}({jg}/{lq})" for c, jg, lq in
                               zip(pan.chuan, pan.chuan_jiang, pan.chuan_liuqin)))
        print("课体:", pan.keti, "|", pan.keti_desc, "| 评分", pan.score)
        print("备注:", "; ".join(pan.notes))
