# -*- coding: utf-8 -*-
"""
从「模板 + 环境变量」生成真正可用的 data/profile.json。

为什么需要这一步：
    本仓库是公开的，出生年月日时、出生地经度、收件邮箱一律不入库。
    仓库里只放 data/profile.example.json（全是占位值），
    真实数据用环境变量注入，在 CI 里就是 GitHub Secrets。

环境变量（全部可选，未设置则沿用模板占位值）：
    DESTINY_NAME        称呼，例：江公子
    DESTINY_GENDER      male | female
    DESTINY_BIRTH       公历出生时刻，例："1980-07-17 09:28"
    DESTINY_LONGITUDE   出生地东经度数，例：119.30
    DESTINY_CITY        出生地名称（仅用于展示）
    DESTINY_EMAIL       收件邮箱，例：you@qq.com（也可只设 MAIL_TO）
    MAIL_TO             收件邮箱（优先级低于 DESTINY_EMAIL）

用法：
    python scripts/make_profile.py                # 生成（已存在则跳过，除非 --force）
    python scripts/make_profile.py --force        # 强制覆盖
    python scripts/make_profile.py --print        # 只打印结果，不写文件
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(ROOT, "data", "profile.example.json")
TARGET = os.path.join(ROOT, "data", "profile.json")


def parse_birth(s: str) -> dict:
    """接受 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DDTHH:MM'。"""
    s = s.strip().replace("T", " ")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})[ ]+(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
    if not m:
        raise SystemExit(f"[error] DESTINY_BIRTH 格式无法识别：{s!r}（应为 1980-07-17 09:28）")
    return {
        "year": int(m.group(1)), "month": int(m.group(2)), "day": int(m.group(3)),
        "hour": int(m.group(4)), "minute": int(m.group(5)),
        **({"second": int(m.group(6))} if m.group(6) else {}),
    }


def main() -> int:
    args = sys.argv[1:]
    force = "--force" in args
    only_print = "--print" in args

    with open(EXAMPLE, encoding="utf-8") as f:
        prof = json.load(f)
    prof.pop("_comment", None)

    name = os.environ.get("DESTINY_NAME", "").strip()
    gender = os.environ.get("DESTINY_GENDER", "").strip().lower()
    birth = os.environ.get("DESTINY_BIRTH", "").strip()
    lon = os.environ.get("DESTINY_LONGITUDE", "").strip()
    city = os.environ.get("DESTINY_CITY", "").strip()
    email = (os.environ.get("DESTINY_EMAIL") or os.environ.get("MAIL_TO") or "").strip()

    filled = []
    if name:
        prof["name"] = name
        filled.append("name")
    if gender in ("male", "female"):
        prof["gender"] = gender
        prof["gender_confirmed"] = True
        filled.append("gender")
    if birth:
        prof["birth"] = parse_birth(birth)
        filled.append("birth")
    if lon:
        try:
            prof["birth_longitude"] = float(lon)
        except ValueError:
            raise SystemExit(f"[error] DESTINY_LONGITUDE 不是数字：{lon!r}")
        filled.append("longitude")
    if "birth" in filled or "longitude" in filled:
        # 真实出生数据已注入 → 标记可用，否则 verify.py / 报告会按占位值处理
        prof["birth_place_confirmed"] = True
        filled.append("birth_place_confirmed")
    if city:
        prof["birth_city"] = city
        filled.append("city")
    if email:
        prof["email"] = email
        filled.append("email")

    if only_print:
        print(json.dumps(prof, ensure_ascii=False, indent=2))
        return 0

    if os.path.exists(TARGET) and not force and not filled:
        print(f"[skip] {TARGET} 已存在且未提供环境变量，保持原样（--force 可强制重建）")
        return 0

    with open(TARGET, "w", encoding="utf-8") as f:
        json.dump(prof, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已生成 {TARGET}")
    if filled:
        print(f"     注入字段：{', '.join(filled)}")
    else:
        print("     ⚠ 未注入任何个人数据，当前为模板占位值，报告结果无实际意义")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
