# 在桌面创建「今日运势」快捷方式
#
# 为什么需要这个脚本：直接放个 .bat 会闪黑窗口，而 .lnk 才是桌面上的一等公民
# （可以设图标、描述，双击无杂讯）。
#
# 两种形态的区别：
#   .lnk  —— 启动本地程序，可带参数和工作目录
#   .url  —— Internet 快捷方式，纯文本 INI，专门用来打开网页
#             （.lnk 不能把网页当 TargetPath，否则读回来是空的）
#
# 用法：
#   python scripts/make_shortcut.py            # 创建/更新
#   python scripts/make_shortcut.py --verify   # 校验是否已正确
#   python scripts/make_shortcut.py --remove   # 删除

import os
import sys
import win32com.client

DESKTOP = os.path.join(os.environ["USERPROFILE"], "Desktop")
PYW = r"C:\Users\江\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
ROOT = r"D:\WorkBuddy\2026-09-28-13-14-40\destiny-daily"
SCRIPT = os.path.join(ROOT, "scripts", "open_today.py")
GH_ACTIONS = "https://github.com/MetalRefineByFlame/destiny-daily/actions"

# imageres.dll 里的通用图标索引；换口味改这里即可
ICON_APP = r"C:\Windows\System32\imageres.dll"
ICON_APP_IDX = 168
ICON_WEB = r"C:\Windows\System32\imageres.dll"
ICON_WEB_IDX = 174

TARGETS = [
    {
        "kind": "url",
        "name": "运势·云端控制台.url",
        "url": GH_ACTIONS,
        "icon": ICON_WEB,
        "icon_index": ICON_WEB_IDX,
        "desc": "五术日课 · 手动补发与推送日志",
    },
    {
        "kind": "lnk",
        "name": "今日运势.lnk",
        "target": PYW,
        "args": '"%s"' % SCRIPT,
        "cwd": ROOT,
        "icon": "%s,%d" % (ICON_APP, ICON_APP_IDX),
        "desc": "五术日课 · 打开当日运势完整报告",
    },
]


def path_of(t):
    return os.path.join(DESKTOP, t["name"])


def write_url_shortcut(t):
    path = path_of(t)
    # Windows 对 .url 接受 UTF-8；这里的内容全是 ASCII，兼容性无忧。
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("[InternetShortcut]\n")
        f.write("URL=%s\n" % t["url"])
        f.write("IconFile=%s\n" % t["icon"])
        f.write("IconIndex=%d\n" % t["icon_index"])
    return path


def remove():
    for t in TARGETS:
        p = path_of(t)
        if os.path.exists(p):
            os.remove(p)
            print("已删除", t["name"])
        else:
            print("不存在，跳过", t["name"])


def create():
    ws = win32com.client.Dispatch("WScript.Shell")
    for t in TARGETS:
        if t["kind"] == "url":
            write_url_shortcut(t)
        else:
            sc = ws.CreateShortcut(path_of(t))
            sc.TargetPath = t["target"]
            sc.Arguments = t["args"]
            sc.WorkingDirectory = t["cwd"]
            sc.Description = t["desc"]
            sc.IconLocation = t["icon"]
            sc.Save()
        print("已创建", t["name"])

    print("\n桌面现有「运势」相关项：")
    for n in sorted(os.listdir(DESKTOP)):
        if "运势" in n:
            print("  ", n)


def verify():
    ws = win32com.client.Dispatch("WScript.Shell")
    all_ok = True
    for t in TARGETS:
        p = path_of(t)
        print("=" * 56)
        print(t["name"])
        if not os.path.exists(p):
            print("  ❌ 文件不存在")
            all_ok = False
            continue

        if t["kind"] == "url":
            body = open(p, encoding="utf-8").read()
            ok_url = ("URL=%s" % t["url"]) in body
            ok_icon = ("IconFile=%s" % t["icon"]) in body and \
                      ("IconIndex=%d" % t["icon_index"]) in body
            print(("  ✅" if ok_url else "  ❌"), "URL:", t["url"])
            print(("  ✅" if ok_icon else "  ❌"), "图标:", t["icon"], t["icon_index"])
            all_ok = all_ok and ok_url and ok_icon
        else:
            sc = ws.CreateShortcut(p)
            checks = {
                "目标": (sc.TargetPath, t["target"]),
                "参数": (sc.Arguments, t["args"]),
                "工作目录": (sc.WorkingDirectory, t["cwd"]),
                "图标": (sc.IconLocation, t["icon"]),
            }
            for k, (got, want) in checks.items():
                ok = got == want
                all_ok = all_ok and ok
                print(("  ✅" if ok else "  ❌"), f"{k}: {got}")

        print("  大小 %d bytes" % os.path.getsize(p))

    print("\n校验结果:", "全部正确" if all_ok else "有不符，请重跑本脚本")
    return all_ok


if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove()
    elif "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    else:
        create()
