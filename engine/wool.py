# -*- coding: utf-8 -*-
"""
数字资产板块：平台活动薅羊毛 + 观察清单。

设计取舍
--------
「为什么不做实时活动抓取？」
币安活动公告接口（www.binance.com/bapi/...）在境内外网络表现不一致，
且公告标题多为英文，抓回来对本报告读者价值有限。更重要的是：
币安的羊毛通道绝大多数是「长期机制」（Launchpool / HODLer 空投 / Megadrop /
Simple Earn / 推荐返佣 …），机制本身比"今天开了哪一期"稳定得多。
因此这里维护一份中文「常青通道库」，每日轮换深度讲 2 项、速览 4 项，
并附官网直达链接查当期项目 —— 永不失效、全中文、零依赖。

「观察清单为什么联网？」
价格是事实且必须当日新鲜。联网失败时降级为"只列清单与观察理由"，
不影响整份报告生成（同 market 模块的一贯策略）。

风险立场
--------
本模块只描述"平台机制是什么、门槛与风险在哪"，不给任何收益承诺，
不推荐任何具体代币。双币投资、合约体验金这类高风险的已明确标注为
「不是羊毛，是风险」。
"""
from datetime import datetime
from typing import Dict, List, Optional

from . import market

# ---------------------------------------------------------------- 官网入口

SITE = "https://www.binance.com/zh-CN"

# ---------------------------------------------------------------- 观察清单

# (交易对, 显示名, 定位, 观察理由 —— 静态，不随行情变)
WATCHLIST: List[tuple] = [
    ("BTCUSDT", "BTC", "核心锚定",
     "组合的基准尺子，其余标的强弱都拿它对照；仓位纪律先在它身上生效。"),
    ("ETHUSDT", "ETH", "生态主资产",
     "L2 与质押经济的基本盘，波动通常略大于 BTC，是主流里的中性选择。"),
    ("SOLUSDT", "SOL", "高波动进攻",
     "弹性最大的主流之一，涨跌幅常在 BTC 的 1.5~2 倍，因此仓位要比 BTC 更轻。"),
    ("BNBUSDT", "BNB", "平台币 · 羊毛钥匙",
     "Launchpool / Megadrop / HODLer 空投多以 BNB 锁仓或持仓快照为门槛，"
     "与上面的薅羊毛直接相关。"),
    ("XRPUSDT", "XRP", "事件驱动",
     "受监管与 ETF 消息影响极大，属消息驱动型，不适合当作长期底仓。"),
]

# ---------------------------------------------------------------- 常青羊毛通道库

# 每项：key / 名称 / 类型 / 门槛 / 怎么薅 / 拿到什么 / 风险 / 星级 / 链接 / 一句话
def _w(key, name, kind, need, how, gain, risk, stars, path, one):
    return {"key": key, "name": name, "kind": kind, "need": need, "how": how,
            "gain": gain, "risk": risk, "stars": stars,
            "link": SITE + path, "one": one}


WOOL: List[Dict] = [
    _w("launchpool", "新币挖矿 Launchpool", "长期",
       "持有 BNB / FDUSD / USDC 等当期的指定币种；锁仓期内不能卖出。",
       "进 Launchpool 页选池子 → 锁仓 → 每日自动累计产出 → 到期自动解锁。",
       "本金原样退回，额外多拿一份新币。单看年化通常不高，胜在「本金不亏」。",
       "新币上线可能破发；锁仓期间损失这部分资金的其他机会。",
       5, "/launchpool", "零成本拿新币，羊毛主线"),
    _w("hodler", "HODLer 空投（持仓快照）", "长期",
       "在官方公告的「快照期」内持有 BNB，并放入 Simple Earn 赚币产品。",
       "盯公告 → 快照期内把 BNB 放进赚币 → 空投按持仓追溯发放，无需手动申购。",
       "完全被动，操作成本几乎为零，是性价比最高的一类。",
       "错过快照期没有补发；BNB 本身有价格波动，不是无风险。",
       5, "/earn", "被动追溯发放，最省心"),
    _w("simpleearn", "Simple Earn 保本赚币（加息档）", "长期",
       "有闲置 USDT/USDC 或主流币即可，门槛最低。",
       "买入活期或定期 → 留意新币首期加息、阶梯加息券 → 到期自动赎回。",
       "稳定币年化收益，波动小，适合放「等待期」的资金。",
       "平台风险与稳定币脱锚风险；定期产品提前赎回会损失利息。",
       5, "/simple-earn", "闲置资金的基本盘"),
    _w("learn", "Learn & Earn 学赚", "阶段",
       "完成身份认证即可；答题名额有限，常需抢。",
       "看教学视频或文章 → 答对题目 → 领取代币奖励。",
       "零成本、几分钟完成，纯粹白拿。",
       "名额经常秒光；单次奖励金额通常不大。",
       4, "/learn", "零投入，几分钟搞定"),
    _w("megadrop", "Megadrop（锁仓 + Web3 任务）", "阶段",
       "BNB 锁仓 + 完成指定 Web3 任务（绑定钱包、链上交互等）。",
       "锁定 BNB → 按任务清单完成链上操作 → 按份额加权分配奖励。",
       "份额通常高于纯锁仓类活动。",
       "链上任务要花 gas；「只认官网任务页」，任何私信发来的链接一律不点。",
       4, "/megadrop", "份额更高，但要动手"),
    _w("referral", "推荐返佣 Referral", "长期",
       "有真实新用户可被邀请（对方需实际交易才产生返佣）。",
       "生成返佣链接或邀请码 → 对方注册并交易 → 持续拿手续费返佣。",
       "被动、长期，可调返佣比例回馈被邀请人。",
       "不得承诺收益、不得公开诱导开户 —— 合规表述是底线。",
       4, "/referral", "长期被动，合规第一"),
    _w("launchpad", "Launchpad 新币打新", "阶段",
       "持仓快照期内持有 BNB，并按规则获得认购额度。",
       "快照期备好 BNB → 申购 → 中签后自动扣款 → 上市后自行处理。",
       "中签上市通常有溢价。",
       "中签率偏低，上市也可能破发；需提前占用 BNB 仓位。",
       3, "/launchpad", "打新，看运气"),
    _w("zerofee", "零手续费交易对", "阶段",
       "无门槛，看公告指定哪些交易对为 0 费率。",
       "关注公告 → 在这些交易对上做本来就计划好的换仓。",
       "直接省手续费，做网格或搬砖时效果最明显。",
       "只为省费，「不要为了免手续费而多做出本不该做的交易」。",
       3, "/support/announcement", "省手续费，别为省而做"),
    _w("alpha", "Alpha / Web3 钱包积分活动", "阶段",
       "需要币安 Web3 钱包与链上交互。",
       "完成指定链上交易积累积分 → 积分兑换空投或代币。",
       "有机会拿到早期项目份额。",
       "⚠ 链上交互有 gas 与合约授权风险，「假冒活动极多」，只从官方入口进入。",
       3, "/alpha", "链上积分，防假冒"),
    _w("newuser", "新人礼包 / 体验金", "一次性",
       "仅限从未注册过的新账户，老用户不适用。",
       "注册 → 完成身份认证 → 领取优惠券或体验金 → 按规则交易。",
       "起点奖励，一次性。",
       "体验金通常需完成规定交易量，盈利部分才可提现。",
       3, "/activity", "只有一次，别浪费"),
    _w("tradingcomp", "交易竞赛 / 交易量排行榜", "阶段",
       "需先报名，并按指定交易对累积交易额。",
       "报名 → 在指定交易对累积交易额 → 按排名分奖池。",
       "奖池金额有时不小。",
       "⚠ 为冲量频繁交易，手续费与滑点常常「超过奖金本身」。"
       "只在你本来就要交易的量上顺手做，不要为排名造量。",
       2, "/activity", "易反亏，量力而为"),
    _w("pay", "Binance Pay 红包 / 返现", "长期",
       "开通 Binance Pay，需要好友互动。",
       "发红包或邀请好友通过 Pay 转账 → 得返现券。",
       "频次高，可反复。",
       "金额小，且涉及好友与隐私 —— 别为几块钱去打扰别人。",
       2, "/binance-pay", "小额高频，别扰人"),
    _w("bonus", "合约体验金 / 赠金", "阶段",
       "由活动发放，通常需完成指定任务。",
       "领券 → 用赠金开合约单 → 盈利可提、赠金本身不可提。",
       "名义上免费试错。",
       "⚠ 高倍一把梭最容易把赠金亏光，还会养成坏习惯。"
       "只做低倍、当练习，别把它当收入。",
       2, "/activity", "赠金不是收入"),
    _w("dual", "双币投资 Dual Investment", "高风险",
       "有币或 USDT 即可，门槛极低 —— 这正是它危险的地方。",
       "选目标价与到期日 → 到期按条件自动结算。",
       "名义年化看起来很高。",
       "⚠ 「这不是羊毛，是卖出期权」：可能被结算成另一种币，或在不利价位被动接货。"
       "本栏目不推荐把它当作薅羊毛手段。",
       1, "/dual-investment", "不是羊毛，是风险"),
]

# ---------------------------------------------------------------- 防坑清单

SAFETY: List[str] = [
    "只从官网活动页进入。任何私信、社群、邮件里发来的「活动链接」一律不点。",
    "任何人索要助记词、私钥、验证码的都是骗子 —— 官方永远不会问。",
    "链上任务只授权你知道的合约，交互后及时撤销不用的授权。",
    "收益越高说明你要承担的风险越大：锁仓考验机会成本，打新考验破发，竞赛考验手续费。",
    "开启提现白名单 + 二次验证（2FA），这是账户层面最值得花的两分钟。",
    "所有「内部消息」「保本高息」「代客操作」都是骗局标准话术。",
]


# ---------------------------------------------------------------- 组装

def _fmt_price(p: float) -> str:
    """按量级选小数位 —— BTC 显示整数，XRP 显示四位。"""
    if p >= 1000:
        return f"{p:,.0f}"
    if p >= 10:
        return f"{p:,.2f}"
    if p >= 1:
        return f"{p:,.3f}"
    return f"{p:,.4f}"


def _row_note(row: Dict) -> str:
    """把客观量翻译成一句话状态描述。只描述，不判断方向。"""
    bits = []
    dev = row.get("ma30_dev")
    if dev is not None:
        bits.append(f"较 MA30 {'高' if dev >= 0 else '低'} {abs(dev):.1f}%")
    pos = row.get("pos30")
    if pos is not None:
        bits.append(f"处近 30 日区间 {pos:.0f}% 分位")
    v = row.get("vol")
    if v is not None:
        bits.append(f"年化波动 {v:.0f}%")
    return "，".join(bits) + "。" if bits else "日线数据未取到。"


def watch_rows(symbols: Optional[List[str]] = None,
               offline: bool = False) -> Dict:
    """取观察清单行情。失败或 offline 时降级：仍返回清单（名称+理由），只是没有价格。"""
    symbols = symbols or [w[0] for w in WATCHLIST]
    meta = {w[0]: w for w in WATCHLIST}
    snap = ({"ok": False, "rows": {}, "ts": "", "error": "offline"}
            if offline else market.build_watch(symbols))
    rows = []
    for s in symbols:
        sym, name, role, why = meta.get(s, (s, s, "", ""))
        q = snap.get("rows", {}).get(s)
        row = {"sym": sym, "name": name, "role": role, "why": why,
               "ok": bool(q)}
        if q:
            row.update({"price": q["price"], "chg": q["chg"],
                        "ma30_dev": q.get("ma30_dev"), "pos30": q.get("pos30"),
                        "vol": q.get("vol")})
            row["note"] = _row_note(q)
            row["price_txt"] = _fmt_price(q["price"])
        rows.append(row)
    return {"ok": snap.get("ok", False), "rows": rows,
            "ts": snap.get("ts", ""), "error": snap.get("error", "")}


# 轮换起始日：对齐到本板块上线日 2026-10-03，使首日从第 1 条（价值最高的通道）开始，
# 而不是随机落在某一条上。库内顺序已按实用性降序排好。
EPOCH = datetime(2026, 10, 3).toordinal()


def pick_wool(target: datetime, focus_n: int = 2, glance_n: int = 4) -> Dict:
    """
    按日期确定性轮换羊毛条目。同一天必得同一组，相邻几天不重样。
    重点 focus_n 条（完整展开）+ 速览 glance_n 条（一句话）。
    """
    n = len(WOOL)
    p = ((target.toordinal() - EPOCH) * 2) % n   # 步长 2，保证每天推进不原地打转
    focus = [WOOL[(p + i) % n] for i in range(focus_n)]
    glance = [WOOL[(p + focus_n + i) % n] for i in range(glance_n)]
    return {"focus": focus, "glance": glance,
            "total": n, "cursor": p,
            "site": SITE + "/activity"}


def wool_advice(cai_score: float) -> str:
    """把当日财气翻译成「今天做哪类羊毛」的分配建议 —— 只限投入程度，不限具体项目。"""
    if cai_score >= 70:
        return ("今日财气较旺，可以处理需要占用资金的项目：锁仓挖矿、定期加息、打新申购，"
                "今天的判断力相对在线。")
    if cai_score >= 50:
        return ("今日财气中性，以零成本项目为主（学赚答题、快照持仓、公告蹲守）；"
                "需要拿出本金的留一留，不必赶今天。")
    if cai_score >= 40:
        return ("今日财气偏弱，只做零投入项：答题、看公告、确认持仓是否在快照期内。"
                "不做新开仓，不追加锁仓。")
    return ("今日财气很弱，属于该收的日子。今天唯一该做的羊毛动作是"
            "「确认没有到期未赎回的产品」，其余一律不动。")


def build(target: datetime, cai_score: float,
          symbols: Optional[List[str]] = None,
          offline: bool = False) -> Dict:
    """组装整个数字资产板块。"""
    w = pick_wool(target)
    try:
        watch = watch_rows(symbols, offline=offline)
    except Exception as e:                  # noqa: BLE001
        watch = {"ok": False, "rows": [
            {"sym": s, "name": nm, "role": rl, "why": why, "ok": False}
            for s, nm, rl, why in WATCHLIST], "ts": "", "error": repr(e)[:120]}
    return {
        "focus": w["focus"],
        "glance": w["glance"],
        "total": w["total"],
        "site": w["site"],
        "advice": wool_advice(cai_score),
        "watch": watch,
        "safety": SAFETY,
        "disclaimer": "以上均为平台机制说明，非收益承诺、非投资建议；"
                      "当期是否有活动、具体收益率以官网活动页为准。",
    }


if __name__ == "__main__":
    b = build(datetime(2026, 10, 3, 8, 0), 60.0)
    print("今日重点：", "、".join(x["name"] for x in b["focus"]))
    print("速览：", "、".join(x["name"] for x in b["glance"]))
    print("建议：", b["advice"])
    print(f"\n观察清单（ok={b['watch']['ok']} {b['watch'].get('ts','')}"
          f" {b['watch'].get('error','')}）")
    for r in b["watch"]["rows"]:
        if r["ok"]:
            print(f"  {r['name']:<5} {r['price_txt']:>12}  {r['chg']:+6.2f}%  {r['note']}")
        else:
            print(f"  {r['name']:<5} 行情未取到 —— {r['why'][:30]}")
