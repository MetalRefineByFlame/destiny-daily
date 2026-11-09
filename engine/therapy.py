# -*- coding: utf-8 -*-
"""
destiny-daily :: engine.therapy
「今日食疗 / 经络拍拉」调理层 —— 按体质方向做每日轮转。

设计原则（与 almanac.py 一致）：
  1. 纯本地推算，不依赖任何数据库、不联网，境外 GitHub Actions 同样可跑。
     轮换只用 base.day_gz（日干支序，逐日 +1，60 日一循环）与
     base.current_jie（节气），同一天无论跑几次结果完全一致。
  2. 只做「日常食疗 / 经络保健参考」，不下诊断、不开处方，
     不替代面诊；所有加减都注明适用体感与暂停条件。
  3. 【隐私】本仓库公开，个人体质档案（症状、辨识结论、当前调理）一律
     不写在代码里。代码内只保留「通用默认值 + 通用中医调理知识」，
     真实档案由 profile.json 的 constitution 段注入 —— 云端由
     scripts/make_profile.py 从 GitHub Secret DESTINY_CONSTITUTION
     现场写入，仓库中不含任何可指向特定个人的健康描述。
     如需连同食疗/穴位文案一起定制，可再用 Secret DESTINY_THERAPY
     注入 profile["therapy"] 做整段覆盖（见 _apply_override）。
     无 Secret 时自动降级为通用版，功能完整、不报错。

对外唯一入口：therapy_of(dt, focus_wx=None, profile=None) -> dict
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .base import current_jie, day_gz, ensure_cst

# ---------------------------------------------------------------- 体质基线
# 【仅通用默认值，不含任何个人健康资料】
# 真实档案由 profile["constitution"] 覆盖；该段由 Secret 注入，不入公开仓库。
# 下面这段是「未配置个人档案」时展示的中性内容，任何人都适用。

CONSTITUTION = {
    "label": "通用调理 · 顾护脾胃为本",
    "direction": "顾护脾胃、扶正固本，随四时与当日五行微调",
    "basis": [
        "以平和为本：饮食温软规律、忌生冷贪凉、作息勿熬夜。",
        "食疗以四神汤类平和健脾方为基础，加减务必辨明体感再用。",
        "个人体质档案未注入时，本栏目只给通用保健方向，不作个体辨识。",
    ],
    "current_regimen": "四神汤（茯苓 / 山药 / 莲子 / 芡实）—— 健脾祛湿的通用基础方。",
}

# 四神汤底方（每日固定，作为其余加减的基础）
CORE_DECOCTION = "四神汤底方：茯苓 15g、山药 15g、莲子 15g、芡实 15g，可配瘦肉或排骨同炖，温服。"

# ---------------------------------------------------------------- 食疗轮转表
# 每方 5 个字段：名称 / 组成与做法 / 对症体感 / 服法 / 注意
# 轮转以日干支序取模，8 日一轮；加减方每周 2~3 次即可，不必天天换。
DIET_PLANS: List[Dict] = [
    {
        "name": "四神汤 · 原方（守方日）",
        "items": [
            "不加味，专注健脾祛湿；汤渣同食，莲子芡实煮至软烂更好消化。",
            "配一碗温热小米粥作早餐，辰时 7~9 点胃经当令时进食。",
        ],
        "for": "无明显加重体感时的日常守方，观察舌象与苔色变化。",
        "dose": "午后或傍晚温服一碗，睡前 2 小时不再饮汤，以免夜尿扰眠。",
        "care": "感冒发热、咽痛或舌苔转黄腻时暂停，改清淡饮食。",
    },
    {
        "name": "四神汤 · 陈皮炒薏米加减（化湿）",
        "items": [
            "加陈皮 3g、炒薏苡仁 15g；薏苡仁务必炒用（或干锅小火炒至微黄）以减寒性。",
            "舌苔白厚、身体困重、大便黏滞时最合拍。",
        ],
        "for": "舌苔白厚、头身困重、湿浊偏盛。",
        "dose": "每周 2~3 次，午后温服；连服 3 天白苔未转薄即停，回到原方。",
        "care": "脾虚便溏者薏米减至 10g；出汗多、口干明显时不宜久用。",
    },
    {
        "name": "四神汤 · 玉屏风加减（固表通鼻）",
        "items": [
            "加黄芪 10g、炒白术 10g、防风 5g、生姜 2 片（取玉屏风之意）。",
            "遇冷流清涕、晨起喷嚏频作、易感冒时适用。",
        ],
        "for": "表虚易感、畏风、卫表不固。",
        "dose": "上午温服，服后避风；每周 2~3 次，症状缓和即回原方。",
        "care": "一旦出现黄浊涕、咽痛、发热等化热征象立即停用，及时就医；血压偏高或正在服药者先咨询医师。",
    },
    {
        "name": "四神汤 · 参术红枣加减（益气健脾）",
        "items": [
            "加党参 10g、炒白术 10g、红枣 3 枚（去核）。",
            "食后腹胀、乏力、大便偏溏时适用。",
        ],
        "for": "脾虚气弱、气短乏力、食后困倦。",
        "dose": "早餐后至午前温服，不宜晚间服用以免腹胀。",
        "care": "腹胀明显时芡实、莲子各减至 10g；口干口苦时暂缓。",
    },
    {
        "name": "四神汤 · 归杞黑芝麻加减（养肝血）",
        "items": [
            "加当归 6g、枸杞 10g，起锅前撒熟黑芝麻 1 小勺。",
            "另可单用黑芝麻核桃糊作下午加餐，缓慢补养。",
        ],
        "for": "眼干、睡眠浅、爪甲失养等血虚之象。",
        "dose": "每周 1~2 次即可，晚饭后 2 小时温服，连服一月再观察体感。",
        "care": "便溏或腹泻时当归减半或去之；感冒期间停用。",
    },
    {
        "name": "四神汤 · 山药小米粥佐餐（温和养脾）",
        "items": [
            "汤方不加味，早餐另煮山药小米南瓜粥：鲜山药 30g、小米 50g、南瓜 100g，可加 2 枚红枣。",
            "不寒不腻，作为加减方之间的缓冲日；粥忌加糖、忌配冷饮。",
            "细嚼慢咽，每口约 20 下，减轻脾胃负担。",
        ],
        "for": "脾胃疲弱、食欲一般，或加减方之间的缓冲日。",
        "dose": "粥于辰时 7~9 点作早餐温服七分饱；四神汤仍按午后温服。",
        "care": "血糖偏高者南瓜减量并监测餐后血糖。",
    },
    {
        "name": "四神汤 · 姜枣葱白佐饮（受凉备用）",
        "items": [
            "汤方照常不加味；本日备一剂生姜 3 片、红枣 3 枚（去核）、葱白 2 段，水煮 10 分钟。",
            "仅在清水涕骤增、畏寒、鼻塞而无咽痛时温饮，未受凉则不必煮。",
            "饮后覆被微汗即止，不可大汗；汗后避风、及时擦干。",
        ],
        "for": "受凉后清涕、鼻塞、怕冷（风寒初起）的临时应对。",
        "dose": "受凉后温饮一次，当日一次为限，不连续超过 2 天；四神汤与之错开 2 小时。",
        "care": "咽痛、口干、黄涕、发热者禁用；有胃热泛酸者生姜减量。",
    },
    {
        "name": "四神汤 · 瘦肉炖法（补脾固摄）",
        "items": [
            "底方配瘦猪肉 100g，小火炖 60 分钟；可加 2 片生姜温中。",
            "少盐，不放味精；配一小碗糙米饭，作为当日主餐的汤品。",
            "莲子、芡实煮至软烂，汤渣同食更助脾运。",
        ],
        "for": "易疲、便溏、夜间频尿或晨起面部浮肿。",
        "dose": "午间温服，每周 1~2 次。",
        "care": "便秘或腹胀明显时芡实减量（收涩）；高尿酸者浓肉汤不宜多饮。",
    },
]

# 忌口 / 饮食习惯（每日固定，精简为 5 条，避免刷屏）
AVOID = [
    "严格忌冰饮、生冷沙拉与大量寒凉水果（西瓜、梨、香蕉）；甜腻糕点、奶茶、乳制品助湿，宜减。",
    "忌空腹冷食、暴饮暴食与夜宵；20:00 后不再进食，晚餐七分饱。",
    "油炸、烧烤、烈酒与过咸皆伤脾生湿；烹调以蒸、煮、炖为主。",
    "晨起先饮一杯温水再进食；全天小口温饮，不以冷茶代水。",
    "鼻窍不适期减少辛辣刺激与酒精，避免冷热骤变刺激鼻黏膜。",
]

# ---------------------------------------------------------------- 穴位拍拉组

ACU_GROUPS: List[Dict] = [
    {
        "name": "健脾祛湿组（足太阴脾经）",
        "points": [
            "足三里：外膝眼下 3 寸、胫骨前缘一横指，双向按揉 3 分钟（健脾益气第一要穴）。",
            "阴陵泉：胫骨内侧髁下方凹陷，按揉 3 分钟（利水化湿）。",
            "丰隆：外膝眼与外踝连线中点、胫骨旁两横指，按揉 2 分钟（化痰湿）。",
            "三阴交：内踝尖上 3 寸，按揉 2 分钟（肝脾肾三经交会）。",
        ],
        "method": [
            "巳时 9~11 点脾经当令，此时按揉效果最佳；每穴以酸胀为度，不追求疼痛。",
            "再沿大腿内侧至小腿内侧拍打脾经 5 分钟，自上而下、掌心虚拍至微热。",
        ],
    },
    {
        "name": "固表通鼻组（手太阴肺经 / 头面）",
        "points": [
            "迎香：鼻翼旁开 0.5 寸，两食指搓热后上下搓擦 50 次至鼻梁发热（通鼻第一要穴）。",
            "印堂：两眉中点，指腹按揉 2 分钟；再沿眉弓向两侧分推 20 次。",
            "风池：后颈枕骨下两侧凹陷，拇指按揉 2 分钟，方向朝鼻尖（祛风散寒）。",
            "大椎 / 肺俞：颈后第 7 颈椎下及第 3 胸椎旁开 1.5 寸，搓热或轻拍至温热。",
        ],
        "method": [
            "晨起洗脸前先搓迎香，有助缓解遇冷流涕；出门前搓热大椎、风池护表。",
            "再沿手臂内侧前缘（肺经）自肩向拇指方向拍打 3 分钟，左右各一次。",
        ],
    },
    {
        "name": "养肝血组（足厥阴肝经 / 足少阴肾经）",
        "points": [
            "太冲：足背第 1、2 趾骨间凹陷，向足心方向按揉 3 分钟（疏肝养血）。",
            "血海：屈膝，髌骨内上缘上 2 寸，按揉 3 分钟（补血要穴）。",
            "太溪：内踝尖与跟腱之间凹陷，按揉 3 分钟（滋肾填精，助生血）。",
            "三阴交：内踝尖上 3 寸，按揉 2 分钟；睡前以木梳梳头 100 下。",
        ],
        "method": [
            "酉时 17~19 点肾经当令或睡前温水泡脚 15 分钟后操作，最宜养血。",
            "配合十指从指尖向指根逐一捋按 10 遍，改善末梢循环、助气血荣养。",
        ],
    },
]

# 每日固定功课（不轮转）
ROUTINE = [
    "摩腹：睡前仰卧，掌心绕脐顺时针 36 圈、逆时针 36 圈，力度轻柔，助脾运化。",
    "拍八虚：腋窝、肘窝、腹股沟、腘窝各虚掌拍 30~50 下至微热，促气血周流。",
    "晨起搓迎香 50 次 + 温水一杯，作为每日固定起手式。",
]

# 时辰提示（每日固定）
TIMING = [
    "辰时 7~9 胃经：温热早餐，忌冷食；巳时 9~11 脾经：按揉健脾穴。",
    "酉时 17~19 肾经：养血穴与泡脚；23 点前入睡，肝血得藏，方有改善余地。",
]

# 节气/季节提示
_SEASON = {
    "春": "春月风盛，鼻窍易感：出门护好后颈风池，少食笋、虾蟹等发物，辛温之品不宜过量。",
    "夏": "夏月湿重且贪凉最伤脾：空调房护腹背，冷饮一律不碰，可佐炒薏米、赤小豆。",
    "秋": "秋燥伤肺：四神汤可加百合、银耳少许，晨起温水润鼻，忌过度辛辣与熬夜。",
    "冬": "冬三月避寒就温：晨起先温饮、外出戴口罩护鼻，汤药一律温服，忌一切冷食。",
}
_JIE_SEASON = {
    "立春": "春", "惊蛰": "春", "清明": "春", "立夏": "夏", "芒种": "夏",
    "小暑": "夏", "立秋": "秋", "白露": "秋", "寒露": "秋", "立冬": "冬",
    "大雪": "冬", "小寒": "冬",
}

# 当日五行 -> 脏腑侧重（与 synthesize 的 focus_wx 联动）
_WX_NOTE = {
    "木": "当日五行偏「木」，肝胆筋目当令；筋目与眼干可多留意，穴位偏向养肝血。",
    "火": "当日五行偏「火」，心血当令；忌熬夜耗神，午间小憩，按揉宜轻缓。",
    "土": "当日五行偏「土」，脾胃当令；正是健脾祛湿的主场，饮食务求温软规律。",
    "金": "当日五行偏「金」，肺与皮毛鼻窍当令；鼻窍最易被引动，晨起搓迎香、出门护口鼻。",
    "水": "当日五行偏「水」，肾与骨当令；忌受寒过劳，泡脚与太溪按揉可加重。",
}

DISCLAIMER = ("以上为日常食疗与经络保健参考，非医疗诊断或处方；症状持续加重、鼻涕转黄浊、"
              "发热、舌象明显变化或出现新的不适，请至耳鼻喉科 / 中医科面诊。"
              "正在服药、有慢性病或准备长期加味者，请先咨询执业中医师。"
              "皮肤破损、静脉曲张、出血倾向、急性发热期不宜拍打。")

# ---------------------------------------------------------------- 主入口

# profile 里允许覆盖的白名单（只认这些键，其它一律忽略，避免脏配置污染输出）
_OVERRIDE_KEYS = {
    "constitution", "core_decoction", "diet_plans", "avoid", "acu_groups",
    "routine", "timing", "season", "wx_note", "disclaimer",
}


def _overrides(profile: Optional[Dict]) -> Dict:
    """取 Secret 注入的个人调理配置。

    两种写法都支持（make_profile.py 会把 Secret 写进 profile.json）：
      - profile["constitution"]          个人体质档案（常用，短）
      - profile["therapy"][<任一白名单键>]  连同食疗/穴位文案整套定制（可选）
    未配置时返回空 dict，全部走公开代码里的通用默认值。
    """
    out: Dict = {}
    if not isinstance(profile, dict):
        return out
    pack = profile.get("therapy")
    if isinstance(pack, dict):
        out.update({k: v for k, v in pack.items() if k in _OVERRIDE_KEYS})
    c = profile.get("constitution")
    if isinstance(c, dict) and "constitution" not in out:
        out["constitution"] = c
    return out


def therapy_of(dt: datetime, focus_wx: Optional[str] = None,
               profile: Optional[Dict] = None) -> Dict:
    """返回当日食疗与经络调理方案；同日结果确定不变。"""
    t = ensure_cst(dt)
    idx = day_gz(t)                       # 逐日 +1，可作稳定轮换种子
    ov = _overrides(profile)

    plans = ov.get("diet_plans") or DIET_PLANS
    groups = ov.get("acu_groups") or ACU_GROUPS
    core = ov.get("core_decoction") or CORE_DECOCTION
    plans = [p for p in plans if isinstance(p, dict) and p.get("name")]
    groups = [g for g in groups if isinstance(g, dict) and g.get("name")]
    if not plans:
        plans = DIET_PLANS
    if not groups:
        groups = ACU_GROUPS

    plan = plans[idx % len(plans)]
    # 每日都锚定底方，轮转的只是加减 / 佐方
    diet = dict(plan)
    diet["items"] = [core] + list(plan.get("items", []))
    acu = groups[(idx // len(plans) + idx) % len(groups)]

    jie_name, _ = current_jie(t)
    season = _JIE_SEASON.get(jie_name, "")
    season_note = (ov.get("season") or _SEASON).get(season, "")
    wx_line = (ov.get("wx_note") or _WX_NOTE).get(focus_wx or "", "")

    cfg = dict(CONSTITUTION)
    c = ov.get("constitution")
    if isinstance(c, dict):
        for k, v in c.items():
            if k in cfg and v:
                cfg[k] = v

    return {
        "constitution": cfg["label"],
        "direction": cfg["direction"],
        "basis": list(cfg["basis"]),
        "current_regimen": cfg["current_regimen"],
        "diet": diet,
        "avoid": list(ov.get("avoid") or AVOID),
        "acupoint": acu,
        "routine": list(ov.get("routine") or ROUTINE),
        "timing": list(ov.get("timing") or TIMING),
        "season_note": season_note,
        "wx_note": wx_line,
        "disclaimer": ov.get("disclaimer") or DISCLAIMER,
        "rotation_hint": f"第 {idx % len(plans) + 1}/{len(plans)} 方 · 按日干支轮转",
    }


def render_therapy_text(a: Dict) -> List[str]:
    """纯文本版：食疗 / 忌口 / 穴位 / 功课，供日报 TXT 与调试使用。"""
    L: List[str] = []
    d, ac = a["diet"], a["acupoint"]
    L.append(f"【今日食疗】{d['name']}　|　{a['rotation_hint']}")
    for x in d["items"]:
        L.append(f"  · {x}")
    L.append(f"  对症：{d['for']}")
    L.append(f"  服法：{d['dose']}")
    L.append(f"  注意：{d['care']}")
    L.append("【饮食宜忌】")
    for x in a["avoid"]:
        L.append(f"  · {x}")
    L.append(f"【穴位拍拉按摩】{ac['name']}")
    for x in ac["points"]:
        L.append(f"  · {x}")
    for x in ac["method"]:
        L.append(f"  · {x}")
    L.append("【每日固定功课】")
    for x in a["routine"]:
        L.append(f"  · {x}")
    for x in a["timing"]:
        L.append(f"  · {x}")
    if a["season_note"]:
        L.append(f"  · {a['season_note']}")
    if a["wx_note"]:
        L.append(f"  · {a['wx_note']}")
    L.append(f"  · 提示：{a['disclaimer']}")
    return L


if __name__ == "__main__":  # pragma: no cover
    import sys
    from datetime import timedelta
    days = ([datetime.strptime(x, "%Y-%m-%d") for x in sys.argv[1:]]
            or [datetime.now()])
    for dt in days:
        a = therapy_of(dt, focus_wx="土")
        print("=" * 70)
        print(dt.strftime("%Y-%m-%d"), "|", a["constitution"], "|",
              a["diet"]["name"], "|", a["acupoint"]["name"])
        print("\n".join(render_therapy_text(a)[:6]))
