# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.synthesize
五门汇总 + 六大板块建议生成

输入：出生数据(profile) + 目标日
输出：结构化 dict —— 供 HTML 报告 / 邮件正文渲染

设计要点：
* 五门各自独立评分，再按 profile.weights 加权得到「本日总运势」
* 各板块并非简单复用总分，而是从不同门提取各自有解释力的信号：
    出行   <- 奇门吉方吉时 + 六壬初传方位
    人际   <- 八字日支刑冲合害 + 六壬六合/青龙 + 梅花体用
    投资   <- 八字财星(流日十神) + 六爻妻财 + 六壬财爻
    学习   <- 八字印星 + 文昌时 + 卦象
    健康   <- 五行失衡 + 卦象意象 + 固定训练分化
    日常   <- 五门综合 + 宜忌清单
* 投资/彩票部分强制附带风险免责声明
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from .base import (
    TIAN_GAN, DI_ZHI, JIA_ZI, hour_zhi, hour_gz, day_gz, ensure_cst,
    clamp, WX_SHENG, WX_SHENG_BY, WX_KE, WX_KE_BY, zhi_wuxing, gan_wuxing,
    solar_term_datetime, GAN_YANG,
)
from . import (bazi, qimen, liuren, yijing, market, lottery, zhouyi,
               classic, curriculum, wool)
from .lunar import lunar_info

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(BASE_DIR, "data", "profile.json")

ZHI_FANG = {
    "子": "正北", "丑": "东北偏北", "寅": "东北偏东", "卯": "正东",
    "辰": "东南偏东", "巳": "东南偏南", "午": "正南", "未": "西南偏南",
    "申": "西南偏西", "酉": "正西", "戌": "西北偏西", "亥": "西北偏北",
}
# 五行 -> 河图数 + 脏腑 + 建议焦点
WX_NUM = {"水": [1, 6], "火": [2, 7], "木": [3, 8], "金": [4, 9], "土": [5, 0]}
WX_ORGAN = {
    "木": "肝胆·筋·目", "火": "心·小肠·血脉", "土": "脾胃·肌肉·口",
    "金": "肺·大肠·皮毛·鼻", "水": "肾·膀胱·骨·耳",
}
WX_ORGAN_TIP = {
    "木": "宜早卧早起、舒展筋骨，少怒以养肝；酸味入肝，可食青蔬、山楂少许。",
    "火": "忌熬夜耗神，午间小憩最养心；苦味入心，可饮莲子芯/苦丁茶少许。",
    "土": "饮食宜温软规律，忌生冷伤脾；甘味入脾，山药、小米粥皆宜。",
    "金": "注意保暖防燥，多做深长呼吸；辛味入肺，可食白萝卜、梨。",
    "水": "忌过劳与受寒，注意腰部保暖；咸味入肾，可食黑豆、核桃、黑芝麻。",
}

WEEK_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 奇门九宫：宫号 -> (宫名, 方位)
PALACE_NAME = {1: ("坎", "正北"), 2: ("坤", "西南"), 3: ("震", "正东"),
               4: ("巽", "东南"), 5: ("中", "中央"), 6: ("乾", "西北"),
               7: ("兑", "正西"), 8: ("艮", "东北"), 9: ("离", "正南")}


def load_profile(path: str = PROFILE_PATH) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# 分级阈值按校准后的分布(μ≈50 σ≈12.7)设定，使各等级占比合理：
# 上吉≈2% / 吉≈14% / 平顺≈36% / 宜守≈31% / 低调≈17%
GRADE_THRESHOLDS = [(76, "上吉"), (64, "吉"), (50, "平顺"), (41, "宜守"), (0, "低调")]


def grade(score: float) -> str:
    for th, name in GRADE_THRESHOLDS:
        if score >= th:
            return name
    return "低调"


def tier(score: float) -> int:
    """0=最弱 … 4=最强"""
    for i, th in enumerate([41, 50, 64, 76]):
        if score < th:
            return i
    return 4


# ---------------------------------------------------------------- 主流程


# ---------------------------------------------------------------- 分布标定
# 原始分来自五套独立评价体系，均值与离散度各不相同；直接加权会导致结果
# 集中且偏悲观(实测 μ≈49 σ≈8)。此处对各门做 z-score 标准化后再加权。
# 各门 target_sigma 依其「日间信息量」而定：
#   * 八字/六壬/梅花/六爻 的 raw 分布天然较宽  -> 保留 15
#   * 奇门是全日 12 时辰的综合，日间差异本就小(σ≈2.3)
#     -> 若强行放大到 15 只会放大噪声，故给 9
# 参数由 150 天采样估计所得。
CALIB = {
    # mu/sigma 为 200 天采样的原始分布参数（2026-09 修正日柱后重测）
    "bazi":   {"mu": 52.13, "sigma": 14.45, "target_sigma": 15.0},
    "qimen":  {"mu": 80.80, "sigma": 2.25,  "target_sigma": 9.0},
    "liuren": {"mu": 50.35, "sigma": 16.06, "target_sigma": 15.0},
    "meihua": {"mu": 53.88, "sigma": 15.58, "target_sigma": 15.0},
    "liuyao": {"mu": 47.77, "sigma": 16.65, "target_sigma": 15.0},
}
# 加权后 blended 的采样参数（加权会压缩方差，故 σ 小于各门自身 σ）
TOTAL_MU = 51.14
TOTAL_SIGMA = 5.96
_LAST_BLENDED = [0.0]


FIVE_NAME = {"bazi": "八字", "qimen": "奇门", "liuren": "六壬",
             "meihua": "梅花", "liuyao": "六爻"}


def calibrate(key: str, raw: float) -> float:
    """把某门的原始分标准化到 μ=52、σ=target_sigma 的可比区间"""
    c = CALIB.get(key)
    if not c:
        return raw
    z = (raw - c["mu"]) / c["sigma"]
    return round(clamp(52.0 + z * c["target_sigma"], 6, 96), 1)


def generate(target: datetime, profile: Optional[Dict] = None,
             longitude: Optional[float] = None,
             offline: bool = False) -> Dict:
    """offline=True 时跳过一切联网（行情抓取），用于测试与批量生成。"""
    target = ensure_cst(target)
    profile = profile or load_profile()
    if longitude is None:
        longitude = profile["birth_longitude"]

    b = profile["birth"]
    birth_dt = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"])
    male = str(profile.get("gender", "male")).lower() in ("male", "m", "男")

    # ---- 五门 ----
    bz = bazi.analyze(birth_dt, longitude=longitude, now=target, male=male)
    lr_day = bazi.liuri_relation(bz, target)

    qm_day = qimen.day_report(target)
    qm_am = qimen.paipan(target.replace(hour=8, minute=0))

    lr = liuren.paipan(target.replace(hour=8, minute=0))
    mh = yijing.meihua(target.replace(hour=8, minute=0))
    ly = yijing.liuyao(target.replace(hour=8, minute=0))

    w = profile.get("weights", {})
    raw = {
        "bazi": lr_day["score"],
        "qimen": qm_day.get("day_score", qm_day["day_avg"]),
        "liuren": lr.score,
        "meihua": mh.score,
        "liuyao": ly.score,
    }
    parts = {k: calibrate(k, v) for k, v in raw.items()}
    blended = sum(parts[k] * w.get(k, 0.2) for k in parts)
    total = round(clamp((blended - TOTAL_MU) / TOTAL_SIGMA * 13.0 + 50.0, 5, 96), 1)
    _LAST_BLENDED[0] = blended

    lu = lunar_info(target)

    ctx = dict(
        target=target, profile=profile, bz=bz, lr_day=lr_day,
        qm_day=qm_day, qm_am=qm_am, lr=lr, mh=mh, ly=ly,
        lu=lu, total=total, male=male, parts=parts, offline=offline,
    )

    health = _health(ctx)
    study = _study(ctx)
    career = _career(ctx)
    zhouyi_pan = _zhouyi(ctx)
    return {
        "meta": _meta(ctx),
        "destiny": _destiny_summary(ctx),
        "zhouyi": zhouyi_pan,
        "classic": classic.daily_classic(ctx, zhouyi_pan,
                                         health_score=health.get("score")),
        "five": _five_panels(ctx),
        "general": _general(ctx),
        "career": career,
        "health": health,
        "travel": _travel(ctx),
        "social": _social(ctx),
        "invest": _invest(ctx),
        "study": study,
        "checklist": _checklist(ctx, health, study),
        "disclaimer": DISCLAIMER,
    }


DISCLAIMER = (
    "本报告由「八字 + 奇门遁甲 + 大六壬 + 梅花易数 + 六爻」五门术数模型自动推演，"
    "属于传统易学文化与民俗参考，用于自我觉察与生活节奏调节。"
    "其中涉及投资、彩票、数字资产的内容仅为传统文化视角的倾向性描述，"
    "不构成任何投资建议或财务决策依据。金融市场与博彩存在极高风险，"
    "请严格遵守当地法律法规，自行承担全部后果。"
)


def _meta(ctx) -> Dict:
    t: datetime = ctx["target"]
    return {
        "date_str": t.strftime("%Y年%m月%d日"),
        "weekday": WEEK_CN[t.weekday()],
        "lunar": ctx["lu"].label,
        "lunar_full": f"{ctx['lu'].gz_year}年 {ctx['lu'].label}",
        "day_gz": ctx["lr_day"]["gz"],
        "day_nayin": ctx["lr_day"]["nayin"],
        "jieqi": f"{ctx['qm_day']['jie']}",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": ctx["total"],
        "grade": grade(ctx["total"]),
        "name": ctx["profile"].get("name", ""),
    }


def _destiny_summary(ctx) -> Dict:
    bz: bazi.BaZiResult = ctx["bz"]
    pillars = [k for k in ["年", "月", "日", "时"]]
    return {
        "sizhu": [bz.pillars[k].name for k in pillars],
        "sizhu_ten": [bz.pillars[k].ten_god for k in pillars],
        "sizhu_nayin": [bz.pillars[k].nayin for k in pillars],
        "day_master": bz.day_master,
        "strength": bz.strength,
        "strength_label": bz.strength_label,
        "pattern": bz.pattern,
        "pattern_detail": bz.pattern_detail,
        "yong": "/".join(bz.yong_shen_wx),
        "ji": "/".join(bz.ji_shen_wx),
        "dayun": (f"{bz.current_dayun.name}（{bz.current_dayun.ten_god}）"
                  if bz.current_dayun else "未起运"),
        "liunian": JIA_ZI[bz.liunian_idx],
        "stars": bz.stars_all,
    }


def _zhouyi(ctx) -> Dict:
    """每日一卦（大衍筮法）——本命提要之下的独立栏目，不并入五门评分"""
    bz: bazi.BaZiResult = ctx["bz"]
    prof = ctx["profile"]
    b = prof["birth"]
    # 个人标识：同一人对同一日必得同一卦；换人则卦亦不同
    personal = f"{prof.get('name', '')}|{b['year']}-{b['month']}-{b['day']}|{bz.day_master}"
    return zhouyi.daily_block(
        ctx["target"], personal=personal,
        day_master_wx=gan_wuxing(bz.day_master),
        yong_shen=list(bz.yong_shen_wx),
    )


def _five_panels(ctx) -> List[Dict]:
    p = ctx["parts"]
    return [
        {"name": "八字·流日", "key": "bazi", "score": p["bazi"],
         "summary": f"{ctx['lr_day']['gz']}日，{ctx['lr_day']['ten_god']}临身，"
                    f"纳音{ctx['lr_day']['nayin']}"},
        {"name": "奇门遁甲", "key": "qimen", "score": p["qimen"],
         "summary": f"{ctx['qm_day']['jie']}·{ctx['qm_day']['title']}"
                    f"（{ctx['qm_day']['yuan']}），吉时"
                    f"{'、'.join(ctx['qm_day']['good_hours'][:2])}"},
        {"name": "大六壬", "key": "liuren", "score": p["liuren"],
         "summary": f"{ctx['lr'].keti}课，月将{ctx['lr'].jiang_name}"},
        {"name": "梅花易数", "key": "meihua", "score": p["meihua"],
         "summary": f"{ctx['mh'].ben_gua}之{ctx['mh'].bian_gua}，{ctx['mh'].relation}"},
        {"name": "六爻纳甲", "key": "liuyao", "score": p["liuyao"],
         "summary": f"{ctx['ly'].name}（{ctx['ly'].gong_name}）"
                    f"第{ctx['ly'].dong_idx+1}爻动"},
    ]


# ---------------------------------------------------------------- 日常生活


def _general(ctx) -> Dict:
    total = ctx["total"]
    t = tier(total)
    lr_day = ctx["lr_day"]
    tg = lr_day["ten_god"]
    bz: bazi.BaZiResult = ctx["bz"]

    headline = [
        "诸事低调，宜休养生息、处理积压事务，不宜开启新事。",
        "气机偏弱，宜按部就班完成既定计划，避免临时变更。",
        "平稳之日，常规事务可正常推进，注意劳逸结合。",
        "气机畅达，适合推进关键事项、谈判与表达。",
        "今日气数上乘，宜主动出击，承担有挑战的工作。",
    ][t]

    tips = []
    TEN_GOD_ACTION = {
        "正印": "利于学习、写作、复盘与请教长辈；印绶护身，思路清晰。",
        "偏印": "利于钻研偏门学术、技术攻关；但须防钻牛角尖、钻 Socio。"
                .replace("钻 Socio.", "思维过度发散"),
        "正官": "利于规矩性事务、流程合规、接受检查验收；言行宜端正。",
        "七杀": "压力偏重之日，宜把难题集中在上午处理，午后收敛。",
        "正财": "利于稳定经营、收款、签署常规合同；忌投机。",
        "偏财": "有意外财货之象，可关注横财机会，但需见好就收。",
        "食神": "利于创作、输出、社交吃喝；身心舒畅，适合放松。",
        "伤官": "利于表达与创意，但言辞易锐，注意分寸与人际。",
        "比肩": "利与人协作分工，朋辈助力明显；忌独断。",
        "劫财": "财来财去之象，注意开销与合伙账目清晰。",
    }
    tips.append(TEN_GOD_ACTION.get(tg, "常规推进即可。"))

    # 五行助力
    yong = bz.yong_shen_wx
    tips.append(f"本命用神为「{'、'.join(yong)}」，"
                f"今日宜多接触属此五行的人事物（颜色/方位/时辰）。")
    WX_COLOR = {"木": "青绿", "火": "红紫", "土": "黄棕", "金": "白金", "水": "黑蓝"}
    if yong:
        tips.append(f"幸运色：{WX_COLOR.get(yong[0], '—')}系；"
                    f"数字倾向：{'、'.join(map(str, WX_NUM.get(yong[0], [])))}。")

    # 当日忌的工作人员
    hits = lr_day["hits"]
    if hits:
        conflict = [h for h in hits if "冲" in h]
        if conflict:
            tips.append("流日与命局有冲：" + "、".join(conflict) +
                        "，凡涉签约、出行、动工宜缓。")

    return {
        "score": round(total, 1),
        "grade": grade(total),
        "headline": headline,
        "tips": tips,
        "yi": _yi_ji(ctx)[0],
        "ji": _yi_ji(ctx)[1],
    }


def _yi_ji(ctx) -> Tuple[List[str], List[str]]:
    """简易宜忌清单"""
    score = ctx["total"]
    qm: qimen.QiMenPan = ctx["qm_am"]
    lr = ctx["lr"]
    mh = ctx["mh"]
    yi, ji = [], []

    if score >= 68:
        yi += ["推进核心项目", "谈判签约", "提出方案 / 公开发言", "开拓新客户"]
    elif score >= 55:
        yi += ["常规工作推进", "整理复盘", "学习充电", "轻量社交"]
    else:
        yi += ["内部整理", "休息调理", "复盘总结", "低风险事务"]

    if score < 55:
        ji += ["重大决策", "大额支出", "与人争执", "高强度对抗运动"]

    kaimen = qm.summary["kaimen"]
    if kaimen:
        yi.append(f"行事取{''.join(qimen.PALACE_FANG[p] for p in kaimen)}"
                  f"（{qimen.PALACE_NAME[kaimen[0]]}宫开门）方位")
    worst = qm.summary["worst"]
    if worst:
        ji.append(f"规避{worst[2]}（{worst[1]}宫，凶气最重）")

    if lr.keti in ("伏吟", "返吟", "昴星"):
        ji.append(f"{lr.keti}课，忌频繁变更计划")
    if mh.relation == "用克体":
        ji.append("外力压制明显，忌硬碰硬")
    if lr_day_ok(ctx):
        pass
    return yi, ji[:6]


def lr_day_ok(ctx) -> bool:
    return ctx["lr_day"]["score"] >= 60


# ---------------------------------------------------------------- 健康


def _health(ctx) -> Dict:
    bz: bazi.BaZiResult = ctx["bz"]
    lr_day = ctx["lr_day"]
    target: datetime = ctx["target"]
    prof = ctx["profile"]

    # 当日五行失衡 -> 脏腑提醒
    day_wx = lr_day["wuxing"]
    ji = bz.ji_shen_wx
    focus_wx = None
    for w in [day_wx["天干"], day_wx["地支"]]:
        if w in ji:
            focus_wx = w
            break
    focus_wx = focus_wx or (bz.ji_shen_wx[0] if bz.ji_shen_wx else "土")

    score = round(clamp((lr_day["score"] * 0.5 + ctx["parts"]["liuyao"] * 0.2
                         + ctx["parts"]["qimen"] * 0.3)), 1)

    t = tier(score)
    headline = [
        "今日元气偏弱，训练宜降强度，重恢复与睡眠。",
        "体力一般，按计划完成即可，不宜冲击极限重量。",
        "状态平稳，常规训练日，注意热身与拉伸。",
        "精力充沛，适合挑战重量或增加训练容量。",
        "状态上佳，可安排强度课或突破性训练。",
    ][t]

    week = WEEK_CN[target.weekday()]
    fit = prof.get("fitness", {})
    split = fit.get("weekly_split", {}).get(week, "综合训练")
    goal = fit.get("goal", "")

    training = [f"今日（{week}）分化：{split}"]
    if t >= 3:
        training.append("可尝试：主项冲 PR 或增加 1~2 组容量；组间休息压缩至 60~90 秒。")
    elif t <= 1:
        training.append("降载方案：总量降至常规的 60%，以动作质量与泵感为主。")
    else:
        training.append("按 8~12RM × 3~4 组完成，最后一组的 RIR 保留 2~3。")
    focus = fit.get("focus", [])
    if focus:
        training.append(f"优先弱项：{'、'.join(focus)}，建议安排在训练前半程体力最充沛时。")
    training.append("有氧建议：每周 2~3 次、每次 20~30 分钟 Zone2，避免过度消耗影响增肌。")

    # 饮食
    nutrition = []
    nutrition.append("睡前 20:00 后减少碳水，保留 30g 缓释蛋白（酪蛋白/希腊酸奶）利于夜间合成。")
    nutrition.append("训练后 30~60 分钟内：碳水:蛋白 ≈ 2:1。")

    # 八部金刚功（只早上练一遍，不设晚课）
    qg = prof.get("qigong", {})
    sections = qg.get("sections", [])
    n = len(sections) or 8
    # 依当日干支数决定"重点部"
    day_idx = day_gz(target)
    key_idx = day_idx % n
    key_name = sections[key_idx] if sections else ""
    window = qg.get("window") or "05:30~07:30（卯时）"
    qigong = [
        f"只在清晨 {window}练一遍，上午一次做完，不设晚课；每部 5~9 遍起。",
        f"今日主练：第{key_idx+1}部「{key_name}」——整套照做之外，此部加练 2 遍。",
        "要点：动作到位、呼吸自然不憋气，微汗即止；饭后 1 小时内不做。",
    ]

    organ_tips = [
        f"当日五行偏「{focus_wx}」且为本命忌神所临，须留意：{WX_ORGAN.get(focus_wx, '脾胃')}",
        WX_ORGAN_TIP.get(focus_wx, ""),
    ]

    return {
        "score": score,
        "headline": headline,
        "organ": WX_ORGAN.get(focus_wx, "脾胃"),
        "organ_tips": [o for o in organ_tips if o],
        "training": training,
        "nutrition": nutrition,
        "qigong": qigong,
        "goal": goal,
        "checkin": {
            "金刚功早课": False,
            "力量训练": False,
            "蛋白达标": False,
            "23点前入睡": False,
        },
    }


# ---------------------------------------------------------------- 出行


def _travel(ctx) -> Dict:
    qm_day = ctx["qm_day"]
    qm: qimen.QiMenPan = ctx["qm_am"]
    lr: liuren.LiuRenPan = ctx["lr"]

    score = round(clamp(qm_day["day_avg"] * 0.65 + lr.score * 0.35), 1)
    t = tier(score)
    headline = [
        "出行不顺，非必要不安排远行，若须外出请留足余量。",
        "路况与沟通易有波折，建议提前出发、反复确认。",
        "出行平顺，常规安排即可。",
        "利于出行洽谈，行程安排可偏积极。",
        "出行大吉，适合远行、拜访、开拓市场。",
    ][t]

    tips = []
    jifang = []
    for key in ["kaimen", "shengmen", "xiumen"]:
        for p in qm.summary[key]:
            pl = qm.palace[p]
            jifang.append(f"{pl.fang}（{pl.name}宫·{pl.men}·{pl.score:.0f}分）")
    if jifang:
        tips.append("吉利方位：" + "；".join(jifang[:3]))
    w = qm.summary["worst"]
    tips.append(f"宜规避：{w[2]}（{w[1]}宫，{w[3]:.0f}分，凶气最重）")

    gh = qm_day["good_hours"]
    bh = qm_day["bad_hours"]
    HOUR_RANGE = {"子": "23-1", "丑": "1-3", "寅": "3-5", "卯": "5-7", "辰": "7-9",
                  "巳": "9-11", "午": "11-13", "未": "13-15", "申": "15-17",
                  "酉": "17-19", "戌": "19-21", "亥": "21-23"}
    if gh:
        tips.append("优选时段：" + "、".join(f"{z}时({HOUR_RANGE[z]}点)" for z in gh))
    if bh:
        tips.append("不利时段：" + "、".join(f"{z}时({HOUR_RANGE[z]}点)" for z in bh))

    chuan_fang = ZHI_FANG.get(DI_ZHI[lr.chuan[0]], "")
    tips.append(f"六壬初传在{DI_ZHI[lr.chuan[0]]}"
                f"{'（' + chuan_fang + '）' if chuan_fang else ''}，"
                f"乘{str(lr.chuan_jiang[0])}——" +
                ("外应助我，出门办事顺。" if lr.chuan_jiang[0] in liuren.PROPITIOUS
                 else "外应带扰，途中留意沟通与财物。"))

    if lr.keti in ("伏吟", "返吟"):
        tips.append(f"{lr.keti}课：行程易有反复，建议预留弹性时间。")

    return {
        "score": score,
        "headline": headline,
        "tips": tips,
        "good_hours": gh,
        "bad_hours": bh,
        "good_dirs": [qimen.PALACE_FANG[p] for p in
                      (qm.summary["kaimen"] + qm.summary["shengmen"])[:3]],
        "avoid_dir": qm.summary["worst"][2],
    }


# ---------------------------------------------------------------- 人际


# 六亲 -> 所主十神。据《渊海子平》六亲歌：
#   生我父母印绶是，我生子孙食伤类，克我官鬼夫主是，我克妻财兄弟比。
LIUQIN_STAR = {
    "父母": ("正印", "偏印"),
    "子女": ("食神", "伤官"),
    "爱人": ("正财", "正财"),
    "同事": ("比肩", "劫财"),
    "客户": ("正财", "偏财"),
    "朋友": ("比肩", "劫财"),
}
# 十神 -> 相对日主的五行作用（据此推出该十神所属五行）
STAR_REL = {"正印": "生我", "偏印": "生我",
            "比肩": "同我", "劫财": "同我",
            "食神": "我生", "伤官": "我生",
            "正财": "我克", "偏财": "我克",
            "正官": "克我", "七杀": "克我"}


def _star_wuxing(star: str, dmwx: str) -> str:
    rel = STAR_REL.get(star, "同我")
    return {"同我": dmwx, "生我": WX_SHENG_BY[dmwx], "我生": WX_SHENG[dmwx],
            "我克": WX_KE[dmwx], "克我": WX_KE_BY[dmwx]}[rel]


def _wx_relation(a: str, b: str) -> str:
    """a 对 b 的五行作用"""
    if a == b:
        return "比和"
    if WX_SHENG.get(a) == b:
        return "我生彼"
    if WX_SHENG.get(b) == a:
        return "彼生我"
    if WX_KE.get(a) == b:
        return "我克彼"
    if WX_KE.get(b) == a:
        return "彼克我"
    return "平常"


def _social(ctx) -> Dict:
    bz: bazi.BaZiResult = ctx["bz"]
    lr_day = ctx["lr_day"]
    lr: liuren.LiuRenPan = ctx["lr"]
    mh = ctx["mh"]

    base = lr_day["score"]
    he_cnt = sum(1 for h in lr_day["hits"] if "六合" in h)
    chong_cnt = sum(1 for h in lr_day["hits"] if "冲" in h)
    hai_cnt = sum(1 for h in lr_day["hits"] if "害" in h)
    bonus = he_cnt * 7 - chong_cnt * 8 - hai_cnt * 5
    if lr.chuan_jiang[0] in ("六合", "青龙", "贵人"):
        bonus += 8
    if mh.relation in ("体用比和", "用生体"):
        bonus += 6
    score = round(clamp(base * 0.5 + lr.score * 0.2 + mh.score * 0.3 + bonus), 1)
    t = tier(score)
    headline = [
        "口舌易生，宜少说多做，重要沟通改期或改为书面。",
        "气氛偏紧，沟通宜直白但留出缓冲，避免争论立场。",
        "人际平稳，正常社交即可。",
        "利于沟通合作，适合约谈、修复关系、求助他人。",
        "人缘极佳，适合拓展人脉、团队动员、公开表达。",
    ][t]

    tips = []
    if he_cnt:
        tips.append(f"流日有合（{'、'.join(h for h in lr_day['hits'] if '六合' in h)}），"
                    "易得他人主动助力，宜顺势请求协助。")
    if chong_cnt:
        tips.append(f"流日有冲（{'、'.join(h for h in lr_day['hits'] if '冲' in h)}），"
                    "易起摩擦，切忌当面议价、批评或提离职/分手。")
    if hai_cnt:
        tips.append("流日相害，留意背后议论与信息误传，重要事项留书面凭证。")
    if mh.relation == "体克用":
        tips.append("体克用：你主导谈话节奏会更顺，可主动约对方。")
    elif mh.relation == "用克体":
        tips.append("用克体：对方态度强硬，先倾听再回应，不宜当场定论。")

    # ---- 六亲细分 ----
    dmwx = gan_wuxing(bz.day_master)
    tg = lr_day["ten_god"]
    tg_wx = _star_wuxing(tg, dmwx)

    # 状态 -> 通用基调
    STATE_MOOD = {
        "比和":   ("平顺", "关系处在常态，正常往来即可，不必刻意。"),
        "我生彼": ("我付出", "你在这段关系上是付出方，主动关怀会很受用，但别透支。"),
        "彼生我": ("对方付出", "对方今日更愿意迁就你，是求助与修复关系的好时机。"),
        "我克彼": ("我主导", "你掌握主导权，适合推动安排、定规矩，但别压得太硬。"),
        "彼克我": ("受压力", "对方今日态度较强或有诉求压来，先接住再回应，不宜硬顶。"),
        "平常":   ("平和", "无特殊生克，按既有节奏相处。"),
    }
    # 六亲 -> 各状态下的具体做法
    LIUQIN_ACTION = {
        "父母": {
            "当值": "今日十神正落父母宫，宜主动联系父母：问候、代办事务、安排体检都合适；忌在此日争论旧事或拒接电话。",
            "我付出": "打个电话或视频问候，顺手代办一件小事（买药、缴费、挂号）比说漂亮话管用。",
            "对方付出": "父母今日可能主动关心你，别嫌啰嗦，认真听完再回应。",
            "我主导": "适合推动体检、保险、养老这类「为他们好但需安排」的事，态度要软。",
            "受压力": "易因旧事或观念起争执，只听不辩，换个时间再谈。",
            "平顺": "照常问候即可，留意他们的睡眠与血压。",
            "平和": "例行问候，无需多言。",
        },
        "子女": {
            "当值": "今日十神正落子女宫，孩子的事今天最该优先：陪伴、作业、情绪，今天投入一小时胜过平时三小时。",
            "我付出": "今天适合专心陪孩子，放下手机 30 分钟，效果胜过全天在场。",
            "对方付出": "孩子今日更黏你、更愿表达，是谈心与倾听的好窗口。",
            "我主导": "适合立规矩、定计划，但要先肯定再提要求。",
            "受压力": "孩子可能有情绪或抗拒，先处理情绪再处理事情，别当场训斥。",
            "平顺": "作业与作息照常，多给一句具体的肯定。",
            "平和": "常规陪伴，观察其作息即可。",
        },
        "爱人": {
            "当值": "今日十神正落妻财宫，伴侣关系是今日重点：宜安排一次二人时间，或把拖着的家庭决策今天定下来。",
            "我付出": "主动承担一件家务或一次接送，比送礼更暖。",
            "对方付出": "对方今日更包容，适合谈需要对方配合的事。",
            "我主导": "适合一起做决策（家庭开支、行程），但必须留一半决定权给对方。",
            "受压力": "对方可能有情绪或诉求，先听完，别急着给解决方案。",
            "平顺": "正常的相处日，晚上留 20 分钟聊聊天就够。",
            "平和": "各忙各的也无妨，别用沉默表达不满。",
        },
        "同事": {
            "当值": "今日十神正落兄弟宫，同事互动密集：协作与信息交换是主线，功劳归属提前说清，事后不扯皮。",
            "我付出": "今天多承担一点协作成本，功劳先分出去，人缘会记着。",
            "对方付出": "同事今日愿配合，适合推动跨部门的事。",
            "我主导": "适合推进分工、明确责任，但把话说在前面，别事后追责。",
            "受压力": "资源或功劳易有竞争，重要结论留书面记录。",
            "平顺": "协作正常，别卷入他人是非。",
            "平和": "按流程推进，保持边界。",
        },
        "客户": {
            "当值": "今日十神正落财星，客户与财源是今日主线：最宜约访、提案、推进签约与回款，把最难谈的那个放在今天。",
            "我付出": "适合主动多做一步（方案细化、售后跟进），为后续铺垫。",
            "对方付出": "客户今日更愿倾听，是提案与推进签约的好时机。",
            "我主导": "适合谈条件、推进流程、催进度，但承诺必须留余地。",
            "受压力": "客户可能施压或压价，先问清真实诉求，别当场让步。",
            "平顺": "正常跟进已有客户即可，不必强推新单。",
            "平和": "例行维护，别过度打扰。",
        },
        "朋友": {
            "当值": "今日十神正落兄弟宫，朋友往来频繁：适合组局或联络老友，但今日忌金钱借贷与担保。",
            "我付出": "主动联系一位久未联络的老友，成本很低、回报很高。",
            "对方付出": "朋友可能主动找你，能帮就帮一把。",
            "我主导": "适合组局、牵线，你来定时间地点。",
            "受压力": "今日不宜金钱往来与担保，借与不借都伤感情，先缓。",
            "平顺": "小聚或线上聊聊都好，不必刻意。",
            "平和": "保持联系，无需特别动作。",
        },
    }

    relations = []
    for who, stars in LIUQIN_STAR.items():
        star = stars[0]
        s_wx = _star_wuxing(star, dmwx)
        rel = _wx_relation(tg_wx, s_wx)
        mood, mood_txt = STATE_MOOD[rel]
        # 当日十神正好是该宫之星 -> 该宫「当值」，事务最集中
        on_duty = tg in stars
        if on_duty:
            mood = "当值"
            mood_txt = f"今日十神正是{star}，此宫事务最集中、感应最强，宜主动处理。"
        actions = LIUQIN_ACTION[who]
        advice = actions.get(mood) or actions["平顺"]
        relations.append({
            "who": who,
            "star": star,
            "state": mood,
            "desc": mood_txt,
            "advice": advice,
            "on_duty": on_duty,
        })

    return {
        "score": score,
        "headline": headline,
        "tips": tips,
        "relations": relations,
        "today_star": tg,
    }


# ---------------------------------------------------------------- 投资


def _invest(ctx) -> Dict:
    """
    传统术数视角的财气倾向。分「稳健理财/数字资产」「彩票娱乐」两段，
    均附强风险提示 —— 不构成任何投资建议。
    """
    bz: bazi.BaZiResult = ctx["bz"]
    lr_day = ctx["lr_day"]
    lr: liuren.LiuRenPan = ctx["lr"]
    ly = ctx["ly"]
    prof = ctx["profile"]
    inv = prof.get("invest", {})

    tg = lr_day["ten_god"]
    cai_score = 0.0
    notes = []

    if tg in ("偏财", "正财"):
        cai_score += 16
        notes.append(f"流日{tg}透出，财星当令，为近期较明显的财气日。")
    elif tg in ("食神", "伤官"):
        cai_score += 8
        notes.append(f"食伤生财（{tg}），利于靠创意/技术变现，而非被动投资。")
    elif tg in ("七杀", "正官"):
        cai_score -= 8
        notes.append(f"官杀克身（{tg}），主压力与破耗，不宜加仓。")
    elif tg in ("正印", "偏印"):
        cai_score -= 3
        notes.append(f"印星{tg}在位，宜守成与学习，不宜进取之财。")

    # 六爻妻财
    cai_yaos = [y for y in ly.yaos if y.liuqin == "妻财"]
    for y in cai_yaos:
        if y.is_shi:
            cai_score += 8
            notes.append("妻财持世，求财有利，但财去财来亦快。")
        if y.is_dong:
            cai_score += 6
            notes.append(f"第{y.idx+1}爻妻财发动，财动之象，注意来得快去得快。")
    if ly.xunkong and any(y.is_shi and y.gan_zhi[1] in ly.xunkong for y in ly.yaos):
        cai_score -= 10
        notes.append("世爻空亡，求财难实，忌追高。")

    # 六壬财爻
    if "妻财" in lr.chuan_liuqin:
        cai_score += 6
        notes.append(f"三传见妻财（{'、'.join(DI_ZHI[c] for c, l in zip(lr.chuan, lr.chuan_liuqin) if l == '妻财')}）")
    if lr.keti in ("伏吟", "返吟"):
        cai_score -= 8
        notes.append(f"{lr.keti}课，行情反复，忌频繁操作。")

    base = (lr_day["score"] * 0.4 + lr.score * 0.2 + ly.score * 0.15
            + ctx["parts"]["qimen"] * 0.25)
    score = round(clamp(base + cai_score * 0.5), 1)
    t = tier(score)

    action = [
        ("空仓观望", "今日无财气，任何新开仓位都属于逆势操作。"),
        ("减仓/止盈", "以降低暴露为主，把利润落袋、保留现金。"),
        ("持仓不动", "中性日，维持既有配置，不宜加减。"),
        ("轻仓试探", "可小仓位试单，但必须带止损。"),
        ("可积极部署", "财气较旺，可按既定策略分批建仓。"),
    ][t]

    max_pos = inv.get("max_position_pct", 15)
    crypto = [
        f"术数倾向：{action[0]}。{action[1]}",
        f"仓位纪律：单一标的占比不超过总资金 {max_pos}%，"
        f"单笔亏损止损不超过账户 {inv.get('crypto_alert_pct', 2.5)}%。",
        "账户安全：开启提现白名单与二次验证（2FA）；只做观察清单内的标的，"
        "不加杠杆、不碰合约。",
    ]

    # ---- 数字资产：平台活动薅羊毛 + 观察清单（行情联网，失败自动降级）----
    watch_syms = inv.get("watchlist") or None
    assets = wool.build(ctx["target"], score, symbols=watch_syms,
                        offline=bool(ctx.get("offline")))

    # ---- 彩票：以五门加权总分为主要参考，可给「不购买」建议，同一天只一个彩种 ----
    budget = inv.get("lottery_monthly_budget_cny", 100)
    skip_at = float(inv.get("lottery_skip_threshold", 50))
    lotto = lottery.lottery_block(ctx, ctx["total"], tg, budget, skip_at,
                                  one_game=bool(inv.get("lottery_one_game_per_day", True)))
    lotto_score = lotto["score"]
    # 五门明细（供报告展示"彩气由哪几门托起"）
    parts = ctx["parts"]
    drivers = sorted(parts.items(), key=lambda kv: -kv[1])[:2]
    lags = sorted(parts.items(), key=lambda kv: kv[1])[:1]
    five_txt = "、".join(f"{FIVE_NAME.get(k, k)}{v:.0f}" for k, v in drivers)
    lag_txt = "、".join(f"{FIVE_NAME.get(k, k)}{v:.0f}" for k, v in lags)

    if lotto["skip"]:
        lottery_lines = [
            f"今日彩气 {lotto_score:.0f}（{lotto['level']}），低于建议线 {skip_at:.0f}——"
            f"今日不建议购买任何彩种。",
            f"五门参考：五门加权总分 {ctx['total']:.0f}，流日十神「{tg}」；"
            f"较强 {five_txt}，偏弱 {lag_txt}。",
            "不出号码。术数不是预测工具，这个建议的价值在于帮你把「今天不买」变成"
            "一个有依据的决定，而不是靠手气冲动。",
            f"预算纪律：本月娱乐预算 ¥{budget}，今日建议支出 ¥0；省下的额度可累计到彩气旺日再用。",
        ]
    else:
        g = lotto["chosen"]
        lottery_lines = [
            f"今日彩气 {lotto_score:.0f}（{lotto['level']}），达到建议线 {skip_at:.0f}——"
            f"今日只买一种：{g}。",
            f"选种依据：{lotto['chosen_reason']}。"
            + (f"（当日开奖：{'、'.join(lotto['open_games'])}，其余一律不碰。）"
               if len(lotto["open_games"]) > 1 else ""),
            f"五门参考：加权总分 {ctx['total']:.0f}，流日十神「{tg}」；"
            f"较强 {five_txt}，偏弱 {lag_txt}。",
            f"预算纪律：本月娱乐预算 ¥{budget}，今日上限 ¥{lotto['daily_cap']}；"
            f"只买 {g} 一注，超出即停。",
        ]

    return {
        "score": score,
        "headline": f"财气指数 {score:.0f}｜{action[0]}",
        "notes": notes,
        "crypto": crypto,
        "assets": assets,
        "lottery": lottery_lines,
        "lottery_detail": lotto,
        "lottery_score": lotto_score,
        "exchange": inv.get("crypto_exchange", "binance"),
        "risk_banner": "⚠ 术数仅为文化视角参考，不构成投资建议。"
                       "加密资产与彩票均为高风险，可能损失全部本金。",
    }


def _best_windows(ctx) -> str:
    HOUR_RANGE = {"子": "23-1", "丑": "1-3", "寅": "3-5", "卯": "5-7", "辰": "7-9",
                  "巳": "9-11", "午": "11-13", "未": "13-15", "申": "15-17",
                  "酉": "17-19", "戌": "19-21", "亥": "21-23"}
    gh = ctx["qm_day"]["good_hours"][:2]
    return "、".join(f"{z}时({HOUR_RANGE[z]}点)" for z in gh) if gh else "—"


# ---------------------------------------------------------------- 学习


def _study(ctx) -> Dict:
    bz: bazi.BaZiResult = ctx["bz"]
    lr_day = ctx["lr_day"]
    lr: liuren.LiuRenPan = ctx["lr"]
    prof = ctx["profile"]
    study = prof.get("study", {})

    tg = lr_day["ten_god"]
    bonus = 0.0
    notes = []
    if tg in ("正印", "偏印"):
        bonus += 14
        notes.append(f"流日{tg}主事，最利读书钻研、记诵与体系化整理。")
    elif tg in ("食神", "伤官"):
        bonus += 6
        notes.append("食伤泄秀，利于输出式学习：写笔记、做分享、录讲解。")
    elif tg in ("七杀", "正官"):
        bonus -= 6
        notes.append("官杀压身，注意力易被事务拉走，宜安排在清晨。")
    elif tg in ("正财", "偏财"):
        bonus -= 4
        notes.append("财星破印，学习易被赚钱念头打断，先定番茄钟再开始。")

    score = round(clamp(lr_day["score"] * 0.45 + lr.score * 0.2
                        + ctx["parts"]["meihua"] * 0.2
                        + ctx["parts"]["qimen"] * 0.15 + bonus), 1)
    t = tier(score)
    # 系统课：按日推进、每天一节，不再在几个专题间轮换（旧版每隔几天就是同一句话）
    lesson = curriculum.lesson_for(ctx["target"])
    focus = f"{lesson['track']} · {lesson['title']}"

    headline = [
        "心神易散，只做轻量复习与抄录，不宜啃硬骨头。",
        "效率一般，建议以复习旧课为主，穿插新概念。",
        "状态平稳，按既定节奏推进即可。",
        "思路清晰，适合攻难点、做体系梳理。",
        "领悟力强，宜读经典原文、做批注与印证。",
    ][t]

    plan = [
        f"推荐时段：{_best_windows(ctx)}——此时段气机最清、记诵效率最高。",
        f"本周目标 {study.get('weekly_hours', 6)} 小时，今日建议投入 "
        f"{'20~30 分钟' if t <= 1 else '45~60 分钟' if t <= 3 else '60~90 分钟'}。",
        "方法建议：看讲解或读原文 30 分钟 → 手写笔记 10 分钟 → 用自己的话复述 5 分钟。",
    ]

    return {
        "score": score,
        "headline": headline,
        "focus": focus,
        "notes": notes,
        "plan": plan,
        "lesson": lesson,
    }


# ---------------------------------------------------------------- 事业


def _career(ctx) -> Dict:
    """
    事业板块。江公子的业务形态：
      帮客户规划优化公司运营 / 提升业绩（技术输出=食伤）
      提供资产配置建议          （财星）
      办理银行贷款              （官杀=官方金融机构 + 财星=资金）
    故按「食伤 / 财星 / 官杀」三条线分别看今日适合推进哪类事务。
    """
    bz: bazi.BaZiResult = ctx["bz"]
    lr_day = ctx["lr_day"]
    lr: liuren.LiuRenPan = ctx["lr"]
    ly = ctx["ly"]
    qm = ctx["qm_day"]

    tg = lr_day["ten_god"]
    score = 50.0
    notes: List[str] = []

    # 1) 流日十神对三条业务线的作用
    LINE = {
        "食神": ("方案/运营优化", 14, "食伤泄秀，最利做方案、写诊断、给客户做运营优化这类「技术输出」的事。"),
        "伤官": ("方案/运营优化", 10, "伤官主表达与突破，适合提案与说服，但锋芒易露，书面材料要留余地。"),
        "正财": ("资产配置/回款", 14, "正财当值，资产配置、回款、谈费用这类务实事务最顺。"),
        "偏财": ("资产配置/开拓", 12, "偏财主变通与机会，适合接触新客户、新渠道，但忌承诺过头。"),
        "正官": ("银行/合规事务", 10, "正官主官方与规则，跑银行、递材料、走流程正合时宜。"),
        "七杀": ("银行/攻坚", 6, "七杀主压力与攻坚，难办的单子可推，但过程必有反复，留足时间。"),
        "正印": ("学习/沉淀", 4, "印星主守成与学习，宜整理案例、沉淀方法论，不宜强推新单。"),
        "偏印": ("研究/复盘", 2, "偏印主偏门与思考，适合研究疑难案例、写内部分享，不宜外务。"),
        "比肩": ("协作/同行", -2, "比肩主共事与竞争，同行交流有价值，但要防方案被抄、功劳被分。"),
        "劫财": ("竞争/防耗", -6, "劫财主争夺与耗散，报价与条款务必落到书面，忌口头承诺。"),
    }
    line_name, dv, line_txt = LINE.get(tg, ("常规推进", 0, "按既有节奏推进。"))
    score += dv
    notes.append(f"流日「{tg}」→ 今日主线：{line_name}。{line_txt}")

    # 2) 六爻：官鬼爻(银行/官方) 与 妻财爻(回款)
    guigui = [y for y in ly.yaos if y.liuqin == "官鬼"]
    cai = [y for y in ly.yaos if y.liuqin == "妻财"]
    if any(y.is_dong for y in guigui):
        score += 6
        notes.append("官鬼爻发动：银行/机构环节今日有动静，适合主动跟进审批进度。")
    if any(y.is_dong for y in cai):
        score += 6
        notes.append("妻财爻发动：款项有流动之象，宜催回款或推进收费，但来得快去得也快。")
    if ly.xunkong and any(y.is_shi and y.gan_zhi[1] in ly.xunkong for y in ly.yaos):
        score -= 9
        notes.append("世爻空亡：今日谈成的事易虚，重要约定务必落到书面并设确认节点。")

    # 3) 奇门：开门(事业) 与 生门(财) 的质量
    try:
        best_h = max(qm["hours"], key=lambda x: x["quality"])
        for key, name, tip in (("kaimen", "开门", "对外谈判与提案可用此时段"),
                               ("shengmen", "生门", "谈费用与回款宜取此方位/时段")):
            pal = best_h.get(key)
            if not pal:
                continue
            no = pal[0] if isinstance(pal, (list, tuple)) else pal
            info = PALACE_NAME.get(no)
            score += 4
            if info:
                notes.append(f"{name}落{info[0]}宫（{info[1]}），{name}有气，{tip}。")
            else:
                notes.append(f"{name}有气，{tip}。")
    except Exception:      # noqa: BLE001
        pass

    # 4) 六壬三传
    if lr.keti in ("伏吟", "返吟"):
        score -= 7
        notes.append(f"{lr.keti}课：流程易反复（补材料、改方案），别把截止时间卡死。")
    if lr.chuan_jiang[0] in ("青龙", "六合", "贵人"):
        score += 6
        notes.append(f"初传乘{lr.chuan_jiang[0]}：贵人运在，适合约见关键人、请人引荐。")

    score = round(clamp(lr_day["score"] * 0.4 + score * 0.6), 1)
    t = tier(score)

    headline = [
        "宜守不宜攻：只做维护与整理，不推新单、不签新约。",
        "进展偏慢，先处理积压与补漏，重要谈判改期。",
        "常规推进日，按计划完成任务即可。",
        "推进顺畅，适合提案、约访、跟进审批。",
        "事业运旺，适合签单、攻坚、开拓新客户。",
    ][t]

    # 三条业务线的具体动作
    actions = []
    if tg in ("食神", "伤官"):
        actions.append("方案类：今天写诊断与优化方案效率高，先出框架再补数据，别追求一次成型。")
    elif tg in ("正财", "偏财"):
        actions.append("资产配置类：今天适合给客户做配置复盘与再平衡，数据说话最有说服力。")
    elif tg in ("正官", "七杀"):
        actions.append("银行类：今天适合跑银行、递材料、催审批；材料宁可多带一份。")
    else:
        actions.append("常规：按客户优先级排序，先处理已承诺的事，再安排新增。")

    if t >= 3:
        actions.append("可主动约见 1~2 位重点客户，把方案当面讲一遍，比邮件有效得多。")
        actions.append("回款：有到期的款项今天就催，态度明确但不施压。")
    elif t <= 1:
        actions.append("今日不做新承诺，只交付已答应交付的东西。")
        actions.append("把卡住的单子列出来，写下卡点与下一步，明天再动。")
    else:
        actions.append("按计划推进在手项目，别临时加塞新需求。")
        actions.append("顺手整理客户档案与案例，为后续提案备料。")

    actions.append(f"优选时段：{_best_windows(ctx)}。")

    return {
        "score": score,
        "headline": f"事业指数 {score:.0f}｜主线 {line_name}",
        "advice_headline": headline,
        "notes": notes,
        "actions": actions,
        "line": line_name,
        "today_star": tg,
    }


# ---------------------------------------------------------------- 打卡清单


def _checklist(ctx, health: Dict, study: Dict) -> List[Dict]:
    split = health["training"][0].split("：")[-1]
    return [
        {"icon": "\u262f", "task": "八部金刚功 · 早课一遍（卯时 05:00~07:00）", "tag": "气功", "mins": 20},
        {"icon": "\U0001F3CB", "task": f"力量训练 · {split}", "tag": "健身", "mins": 60},
        {"icon": "\U0001F95B", "task": "蛋白质达标（体重kg × 1.8g）", "tag": "饮食", "mins": 0},
        {"icon": "\U0001F4D6", "task": f"传统文化研读 · {study['focus']}",
         "tag": "学习", "mins": 45},
        {"icon": "\U0001F4A7", "task": "饮水 2L · 23:00 前入睡", "tag": "作息", "mins": 0},
    ]


if __name__ == "__main__":
    from datetime import datetime
    r = generate(datetime(2026, 9, 28, 8, 0))
    print(json.dumps({
        "meta": r["meta"],
        "destiny": {k: v for k, v in r["destiny"].items() if k != "stars"},
        "scores": {p["name"]: p["score"] for p in r["five"]},
    }, ensure_ascii=False, indent=2))
    print("\n--- 出行 ---")
    for x in r["travel"]["tips"]:
        print(" ", x)
    print("\n--- 投资 ---")
    print(" ", r["invest"]["headline"])
    for x in r["invest"]["crypto"][:2]:
        print(" ", x)
    print("\n--- 学习 ---")
    for x in r["study"]["plan"]:
        print(" ", x)
    print("\n--- 健康 ---")
    for x in r["health"]["training"]:
        print(" ", x)
    for x in r["health"]["qigong"]:
        print(" ", x)
