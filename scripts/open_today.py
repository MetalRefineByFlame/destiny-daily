# 一键打开当日运势报告（给桌面快捷方式用）
#
# 行为：
#   1. 若 output/ 下已有当天报告，直接用默认浏览器打开（秒开）
#   2. 否则先排盘生成，再打开；生成期间弹一个小提示窗，避免双击后毫无反应
#
# 用法：
#   pythonw scripts/open_today.py            # 打开今天的报告
#   pythonw scripts/open_today.py --fresh    # 强制重算今天的报告再打开
#   pythonw scripts/open_today.py --date 2026-09-28   # 打开指定日期（须已生成过）

import os
import sys
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
SCRIPT = ROOT / "daily_run.py"


def tz_today(offset: int = 8) -> str:
    """与 daily_run.py 保持一致：按 UTC+8 判定「今天」，不依赖本机时区。"""
    now = datetime.now(timezone.utc) + timedelta(hours=offset)
    return now.strftime("%Y-%m-%d")


class Splash:
    """生成期间的小提示窗。任何异常都不影响主流程，装饰而已。"""

    def __init__(self, text):
        self.ok = False
        try:
            import tkinter as tk

            self.root = tk.Tk()
            self.root.title("五术日课")
            self.root.overrideredirect(True)          # 无边框
            self.root.attributes("-topmost", True)
            tk.Label(
                self.root, text=text, font=("Microsoft YaHei UI", 11),
                padx=28, pady=22, fg="#222",
            ).pack()
            # 右下角显示
            self.root.update_idletasks()
            w, h = self.root.winfo_width(), self.root.winfo_height()
            x = self.root.winfo_screenwidth() - w - 40
            y = self.root.winfo_screenheight() - h - 80
            self.root.geometry(f"+{x}+{y}")
            self.root.update()
            self.ok = True
        except Exception:
            pass

    def close(self):
        if self.ok:
            try:
                self.root.destroy()
            except Exception:
                pass


def generate(day: str) -> bool:
    """调用 daily_run.py 生成指定日期的报告。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", DESTINY_TZ_OFFSET="8")
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT)],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180, env=env,
    )
    if proc.returncode != 0:
        print(proc.stdout[-2000:], file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
    return proc.returncode == 0


def main():
    args = sys.argv[1:]
    day, fresh = None, False
    i = 0
    while i < len(args):
        if args[i] == "--fresh":
            fresh = True
        elif args[i] == "--date" and i + 1 < len(args):
            day = args[i + 1]
            i += 1
        i += 1

    day = day or tz_today()
    html = OUTPUT / f"destiny-{day}.html"

    if fresh or not html.exists():
        splash = Splash(f"正在排盘 {day} …\n稍候片刻")
        ok = generate(day)
        splash.close()
        if not ok or not html.exists():
            # pythonw 下没有控制台，只能靠弹窗告知；实在弹不出也要让被调用者有非零退出码
            try:
                import tkinter.messagebox as mb
                mb.showerror("五术日课", f"{day} 的报告生成失败。\n\n" +
                             "请把这个情况反馈给 WorkBuddy 处理。")
            except Exception:
                pass
            sys.exit(1)

    os.startfile(str(html))


if __name__ == "__main__":
    main()
