# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.zhouyi
每日一卦 —— 大衍筮法起卦 + 《周易》经文占断

起卦：蓍草法（大衍之数五十，其用四十有九），三变成一爻，十八变成六爻。
      每爻得数 6=老阴(动) 7=少阳(静) 8=少阴(静) 9=老阳(动)。
      随机数种子由「日期 + 农历 + 日干支 + 本命」混合生成，同日同人结果恒定。

断法：依朱熹《易学启蒙》——
      六爻皆静，以本卦卦辞断；
      一动爻，以该爻爻辞断；
      二动爻，以上爻辞为主、下爻辞为参；
      三动爻，合参本卦与之卦卦辞；
      四动爻，以之卦两静爻之在下者为主；
      五动爻，以之卦唯一静爻为主；
      六爻皆动，乾坤取用九用六，余取之卦卦辞。
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .base import day_gz, ensure_cst, JIA_ZI, DI_ZHI, WX_SHENG, WX_SHENG_BY, WX_KE, WX_KE_BY
from .lunar import lunar_numbers
from .yijing import GUA64, GUA_YAO, BAGUA, BAGUA_WX, _YAO_TO_BAGUA
from .gua64_data import GUA64_DATA

# ---------------------------------------------------------------- 爻位通则（学习资料）

YAOWEI_NOTE = {
    1: "初爻为事之始端。此时念头方萌、形势未显，辞多言「潜」「履」，贵在慎始。",
    2: "二爻居下卦之中位。得中得正，柔顺而有应，故多美辞，是六爻中最安稳的位置。",
    3: "三爻居下卦之极，处上下之际而未及中。危惧之地，辞多「厉」「吝」，宜自守。",
    4: "四爻近五之尊位，所谓「近君」。伴君如伴虎，辞多「惧」「戒」，须恭慎自持。",
    5: "五爻居上卦之中，为君位、为卦主。既中且正，多吉辞，是全卦最贵重之位。",
    6: "上爻为事之终极。物极必反，多「亢」「悔」之辞，宜知退知止。",
}

YAO_NAME = {6: "老阴", 7: "少阳", 8: "少阴", 9: "老阳"}

# 乾坤用九、用六
QIAN_KUN_YONG = {
    "乾为天": "用九：见群龙无首，吉　——　群阳并进而各不争首，刚而能柔，是为吉道。",
    "坤为地": "用六：利永贞　——　柔而能刚，长久守正则利。",
}

# 卦爻好用词汇普查（用于倾向推定，非硬断）


@dataclass
class GuaCI:
    """一卦的经文资料"""
    name: str
    xu: int
    symbol: str
    pair: Tuple[int, int]
    ci: str
    ci_bai: str
    xiang: str
    xg_bai: str
    yao: List[str]
    yi: str
    yong: str
    tags: List[str]

    @property
    def upper_name(self) -> str:
        return BAGUA[self.pair[0]]

    @property
    def lower_name(self) -> str:
        return BAGUA[self.pair[1]]

    @property
    def upper_wx(self) -> str:
        return BAGUA_WX[self.pair[0]]

    @property
    def lower_wx(self) -> str:
        return BAGUA_WX[self.pair[1]]


@dataclass
class GuaResult:
    ben: GuaCI                      # 本卦
    bian: Optional[GuaCI] = None    # 之卦（变卦）
    hu: Optional[GuaCI] = None      # 互卦
    cuo: Optional[GuaCI] = None     # 错卦（旁通）
    zong: Optional[GuaCI] = None    # 综卦（覆卦）
    lines: List[int] = field(default_factory=list)      # 自下而上，值 6/7/8/9
    yin_yang: List[int] = field(default_factory=list)   # 自下而上，1阳 0阴
    moving: List[int] = field(default_factory=list)     # 动爻位 1..6
    method: str = ""                # 采用的断法
    judge_src: str = ""             # 主断依据名
    judge_text: str = ""            # 主断爻辞/卦辞
    judge_pos: Optional[int] = None # 主断爻位 1..6（若为爻断）
    tendency: str = ""              # 倾向
    tend_note: str = ""             # 倾向判语
    analysis: List[str] = field(default_factory=list)   # 具体分析
    benming: List[str] = field(default_factory=list)    # 与本命的呼应


# ---------------------------------------------------------------- 起卦

def _three_bian(rng: random.Random) -> int:
    """
    三变成一爻，返回 6/7/8/9。

    每一变：分二 → 挂一 → 揲四 → 归奇。
    设本变起手 n 根，取挂一之一根后，参与揲四者为 T = n - 1 根，分作左右两堆：
        左手一堆之余数 ρ 视所属「四时」而定——其值 1/2/3/4 四类等可能
        （满四者即取四，古法所谓「奇」不出此四数）
        右手一堆之余数由 T - ρ 定，同理逢四则记作 4
    本变所去 = 左余 + 右余 + 挂一之一，即 变1 去 5 或 9，变2 变3 去 4 或 8。

    按此古典模型，三变所得之概率恰为：
        老阴 6 = 1/16　少阳 7 = 5/16　少阴 8 = 7/16　老阳 9 = 3/16
    （阳多于阴，静爻十二之十六，是大衍法区别于金钱卦的本有特征。）
    """
    n = 49
    for _ in range(3):
        total = n - 1                       # 挂一之后参与揲四的总数
        rho = rng.randrange(4)              # 左手余数所属之类，四类等可能
        r_left = 4 if rho == 0 else rho
        tail = (total - rho) % 4
        r_right = 4 if tail == 0 else tail
        n -= (r_left + r_right + 1)         # 归奇于扐，连同挂一一起除去
    return n // 4                           # 36/32/28/24 -> 9/8/7/6


def _seed_of(target: datetime, personal: str = "") -> int:
    """种子：日期 + 农历 + 日干支 + 本命标识。同日同人 → 同一卦。"""
    y, mo, d, h = lunar_numbers(target)
    dg = day_gz(target)
    material = "|".join([
        target.strftime("%Y-%m-%d"),
        f"L{y}-{mo}-{d}-{h}",
        f"GZ{JIA_ZI[dg % 60]}",
        personal or "anonymous",
    ])
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16)


def _ci_of(pair: Tuple[int, int]) -> GuaCI:
    d = GUA64_DATA[pair]
    return GuaCI(
        name=GUA64[pair], xu=d["xu"], symbol=chr(0x4DC0 + d["xu"] - 1),
        pair=pair, ci=d["ci"], ci_bai=d["ci_bai"], xiang=d["xiang"],
        xg_bai=d["xg_bai"], yao=list(d["yao"]), yi=d["yi"],
        yong=d["yong"], tags=list(d["tags"]),
    )


def _pair_of(yin_yang: List[int]) -> Tuple[int, int]:
    """yin_yang 自下而上 -> (上卦索引, 下卦索引)"""
    lower = _YAO_TO_BAGUA[tuple(yin_yang[0:3])]
    upper = _YAO_TO_BAGUA[tuple(yin_yang[3:6])]
    return upper, lower


# ---------------------------------------------------------------- 主流程

def cast(target: datetime, personal: str = "",
         day_master_wx: Optional[str] = None,
         yong_shen: Optional[List[str]] = None) -> GuaResult:
    target = ensure_cst(target)
    rng = random.Random(_seed_of(target, personal))

    lines = [_three_bian(rng) for _ in range(6)]            # 自下而上
    yy = [1 if v in (7, 9) else 0 for v in lines]           # 9/7 阳，8/6 阴
    moving = [i + 1 for i, v in enumerate(lines) if v in (6, 9)]

    ben_pair = _pair_of(yy)
    ben = _ci_of(ben_pair)

    # --- 之卦：老阴变阳、老阳变阴 ---
    bian = None
    if moving:
        by = [1 - v for v in yy]
        bian = _ci_of(_pair_of(by))

    # --- 互卦：二三四爻为下互，三四五爻为上互 ---
    hu = None
    try:
        low_m = _YAO_TO_BAGUA[tuple(yy[1:4])]
        up_m = _YAO_TO_BAGUA[tuple(yy[2:5])]
        hu = _ci_of((up_m, low_m))
    except KeyError:
        pass

    # --- 错卦：阴阳全变 ---
    cuo = _ci_of(_pair_of([1 - v for v in yy]))

    # --- 综卦：上下颠倒 ---
    zong = _ci_of(_pair_of(list(reversed(yy))))

    r = GuaResult(ben=ben, bian=bian, hu=hu, cuo=cuo, zong=zong,
                  lines=lines, yin_yang=yy, moving=moving)

    _judge(r)
    r.analysis = _analysis(r)
    if day_master_wx:
        r.benming = _benming(r, day_master_wx, yong_shen or [])
    return r


# ---------------------------------------------------------------- 占断

def _judge(r: GuaResult) -> None:
    m = r.moving
    n = len(m)

    if n == 0:
        r.method = "六爻皆静　→　以本卦卦辞断"
        r.judge_src = "本卦卦辞"
        r.judge_text = r.ben.ci
    elif n == 1:
        p = m[0]
        r.method = "一动爻　→　以该爻爻辞断"
        r.judge_src = f"本卦第{p}爻"
        r.judge_text = r.ben.yao[p - 1]
        r.judge_pos = p
    elif n == 2:
        p = max(m)
        r.method = "二动爻　→　以上方动爻爻辞为主，下方者参之"
        r.judge_src = f"本卦第{p}爻（下动爻第{min(m)}爻为参）"
        r.judge_text = r.ben.yao[p - 1]
        r.judge_pos = p
    elif n == 3:
        r.method = "三动爻　→　本卦、之卦卦辞合参，以本卦为主"
        r.judge_src = "本卦卦辞（参之卦）"
        r.judge_text = f"{r.ben.ci}　‖　之卦{r.bian.name}：{r.bian.ci}"
    elif n == 4:
        still = [i + 1 for i in range(6) if (i + 1) not in m]     # 之卦中的静爻
        p = min(still)
        r.method = "四动爻　→　以之卦两个静爻中居下者断"
        r.judge_src = f"之卦{r.bian.name}第{p}爻"
        r.judge_text = r.bian.yao[p - 1]
        r.judge_pos = p
    elif n == 5:
        still = [i + 1 for i in range(6) if (i + 1) not in m][0]
        r.method = "五动爻　→　以之卦唯一静爻断"
        r.judge_src = f"之卦{r.bian.name}第{still}爻"
        r.judge_text = r.bian.yao[still - 1]
        r.judge_pos = still
    else:
        if r.ben.name in QIAN_KUN_YONG:
            r.method = "六爻皆动　→　乾坤取用九、用六"
            r.judge_src = "用爻"
            r.judge_text = QIAN_KUN_YONG[r.ben.name]
        elif r.bian:
            r.method = "六爻皆动　→　取之卦卦辞断"
            r.judge_src = f"之卦{r.bian.name}卦辞"
            r.judge_text = r.bian.ci
        else:
            r.method = "六爻皆动　→　取之卦卦辞断"
            r.judge_src = "之卦"
            r.judge_text = r.ben.ci

    # --- 倾向（依断辞用词推定，非硬断吉凶） ---
    good = sum(r.judge_text.count(w) for w in ("元吉", "大吉", "吉", "无咎", "无不利", "利"))
    bad = sum(r.judge_text.count(w) for w in ("凶", "吝", "厉", "灾眚", "眚"))
    if good > bad:
        r.tendency, r.tend_note = "顺", "断辞见吉语，顺势而行可有所得"
    elif bad > good:
        r.tendency, r.tend_note = "警", "断辞含警语，宜收敛自重、先防其失"
    else:
        r.tendency, r.tend_note = "平", "断辞平实，守常即是较好选择"


# ---------------------------------------------------------------- 分析

def _wx_rel(a: str, b: str) -> str:
    """以 a 为主体看 b"""
    if a == b:
        return "比和"
    if WX_SHENG_BY[a] == b:
        return f"{b}生{a}（得生扶）"
    if WX_SHENG[a] == b:
        return f"{a}生{b}（泄气）"
    if WX_KE[a] == b:
        return f"{a}克{b}（耗力）"
    if WX_KE_BY[a] == b:
        return f"{b}克{a}（受制）"
    return ""


def _analysis(r: GuaResult) -> List[str]:
    a: List[str] = []
    b = r.ben

    # 1 卦象结构
    struct = (f"{b.name}（{b.symbol}）　第{b.xu}卦　"
              f"上{b.upper_name}（{b.upper_wx}）下{b.lower_name}（{b.lower_wx}）")
    a.append(struct)

    # 2 动爻
    if r.moving:
        detail = "、".join(
            f"第{p}爻({YAO_NAME[r.lines[p-1]]})" for p in r.moving)
        a.append(f"动爻 {len(r.moving)} 个：{detail}　→　之卦{r.bian.name}（{r.bian.symbol}）")
    else:
        a.append("动爻 0 个，六爻皆静　→　卦象稳定，事无突变，以守常为本")

    # 3 主断
    a.append(f"主断取「{r.judge_src}」：{r.judge_text}")

    # 4 上下卦体用（内生外）
    a.append(f"内卦（下）{b.lower_name}为体、主自身；外卦（上）{b.upper_name}为用、主环境。"
             f"上下关系：{_wx_rel(b.lower_wx, b.upper_wx)}")

    # 5 互卦 = 过程
    if r.hu:
        a.append(f"互卦{r.hu.name}（{r.hu.symbol}）——事情的中间过程与内在肌理，"
                 f"看 {r.hu.tags[0]} 的意味")

    # 6 变卦 = 结果走势
    if r.bian:
        a.append(f"之卦{r.bian.name}（{r.bian.symbol}）——事态走向，"
                 f"今日宜以「{r.bian.tags[0]}」收梢")

    # 7 另一视角
    a.append(f"换个立场看：错卦{r.cuo.name}（对立面）　综卦{r.zong.name}（反过来看）")

    return a


def _benming(r: GuaResult, dmwx: str, yong: List[str]) -> List[str]:
    """卦与本命的呼应"""
    out: List[str] = []
    b = r.ben
    out.append(f"本命日主属{dmwx}，本卦内卦{b.lower_name}属{b.lower_wx}："
               f"{_wx_rel(dmwx, b.lower_wx)}")
    out.append(f"本命日主属{dmwx}，本卦外卦{b.upper_name}属{b.upper_wx}："
               f"{_wx_rel(dmwx, b.upper_wx)}")

    if yong:
        ys = "/".join(yong)
        lower_hit = "内卦正扶用神，今日发挥自己的优势成本最低" \
            if b.lower_wx in yong else "内卦非用神之属，今日宜依常规行事，勿强求出彩"
        upper_hit = "外卦环境合于用神，外部条件较配合" \
            if b.upper_wx in yong else "外卦环境不合用神，外部助力有限，宜靠自己"
        out.append(f"用神{ys}：{lower_hit}；{upper_hit}")
    return out


# ---------------------------------------------------------------- 输出 dict

def daily_block(target: datetime, personal: str = "",
                day_master_wx: Optional[str] = None,
                yong_shen: Optional[List[str]] = None) -> Dict:
    """供 report 层直接消费的结构"""
    r = cast(target, personal, day_master_wx, yong_shen)
    b, bi = r.ben, r.bian

    # 爻位学习材料
    yao_study = []
    for i in range(6):
        v = r.lines[i]
        pos = i + 1
        yang = r.yin_yang[i] == 1
        right = (pos % 2 == 1) == yang          # 阳居阳位、阴居阴位为得位
        yao_study.append(dict(
            pos=pos,
            name=YAO_NAME[v],
            text=b.yao[i],
            dong=pos in r.moving,
            wei=YAOWEI_NOTE[pos],
            dewei="得位（刚柔当其位）" if right else "不当位（刚柔失其位）",
        ))

    return dict(
        name=b.name, xu=b.xu, symbol=b.symbol,
        upper=f"{b.upper_name}（{b.upper_wx}）", lower=f"{b.lower_name}（{b.lower_wx}）",
        ci=b.ci, ci_bai=b.ci_bai, xiang=b.xiang, xg_bai=b.xg_bai,
        yi=b.yi, yong=b.yong, tags=b.tags,
        lines=r.lines, yin_yang=r.yin_yang, moving=r.moving,
        line_labels=[YAO_NAME[v] for v in r.lines],
        bian=dict(name=bi.name, xu=bi.xu, symbol=bi.symbol, ci=bi.ci,
                  tags=bi.tags) if bi else None,
        hu=dict(name=r.hu.name, symbol=r.hu.symbol, tags=r.hu.tags) if r.hu else None,
        cuo=dict(name=r.cuo.name, symbol=r.cuo.symbol) if r.cuo else None,
        zong=dict(name=r.zong.name, symbol=r.zong.symbol) if r.zong else None,
        method=r.method, judge_src=r.judge_src, judge_text=r.judge_text,
        judge_pos=r.judge_pos,
        tendency=r.tendency, tend_note=r.tend_note,
        analysis=r.analysis, benming=r.benming,
        yao_study=yao_study,
    )


if __name__ == "__main__":
    import sys
    from datetime import datetime
    day = datetime.strptime(sys.argv[1], "%Y-%m-%d") if len(sys.argv) > 1 \
        else datetime.now()
    d = daily_block(day, personal="demo", day_master_wx="金", yong_shen=["水", "木", "火"])
    print("=" * 66)
    print(f"本卦 {d['symbol']} {d['name']}（第{d['xu']}卦）")
    print(f"  上{d['upper']}　下{d['lower']}")
    print(f"  卦辞：{d['ci']}")
    print(f"  白话：{d['ci_bai']}")
    print(f"  大象：{d['xiang']}")
    print("-" * 66)
    print("  爻象（自下而上）：")
    for i, y in enumerate(d["yao_study"]):
        mark = " ← 动" if y["dong"] else ""
        yang = d["yin_yang"][i] == 1
        print(f"    {y['pos']}爻 {'▅▅▅' if yang else '▅ ▅'} "
              f"{y['name']:>3} {y['dewei']}{mark}　{y['text']}")
    print("-" * 66)
    if d["bian"]:
        print(f"  之卦 {d['bian']['symbol']} {d['bian']['name']}：{d['bian']['ci']}")
    if d["hu"]:
        print(f"  互卦 {d['hu']['symbol']} {d['hu']['name']}")
    print(f"  错卦 {d['cuo']['symbol']} {d['cuo']['name']}　综卦 {d['zong']['symbol']} {d['zong']['name']}")
    print("-" * 66)
    print(f"  断法：{d['method']}")
    print(f"  主断：{d['judge_src']}　{d['judge_text']}")
    print(f"  倾向：{d['tendency']}　{d['tend_note']}")
    print("-" * 66)
    for x in d["analysis"]:
        print("  ·", x)
    for x in d["benming"]:
        print("  ◈", x)
    print("-" * 66)
    print(f"  义理：{d['yi']}")
    print(f"  日用：{d['yong']}")
