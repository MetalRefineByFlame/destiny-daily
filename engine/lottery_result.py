# -*- coding: utf-8 -*-
"""
彩票推荐「回溯核对」：把历次推送过的号码记进台账，次日自动抓官方开奖号并对奖。

数据来源：
  主源（官方，只读）：
    双色球 / 快乐8 -> 中国福利彩票 www.cwl.gov.cn
    大乐透        -> 中国体育彩票 webapi.sporttery.cn
  备用源（仅主源不可达时启用）：
    500 彩票网 XML -> kaijiang.500.com/static/info/kaijiang/xml/<code>/list.xml

  ⚠ 为什么必须有备用源：cwl.gov.cn 与 sporttery.cn 按 IP 属地封锁，
    境外出口（GitHub Actions 的 Azure 节点）访问一律返回 403 Forbidden，
    而早报正是跑在 GitHub Actions 上的。没有备用源，云端永远核不出奖，
    还会把「取数失败」误报成「官方尚未公布」。
    500 彩票网全球可达（含美国节点），三个彩种统一 XML、含开奖日期，故选它兜底。

设计原则：
  1) 只对「已经推送过」的号码核对，不做事后诸葛式的补号。
  2) 台账落盘（data/lottery_picks.json），结果算过一次就缓存，不重复联网。
  3) 抓不到开奖数据时降级，绝不影响主报告生成；但**必须如实说明是取数失败，
     不得伪装成「官方未公布」**（用 result_reason 区分）。
  4) 只报「中没中、中几个、几等奖」，不承诺具体金额（浮动奖以官方公告为准）。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
LOG_PATH = os.path.join(_ROOT, "data", "lottery_picks.json")

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.cwl.gov.cn/",
}

TIMEOUT = 12
REVIEW_WINDOW = 1      # 只核对「昨日」的推荐（用户要求：只给最近一天）
SHOW_WINDOW = 1        # 报告里只展示 1 条


# ---------------------------------------------------------------- 抓取
def _http_json(url: str) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, ValueError, OSError):
        return None


def _cwl(name: str, count: int) -> List[Dict]:
    """福彩双色球 ssq / 快乐8 kl8"""
    url = ("https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
           f"?name={name}&issueCount={count}")
    j = _http_json(url)
    out: List[Dict] = []
    if not j or not j.get("result"):
        return out
    for it in j["result"]:
        d = str(it.get("date", ""))[:10]
        red = [int(x) for x in re.findall(r"\d+", it.get("red") or "")]
        blue = [int(x) for x in re.findall(r"\d+", it.get("blue") or "")]
        if not d or not red:
            continue
        out.append({"date": d, "issue": str(it.get("code", "")),
                    "front": sorted(red), "back": sorted(blue)})
    return out


def _dlt(count: int) -> List[Dict]:
    """体彩大乐透"""
    url = ("https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
           f"?gameNo=85&provinceId=0&pageSize={count}&isVerify=1&pageNo=1")
    j = _http_json(url)
    out: List[Dict] = []
    try:
        lst = (j or {}).get("value", {}).get("list") or []
    except AttributeError:
        return out
    for it in lst:
        d = str(it.get("lotteryDrawTime", ""))[:10]
        nums = [int(x) for x in re.findall(r"\d+", it.get("lotteryDrawResult") or "")]
        if not d or len(nums) < 7:
            continue
        out.append({"date": d, "issue": str(it.get("lotteryDrawNum", "")),
                    "front": sorted(nums[:5]), "back": sorted(nums[5:7])})
    return out


# ---- 备用源：500 彩票网（全球可达，用于境外出口的 CI 环境）----
_XML_500_CODE = {"双色球": "ssq", "大乐透": "dlt", "快乐8": "kl8"}
_XML_500_URL = "https://kaijiang.500.com/static/info/kaijiang/xml/{code}/list.xml"

# 各彩种合法号码形态 (前区个数, 后区个数)。备用源必须逐条校验，
# 否则格式一变就会把别的玩法的号码当成当日开奖号，导致奖级误判。
_DRAW_SHAPE = {"双色球": (6, 1), "大乐透": (5, 2), "快乐8": (20, 0)}

# 每次抓取后记录状态，供 review() 区分「取数失败」与「官方确实未公布」
_FETCH_STATE: Dict[str, Dict] = {}


def _http_text(url: str, referer: str = "") -> Optional[str]:
    """取纯文本（HTML / XML 数据源）。失败返回 None。"""
    h = dict(UA)
    if referer:
        h["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        return None
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _500(game: str, count: int) -> List[Dict]:
    """
    500 彩票网 XML：<row expect="期号" opencode="号码" opentime="开奖时间"/>
      opencode 用 | 分隔前后区：双色球 6+1、大乐透 5+2、快乐8 无分隔（20 个）。
    """
    code = _XML_500_CODE.get(game)
    if not code:
        return []
    txt = _http_text(_XML_500_URL.format(code=code),
                     referer="https://kaijiang.500.com/")
    if not txt:
        return []
    out: List[Dict] = []
    shape = _DRAW_SHAPE.get(game)
    for m in re.finditer(r"<row\b([^>]*?)/?>", txt):
        attrs = m.group(1)

        def attr(key: str) -> str:
            mm = re.search(rf'{key}\s*=\s*"([^"]*)"', attrs)
            return mm.group(1) if mm else ""

        date = attr("opentime")[:10]
        raw_nums = attr("opencode")
        if not date or not raw_nums:
            continue
        seg = raw_nums.split("|")
        front = [int(x) for x in re.findall(r"\d+", seg[0])]
        back = [int(x) for x in re.findall(r"\d+", seg[1])] if len(seg) > 1 else []
        if not front:
            continue
        if shape and (len(front), len(back)) != shape:
            continue          # 形态不符，宁可不用也不能错判
        out.append({"date": date, "issue": attr("expect"),
                    "front": sorted(front), "back": sorted(back)})
        if len(out) >= count:
            break
    return out


def fetch_draws(game: str, count: int = 20) -> List[Dict]:
    """
    取该彩种最近若干期开奖。官方源优先，不可达时自动切备用源。

    返回 [] 表示「两个源都没拿到」——调用方必须据此区分失败原因，
    不能当成「官方还没公布」。
    """
    out: List[Dict] = []
    err = ""
    try:
        if game == "双色球":
            out = _cwl("ssq", count)
        elif game == "快乐8":
            out = _cwl("kl8", count)
        elif game == "大乐透":
            out = _dlt(count)
    except Exception as exc:      # noqa: BLE001
        err = f"official:{type(exc).__name__}"
    if out:
        _FETCH_STATE[game] = {"ok": True, "source": "official", "reason": ""}
        return out

    backup = _500(game, count)
    if backup:
        _FETCH_STATE[game] = {"ok": True, "source": "500", "reason": ""}
        return backup

    _FETCH_STATE[game] = {"ok": False, "source": "",
                          "reason": err or "all-sources-unreachable"}
    return []


def find_draw(game: str, date: str) -> Optional[Dict]:
    """取该彩种在 date 当日（或当日之后最近一期）的开奖。命中不了当日则 None。"""
    for d in fetch_draws(game):
        if d["date"] == date:
            return d
    return None


# ---------------------------------------------------------------- 对奖
def _fmt(nums: List[int]) -> str:
    return " ".join(f"{n:02d}" for n in nums)


def settle(game: str, front: List[int], back: List[int],
           draw: Dict) -> Dict:
    """对照开奖号，返回命中与奖级。"""
    df, db = draw.get("front", []), draw.get("back", [])
    hf = len(set(front) & set(df))
    hb = len(set(back or []) & set(db)) if back else 0
    res = {"hit_front": hf, "hit_back": hb, "level": "未中奖", "win": False,
           "prize_note": "", "draw_front": df, "draw_back": db,
           "issue": draw.get("issue", ""), "draw_date": draw.get("date", ""),
           "draw_txt": _fmt(df) + (("  +  " + _fmt(db)) if db else "")}
    txt = f"{hf}"
    if back:
        txt += f"+{hb}"

    if game == "双色球":
        if hf == 6 and hb == 1:
            res.update(level="一等奖", win=True, prize_note="浮动奖金")
        elif hf == 6:
            res.update(level="二等奖", win=True, prize_note="浮动奖金")
        elif hf == 5 and hb == 1:
            res.update(level="三等奖", win=True, prize_note="3000 元")
        elif (hf == 5 and hb == 0) or (hf == 4 and hb == 1):
            res.update(level="四等奖", win=True, prize_note="200 元")
        elif (hf == 4 and hb == 0) or (hf == 3 and hb == 1):
            res.update(level="五等奖", win=True, prize_note="10 元")
        elif hb == 1:
            # 六等奖：中 1 蓝（2红+1蓝 / 1红+1蓝 / 0红+1蓝）
            res.update(level="六等奖", win=True, prize_note="5 元")
    elif game == "大乐透":
        table = [((5, 2), "一等奖"), ((5, 1), "二等奖"), ((5, 0), "三等奖"),
                 ((4, 2), "四等奖"), ((4, 1), "五等奖")]
        for (f, b), lv in table:
            if hf == f and hb == b:
                res.update(level=lv, win=True, prize_note="浮动奖金")
                break
        else:
            if (hf == 4 and hb == 0) or (hf == 3 and hb == 2):
                res.update(level="六等奖", win=True)
            elif (hf == 3 and hb == 1) or (hf == 2 and hb == 2):
                res.update(level="七等奖", win=True)
            elif hf == 3 or (hf == 2 and hb == 1) or (hf == 1 and hb == 2) or (hf == 0 and hb == 2):
                res.update(level="八等奖", win=True)
            elif hf == 2 or (hf == 1 and hb == 1) or (hf == 0 and hb == 1):
                res.update(level="九等奖", win=True)
    elif game == "快乐8":
        # 选十玩法：中10/9/8/7/6/5 对应一至六等奖
        m = {10: "一等奖", 9: "二等奖", 8: "三等奖",
             7: "四等奖", 6: "五等奖", 5: "六等奖"}
        lv = m.get(hf)
        if lv:
            res.update(level=lv, win=True, prize_note="浮动奖金（含固定奖档）")

    res["hit_txt"] = txt
    if res["win"] and not res["prize_note"]:
        res["prize_note"] = "固定奖，金额以官方公告为准"
    return res


# ---------------------------------------------------------------- 台账
def _load() -> Dict:
    if not os.path.exists(LOG_PATH):
        return {}
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _save(data: Dict) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    tmp = LOG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, LOG_PATH)


def record_pick(day: datetime, game: Optional[str], front: List[int],
                back: Optional[List[int]] = None, score: float = 0.0,
                recomputed: bool = False) -> None:
    """记录一次推荐号码。同一天重复调用以最后一次为准，但保留已算过的开奖结果。"""
    if not game or not front:
        return
    key = day.strftime("%Y-%m-%d")
    data = _load()
    entry = {
        "game": game,
        "front": [int(x) for x in front],
        "back": [int(x) for x in (back or [])],
        "score": round(float(score), 1),
    }
    if recomputed:
        entry["recomputed"] = True
    old = data.get(key)
    if isinstance(old, dict) and isinstance(old.get("result"), dict):
        entry["result"] = old["result"]        # 已核对过的开奖结果不因重写而丢失
    data[key] = entry
    _save(data)


def record_from_block(day: datetime, lotto: Dict) -> None:
    """从 lottery_block 的返回值里记账。"""
    if not lotto or lotto.get("skip"):
        return
    for p in lotto.get("picks") or []:
        record_pick(day, p.get("game"), p.get("front") or [],
                    p.get("back") or [], lotto.get("score", 0.0))
        break

def _weekday_cn(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return ""
    return "周" + "一二三四五六日"[d.weekday()]


def _recompute_pick(day: datetime) -> Optional[Dict]:
    """
    台账里没有这一天时，按当日盘面**确定性复算**当时的推荐号码。

    为什么需要它：CI（GitHub Actions）每次都是全新 checkout，跑完即丢，
    data/lottery_picks.json 这种本地台账天生跨不过天。而 gen_numbers 的种子是
    「日期 + 盘面数源」，完全确定——同一个日期重算必然得到同一组号码。
    所以台账缺失不等于历史丢失，重算即可，且结果与当日实际推送一致。
    """
    try:
        from .synthesize import generate, load_profile
        r = generate(day, load_profile(), offline=True)
        ld = r["invest"].get("lottery_detail") or {}
        if ld.get("skip") or not ld.get("picks"):
            return None
        p = ld["picks"][0]
        return {"game": p["game"], "front": [int(x) for x in p["front"]],
                "back": [int(x) for x in (p.get("back") or [])],
                "score": float(ld.get("score", 0.0)), "recomputed": True}
    except Exception:      # noqa: BLE001
        return None


def review(today: datetime, offline: bool = False) -> Dict:
    """
    核对「昨日」的推荐（REVIEW_WINDOW = 1），报告里只展示这一条。
    返回 {"ok": bool, "items": [...], "note": str}

    取数顺序：台账优先；台账缺失且未离线 → 确定性复算补录。
    昨日「建议停买」的（没出号码）直接返回空，报告里不出现任何核对信息。
    开奖还没公布的，保留条目并标注，绝不静默丢弃。
    """
    data = _load()
    today_d = datetime(today.year, today.month, today.day).date()

    # 由近及远找，够 SHOW_WINDOW 条就停，避免为用不到的日期白跑重算
    found: List[Dict] = []
    dirty = False
    for back in range(1, REVIEW_WINDOW + 1):
        if len(found) >= SHOW_WINDOW:
            break
        d = today_d - timedelta(days=back)
        ds = d.strftime("%Y-%m-%d")
        rec = data.get(ds)

        if not isinstance(rec, dict) or not rec.get("front"):
            if offline:
                continue
            rec = _recompute_pick(datetime(d.year, d.month, d.day, 8, 0))
            if not rec:
                continue                      # 当日本就建议停买，无号可核
            rec = dict(rec)
            rec["recomputed"] = True
            data[ds] = rec                    # 补录进台账（CI 里不落盘也无妨）
            dirty = True

        item = {"date": ds, "week": _weekday_cn(ds), "game": rec.get("game", ""),
                "front": [int(x) for x in rec.get("front", [])],
                "back": [int(x) for x in (rec.get("back") or [])],
                "score": rec.get("score", 0.0),
                "recomputed": bool(rec.get("recomputed"))}
        item["pick_txt"] = _fmt(item["front"]) + (
            ("  +  " + _fmt(item["back"])) if item["back"] else "")

        cached = rec.get("result")
        if isinstance(cached, dict) and cached.get("level"):
            item["result"] = cached
        elif offline:
            item["result"] = None
        else:
            draw = find_draw(item["game"], ds)
            if draw:
                item["result"] = settle(item["game"], item["front"],
                                        item["back"], draw)
                rec["result"] = item["result"]
                dirty = True
            else:
                item["result"] = None
                # 取数失败 ≠ 官方未公布：抓取状态决定文案，避免再次误导
                state = _FETCH_STATE.get(item["game"]) or {}
                item["result_reason"] = ("not_published" if state.get("ok")
                                         else "unreachable")
        found.append(item)

    if dirty:
        _save(data)

    items = list(reversed(found))            # 时间正序（窗口=1 时即唯一一条）
    note = ""
    if not items:
        note = "（昨日建议停买，无号码可核对）"
    elif not any(x.get("result") for x in items):
        if any(x.get("result_reason") == "unreachable" for x in items):
            note = "（开奖数据获取失败：数据源当前不可达）"
        else:
            note = "（开奖结果尚未公布）"
    return {"ok": bool(items), "items": items, "note": note}
