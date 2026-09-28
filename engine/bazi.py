# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.bazi
八字排盘 / 大运 / 流年 / 流日 引擎。

包含：
  - 四柱、藏干通根、十神、纳音、十二长生
  - 主要神煞（天乙、太极、文昌、驿马、桃花、华盖、禄、羊刃、魁罡等）
  - 日主强弱量化（得令/得地/得势 + 刑冲合会修正）
  - 格局判定（正官/七杀/正财/偏财/食神/伤官/印/建禄/从格）
  - 用神 / 喜神 / 忌神
  - 大运起运（三天折一岁）与流年流月流日
  - 单日流日 vs 命局生克打分
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from .base import (
    TIAN_GAN, DI_ZHI, JIA_ZI, GAN_WX, ZHI_WX, GAN_YANG, ZHI_YANG,
    WX_SHENG, WX_SHENG_BY, WX_KE, WX_KE_BY, WX_INDEX,
    ZHI_CANGGAN, CANGGAN_WEIGHT, NA_YIN, CHANGSHENG_12, GAN_CHANGSHENG,
    JIE_TERMS, hour_zhi, hour_gz, day_gz, year_gz_by_lichun, month_gz_by_jie,
    solar_term_datetime, next_jie, current_jie, year_terms,
    ten_god, changsheng_stage, gan_wuxing, zhi_wuxing, clamp, ensure_cst,
)

# ---------------------------------------------------------------- 神煞表

TIANYI_GUI = {  # 天乙贵人: 日干 -> 地支
    "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
    "乙": ["子", "申"], "己": ["子", "申"],
    "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "壬": ["巳", "卯"], "癸": ["巳", "卯"],
    "辛": ["午", "寅"],
}
TAIJI = {
    "甲": ["子", "午"], "乙": ["子", "午"],
    "丙": ["卯", "酉"], "丁": ["卯", "酉"],
    "戊": ["辰", "戌", "丑", "未"], "己": ["辰", "戌", "丑", "未"],
    "庚": ["寅", "亥"], "辛": ["寅", "亥"],
    "壬": ["巳", "申"], "癸": ["巳", "申"],
}
WENCHANG = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
    "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}
LU_SHEN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
           "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
YANG_REN = {"甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
            "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥"}
YI_MA = {"申": "寅", "子": "寅", "辰": "寅", "辰3": None,  # 申子辰马在寅
         "寅": "申", "午": "申", "戌": "申",
         "巳": "亥", "酉": "亥", "丑": "亥",
         "亥": "巳", "卯": "巳", "未": "巳"}
TAOHUA = {"申": "酉", "子": "酉", "辰": "酉",
          "寅": "卯", "午": "卯", "戌": "卯",
          "巳": "午", "酉": "午", "丑": "午",
          "亥": "子", "卯": "子", "未": "子"}
HUAGAI = {"寅": "戌", "午": "戌", "戌": "戌",
          "亥": "未", "卯": "未", "未": "未",
          "申": "辰", "子": "辰", "辰": "辰",
          "巳": "丑", "酉": "丑", "丑": "丑"}
KUIGANG = ["庚辰", "庚戌", "壬辰", "戊戌"]   # 魁罡日

# 地支六合 / 三合 / 六冲 / 相刑 / 相害
LIUHE = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"),
         ("巳", "申"), ("午", "未")]
LIUHE_MAP = {}
for _a, _b in LIUHE:
    LIUHE_MAP[_a] = _b
    LIUHE_MAP[_b] = _a
LIUCHONG = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"),
            ("辰", "戌"), ("巳", "亥")]
SANHE = [("申", "子", "辰", "水"), ("亥", "卯", "未", "木"),
         ("寅", "午", "戌", "火"), ("巳", "酉", "丑", "金")]
SHEHUI = [("亥", "子", "丑", "水"), ("寅", "卯", "辰", "木"),
          ("巳", "午", "未", "火"), ("申", "酉", "戌", "金")]
LIUHAI = [("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"),
          ("申", "亥"), ("酉", "戌")]
ZIXING = [("辰", "辰"), ("午", "午"), ("酉", "酉"), ("亥", "亥")]

TEN_GOD_SCORE = {
    "正印": 8.0, "偏印": 6.0, "比肩": 6.0, "劫财": 5.0,
    "食神": -2.0, "伤官": -3.0, "正财": -4.0, "偏财": -3.5,
    "正官": -5.0, "七杀": -6.0,
}


# ---------------------------------------------------------------- 数据结构


@dataclass
class Pillar:
    pos: str                     # 年/月/日/时
    idx: int
    gan: str
    zhi: str
    ten_god: str
    nayin: str
    cs: str = ""                 # 日干在此支的十二长生
    canggan: List[Tuple[str, str, float]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return JIA_ZI[self.idx]


@dataclass
class DaYun:
    seq: int
    idx: int
    start_age: float
    end_age: float
    start_date: datetime
    ten_god: str
    nayin: str

    @property
    def name(self) -> str:
        return JIA_ZI[self.idx]


@dataclass
class BaZiResult:
    pillars: Dict[str, Pillar]
    day_master: str
    strength: float
    strength_label: str
    pattern: str
    pattern_detail: str
    yong_shen_wx: List[str]
    xi_shen_wx: List[str]
    ji_shen_wx: List[str]
    dayun: List[DaYun]
    current_dayun: Optional[DaYun]
    qiyun_date: Optional[datetime]
    liunian_idx: int
    stars_all: Dict[str, List[str]]
    analysis: Dict = field(default_factory=dict)


# ---------------------------------------------------------------- 排盘


def build_pillar(pos: str, idx: int, day_idx: int) -> Pillar:
    gan = TIAN_GAN[idx % 10]
    zhi = DI_ZHI[idx % 12]
    dm = TIAN_GAN[day_idx % 10]
    tg = "日主" if pos == "日" else ten_god(dm, gan)
    cg = []
    for cgan, cw in zip(ZHI_CANGGAN[zhi], CANGGAN_WEIGHT[zhi]):
        cg.append((cgan, ten_god(dm, cgan), cw))
    return Pillar(
        pos=pos, idx=idx, gan=gan, zhi=zhi, ten_god=tg,
        nayin=NA_YIN[JIA_ZI[idx]],
        cs=changsheng_stage(dm, zhi) if pos != "日" else "-",
        canggan=cg,
    )


def paipan(dt: datetime, longitude: float = 120.00) -> Tuple[Dict[str, Pillar], datetime]:
    """排四柱，返回 (四柱, 真太阳时)"""
    from .base import true_solar_time
    dt = ensure_cst(dt)
    tst = true_solar_time(dt, longitude)
    y = year_gz_by_lichun(tst)
    m = month_gz_by_jie(tst)
    d = day_gz(tst)
    hz = hour_zhi(tst)
    h = hour_gz(d, hz)
    return {
        "年": build_pillar("年", y, d),
        "月": build_pillar("月", m, d),
        "日": build_pillar("日", d, d),
        "时": build_pillar("时", h, d),
    }, tst


# ---------------------------------------------------------------- 神煞


def compute_stars(pillars: Dict[str, Pillar]) -> Dict[str, List[str]]:
    day = pillars["日"]
    year_z = pillars["年"].zhi
    month_z = pillars["月"].zhi
    day_z = pillars["日"].zhi
    hour_z_str = pillars["时"].zhi
    all_zhi = [year_z, month_z, day_z, hour_z_str]
    dm = day.gan
    res: Dict[str, List[str]] = {k: [] for k in ["年", "月", "日", "时"]}

    def put(pos_list, star, target):
        for p in pos_list:
            if p in res:
                res[p].append(star)

    for pos, p in pillars.items():
        z = p.zhi
        if z in TIANYI_GUI.get(p.gan, []):
            res[pos].append("天乙贵人")
        if z in TAIJI.get(p.gan, []):
            res[pos].append("太极贵人")
        if z == WENCHANG.get(p.gan, ""):
            res[pos].append("文昌贵人")
        if z == LU_SHEN.get(p.gan, ""):
            res[pos].append("禄神")
        if z == YANG_REN.get(p.gan, ""):
            res[pos].append("羊刃")
        others = [x for kk, x in zip(["年","月","日","时"], all_zhi) if kk != pos]
        if YI_MA.get(z) and YI_MA[z] in others:
            res[pos].append("驿马")
        if TAOHUA.get(z) and TAOHUA[z] in others:
            res[pos].append("桃花")
        if HUAGAI.get(z) and HUAGAI[z] in others:
            res[pos].append("华盖")

    if day.name in KUIGANG:
        res["日"].append("魁罡")
    # 日贵：丁酉、丁亥、癸巳、癸卯
    if day.name in ["丁酉", "丁亥", "癸巳", "癸卯"]:
        res["日"].append("日贵")

    return res


# ---------------------------------------------------------------- 强弱


# 十二长生 -> 根气强度系数。帝旺/临官/长生为实根，绝/墓为虚根。
CS_ROOT_W = {"长生": 1.30, "沐浴": 1.00, "冠带": 1.25, "临官": 1.30,
             "帝旺": 1.35, "衰": 0.85, "病": 0.60, "死": 0.50,
             "墓": 0.40, "绝": 0.35, "胎": 0.50, "养": 0.90}

# 燥土(未/戌)含火气，古法云「燥土脆金不生金」；湿土(辰/丑)方能真生金。
DRY_EARTH = ("未", "戌")
WET_EARTH = ("辰", "丑")


def compute_strength(pillars: Dict[str, Pillar]) -> Tuple[float, Dict]:
    dm = pillars["日"].gan
    dmwx = gan_wuxing(dm)
    month_z = pillars["月"].zhi
    month_wx = zhi_wuxing(month_z)
    detail: Dict = {}
    score = 50.0

    # 1) 月令「旺相休囚死」（较得令/失令二分更符合子平法）
    if month_wx == dmwx:
        cmd, v = "旺(月令同气)", 26.0
    elif month_wx == WX_SHENG_BY[dmwx]:
        cmd, v = "相(月令生我)", 17.0
        # 燥土不生金：金日主逢未/戌月，生扶之力大打折扣
        if dmwx == "金" and month_z in DRY_EARTH:
            v = 9.0
            cmd = "相(燥土脆金，生扶减半)"
    elif month_wx == WX_SHENG[dmwx]:
        cmd, v = "休(我生月令)", -8.0
    elif month_wx == WX_KE[dmwx]:
        cmd, v = "囚(我克月令)", -12.0
    else:
        cmd, v = "死(月令克我)", -24.0
    score += v
    detail["月令"] = cmd

    # 2) 通根 —— 帮扶与克泄耗对称计分（旧版只加不减，导致辛金误判身极旺）
    root = 0.0
    for pos in ["年", "月", "日", "时"]:
        z = pillars[pos].zhi
        base = 20.0 if pos == "日" else 13.0
        cs = CS_ROOT_W.get(changsheng_stage(dm, z), 1.0)
        for g, tg, w in pillars[pos].canggan:
            gwx = gan_wuxing(g)
            if gwx == dmwx:                       # 同我(比劫)之根
                root += w * base * cs
            elif gwx == WX_SHENG_BY[dmwx]:        # 生我(印)之根
                k = 0.50
                if dmwx == "金" and z in DRY_EARTH:
                    k *= 0.55                     # 燥土脆金
                elif dmwx == "金" and z in WET_EARTH:
                    k *= 1.15                     # 湿土生金
                root += w * base * k
            elif gwx == WX_SHENG[dmwx]:           # 我生(食伤)泄
                root -= w * base * 0.30
            elif gwx == WX_KE[dmwx]:              # 我克(财)耗
                root -= w * base * 0.28
            elif gwx == WX_KE_BY[dmwx]:           # 克我(官杀)损
                root -= w * base * 0.45
    score += root
    detail["通根分"] = round(root, 1)
    detail["日主根气"] = f"{dm}在{month_z}({changsheng_stage(dm, month_z)})"

    # 3) 天干帮扶/克泄耗
    gan_score = 0.0
    for pos in ["年", "月", "时"]:
        tg = pillars[pos].ten_god
        gan_score += TEN_GOD_SCORE.get(tg, 0.0) * (1.3 if pos == "月" else 1.0)
    score += gan_score
    detail["天干分"] = round(gan_score, 1)

    # 4) 地支刑冲合会修正
    zhis = {pos: pillars[pos].zhi for pos in ["年", "月", "日", "时"]}
    combos = []
    zs = list(zhis.items())
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = zs[i][1], zs[j][1]
            if LIUHE_MAP.get(a) == b:
                combos.append(f"{a}{b}六合")
                if zhi_wuxing(a) == dmwx or zhi_wuxing(b) == dmwx:
                    score += 4
                elif zhi_wuxing(a) == WX_SHENG_BY[dmwx] or zhi_wuxing(b) == WX_SHENG_BY[dmwx]:
                    score += 2
            for grp, wx in [(g[0:3], g[3]) for g in SANHE]:
                if a in grp and b in grp:
                    combos.append("".join(grp) + "半合")
                    if wx == dmwx:
                        score += 5
            for ch in LIUCHONG:
                if (a, b) == ch or (b, a) == ch:
                    combos.append(f"{a}{b}六冲")
                    score -= 3
    # 三合/三会全
    for grp, wx in [(g[0:3], g[3]) for g in SANHE]:
        if all(x in zhis.values() for x in grp):
            combos.append("".join(grp) + "三合")
            score += 10 if wx == dmwx else -3
    for grp, wx in [(g[0:3], g[3]) for g in SHEHUI]:
        if all(x in zhis.values() for x in grp):
            combos.append("".join(grp) + "三会")
            score += 14 if wx == dmwx else -5
    detail["刑冲合会"] = combos

    score = clamp(score, 5, 95)
    return score, detail


def _strength_label(s: float) -> str:
    if s >= 72:
        return "身极旺"
    if s >= 64:
        return "身旺"
    if s >= 56:
        return "中和偏强"
    if s >= 47:
        return "中和"
    if s >= 39:
        return "中和偏弱"
    if s >= 30:
        return "身弱"
    return "身极弱"


# ---------------------------------------------------------------- 格局用神


def judge_pattern(pillars: Dict[str, Pillar], strength: float) -> Tuple[str, str]:
    month_z = pillars["月"].zhi
    month_zg = ZHI_CANGGAN[month_z]
    benergy = month_zg[0]
    bwx = gan_wuxing(benergy)
    dm = pillars["日"].gan
    dmwx = gan_wuxing(dm)

    tgs = [pillars[p].ten_god for p in ["年", "月", "时"]]
    # 月令本气透干?
    trans = []
    for p in ["年", "月", "时"]:
        if pillars[p].gan == benergy:
            trans.append((p, pillars[p].ten_god))

    if strength <= 30:
        return ("从格", "日主极弱无根，宜顺势而从旺神，不可逆其旺气")

    if trans:
        pos, tg = trans[0]
        mapping = {
            "正官": "正官格", "七杀": "七杀格",
            "正财": "正财格", "偏财": "偏财格",
            "食神": "食神格", "伤官": "伤官格",
            "正印": "正印格", "偏印": "偏印格",
            "比肩": "建禄格", "劫财": "月刃格",
        }
        base = mapping.get(tg, "杂气格")
    else:
        base = "杂气格"

    extra = []
    gods = set(tgs)
    if "伤官" in gods and ("正印" in gods or "偏印" in gods):
        extra.append("伤官配印")
    if "食神" in gods and "七杀" in gods:
        extra.append("食神制杀")
    if "伤官" in gods and "正财" in gods:
        extra.append("伤官生财")
    if "正官" in gods and "正印" in gods:
        extra.append("官印相生")
    if "偏财" in gods and "七杀" in gods:
        extra.append("财生杀党")

    pattern = base + ("·" + "+".join(extra) if extra else "")
    detail = f"月令{month_z}本气{benergy}({ten_god(dm, benergy)})"
    if trans:
        detail += f"，透于{trans[0][0]}干"
    detail += f"；天干并见{'、'.join(sorted(gods))}"
    return pattern, detail


def compute_yongshen(pillars: Dict[str, Pillar], strength: float
                     ) -> Tuple[List[str], List[str], List[str]]:
    """
    扶抑为主的用神取法(辅以调候)：身弱取印比，身旺取官杀食伤财。
    返回 (用神, 喜神, 忌神) 五行列表。
    """
    dm = pillars["日"].gan
    dmwx = gan_wuxing(dm)
    sheng_me = WX_SHENG_BY[dmwx]
    tong_me = dmwx
    xie_me = WX_SHENG[dmwx]
    hao_me = WX_KE[dmwx]
    ke_me = WX_KE_BY[dmwx]

    month_z = pillars["月"].zhi
    # 调候倾向：冬生(亥子丑月)喜火，夏生(巳午未月)喜水
    tiaohou = []
    if month_z in ["亥", "子", "丑"]:
        tiaohou.append("火")
    elif month_z in ["巳", "午", "未"]:
        tiaohou.append("水")

    if strength < 52:        # 中和偏弱及以下：扶抑取印比
        yong = [sheng_me, tong_me]
        xi = list(dict.fromkeys(tiaohou + [sheng_me, tong_me]))
        ji = [hao_me, ke_me, xie_me]
    elif strength > 65:      # 身旺：抑
        yong = [ke_me, xie_me, hao_me]
        xi = list(dict.fromkeys(tiaohou + [xie_me, ke_me]))
        ji = [sheng_me, tong_me]
    else:                    # 中和：平衡，略扶
        yong = list(dict.fromkeys([sheng_me] + tiaohou))
        xi = [tong_me, sheng_me]
        ji = [hao_me, ke_me]

    def dedup(v):
        out = []
        for x in v:
            if x not in out:
                out.append(x)
        return out

    return dedup(yong), dedup(xi), dedup([j for j in ji if j not in dedup(yong)])


# ---------------------------------------------------------------- 大运


def build_dayun(birth_tst: datetime, month_idx: int, year_idx: int,
                day_idx: int, male: bool = True,
                max_steps: int = 9) -> Tuple[List[DaYun], datetime]:
    """
    三天折一岁。阳年男顺 / 阴年女顺；阳年女逆 / 阴年男逆。
    返回 (大运列表, 起运日)
    """
    year_gan_yang = GAN_YANG[year_idx % 10]
    forward = (year_gan_yang == male)   # 阳男阴女顺，阴男阳女逆

    terms = year_terms(birth_tst.year)
    if forward:
        target_name, target_t = None, None
        for name, t in terms:
            if t > birth_tst and name in JIE_TERMS:
                target_name, target_t = name, t
                break
        if target_t is None:
            terms2 = year_terms(birth_tst.year + 1)
            for name, t in terms2:
                if name in JIE_TERMS:
                    target_name, target_t = name, t
                    break
    else:
        target_name, target_t = None, None
        for name, t in terms:
            if t <= birth_tst and name in JIE_TERMS:
                target_name, target_t = name, t
        if target_t is None:
            terms2 = year_terms(birth_tst.year - 1)
            for name, t in reversed(terms2):
                if name in JIE_TERMS:
                    target_name, target_t = name, t
                    break

    delta = abs((target_t - birth_tst).total_seconds()) / 86400.0
    qiyun_age = delta / 3.0
    qiyun_date = birth_tst + timedelta(days=delta * 121.75)  # 一天折四月(=1/3年)

    dayun_list: List[DaYun] = []
    for i in range(1, max_steps + 1):
        offset = i if forward else -i
        idx = (month_idx + offset) % 60
        start_age = qiyun_age + (i - 1) * 10
        dm = TIAN_GAN[day_idx % 10]
        dayun_list.append(DaYun(
            seq=i, idx=idx,
            start_age=round(start_age, 2),
            end_age=round(start_age + 10, 2),
            start_date=qiyun_date + timedelta(days=(i - 1) * 3652.5),
            ten_god=ten_god(dm, TIAN_GAN[idx % 10]),
            nayin=NA_YIN[JIA_ZI[idx]],
        ))
    return dayun_list, qiyun_date


def pick_current_dayun(dayun: List[DaYun], now: datetime, qiyun_date: datetime) -> Optional[DaYun]:
    if now < qiyun_date:
        return None
    for d in dayun:
        if qiyun_date + timedelta(days=(d.seq - 1) * 3652.5) <= now < \
           qiyun_date + timedelta(days=d.seq * 3652.5):
            return d
    return dayun[-1]


# ---------------------------------------------------------------- 主入口


def analyze(dt: datetime, longitude: float = 120.00,
            now: Optional[datetime] = None, male: bool = True) -> BaZiResult:
    pillars, tst = paipan(dt, longitude)
    now = ensure_cst(now) if now else ensure_cst(dt)
    strength, sdetail = compute_strength(pillars)
    pattern, pdetail = judge_pattern(pillars, strength)
    yong, xi, ji = compute_yongshen(pillars, strength)

    day_idx = pillars["日"].idx
    month_idx = pillars["月"].idx
    year_idx = pillars["年"].idx

    dayun, qiyun = build_dayun(tst, month_idx, year_idx, day_idx, male=male)
    cur_dy = pick_current_dayun(dayun, now, qiyun)

    liunian = year_gz_by_lichun(now)
    stars = compute_stars(pillars)

    return BaZiResult(
        pillars=pillars,
        day_master=pillars["日"].gan,
        strength=round(strength, 1),
        strength_label=_strength_label(strength),
        pattern=pattern,
        pattern_detail=pdetail,
        yong_shen_wx=yong,
        xi_shen_wx=xi,
        ji_shen_wx=ji,
        dayun=dayun,
        current_dayun=cur_dy,
        qiyun_date=qiyun,
        liunian_idx=liunian,
        stars_all=stars,
        analysis={"detail": sdetail},
    )


# ---------------------------------------------------------------- 流日 vs 命局


def liuri_relation(res: BaZiResult, day_dt: datetime) -> Dict:
    """
    流日与命局的互动：天干十神、地支刑冲合害、对日主的扶抑。
    """
    dm = res.day_master
    day_idx = day_gz(day_dt)
    gan = TIAN_GAN[day_idx % 10]
    zhi = DI_ZHI[day_idx % 12]
    tg = ten_god(dm, gan)
    naphta = NA_YIN[JIA_ZI[day_idx]]

    hits = []
    for pos in ["年", "月", "日", "时"]:
        pz = res.pillars[pos].zhi
        if LIUHE_MAP.get(pz) == zhi:
            hits.append(f"流日{zhi}与{pos}支{pz}六合")
        for ch in LIUCHONG:
            if sorted([pz, zhi]) == sorted(ch):
                hits.append(f"流日{zhi}冲{pos}支{pz}")
        for hp in LIUHAI:
            if sorted([pz, zhi]) == sorted(hp):
                hits.append(f"流日{zhi}害{pos}支{pz}")

    gan_wx = gan_wuxing(gan)
    zhi_wx = zhi_wuxing(zhi)
    dmwx = gan_wuxing(dm)

    support = 0.0
    if gan_wx in res.yong_shen_wx:
        support += 14
    elif gan_wx in res.ji_shen_wx:
        support -= 12
    if zhi_wx in res.yong_shen_wx:
        support += 10
    elif zhi_wx in res.ji_shen_wx:
        support -= 9

    tg_effect = TEN_GOD_SCORE.get(tg, 0.0)
    support += tg_effect * 0.6

    for h in hits:
        if "六合" in h:
            support += 2
        elif "冲" in h:
            support -= 4
        elif "害" in h:
            support -= 2

    return {
        "gz": JIA_ZI[day_idx],
        "gan": gan,
        "zhi": zhi,
        "ten_god": tg,
        "nayin": naphta,
        "hits": hits,
        "raw_support": round(support, 1),
        "score": round(clamp(50 + 35 * math.tanh(support / 30.0), 6, 96), 1),
        "wuxing": {"天干": gan_wx, "地支": zhi_wx},
    }


if __name__ == "__main__":
    from datetime import datetime
    dt = datetime(2000, 1, 1, 12, 0)
    r = analyze(dt)
    print("四柱:", " ".join(f"{p.name}({p.ten_god})" for p in [r.pillars[k] for k in "年月日时"]))
    print("日主:", r.day_master, "| 强弱:", r.strength, r.strength_label)
    print("格局:", r.pattern)
    print("细节:", r.pattern_detail)
    print("用神:", r.yong_shen_wx, "喜:", r.xi_shen_wx, "忌:", r.ji_shen_wx)
    print("起运:", r.qiyun_date)
    print("大运:")
    for d in r.dayun:
        print(f"  {d.seq} {d.name}({d.ten_god}) {d.start_age}-{d.end_age}岁")
    print("当前大运:", r.current_dayun)
    print("神煞:", r.stars_all)
    print("流日:", liuri_relation(r, datetime(2026, 9, 28, 8, 0)))
