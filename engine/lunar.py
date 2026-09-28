# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.lunar
农历推算（供梅花易数、六爻起卦使用）。

不依赖任何第三方农历数据包，直接用天文算法：
  1. 太阳视黄经（见 base）
  2. 月亮视黄经（Meeus《Astronomical Algorithms》低精度，误差约 10'，
     换算到朔时刻约 ±20 分钟，足以定朔日）
  3. 逐月求「日月同经」之时刻 = 朔
  4. 冬至所在朔月为农历十一月，据此后推正月
  5. 无中气之月置闰
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from .base import (
    jd_from_datetime, datetime_from_jd, sun_apparent_longitude,
    solar_term_jd, solar_term_datetime, ZHONGQI_TERMS, ensure_cst,
    TIAN_GAN, DI_ZHI,
)

SYNODIC = 29.530588853
MEAN_LON_RATE_D = 12.190749          # 月亮相对太阳的黄经日速(度/日)

_nm_cache: dict = {}


def moon_apparent_longitude(jd: float) -> float:
    """月亮视黄经(度)，低精度算法，误差约 10 角分"""
    T = (jd - 2451545.0) / 36525.0
    Lp = (218.3164477 + 481267.88123421 * T
          - 0.0015786 * T * T + T ** 3 / 538841.0 - T ** 4 / 65194000.0)
    M = (134.9633964 + 477198.8675055 * T
         + 0.0087414 * T * T + T ** 3 / 69699.0 - T ** 4 / 14712000.0)
    F = (93.2720950 + 483202.0175233 * T
         - 0.0036539 * T * T - T ** 3 / 3526000.0 + T ** 4 / 863310000.0)
    D = (297.8501921 + 445267.1114034 * T
         - 0.0018819 * T * T + T ** 3 / 545868.0 - T ** 4 / 113065000.0)
    Mr = math.radians(M % 360.0)
    Dr = math.radians(D % 360.0)
    Fr = math.radians(F % 360.0)
    lam = (Lp
           + 6.288774 * math.sin(Mr)
           + 1.274027 * math.sin(2 * Dr - Mr)
           + 0.658314 * math.sin(2 * Dr)
           + 0.213618 * math.sin(2 * Mr)
           - 0.185116 * math.sin(math.radians(357.52911 + 35999.05029 * T))
           - 0.114332 * math.sin(2 * Fr)
           + 0.058793 * math.sin(2 * Dr - 2 * Mr)
           + 0.057066 * math.sin(2 * Dr - Mr + 0)  # 0.057066*sin(2D-M-S) 近似
           + 0.053322 * math.sin(2 * Dr + Mr)
           + 0.045758 * math.sin(2 * Dr - 3 * Mr + 0))
    return lam % 360.0


def _angdiff(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0


def find_new_moon(jd_guess: float) -> float:
    """从近似值出发，牛顿迭代求日月同经之朔"""
    jd = jd_guess
    for _ in range(10):
        d = _angdiff(moon_apparent_longitude(jd), sun_apparent_longitude(jd))
        step = d / MEAN_LON_RATE_D
        jd -= step
        if abs(step) < 1e-6:
            break
    return jd


def new_moons_between(jd0: float, jd1: float) -> List[float]:
    """返回落在 [jd0, jd1] 内的所有朔时刻。
    注意：k 范围须放宽 ±2，因为平均朔公式与实际朔最多差约 14 小时，
    若只用 guess 做边界过滤会漏掉边界朔。"""
    k0 = int(math.floor((jd0 - 2451550.09765) / SYNODIC)) - 2
    k1 = int(math.ceil((jd1 - 2451550.09765) / SYNODIC)) + 2
    res: List[float] = []
    for k in range(k0, k1 + 1):
        if k in _nm_cache:
            nm = _nm_cache[k]
        else:
            nm = find_new_moon(2451550.09765 + SYNODIC * k)
            _nm_cache[k] = nm
        if jd0 <= nm <= jd1:
            res.append(nm)
    return res


def _midnight_of(dt: datetime) -> datetime:
    """北京时间当日零点"""
    dt = ensure_cst(dt)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


class LunarDate:
    __slots__ = ("year", "month", "day", "leap", "gz_year", "gz_month", "gz_day",
                 "month_len", "suishi_name")

    def __init__(self, year, month, day, leap, gz_year, gz_month, gz_day, month_len, suishi_name):
        self.year = year
        self.month = month
        self.day = day
        self.leap = leap
        self.gz_year = gz_year
        self.gz_month = gz_month
        self.gz_day = gz_day
        self.month_len = month_len
        self.suishi_name = suishi_name

    def __repr__(self):
        leap = "闰" if self.leap else ""
        return (f"农历{self.gz_year}年{leap}{self.month}月{self.day}日 "
                f"(初一干支{self.gz_month}·{self.suishi_name})")

    @property
    def label(self) -> str:
        leap = "闰" if self.leap else ""
        return f"{leap}{self.month}月{self.day}日"


_LUNAR_MONTH_NAME = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]

# 地支序号 1..12 (子=1)，供起卦使用
ZHI_SEQ = {z: i + 1 for i, z in enumerate(DI_ZHI)}


# 中气 -> 农历月序
def _zhongqi_in(jd_start: float, jd_end: float, year_span: Tuple[int, int]) -> Optional[str]:
    """找出落在 [jd_start, jd_end) 区间的中气名"""
    for y in range(year_span[0], year_span[1] + 1):
        for name in ZHONGQI_TERMS:
            jd = solar_term_jd(y, name)
            if jd_start <= jd < jd_end:
                return name
    return None


ZQ_MONTH = {"雨水": 1, "春分": 2, "谷雨": 3, "小满": 4, "夏至": 5,
            "大暑": 6, "处暑": 7, "秋分": 8, "霜降": 9, "小雪": 10,
            "冬至": 11, "大寒": 12}


def _month_index_containing(nms: List[float], jd: float) -> Optional[int]:
    for i in range(len(nms) - 1):
        if nms[i] <= jd < nms[i + 1]:
            return i
    return None


def build_lunar_calendar(dt: datetime) -> Tuple[List[Tuple[int, int, bool, float]], int]:
    """
    构造目标日所属农历年的月份表。
    返回 ([(朔索引, 月序, 是否闰, 朔JD)], 该农历年首个朔月在 nms 中的总体偏移)
    """
    from .base import jd_from_datetime
    # 范围须覆盖「上一农历年冬至之前的那个朔」，故向前提足 500 天
    jd = jd_from_datetime(ensure_cst(dt))
    nms = new_moons_between(jd - 500, jd + 80)
    nms.sort()
    # 农历月以「朔所在的那一日」为初一：故把朔时刻落到当日零点后再分月
    starts = [_midnight_of(datetime_from_jd(x)) for x in nms]

    def zheng_idx_for(y: int) -> Optional[int]:
        """农历 y 年的正月朔月索引 = 含冬至(y-1)的朔月 + 2"""
        w = solar_term_jd(y - 1, "冬至")
        i = _month_index_containing(nms, w)
        if i is None or i + 2 >= len(nms):
            return None
        return i + 2

    cur_i = _month_index_containing(starts, _midnight_of(ensure_cst(dt)))
    if cur_i is None:
        cur_i = len(nms) - 1

    year = dt.year
    zidx = zheng_idx_for(year)
    # 目标日若早于本年正月，则归属上一农历年
    if zidx is None or cur_i < zidx:
        year -= 1
        zidx = zheng_idx_for(year)
    if zidx is None:
        raise ValueError("农历推算失败：无法确定正月")

    months: List[Tuple[int, int, bool, float]] = []
    i = zidx
    prev_num = 12
    for _ in range(16):
        s = nms[i]
        e = nms[i + 1] if i + 1 < len(nms) else s + SYNODIC
        zq = _zhongqi_in(s, e, (year - 1, year + 1))
        if zq is None:
            months.append((i, prev_num, True, s))
        else:
            prev_num = ZQ_MONTH[zq]
            months.append((i, prev_num, False, s))
            if prev_num == 12 and zq is not None and i > zidx:
                # 腊月之后即为下一农历年正月，收尾
                i += 1
                break
        i += 1
        if i >= len(nms) - 1:
            break
    return months, cur_i, nms


def lunar_info(dt: datetime) -> LunarDate:
    dt = ensure_cst(dt)
    from .base import jd_from_datetime, year_gz_by_lichun, day_gz, month_gz_by_jie
    jd = jd_from_datetime(dt)
    months, cur_i, nms = build_lunar_calendar(dt)

    month_num, is_leap = 1, False
    month_jd = nms[cur_i]
    for (midx, mnum, leap, sjd) in months:
        if midx == cur_i:
            month_num, is_leap, month_jd = mnum, leap, sjd
            break

    # 农历日：以朔时刻所在的「北京日」为初一，按日期差计算
    month_day0 = _midnight_of(datetime_from_jd(month_jd))
    day0 = _midnight_of(dt)
    lunar_day = (day0 - month_day0).days + 1
    month_len = int(round((nms[cur_i + 1] - month_jd))) if cur_i + 1 < len(nms) else 30

    gy = year_gz_by_lichun(dt)
    gz_year = TIAN_GAN[gy % 10] + DI_ZHI[gy % 12]
    gd = day_gz(dt)
    gz_day = TIAN_GAN[gd % 10] + DI_ZHI[gd % 12]
    gm_idx = month_gz_by_jie(datetime_from_jd(month_jd))
    gz_month = TIAN_GAN[gm_idx % 10] + DI_ZHI[gm_idx % 12]

    return LunarDate(
        year=dt.year, month=month_num, day=lunar_day, leap=is_leap,
        gz_year=gz_year, gz_month=gz_month, gz_day=gz_day,
        month_len=month_len,
        suishi_name=_LUNAR_MONTH_NAME[(month_num - 1) % 12],
    )


def lunar_numbers(dt: datetime) -> Tuple[int, int, int, int]:
    """
    供起卦使用：(农历年地支序号, 农历月数, 农历日数, 时辰地支序号)
    """
    from .base import hour_zhi, year_gz_by_lichun
    lu = lunar_info(dt)
    return (ZHI_SEQ[DI_ZHI[year_gz_by_lichun(dt) % 12]], lu.month, lu.day,
            hour_zhi(dt) + 1)


if __name__ == "__main__":
    from datetime import datetime
    for d in [datetime(2000, 1, 1, 12, 0), datetime(2026, 9, 28, 8, 0),
              datetime(2026, 2, 17, 12, 0), datetime(2000, 2, 16, 12, 0),
              datetime(2025, 1, 29, 12, 0)]:
        lu = lunar_info(d)
        print(d.strftime("%Y-%m-%d"), "->", lu, "| 起卦数", lunar_numbers(d))
