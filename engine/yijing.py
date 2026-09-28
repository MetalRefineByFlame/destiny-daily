# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.yijing
梅花易数 + 六爻纳甲

梅花易数：
  年月日时起卦 -> 本卦 / 互卦 / 变卦，体用生克断吉凶
六爻：
  同一主卦装纳甲六亲六神，判世爻旺衰、动爻变化、旬空

先天数：乾一 兑二 离三 震四 巽五 坎六 艮七 坤八
八卦索引：0乾 1兑 2离 3震 4巽 5坎 6艮 7坤
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from .base import (
    TIAN_GAN, DI_ZHI, day_gz, hour_zhi, hour_gz, ensure_cst,
    gan_wuxing, zhi_wuxing, WX_SHENG, WX_SHENG_BY, WX_KE, WX_KE_BY,
    WX_INDEX,
)
from .lunar import lunar_numbers

BAGUA = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]
XIANTIAN_NUM = {"乾": 1, "兑": 2, "离": 3, "震": 4, "巽": 5, "坎": 6, "艮": 7, "坤": 8}
BAGUA_WX = ["金", "金", "火", "木", "木", "水", "土", "土"]   # 与索引同序

BAGUA_XIANG = {
    "乾": "天·君·金玉·刚健·圆·马",
    "兑": "泽·少女·口舌·喜悦·缺损",
    "离": "火·中女·日·文明·附丽·电",
    "震": "雷·长男·动·足·奋起·龙",
    "巽": "风·长女·入·木·顺·商贾",
    "坎": "水·中男·月·陷·险·隐伏",
    "艮": "山·少男·止·手·径路·门阙",
    "坤": "地·母·众·顺·厚德·承载",
}

# ---------------- 六十四卦名：上卦为行，下卦为列 ----------------
GUA64: Dict[Tuple[int, int], str] = {
    # 上乾
    (0, 0): "乾为天", (0, 1): "天泽履", (0, 2): "天火同人", (0, 3): "天雷无妄",
    (0, 4): "天风姤", (0, 5): "天水讼", (0, 6): "天山遁", (0, 7): "天地否",
    # 上兑
    (1, 0): "泽天夬", (1, 1): "兑为泽", (1, 2): "泽火革", (1, 3): "泽雷随",
    (1, 4): "泽风大过", (1, 5): "泽水困", (1, 6): "泽山咸", (1, 7): "泽地萃",
    # 上离
    (2, 0): "火天大有", (2, 1): "火泽睽", (2, 2): "离为火", (2, 3): "火雷噬嗑",
    (2, 4): "火风鼎", (2, 5): "火水未济", (2, 6): "火山旅", (2, 7): "火地晋",
    # 上震
    (3, 0): "雷天大壮", (3, 1): "雷泽归妹", (3, 2): "雷火丰", (3, 3): "震为雷",
    (3, 4): "雷风恒", (3, 5): "雷水解", (3, 6): "雷山小过", (3, 7): "雷地豫",
    # 上巽
    (4, 0): "风天小畜", (4, 1): "风泽中孚", (4, 2): "风火家人", (4, 3): "风雷益",
    (4, 4): "巽为风", (4, 5): "风水涣", (4, 6): "风山渐", (4, 7): "风地观",
    # 上坎
    (5, 0): "水天需", (5, 1): "水泽节", (5, 2): "水火既济", (5, 3): "水雷屯",
    (5, 4): "水风井", (5, 5): "坎为水", (5, 6): "水山蹇", (5, 7): "水地比",
    # 上艮
    (6, 0): "山天大畜", (6, 1): "山泽损", (6, 2): "山火贲", (6, 3): "山雷颐",
    (6, 4): "山风蛊", (6, 5): "山水蒙", (6, 6): "艮为山", (6, 7): "山地剥",
    # 上坤
    (7, 0): "地天泰", (7, 1): "地泽临", (7, 2): "地火明夷", (7, 3): "地雷复",
    (7, 4): "地风升", (7, 5): "地水师", (7, 6): "地山谦", (7, 7): "坤为地",
}

# 八宫：(宫索引, [(上卦,下卦)顺序]，即 本宫/一世/二世/三世/四世/五世/游魂/归魂)
GONG_MEMBER = {
    0: [(0, 0), (0, 4), (0, 6), (0, 7), (4, 7), (6, 7), (2, 7), (2, 0)],   # 乾宫
    1: [(1, 1), (1, 5), (1, 7), (1, 6), (5, 6), (7, 6), (3, 6), (3, 1)],   # 兑宫
    2: [(2, 2), (2, 6), (2, 4), (2, 5), (6, 5), (4, 5), (0, 5), (0, 2)],   # 离宫
    3: [(3, 3), (3, 7), (3, 5), (3, 4), (7, 4), (5, 4), (1, 4), (1, 3)],   # 震宫
    4: [(4, 4), (4, 0), (4, 2), (4, 3), (0, 3), (2, 3), (6, 3), (6, 4)],   # 巽宫
    5: [(5, 5), (5, 1), (5, 3), (5, 2), (1, 2), (3, 2), (7, 2), (7, 5)],   # 坎宫
    6: [(6, 6), (6, 2), (6, 0), (6, 1), (2, 1), (0, 1), (4, 1), (4, 6)],   # 艮宫
    7: [(7, 7), (7, 3), (7, 1), (7, 0), (3, 0), (1, 0), (5, 0), (5, 7)],   # 坤宫
}
GONG_NAME = {0: "乾宫", 1: "兑宫", 2: "离宫", 3: "震宫",
             4: "巽宫", 5: "坎宫", 6: "艮宫", 7: "坤宫"}

# 爻的强度：本宫6 / 一世1 / 二世2 / 三世3 / 四世4 / 五世5 / 游魂4 / 归魂3
SHI_POS = [6, 1, 2, 3, 4, 5, 4, 3]

# 纳甲天干：(内卦天干, 外卦天干)
NA_GAN = {0: ("甲", "壬"), 7: ("乙", "癸"), 3: ("庚", "庚"), 4: ("辛", "辛"),
          5: ("戊", "戊"), 2: ("己", "己"), 6: ("丙", "丙"), 1: ("丁", "丁")}
# 纳甲地支：八卦六爻地支(自初爻至上爻)
NA_ZHI = {
    0: ["子", "寅", "辰", "午", "申", "戌"],   # 乾
    5: ["寅", "辰", "午", "申", "戌", "子"],   # 坎
    6: ["辰", "午", "申", "戌", "子", "寅"],   # 艮
    3: ["子", "寅", "辰", "午", "申", "戌"],   # 震
    4: ["丑", "亥", "酉", "未", "巳", "卯"],   # 巽
    2: ["卯", "丑", "亥", "酉", "未", "巳"],   # 离
    7: ["未", "巳", "卯", "酉", "亥", "丑"],   # 坤
    1: ["巳", "卯", "丑", "亥", "酉", "未"],   # 兑
}

LIUSHEN_START = {0: "青龙", 5: "青龙", 2: "朱雀", 3: "朱雀", 4: "勾陈",
                 9: "勾陈", 6: "腾蛇", 7: "腾蛇", 8: "白虎", 1: "白虎"}  # 索引为日干
LIUSHEN_ORDER = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]
LIUSHEN_SCORE = {"青龙": 16, "朱雀": -4, "勾陈": -8, "腾蛇": -12, "白虎": -18, "玄武": -14}

LIUQIN_SCORE = {"父母": 2, "兄弟": -3, "子孙": 10, "妻财": 8, "官鬼": -10}


@dataclass
class Yao:
    idx: int          # 0..5 自下而上
    gan_zhi: str
    liuqin: str
    liushen: str
    is_shi: bool = False
    is_ying: bool = False
    is_dong: bool = False
    changed: str = ""


@dataclass
class LiuYaoPan:
    dt: datetime
    name: str
    upper: int
    lower: int
    gong: int
    gong_name: str
    yaos: List[Yao]
    shi_idx: int
    ying_idx: int
    dong_idx: int
    biangua: str
    xunkong: List[str]
    score: float
    notes: List[str]


@dataclass
class MeiHuaPan:
    dt: datetime
    upper: int
    lower: int
    dong: int
    ben_gua: str
    hu_gua: str
    bian_gua: str
    ti: int              # 体卦索引
    yong: int            # 用卦索引
    ti_wx: str
    yong_wx: str
    relation: str
    score: float
    notes: List[str]


# ---------------------------------------------------------------- 起卦


def qigua(dt: datetime) -> Tuple[int, int, int, Tuple[int, int, int, int]]:
    """年月日时数起卦，返回 (上卦索引, 下卦索引, 动爻1..6, 原始数)"""
    n = lunar_numbers(dt)     # (年地支序号, 农历月, 农历日, 时辰序号)
    y, mo, d, h = n
    up = (y + mo + d) % 8
    low = (y + mo + d + h) % 8
    dong = (y + mo + d + h) % 6
    up = 7 if up == 0 else up - 1        # 余数0 -> 坤(索引7)
    low = 7 if low == 0 else low - 1
    dong = 6 if dong == 0 else dong
    return up, low, dong, n


# 八卦爻象(自下而上，1=阳)
GUA_YAO = {
    0: [1, 1, 1],   # 乾
    1: [1, 1, 0],   # 兑  ☱ 上断 -> 下阳中阳上阴
    2: [1, 0, 1],   # 离
    3: [1, 0, 0],   # 震  ☳ 下阳 中上阴
    4: [0, 1, 1],   # 巽  ☴ 下断 -> 下阴 中上阳
    5: [0, 1, 0],   # 坎
    6: [0, 0, 1],   # 艮  ☶ 上阳 下中阴
    7: [0, 0, 0],   # 坤
}
_YAO_TO_BAGUA = {tuple(v): k for k, v in GUA_YAO.items()}


def _flip_trigram(bagua_idx: int, yao_pos: int) -> int:
    """变某爻后得到的经卦索引。yao_pos: 0/1/2 自下而上"""
    y = GUA_YAO[bagua_idx][:]
    y[yao_pos] = 1 - y[yao_pos]
    return _YAO_TO_BAGUA[tuple(y)]


def _compute_mutual(six: List[int]) -> Tuple[int, int]:
    """six 自上而下六爻。下互=2,3,4爻；上互=3,4,5爻(索引1,2,3 与 2,3,4)"""
    lower_tri = tuple(six[3:6]) if False else None
    # six 索引: 0=六爻(上) ... 5=初爻(下)
    # 自下而上序列:
    bottom_up = list(reversed(six))       # bottom_up[0]=初爻
    low_mut = tuple(bottom_up[1:4])       # 二三四爻 -> 下互
    up_mut = tuple(bottom_up[2:5])        # 三四五爻 -> 上互
    return (_YAO_TO_BAGUA[up_mut], _YAO_TO_BAGUA[low_mut])


# ---------------------------------------------------------------- 梅花


MEIHUA_REL = {
    "用生体": (18, "用生体，得外助力，事易成"),
    "体用比和": (14, "体用比和，内外同心，顺遂"),
    "体克用": (6, "体克用，费力而可有成，宜主动"),
    "体生用": (-8, "体生用，耗泄自身，付出多而回报少"),
    "用克体": (-20, "用克体，外力压制阻力重，宜守"),
}


def meihua(dt: datetime) -> MeiHuaPan:
    up, low, dong, nums = qigua(dt)
    ben = GUA64[(up, low)]
    # 动爻在下卦还是上卦（爻序自下而上 1..6）
    # 有动爻者为「用」，无动爻者为「体」
    if dong <= 3:
        yong, ti = low, up
        changed_idx = _flip_trigram(low, dong - 1)
        bian_pair = (up, changed_idx)
    else:
        yong, ti = up, low
        changed_idx = _flip_trigram(up, dong - 4)
        bian_pair = (changed_idx, low)
    bian = GUA64[bian_pair]
    hu = _compute_mutual(GUA_YAO[up] + GUA_YAO[low])
    hu_name = GUA64[hu]

    ti_wx = BAGUA_WX[ti]
    yong_wx = BAGUA_WX[yong]
    if WX_SHENG_BY[ti_wx] == yong_wx:
        rel = "用生体"
    elif WX_SHENG[ti_wx] == yong_wx:
        rel = "体生用"
    elif WX_KE[ti_wx] == yong_wx:
        rel = "体克用"
    elif WX_KE_BY[ti_wx] == yong_wx:
        rel = "用克体"
    else:
        rel = "体用比和"

    adj, desc = MEIHUA_REL[rel]
    s = 50 + adj
    notes = [desc, f"体卦{BAGUA[ti]}({ti_wx})｜用卦{BAGUA[yong]}({yong_wx})"]
    notes.append(f"体卦类象：{BAGUA_XIANG[BAGUA[ti]]}")
    # 旺衰：体卦五行得月令？(以当月地支为月建)
    from .base import month_gz_by_jie, JIA_ZI, DI_ZHI
    mz = DI_ZHI[month_gz_by_jie(dt) % 12]
    month_wx = zhi_wuxing(mz)
    if month_wx == ti_wx or month_wx == WX_SHENG_BY[ti_wx]:
        s += 8
        notes.append(f"体卦得月令({mz}月生扶)，有力")
    elif month_wx == WX_KE[ti_wx] or month_wx == WX_SHENG[ti_wx]:
        s -= 6
        notes.append(f"体卦失令于{mz}月，宜量力")
    return MeiHuaPan(
        dt=dt, upper=up, lower=low, dong=dong, ben_gua=ben,
        hu_gua=GUA64.get(hu, hu_name), bian_gua=bian,
        ti=ti, yong=yong, ti_wx=ti_wx, yong_wx=yong_wx,
        relation=rel, score=max(10, min(92, round(s, 1))), notes=notes,
    )


# ---------------------------------------------------------------- 六爻


def _gong_of(up: int, low: int) -> Tuple[int, int]:
    for g, members in GONG_MEMBER.items():
        for seq, pair in enumerate(members):
            if pair == (up, low):
                return g, seq
    return 0, 0


def xunkong_of(day_idx: int) -> List[str]:
    xun = day_idx - day_idx % 10
    mapping = ["戌", "亥", "申", "酉", "午", "未", "辰", "巳", "寅", "卯", "子", "丑"]
    base = {"甲子": 0, "甲戌": 2, "甲申": 4, "甲午": 6, "甲辰": 8, "甲寅": 10}
    from .base import JIA_ZI
    name = JIA_ZI[xun]
    i = base[name]
    return [mapping[i], mapping[i + 1]]


def liuyao(dt: datetime, dong_idx: Optional[int] = None) -> LiuYaoPan:
    from .base import JIA_ZI, month_gz_by_jie
    up, low, dong, nums = qigua(dt)
    if dong_idx:
        dong = dong_idx
    name = GUA64[(up, low)]
    gong, seq = _gong_of(up, low)
    gong_wx = BAGUA_WX[gong]

    # 装纳甲
    inner_gan, outer_gan = NA_GAN[low][0], NA_GAN[up][1]
    yaos: List[Yao] = []
    for i in range(6):
        if i < 3:
            zhi = NA_ZHI[low][i]
            gan = NA_GAN[low][0]
        else:
            zhi = NA_ZHI[up][i]
            gan = NA_GAN[up][1]
        zw = zhi_wuxing(zhi)
        if zw == WX_SHENG_BY[gong_wx]:
            lq = "父母"
        elif zw == WX_SHENG[gong_wx]:
            lq = "子孙"
        elif zw == WX_KE_BY[gong_wx]:
            lq = "官鬼"
        elif zw == WX_KE[gong_wx]:
            lq = "妻财"
        else:
            lq = "兄弟"
        yaos.append(Yao(i, gan + zhi, lq, ""))

    # 六神
    day_idx = day_gz(dt)
    day_gan_idx = day_idx % 10
    start_shen = LIUSHEN_START.get(day_gan_idx, "青龙")
    si = LIUSHEN_ORDER.index(start_shen)
    for i, y in enumerate(yaos):
        y.liushen = LIUSHEN_ORDER[(si + i) % 6]

    shi_pos = SHI_POS[seq]              # 1..6
    shi_idx = shi_pos - 1
    ying_idx = (shi_idx + 3) % 6
    yaos[shi_idx].is_shi = True
    yaos[ying_idx].is_ying = True

    dong_pos = dong - 1
    yaos[dong_pos].is_dong = True
    changed = GUA64[_changed_pair(up, low, dong)]
    for i, y in enumerate(yaos):
        y.changed = changed

    xk = xunkong_of(day_idx)

    # 逐爻评断
    notes = []
    s = 50.0
    shi = yaos[shi_idx]
    s += LIUQIN_SCORE.get(shi.liuqin, 0)
    s += LIUSHEN_SCORE.get(shi.liushen, 0)
    notes.append(f"世爻在第{shi_pos}爻：{shi.gan_zhi}·{shi.liuqin}·{shi.liushen}")
    # 世爻是否得日月之助
    mzhi = DI_ZHI[month_gz_by_jie(dt) % 12]
    notes.append(f"月建{mzhi}　日辰{JIA_ZI[day_idx % 60]}")
    zw_shi = zhi_wuxing(shi.gan_zhi[1])
    mwx = zhi_wuxing(mzhi)
    dwx = zhi_wuxing(DI_ZHI[day_idx % 12])
    if mwx == zw_shi or mwx == WX_SHENG_BY[zw_shi]:
        s += 8
        notes.append("世爻得月建生扶")
    elif mwx == WX_KE[zw_shi]:
        s -= 8
        notes.append("世爻受月建之克，压力大")
    if dwx == zw_shi or dwx == WX_SHENG_BY[zw_shi]:
        s += 6
        notes.append("世爻得日辰生扶")
    elif dwx == WX_KE[zw_shi]:
        s -= 6
        notes.append("世爻受日辰相克")
    if shi.gan_zhi[1] in xk:
        s -= 8
        notes.append("世爻空亡，诸事迟滞")
    # 动爻影响
    dy = yaos[dong_pos]
    notes.append(f"第{dong}爻动：{dy.gan_zhi}·{dy.liuqin}·{dy.liushen}，变卦{changed}")
    dzw = zhi_wuxing(dy.gan_zhi[1])
    if WX_SHENG_BY[zw_shi] == dzw:
        s += 7
        notes.append("动爻生世，外力助我")
    elif WX_KE[zw_shi] == dzw:
        s -= 9
        notes.append("动爻克世，事有阻")
    s += LIUQIN_SCORE.get(dy.liuqin, 0) * 0.5

    return LiuYaoPan(
        dt=dt, name=name, upper=up, lower=low, gong=gong,
        gong_name=GONG_NAME[gong], yaos=yaos, shi_idx=shi_idx,
        ying_idx=ying_idx, dong_idx=dong_pos, biangua=changed,
        xunkong=xk, score=max(10, min(92, round(s, 1))), notes=notes,
    )


def _changed_pair(up: int, low: int, dong: int) -> Tuple[int, int]:
    if dong <= 3:
        return (up, _flip_trigram(low, dong - 1))
    return (_flip_trigram(up, dong - 4), low)


if __name__ == "__main__":
    from datetime import datetime
    dt = datetime(2026, 9, 28, 8, 0)
    mh = meihua(dt)
    print("=== 梅花易数 ===")
    print(f"本卦 {mh.ben_gua} | 互卦 {mh.hu_gua} | 变卦 {mh.bian_gua}")
    print(f"体{BAGUA[mh.ti]}({mh.ti_wx}) 用{BAGUA[mh.yong]}({mh.yong_wx}) 第{mh.dong}爻动")
    print(f"关系 {mh.relation} | 评分 {mh.score}")
    for n in mh.notes:
        print("  -", n)
    ly = liuyao(dt)
    print("\n=== 六爻 ===")
    print(f"{ly.name}（{ly.gong_name}） 变卦 {ly.biangua} 空亡 {ly.xunkong} 评分 {ly.score}")
    for y in ly.yaos:
        mark = ""
        if y.is_shi:
            mark += " [世]"
        if y.is_ying:
            mark += " [应]"
        if y.is_dong:
            mark += " [动]"
        print(f"  {y.idx+1}爻 {y.gan_zhi} {y.liuqin} {y.liushen}{mark}")
    for n in ly.notes:
        print("  -", n)
