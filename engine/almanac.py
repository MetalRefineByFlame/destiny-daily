# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.almanac
「今日黄历」历注层 —— 每日宜忌 / 特殊忌日 / 神圣纪念日。

设计原则（与本项目其它模块一致）：
  1. 全部本地推算，不依赖任何第三方农历库、不联网。
     节气复用 base.solar_term_datetime（Meeus 太阳视黄经），
     农历复用 lunar.lunar_info（天文定朔 + 无中气置闰）。
  2. 只给「民俗择日参考」，不与五术模型算出的分数混在一起，
     渲染时独立成栏，措辞上与后文「日常生活宜忌」明确区分。
  3. 口径说明：神诞/忌日各家通书略有异同，本表取汉传佛历、
     道教《诸神圣诞日》与民间通行的《玉匣记》系谱，
     凡有异说者在 note 里标「一说」。闰月不重复过节、不计杨公忌。

对外只有一个入口：almanac_of(dt) -> dict
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .base import (
    DI_ZHI, JIA_ZI, day_gz, year_gz_by_lichun, current_jie,
    solar_term_datetime, ensure_cst,
)
from .lunar import lunar_info, LunarDate

# ---------------------------------------------------------------- 基础表

# 「节」→ 节气月支
_JIE_ZHI = {
    "立春": "寅", "惊蛰": "卯", "清明": "辰", "立夏": "巳",
    "芒种": "午", "小暑": "未", "立秋": "申", "白露": "酉",
    "寒露": "戌", "立冬": "亥", "大雪": "子", "小寒": "丑",
}

# 建除十二值神（以节气月支起建，逐日顺行；交节当日两月支同增一位，
# 故 (日支-月支) mod 12 天然实现「交节重复前一日值神」，无需特判）
JIANCHU = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]

_JC_YI = {
    "建": ["出行", "上任", "见贵", "求财", "立契", "祈福"],
    "除": ["除旧", "扫舍", "疗病", "拆卸", "理发", "解厄"],
    "满": ["祭祀", "祈福", "开市", "交易", "进人口", "栽种"],
    "平": ["修饰垣墙", "平治道涂", "安床", "嫁娶", "纳采", "绘塑"],
    "定": ["祭祀", "祈福", "订盟", "纳采", "嫁娶", "安床"],
    "执": ["捕捉", "收敛", "造屋", "立券", "祭祀", "修造"],
    "破": ["破屋坏垣", "求医治病", "拆卸", "除服"],
    "危": ["安床", "祭祀", "祈福", "静守", "修造"],
    "成": ["开市", "交易", "入学", "嫁娶", "动土", "安葬"],
    "收": ["纳财", "进人口", "栽种", "捕捉", "纳畜", "收账"],
    "开": ["祭祀", "祈福", "入学", "开市", "动土", "求医"],
    "闭": ["筑堤", "修补", "收敛", "埋穴", "安葬"],
}
_JC_JI = {
    "建": ["动土", "开仓", "乘船", "掘井"],
    "除": ["求官", "赴任", "嫁娶", "开市"],
    "满": ["服药", "安葬", "栽种", "针灸"],
    "平": ["开渠", "放水", "栽种", "掘井"],
    "定": ["诉讼", "出行", "就医", "争执"],
    "执": ["开市", "交易", "出行", "移徙"],
    "破": ["嫁娶", "开市", "动土", "出行", "签约", "搬迁"],
    "危": ["登高", "行船", "冒险", "竞速"],
    "成": ["诉讼", "争执", "拆卸"],
    "收": ["出行", "安葬", "开市", "放水"],
    "开": ["安葬", "放水", "掘井"],
    "闭": ["开市", "出行", "手术", "求医", "开业"],
}
_JC_NOTE = {
    "建": "万物生育、建基立业之始，宜开创不宜妄动土。",
    "除": "除旧布新之日，宜清扫、疗疾、去弊。",
    "满": "丰盈圆满之日，宜祈福求财，忌服药针砭。",
    "平": "平稳无波之日，宜修整、平治，忌开渠动水。",
    "定": "安定成形之日，宜订盟安床，忌争讼远行。",
    "执": "执守成规之日，宜收敛捕捉，忌开张移徙。",
    "破": "月建相冲之大耗日，只宜破旧，诸吉事不宜。",
    "危": "居高思危之日，宜静守安床，忌登高涉险。",
    "成": "天喜成就之日，百事多宜，为十二值神中的吉日。",
    "收": "收敛归仓之日，宜纳财收账，忌出行开张。",
    "开": "生气开启之日，宜开市入学，忌安葬放水。",
    "闭": "闭藏坚固之日，宜修补收敛，忌开张求医。",
}

# 黄道黑道十二神：以节气月支起青龙，按日支顺行
_HD = ["青龙", "明堂", "天刑", "朱雀", "金匮", "天德",
       "白虎", "玉堂", "天牢", "玄武", "司命", "勾陈"]
_HD_GOOD = {"青龙", "明堂", "金匮", "天德", "玉堂", "司命"}
# 子午月起申、丑未月起戌、寅申月起子、卯酉月起寅、辰戌月起辰、巳亥月起午
_HD_START = [9, 10, 0, 2, 4, 6, 9, 10, 0, 2, 4, 6]

# 彭祖百忌
_PZ_GAN = {
    "甲": "甲不开仓，财物耗散", "乙": "乙不栽植，千株不长",
    "丙": "丙不修灶，必见灾殃", "丁": "丁不剃头，头必生疮",
    "戊": "戊不受田，田主不祥", "己": "己不破券，二比并亡",
    "庚": "庚不经络，织机虚张", "辛": "辛不合酱，主人不尝",
    "壬": "壬不汲水，更难提防", "癸": "癸不词讼，理弱敌强",
}
_PZ_ZHI = {
    "子": "子不问卜，自惹祸殃", "丑": "丑不冠带，主不还乡",
    "寅": "寅不祭祀，神鬼不尝", "卯": "卯不穿井，水泉不香",
    "辰": "辰不哭泣，必主重丧", "巳": "巳不远行，财物伏藏",
    "午": "午不苫盖，屋主更张", "未": "未不服药，毒气入肠",
    "申": "申不安床，鬼祟入房", "酉": "酉不会客，醉坐颠狂",
    "戌": "戌不吃犬，作怪上床", "亥": "亥不嫁娶，不利新郎",
}

# 喜神方位（甲己艮、乙庚乾、丙辛坤、丁壬离、戊癸巽）
_XI_SHEN = {
    "甲": "东北（艮）", "己": "东北（艮）",
    "乙": "西北（乾）", "庚": "西北（乾）",
    "丙": "西南（坤）", "辛": "西南（坤）",
    "丁": "正南（离）", "壬": "正南（离）",
    "戊": "东南（巽）", "癸": "东南（巽）",
}

# 杨公十三忌（农历；闰月不计）
_YANG_GONG = {
    (1, 13), (2, 11), (3, 9), (4, 7), (5, 5), (6, 3),
    (7, 1), (7, 29), (8, 27), (9, 25), (10, 23),
    (11, 21), (12, 19),
}

# 十恶大败日
_SHI_E = {"甲辰", "乙巳", "丙申", "丁亥", "戊戌",
          "己丑", "庚辰", "辛巳", "壬申", "癸亥"}

# 四废日：季 → 忌见干支
_SI_FEI = {
    "春": {"庚申": "春月金气囚绝", "辛酉": "春月金气囚绝"},
    "夏": {"壬子": "夏月水气囚绝", "癸亥": "夏月水气囚绝"},
    "秋": {"甲寅": "秋月木气囚绝", "乙卯": "秋月木气囚绝"},
    "冬": {"丙午": "冬月火气囚绝", "丁巳": "冬月火气囚绝"},
}
# 天赦日（四季各一，最宜祈福解厄）
_TIAN_SHE = {"春": "戊寅", "夏": "甲午", "秋": "戊申", "冬": "甲子"}

_SANNIANG_DAYS = {3, 7, 13, 18, 22, 27}
_YUEJI_DAYS = {5, 14, 23}
_LIU_ZHAI_DAYS = {8, 14, 15, 23, 29, 30}       # 佛教六斋日
_SHI_ZHAI_DAYS = {1, 8, 14, 15, 18, 23, 24, 28, 29, 30}  # 十斋日


def _d(name: str, kind: str, note: str, important: bool = False) -> Dict:
    return {"name": name, "kind": kind, "note": note, "important": important}


# ---------------------------------------------------------------- 神圣纪念日表
# key = (农历月, 农历日)。同日多条并列。important=True 者进入「未来 7 天预告」。
DEITY_DAYS: Dict[Tuple[int, int], List[Dict]] = {
    (1, 1): [_d("弥勒菩萨圣诞", "佛菩萨", "宜礼佛、供灯、行善，全年第一吉日", True),
             _d("天腊之辰 · 春节", "道教 / 民俗", "五腊之首，宜祭祖敬天、斋戒祈福", True)],
    (1, 5): [_d("五路财神圣诞 · 迎财神", "民俗", "宜开市迎财，忌借贷、口舌", True)],
    (1, 8): [_d("顺星节 · 诸星君下降", "道教", "宜顺星祈福、静心斋戒")],
    (1, 9): [_d("玉皇上帝圣诞（天公生）", "道教", "宜敬天、祈福、斋戒；忌杀生、妄语", True)],
    (1, 15): [_d("上元节 · 天官大帝圣诞", "道教", "上元一品赐福天官，宜祈福、求嗣、燃灯", True),
              _d("元宵节", "民俗", "宜团圆、赏灯")],
    (1, 26): [_d("观音开库", "民俗", "宜祈财、行善还愿")],
    (2, 2): [_d("福德正神（土地公）圣诞", "民俗", "宜祭土地、做牙、祈宅安", True),
             _d("龙抬头 · 中和节", "民俗", "宜理发、开耕、祈丰年")],
    (2, 3): [_d("文昌帝君圣诞", "道教", "宜助学、拜文昌、读书立愿", True)],
    (2, 8): [_d("释迦牟尼佛出家日", "佛菩萨", "宜礼佛、斋戒、静修")],
    (2, 15): [_d("太上老君（道德天尊）圣诞", "道教", "宜诵经、斋戒、祈福", True),
              _d("释迦牟尼佛涅槃日", "佛菩萨", "宜礼佛、供灯、追思")],
    (2, 19): [_d("观世音菩萨圣诞", "佛菩萨", "宜礼佛、吃素、行善、求平安", True)],
    (2, 21): [_d("普贤菩萨圣诞", "佛菩萨", "宜礼佛、发愿、行愿")],
    (3, 3): [_d("真武大帝圣诞 · 上巳节", "道教", "宜祈福消灾、祓禊踏青", True)],
    (3, 15): [_d("保生大帝圣诞", "民俗", "宜祈健康、求医问药"),
              _d("武财神赵公明圣诞（一说）", "民俗", "宜求财、守正财")],
    (3, 20): [_d("注生娘娘圣诞", "民俗", "宜求嗣、祈母子平安")],
    (3, 23): [_d("天上圣母妈祖圣诞", "民俗", "闽台要日，宜进香、祈航海出行平安", True)],
    (3, 28): [_d("东岳大帝圣诞", "道教", "宜祈福消灾、慎终追远")],
    (4, 4): [_d("文殊菩萨圣诞", "佛菩萨", "宜礼佛、祈智慧、助学", True)],
    (4, 8): [_d("释迦牟尼佛圣诞 · 浴佛节", "佛菩萨", "宜浴佛、供灯、斋戒、行善", True)],
    (4, 14): [_d("孚佑帝君吕洞宾圣诞", "道教", "宜祈福、助学、行善")],
    (4, 15): [_d("佛吉祥日（卫塞节）", "佛菩萨", "汉传多取此日，宜礼佛斋戒")],
    (4, 18): [_d("碧霞元君（泰山娘娘）圣诞", "道教", "宜祈福、求嗣、保安康"),
              _d("华佗先师诞", "民俗", "宜祈健康")],
    (4, 28): [_d("药王孙思邈圣诞", "民俗", "宜祈健康、求医问药")],
    (5, 5): [_d("地腊之辰 · 端午节", "道教 / 民俗", "五腊之二，宜祭祖、驱邪、斋戒", True)],
    (5, 13): [_d("关圣帝君磨刀日（诞辰一说）", "民俗", "宜祈武运、守诚信；一说六月廿四为诞", True)],
    (5, 18): [_d("张天师圣诞（一说）", "道教", "宜祈福、斋戒")],
    (6, 6): [_d("天贶节 · 晒经节", "民俗", "宜晒书晒经、除霉")],
    (6, 19): [_d("观世音菩萨成道日", "佛菩萨", "宜礼佛、吃素、行善放生", True)],
    (6, 24): [_d("关圣帝君圣诞（通行本）", "民俗", "宜祭关帝、祈信义与武运", True),
              _d("九天应元雷声普化天尊（雷祖）圣诞", "道教", "宜祈福、避雷斋戒"),
              _d("二郎神诞（一说）", "民俗", "宜祈安")],
    (7, 7): [_d("道德腊之辰 · 七夕", "道教 / 民俗", "五腊之三，宜祈巧、拜魁星、斋戒", True),
             _d("魁星圣诞", "民俗", "宜拜魁星、祈文运")],
    (7, 15): [_d("中元节 · 地官大帝圣诞", "道教", "中元二品赦罪地官，宜祭祖、超荐、行善", True),
              _d("盂兰盆节 · 佛欢喜日", "佛菩萨", "宜供僧、报恩、斋戒")],
    (7, 18): [_d("瑶池金母（王母娘娘）圣诞（一说）", "道教", "宜祈福、祈寿")],
    (7, 22): [_d("增福财神李诡祖圣诞 · 财神节", "民俗", "宜祭财神、开市求财", True)],
    (7, 30): [_d("地藏王菩萨圣诞", "佛菩萨", "宜礼佛、斋戒、超荐、行善（月小取廿九）", True)],
    (8, 3): [_d("司命灶君圣诞（一说）", "民俗", "宜祭灶、祈家宅和顺")],
    (8, 15): [_d("太阴星君圣诞 · 月光菩萨圣诞", "道教 / 佛菩萨", "宜拜月、团圆、祈福", True),
              _d("中秋节", "民俗", "宜团圆、赏月")],
    (8, 27): [_d("至圣先师孔子诞辰", "民俗", "宜祭孔、助学、读书", True)],
    (9, 9): [_d("斗姆元君圣诞 · 九皇大帝圣诞", "道教", "九皇斋期之始，宜斋戒、礼斗、祈寿", True),
             _d("重阳节", "民俗", "宜登高、敬老、祭祖"),
             _d("妈祖升天日（一说）", "民俗", "宜进香")],
    (9, 19): [_d("观世音菩萨出家日", "佛菩萨", "宜礼佛、吃素、行善", True)],
    (10, 1): [_d("民岁腊之辰 · 寒衣节", "道教 / 民俗", "五腊之四，宜祭祖、送寒衣、斋戒", True)],
    (10, 5): [_d("达摩祖师圣诞", "佛菩萨", "宜礼佛、静修")],
    (10, 15): [_d("下元节 · 水官大帝圣诞", "道教", "下元三品解厄水官，宜祈福解厄、斋戒", True)],
    (11, 11): [_d("太乙救苦天尊圣诞", "道教", "宜祈福、超荐、消灾")],
    (11, 17): [_d("阿弥陀佛圣诞", "佛菩萨", "宜礼佛、念佛、斋戒、行善", True)],
    (12, 8): [_d("释迦牟尼佛成道日 · 腊八", "佛菩萨", "宜供粥、礼佛、行善", True),
              _d("王侯腊之辰", "道教", "五腊之五，宜祭祖、斋戒祈福")],
    (12, 16): [_d("尾牙 · 祭福德正神", "民俗", "宜祭土地、犒劳、结算")],
    (12, 23): [_d("祭灶 · 送灶神（北方）", "民俗", "宜祭灶、扫舍、祈家宅平安", True)],
    (12, 24): [_d("祭灶 · 送灶神（南方）", "民俗", "宜祭灶、扫舍", True)],
    (12, 25): [_d("玉皇上帝巡天 · 接玉皇", "道教", "宜斋戒、敬天、慎言行", True)],
}

# 四离：二分二至前一日；四绝：四立前一日
_SI_LI = [("春分", "四离 · 春分前一日"), ("夏至", "四离 · 夏至前一日"),
          ("秋分", "四离 · 秋分前一日"), ("冬至", "四离 · 冬至前一日")]
_SI_JUE = [("立春", "四绝 · 立春前一日"), ("立夏", "四绝 · 立夏前一日"),
           ("立秋", "四绝 · 立秋前一日"), ("立冬", "四绝 · 立冬前一日")]
_SI_LI_NOTE = "阴阳分判、气机离散之日，诸事不宜；宜静守、忌嫁娶开市远行。"
_SI_JUE_NOTE = "四时之气将绝、新旧交替之日，诸事不宜；宜静守、忌动土签约搬迁。"

# ---------------------------------------------------------------- 内部工具


def _term_date(year: int, name: str):
    return solar_term_datetime(year, name).date()


_si_cache: Dict[int, Dict] = {}


def _si_map(year: int) -> Dict:
    """一次性算出跨年范围内的四离四绝日，避免逐日重复做天文迭代。"""
    if year not in _si_cache:
        mp: Dict = {}
        for y in (year - 1, year, year + 1):
            for term, cn in _SI_LI:
                dd = _term_date(y, term) - timedelta(days=1)
                mp.setdefault(dd, []).append((cn, "大忌", _SI_LI_NOTE))
            for term, cn in _SI_JUE:
                dd = _term_date(y, term) - timedelta(days=1)
                mp.setdefault(dd, []).append((cn, "大忌", _SI_JUE_NOTE))
        _si_cache[year] = mp
    return _si_cache[year]


def _sili_sijue(d) -> List[Tuple[str, str, str]]:
    """返回 (名称, 等级, 说明)，等级用于排序/预告筛选。"""
    return _si_map(d.year).get(d, [])


def _next_lunar(t: datetime) -> LunarDate:
    """次日的农历日期，用于准确判定「本月是否有三十 / 是否除夕」。"""
    return lunar_info(ensure_cst(t) + timedelta(days=1))


def _deities_of(lu: LunarDate, month_end: bool = False,
                next_is_spring: bool = False) -> List[Dict]:
    """按农历月日取神圣纪念日；闰月不重复过节。

    注意：LunarDate.month_len 是「两朔时刻之差取整」，并不等于农历月天数
    （朔落在不同日期时会差一天），故月末一律用「次日是否初一」判定。
    """
    out: List[Dict] = []
    if lu.leap:
        return out
    m, dd = lu.month, lu.day
    out.extend(DEITY_DAYS.get((m, dd), []))
    # 月小无三十：地藏王诞顺延到廿九
    if m == 7 and dd == 29 and month_end:
        out.extend(DEITY_DAYS.get((7, 30), []))
    if m == 12 and month_end and next_is_spring:
        out.append(_d("除夕 · 辞岁迎新", "民俗", "宜祭祖、团圆、守岁", True))
    return out


def _season(month_zhi: str) -> str:
    i = DI_ZHI.index(month_zhi)
    if i in (2, 3, 4):
        return "春"
    if i in (5, 6, 7):
        return "夏"
    if i in (8, 9, 10):
        return "秋"
    return "冬"


def _uniq(seq: List[str]) -> List[str]:
    return list(dict.fromkeys(x for x in seq if x))


def _brief(dt: datetime) -> List[Tuple[str, str]]:
    """未来预告用：(名称, 等级)。只挑要紧的，免得天天刷屏。"""
    t = ensure_cst(dt)
    d, out = t.date(), []
    for name, level, _ in _sili_sijue(d):
        out.append((name, level))
    lu = lunar_info(t)
    nxt = _next_lunar(t)
    if not lu.leap and (lu.month, lu.day) in _YANG_GONG:
        out.append(("杨公十三忌", "忌"))
    for x in _deities_of(lu, month_end=(nxt.day == 1),
                         next_is_spring=(nxt.day == 1 and nxt.month == 1
                                         and not nxt.leap)):
        out.append((x["name"], "神诞" if x["important"] else "常日"))
    return out


# ---------------------------------------------------------------- 主入口


def almanac_of(dt: datetime, lu: Optional[LunarDate] = None) -> Dict:
    """
    生成某日黄历历注。

    返回字段：
      yi / ji          今日宜 / 忌（建除择日，经忌日与神诞修正）
      jianchu          建除十二值神
      jianchu_note     值神简释
      huangdao         黄道 / 黑道
      huangdao_god     当日值神（青龙、明堂…）
      pengzu           彭祖百忌（干 + 支）
      xishen           喜神方位
      special          [{name, level, note}] 特殊忌日 / 吉日 / 节气日
      deities          [{name, kind, note}] 当日神圣纪念日
      observance       [str] 朔望、斋日之类例行提示
      upcoming         [{date, name, level}] 未来 15 天要紧日子
      warning_level    0 无 / 1 有忌 / 2 有大忌
      one_line         一句话速览（放在日期行下方）
      lunar_label      农历标签
      source_note      口径说明
    """
    t = ensure_cst(dt)
    d = t.date()
    lu = lu or lunar_info(t)

    gz = JIA_ZI[day_gz(t)]
    gan, zhi = gz[0], gz[1]
    # 按「日」取整：交节当日即启用新月建，与万年历每日一页的口径一致
    # （八字/奇门仍按交节时刻换月，两者用途不同，不互相覆盖）
    jie_name, jie_dt = current_jie(datetime(d.year, d.month, d.day, 23, 59))
    mz = _JIE_ZHI[jie_name]
    yz = DI_ZHI[year_gz_by_lichun(t) % 12]
    season = _season(mz)

    # --- 建除 / 黄黑道 / 彭祖 / 喜神
    jc = JIANCHU[(DI_ZHI.index(zhi) - DI_ZHI.index(mz)) % 12]
    hd_god = _HD[(DI_ZHI.index(zhi) - _HD_START[DI_ZHI.index(mz)]) % 12]
    huangdao = "黄道" if hd_god in _HD_GOOD else "黑道"
    pengzu = f"{_PZ_GAN[gan]}；{_PZ_ZHI[zhi]}"
    xishen = _XI_SHEN[gan]

    # --- 特殊日子
    special: List[Dict] = []

    def add(name: str, level: str, note: str) -> None:
        special.append({"name": name, "level": level, "note": note})

    for name, level, note in _sili_sijue(d):
        add(name, level, note)

    if not lu.leap and (lu.month, lu.day) in _YANG_GONG:
        add("杨公十三忌", "大忌",
            "杨救贫所传十三忌日，百事忌用；宜静守，忌嫁娶、开市、动土、出远门。")

    day_zhi_i, mon_zhi_i, yr_zhi_i = (DI_ZHI.index(zhi), DI_ZHI.index(mz),
                                      DI_ZHI.index(yz))
    if (day_zhi_i - mon_zhi_i) % 12 == 6:
        add("月破日", "大忌", f"日支{zhi}冲月建{mz}，为大耗，诸吉事不宜。")
    if (day_zhi_i - yr_zhi_i) % 12 == 6:
        add("岁破日", "忌", f"日支{zhi}冲太岁{yz}，忌动土、搬迁、重大决策。")
    if gz in _SHI_E:
        add("十恶大败日", "忌", "禄空之际，忌开市、签约、求财、上任。")
    if gz in _SI_FEI[season]:
        add("四废日", "忌",
            f"{season}季逢{gz}（{_SI_FEI[season][gz]}），宜静守，忌兴工、嫁娶。")
    if gz == _TIAN_SHE[season]:
        add("天赦日", "吉", "四季天赦，最宜祈福、忏悔、解厄、求医、了结旧怨。")
    if not lu.leap and lu.day in _SANNIANG_DAYS:
        add("三娘煞", "忌", "民俗忌嫁娶、订盟，余事不忌。")
    if not lu.leap and lu.day in _YUEJI_DAYS:
        add("月忌日", "慎", "初五、十四、廿三为月忌，重大事项宜另择日。")
    # 红沙（红煞）：四孟月酉日、四仲月巳日、四季月丑日
    if (mz in ("寅", "申", "巳", "亥") and zhi == "酉") or \
       (mz in ("子", "午", "卯", "酉") and zhi == "巳") or \
       (mz in ("辰", "戌", "丑", "未") and zhi == "丑"):
        add("红沙日", "忌", "民俗忌嫁娶、动土、出行，宜守成。")
    if gan == "戊" and zhi in ("子", "寅", "辰", "午", "申", "戌"):
        add("六戊日（明戊）", "慎",
            "道教「戊不朝真」，忌焚香朝真、诵经、动土；民俗参考。")

    if d == jie_dt.date():
        add(f"交节 · {jie_name}", "节",
            "节气交接、气场转换，宜静养蓄势，忌大动干戈与熬夜。")
    if d == _term_date(d.year, "清明"):
        add("清明节", "俗", "宜祭祖扫墓、慎终追远、踏青；忌嬉闹争执。")
    if d == _term_date(d.year, "冬至"):
        add("冬至 · 一阳来复", "俗", "宜祭祖、进补、静养，传统视为岁首之候。")

    # --- 神圣纪念日 / 例行斋日
    nxt = _next_lunar(t)
    month_end = nxt.day == 1
    deities = _deities_of(lu, month_end=month_end,
                          next_is_spring=(month_end and nxt.month == 1
                                          and not nxt.leap))
    observance: List[str] = []
    if lu.day == 1:
        observance.append("朔日（初一）：宜敬神礼佛、斋戒、立愿")
    if lu.day == 15:
        observance.append("望日（十五）：宜敬神礼佛、斋戒、行善")
    if month_end:
        observance.append("晦日（月尽）：宜收敛内省、不宜开张")
    if lu.day in _LIU_ZHAI_DAYS:
        observance.append("佛教六斋日：宜持斋、诵经、行善")
    elif lu.day in _SHI_ZHAI_DAYS and lu.day not in _LIU_ZHAI_DAYS:
        observance.append("佛教十斋日：宜持斋、行善")
    if lu.day in (2, 16):
        observance.append("做牙日（初二 / 十六）：闽台商家祭福德正神之例")

    # --- 宜忌：建除为底，忌日削减，吉日 / 神诞增益
    yi = list(_JC_YI[jc])
    ji = list(_JC_JI[jc])
    hard_bad = [x for x in special if x["level"] == "大忌"]
    soft_bad = [x for x in special if x["level"] == "忌"]
    if hard_bad or soft_bad:
        _block = {"嫁娶", "开市", "动土", "出行", "上任", "安葬", "交易",
                  "入学", "栽种", "进人口", "纳财", "立契", "立券", "求财",
                  "订盟", "纳采", "修造", "祈福", "祭祀", "捕捉", "开仓"}
        yi = [x for x in yi if x not in _block]
        if len(yi) < 4:
            yi += ["静守", "读书", "内省", "整理", "休养"]
        ji += ["嫁娶", "开市", "动土", "签约", "远行", "搬迁"]
    if any(x["name"] == "天赦日" for x in special):
        yi += ["祈福", "忏悔", "解厄", "求医", "和解"]
    if deities:
        yi += ["敬神礼佛", "斋戒", "行善", "祈福"]
        ji += ["杀生", "口舌"]
    if any("六戊日" in x["name"] for x in special):
        ji += ["焚香朝真", "动土"]
    if lu.day in (1, 15):
        yi += ["敬神", "持斋"]
    yi = _uniq(yi)[:10]
    ji = _uniq(ji)[:10]
    if not yi:
        yi = ["静守", "读书", "内省", "整理", "休养"]

    warning_level = 2 if hard_bad else (1 if soft_bad else 0)

    # --- 未来 15 天预告：神诞 / 四离四绝 / 杨公忌优先，空档补普通纪念日
    primary: Dict = {}
    secondary: Dict = {}
    for k in range(1, 16):
        nd = d + timedelta(days=k)
        for name, level in _brief(datetime(nd.year, nd.month, nd.day, 8, 0)):
            tgt = primary if level != "常日" else secondary
            tgt.setdefault(nd, [])
            if name not in tgt[nd]:
                tgt[nd].append(name)
    keys = sorted(primary)[:4]
    if len(keys) < 2:
        keys = sorted(set(keys) | set(sorted(secondary)[:2]))
    keys = sorted(keys)[:5]
    upcoming = [{"date": k.strftime("%m-%d"),
                 "name": "、".join((primary.get(k) or secondary.get(k) or [])[:2]),
                 "level": "提醒"} for k in keys]

    # --- 一句话速览
    tag = ""
    if hard_bad or soft_bad:
        tag = f"　⚠ {hard_bad[0]['name'] if hard_bad else soft_bad[0]['name']}"
    elif deities:
        imp = next((x for x in deities if x["important"]), deities[0])
        tag = f"　◆ {imp['name']}"
    one_line = (f"{jc}日 · {huangdao}（{hd_god}）　"
                f"宜 {yi[0]}、{yi[1]}　忌 {ji[0]}、{ji[1]}{tag}"
                if len(yi) > 1 and len(ji) > 1 else
                f"{jc}日 · {huangdao}（{hd_god}）{tag}")

    return {
        "date": d.strftime("%Y-%m-%d"),
        "lunar_label": lu.label,
        "day_gz": gz,
        "jie": jie_name,
        "yi": yi,
        "ji": ji,
        "jianchu": jc,
        "jianchu_note": _JC_NOTE[jc],
        "huangdao": huangdao,
        "huangdao_god": hd_god,
        "pengzu": pengzu,
        "xishen": xishen,
        "special": special,
        "deities": deities,
        "observance": observance,
        "upcoming": upcoming,
        "warning_level": warning_level,
        "one_line": one_line,
        "source_note": ("黄历宜忌依建除十二神、黄黑道十二神与彭祖百忌推算"
                        "（交节日按日取整换月建）；忌日、神诞取汉传佛历、"
                        "道教诸神圣诞与民间通行通书，各地传承略有异同，"
                        "仅作民俗参考，不替代五术模型结论。"),
    }


# ---------------------------------------------------------------- 纯文本行


def render_almanac_text(al: Dict) -> List[str]:
    """供 report.render_text 使用的纯文本块（不含首行，避免影响邮件主题解析）。"""
    L: List[str] = []
    L.append("【今日黄历 · 宜忌与神诞】")
    L.append(f"  {al['jianchu']}日 · {al['huangdao']}（{al['huangdao_god']}）　"
             f"日干支 {al['day_gz']}　喜神：{al['xishen']}")
    L.append(f"  宜：{'、'.join(al['yi'])}")
    L.append(f"  忌：{'、'.join(al['ji'])}")
    L.append(f"  彭祖百忌：{al['pengzu']}")
    L.append(f"  {al['jianchu_note']}")
    if al["special"]:
        for x in al["special"]:
            L.append(f"  【{x['level']}】{x['name']} —— {x['note']}")
    if al["deities"]:
        for x in al["deities"]:
            L.append(f"  【{x['kind']}】{x['name']} —— {x['note']}")
    if al["observance"]:
        L.append("  例行：" + "；".join(al["observance"]))
    if al["upcoming"]:
        L.append("  近日提醒：" + "；".join(
            f"{x['date']} {x['name']}" for x in al["upcoming"]))
    L.append(f"  注：{al['source_note']}")
    return L


if __name__ == "__main__":
    import sys
    ds = sys.argv[1:] or [datetime.now().strftime("%Y-%m-%d")]
    for s in ds:
        a = almanac_of(datetime.strptime(s, "%Y-%m-%d"))
        print("=" * 70)
        print(s, a["lunar_label"], a["day_gz"], a["jie"])
        print("\n".join(render_almanac_text(a)))
