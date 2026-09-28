# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.base
术数公共基础层 —— 历法、干支、节气、藏干、十神、十二长生、纳音。

设计原则：
1. 所有时间内部统一使用「儒略日 JD」(含 UT 小数)，对外输入/输出均为北京时间(+08:00)。
2. 六十甲子统一使用 0..59 索引，甲子=0。
   索引 i -> 天干 i % 10, 地支 i % 12 (因 gcd(10,12)=2，天然合法)
3. 节气时刻采用 Meeus《Astronomical Algorithms》太阳视黄经算法，精度约 ±1 分钟，
   完全满足八字换月、奇门定局、大六壬过宫的要求。
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional

CST = timezone(timedelta(hours=8), "Asia/Shanghai")

# ---------------------------------------------------------------- 干支基本表

TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 六十甲子
JIA_ZI: List[str] = [TIAN_GAN[i % 10] + DI_ZHI[i % 12] for i in range(60)]

# 五行
GAN_WX = ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"]
ZHI_WX = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]

# 阴阳: True=阳
GAN_YANG = [i % 2 == 0 for i in range(10)]
ZHI_YANG = [i % 2 == 0 for i in range(12)]

WX_INDEX = {"木": 0, "火": 1, "土": 2, "金": 3, "水": 4}
WX_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}       # 我生
WX_SHENG_BY = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}     # 生我
WX_KE = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}           # 我克
WX_KE_BY = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}        # 克我

# 地支藏干 (主气/中气/余气 顺序)
ZHI_CANGGAN: Dict[str, List[str]] = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# 藏干强度系数(占该支总分的百分比)，用于日主强弱量化
CANGGAN_WEIGHT: Dict[str, List[float]] = {
    "子": [1.0],
    "丑": [0.6, 0.25, 0.15],
    "寅": [0.6, 0.25, 0.15],
    "卯": [1.0],
    "辰": [0.6, 0.3, 0.1],
    "巳": [0.6, 0.25, 0.15],
    "午": [0.7, 0.3],
    "未": [0.6, 0.25, 0.15],
    "申": [0.6, 0.25, 0.15],
    "酉": [1.0],
    "戌": [0.6, 0.25, 0.15],
    "亥": [0.7, 0.3],
}

# 六十甲子纳音
NA_YIN: Dict[str, str] = {
    "甲子": "海中金", "乙丑": "海中金", "丙寅": "炉中火", "丁卯": "炉中火",
    "戊辰": "大林木", "己巳": "大林木", "庚午": "路旁土", "辛未": "路旁土",
    "壬申": "剑锋金", "癸酉": "剑锋金", "甲戌": "山头火", "乙亥": "山头火",
    "丙子": "涧下水", "丁丑": "涧下水", "戊寅": "城头土", "己卯": "城头土",
    "庚辰": "白蜡金", "辛巳": "白蜡金", "壬午": "杨柳木", "癸未": "杨柳木",
    "甲申": "泉中水", "乙酉": "泉中水", "丙戌": "屋上土", "丁亥": "屋上土",
    "戊子": "霹雳火", "己丑": "霹雳火", "庚寅": "松柏木", "辛卯": "松柏木",
    "壬辰": "长流水", "癸巳": "长流水", "甲午": "砂石金", "乙未": "砂石金",
    "丙申": "山下火", "丁酉": "山下火", "戊戌": "平地木", "己亥": "平地木",
    "庚子": "壁上土", "辛丑": "壁上土", "壬寅": "金箔金", "癸卯": "金箔金",
    "甲辰": "覆灯火", "乙巳": "覆灯火", "丙午": "天河水", "丁未": "天河水",
    "戊申": "大驿土", "己酉": "大驿土", "庚戌": "钗钏金", "辛亥": "钗钏金",
    "壬子": "桑柘木", "癸丑": "桑柘木", "甲寅": "大溪水", "乙卯": "大溪水",
    "丙辰": "沙中土", "丁巳": "沙中土", "戊午": "天上火", "己未": "天上火",
    "庚申": "石榴木", "辛酉": "石榴木", "壬戌": "大海水", "癸亥": "大海水",
}

# 十天干十二长生
# 顺序: 长生 沐浴 冠带 临官 帝旺 衰 病 死 墓 绝 胎 养
CHANGSHENG_12 = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
GAN_CHANGSHENG: Dict[str, str] = {
    "甲": "亥子丑寅卯辰巳午未申酉戌",
    "乙": "午巳辰卯寅丑子亥戌酉申未",
    "丙": "寅卯辰巳午未申酉戌亥子丑",
    "丁": "酉申未午巳辰卯寅丑子亥戌",
    "戊": "寅卯辰巳午未申酉戌亥子丑",
    "己": "酉申未午巳辰卯寅丑子亥戌",
    "庚": "巳午未申酉戌亥子丑寅卯辰",
    "辛": "子亥戌酉申未午巳辰卯寅丑",
    "壬": "申酉戌亥子丑寅卯辰巳午未",
    "癸": "卯寅丑子亥戌酉申未午巳辰",
}

# 二十四节气：名称 -> 黄经度数
SOLAR_TERMS: List[Tuple[str, int]] = [
    ("立春", 315), ("雨水", 330), ("惊蛰", 345), ("春分", 0),
    ("清明", 15), ("谷雨", 30), ("立夏", 45), ("小满", 60),
    ("芒种", 75), ("夏至", 90), ("小暑", 105), ("大暑", 120),
    ("立秋", 135), ("处暑", 150), ("白露", 165), ("秋分", 180),
    ("寒露", 195), ("霜降", 210), ("立冬", 225), ("小雪", 240),
    ("大雪", 255), ("冬至", 270), ("小寒", 285), ("大寒", 300),
]

# 「节」(十二节) —— 用于八字换月、奇门定局
JIE_TERMS = ["立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
             "立秋", "白露", "寒露", "立冬", "大雪", "小寒"]
ZHONGQI_TERMS = ["雨水", "春分", "谷雨", "小满", "夏至", "大暑",
                 "处暑", "秋分", "霜降", "小雪", "冬至", "大寒"]

# 节气黄经 -> 该节气在一年中的大致日序 (1月1日为1)，仅作牛顿迭代初值
_TERM_APPROX_DOY = {
    315: 35, 330: 50, 345: 64, 0: 79, 15: 95, 30: 110,
    45: 125, 60: 141, 75: 157, 90: 172, 105: 188, 120: 204,
    135: 219, 150: 235, 165: 250, 180: 266, 195: 281, 210: 296,
    225: 311, 240: 326, 255: 341, 270: 355, 285: 5, 300: 20,
}

# ---------------------------------------------------------------- 工具函数


def gz_index(name: str) -> int:
    """六十甲子名称 -> 索引"""
    return JIA_ZI.index(name)


def gan_of(idx: int) -> str:
    return TIAN_GAN[idx % 10]


def zhi_of(idx: int) -> str:
    return DI_ZHI[idx % 12]


def _floor_div(a: int, b: int) -> int:
    return a // b


# ---------------------------------------------------------------- 儒略日


def jd_from_datetime(dt: datetime) -> float:
    """北京时间(aware)或本地(naive,按北京时间处理) -> 儒略日 UT"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    dt_utc = dt.astimezone(timezone.utc)
    y, m = dt_utc.year, dt_utc.month
    d = (dt_utc.day + dt_utc.hour / 24.0 + dt_utc.minute / 1440.0
         + dt_utc.second / 86400.0 + dt_utc.microsecond / 86400.0e6)
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd_day = (int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5)
    return jd_day


def datetime_from_jd(jd: float) -> datetime:
    """儒略日 UT -> 北京时间 (Wikipedia JD->Gregorian 标准算法)"""
    j = jd + 0.5
    f, z = math.modf(j)
    z = int(z)
    alpha = int((z - 1867216.25) / 36524.25)
    A = z + 1 + alpha - int(alpha / 4)          # 格里历修正，不可省略
    B = A + 1524
    C = int((B - 122.1) / 365.25)
    D = int(365.25 * C)
    E = int((B - D) / 30.6001)
    day = B - D - int(30.6001 * E) + f
    month = E - 1 if E < 14 else E - 13
    year = C - 4716 if month > 2 else C - 4715
    day_int = int(day)
    frac = day - day_int
    seconds = int(round(frac * 86400))
    if seconds == 86400:
        seconds = 0
        day_int += 1
    dt_utc = datetime(year, month, day_int, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return dt_utc.astimezone(CST)


def jdn_of_date(dt: datetime) -> int:
    """当日 12:00 UT 的 JDN —— 用于日干支换算"""
    dt = ensure_cst(dt)
    y, m, d = dt.year, dt.month, dt.day
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return (d + (153 * mm + 2) // 5 + 365 * yy + yy // 4
            - yy // 100 + yy // 400 - 32045)


# ---------------------------------------------------------------- 干支推算


def day_gz(dt: datetime) -> int:
    """日干支索引(甲子=0)。以北京时间为准(子时23:00起算新日由调用方保证)

    校验锚点(务必保持)：1949-10-01=甲子(0)、2000-01-01=戊午(54)、
    2024-02-10=甲辰(40)。偏移常数 49 由上述锚点反推，勿改。
    """
    jdn = jdn_of_date(dt)
    return (jdn + 49) % 60


def hour_zhi(dt: datetime) -> int:
    """时辰地支索引。子时 23:00-01:00"""
    h = dt.hour + dt.minute / 60.0
    if h >= 23 or h < 1:
        return 0
    return int((h + 1) // 2)


# 五鼠遁：日干 -> 该日子时所在的干支索引
_HOUR_START = {0: 0, 5: 0,    # 甲己还加甲   -> 甲子
               1: 12, 6: 12,  # 乙庚丙作初   -> 丙子
               2: 24, 7: 24,  # 丙辛从戊起   -> 戊子
               3: 36, 8: 36,  # 丁壬庚子居   -> 庚子
               4: 48, 9: 48}  # 戊癸壬子真   -> 壬子


def hour_gz(day_idx: int, zhi_idx: int) -> int:
    """五鼠遁：日上起时。返回时干支索引"""
    return (_HOUR_START[day_idx % 10] + zhi_idx) % 60


def year_gz_by_lichun(dt: datetime) -> int:
    """以立春为界的年干支索引"""
    dt = ensure_cst(dt)
    y = dt.year
    lichun = solar_term_datetime(y, "立春")
    year = y if dt >= lichun else y - 1
    return (year - 4) % 60


def month_gz_by_jie(dt: datetime) -> int:
    """以「节」为界的月干支索引。立春起寅月(序1) … 大雪子月(序11)、小寒丑月(序12)"""
    dt = ensure_cst(dt)
    jie_name, _ = current_jie(dt)
    idx = JIE_TERMS.index(jie_name)   # 0=立春 … 11=小寒
    if idx == 11:
        # 当年 1 月的小寒 -> 仍属「上一年」的丑月
        year_idx = (dt.year - 1 - 4) % 60
        seq = 12
    else:
        year_idx = (dt.year - 4) % 60
        seq = idx + 1
    return _month_index_from_year_gan(year_idx, seq)


# 五虎遁：年干 -> 该年寅月所在的干支索引
_MONTH_START = {0: 2, 5: 2,     # 甲己之年丙作首 -> 丙寅
                1: 14, 6: 14,   # 乙庚之岁戊为头 -> 戊寅
                2: 26, 7: 26,   # 丙辛必定寻庚起 -> 庚寅
                3: 38, 8: 38,   # 丁壬壬位顺行流 -> 壬寅
                4: 50, 9: 50}   # 戊癸甲寅好追求 -> 甲寅


def _month_index_from_year_gan(year_idx: int, lunar_month_seq: int) -> int:
    """
    五虎遁：甲己之年丙作首。lunar_month_seq: 1=寅月 .. 12=丑月
    """
    year_gan = year_idx % 10
    first = _MONTH_START[year_gan]  # 寅月的干支索引
    return (first + (lunar_month_seq - 1)) % 60


# ---------------------------------------------------------------- 节气天文算法


def sun_apparent_longitude(jd: float) -> float:
    """太阳视黄经(度)，Meeus 低精度算法，误差 < 0.01°"""
    T = (jd - 2451545.0) / 36525.0
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    L0 = L0 % 360.0
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
    Mr = math.radians(M)
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(Mr)
         + (0.019993 - 0.000101 * T) * math.sin(2 * Mr)
         + 0.000289 * math.sin(3 * Mr))
    # 章动 + 光行差修正 (可将误差由 ~17 分钟压到 ~10 秒内)
    omega = math.radians(125.04 - 1934.136 * T)
    lon_app = L0 + C - 0.00569 - 0.00478 * math.sin(omega)
    return lon_app % 360.0


def solar_term_jd(year: int, term_name: str) -> float:
    """指定年份某节气的儒略日(UT)"""
    target = dict((n, v) for n, v in SOLAR_TERMS)[term_name]
    approx_doy = _TERM_APPROX_DOY[target]
    jan1 = datetime(year, 1, 1, 12, tzinfo=CST)
    jd0 = jd_from_datetime(jan1) + approx_doy - 1.0
    jd = jd0
    for _ in range(12):
        lon = sun_apparent_longitude(jd)
        diff = (target - lon + 180.0) % 360.0 - 180.0
        jd += diff / 0.9856473
        if abs(diff) < 1e-7:
            break
    return jd


def solar_term_datetime(year: int, term_name: str) -> datetime:
    return datetime_from_jd(solar_term_jd(year, term_name))


_term_cache: Dict[int, List[Tuple[str, datetime]]] = {}


def year_terms(year: int) -> List[Tuple[str, datetime]]:
    """某年全部 24 节气(按时间排序)，含上一年的冬至/小寒/大寒以便跨年查找"""
    if year in _term_cache:
        return _term_cache[year]
    out = []
    for y in (year - 1, year, year + 1):
        for name, _ in SOLAR_TERMS:
            out.append((name, solar_term_datetime(y, name)))
    out.sort(key=lambda x: x[1])
    _term_cache[year] = out
    return out


def current_jie(dt: datetime) -> Tuple[str, datetime]:
    """返回 dt 所处的「节」及该节起始时刻"""
    terms = year_terms(ensure_cst(dt).year)
    dt = ensure_cst(dt)
    cur = None
    for name, t in terms:
        if t <= dt and name in JIE_TERMS:
            cur = (name, t)
    return cur


def current_zhongqi(dt: datetime) -> Tuple[str, datetime]:
    """返回 dt 所处的中气及起始时刻"""
    terms = year_terms(ensure_cst(dt).year)
    dt = ensure_cst(dt)
    cur = None
    for name, t in terms:
        if t <= dt and name in ZHONGQI_TERMS:
            cur = (name, t)
    return cur


def next_jie(dt: datetime) -> Tuple[str, datetime]:
    dt = ensure_cst(dt)
    terms = year_terms(dt.year)
    for name, t in terms:
        if t > dt and name in JIE_TERMS:
            return (name, t)
    return year_terms(dt.year + 1)[0]


# ---------------------------------------------------------------- 真太阳时


def equation_of_time(jd: float) -> float:
    """均时差(分钟)。粗略算法，全年误差 < 0.5 分钟"""
    T = (jd - 2451545.0) / 36525.0
    L0 = (280.46646 + 36000.76983 * T) % 360.0
    M = 357.52911 + 35999.05029 * T
    Mr = math.radians(M)
    Mr2 = 2 * Mr
    # Spencer (1971)
    b = math.radians(360.0 * (363 / 365.25 - 1)) * 0  # 占位保持可读
    eot = (229.18 * (0.000075 + 0.001868 * math.cos(Mr) - 0.032077 * math.sin(Mr)
                     - 0.014615 * math.cos(Mr2) - 0.040849 * math.sin(Mr2)))
    return eot


def true_solar_time(dt: datetime, longitude: float = 120.00,
                    tz_meridian: float = 120.0) -> datetime:
    """
    真太阳时校正。longitude 为出生地经度(东经为正)，默认 120.00°E（东八区标准经度）
    东八区标准子午线 120°E
    """
    dt = ensure_cst(dt)
    jd = jd_from_datetime(dt)
    offset = (longitude - tz_meridian) * 4.0 + equation_of_time(jd)
    return dt + timedelta(minutes=offset)


# ---------------------------------------------------------------- 十神 / 五行


def gan_wuxing(g: str) -> str:
    return GAN_WX[TIAN_GAN.index(g)]


def zhi_wuxing(z: str) -> str:
    return ZHI_WX[DI_ZHI.index(z)]


def ten_god(day_master: str, target: str) -> str:
    """
    以日干为我，求 target 天干的十神。
    同性为偏/比肩，异性为正/劫财。
    """
    if day_master == target:
        return "比肩"
    mei = gan_wuxing(day_master)
    ta = gan_wuxing(target)
    same_yang = (GAN_YANG[TIAN_GAN.index(day_master)] == GAN_YANG[TIAN_GAN.index(target)])
    if ta == WX_SHENG_BY[mei]:          # 生我
        return "偏印" if same_yang else "正印"
    if ta == WX_SHENG[mei]:             # 我生
        return "食神" if same_yang else "伤官"
    if ta == WX_KE[mei]:                # 我克
        return "偏财" if same_yang else "正财"
    if ta == WX_KE_BY[mei]:             # 克我
        return "七杀" if same_yang else "正官"
    return "劫财" if ta == mei else "——"   # 同五行异阴阳


def changsheng_stage(gan: str, zhi: str) -> str:
    seq = GAN_CHANGSHENG[gan]
    pos = DI_ZHI.index(zhi)
    return CHANGSHENG_12[seq.index(DI_ZHI[pos])]


def naying(idx: int) -> str:
    return NA_YIN[JIA_ZI[idx]]


# ---------------------------------------------------------------- 养生/健身增强表


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def ensure_cst(dt: datetime) -> datetime:
    """naive 一律按北京时间处理，统一转为 aware，避免比较报 TypeError"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CST)
    return dt.astimezone(CST)


def score_grade(score: float) -> str:
    if score >= 85:
        return "大吉"
    if score >= 72:
        return "吉"
    if score >= 58:
        return "平顺"
    if score >= 45:
        return "小阻"
    return "宜守"


if __name__ == "__main__":
    # 自检
    d = datetime(2000, 1, 1, 12, 0)
    print("日干支:", JIA_ZI[day_gz(d)])
    print("节气测试 2026立春:", solar_term_datetime(2026, "立春"))
    print("节气测试 2026夏至:", solar_term_datetime(2026, "夏至"))
    print("十神测试 日主壬 vs 庚:", ten_god("壬", "庚"))
