# -*- coding: utf-8 -*-
"""
邮件推送模块 —— 云端部署专用。

本机场景可以用 WorkBuddy 的 Agent Mail；但报告一旦搬到云端（GitHub Actions /
云函数），邮件必须由云端的这份代码自己发出，故选用标准 SMTP。

支持服务商（都在 SMTP_HOSTS 里预设，也允许用环境变量完全自定义）：
    QQ 邮箱      smtp.qq.com:465 SSL     口令填「SMTP 授权码」，不是登录密码
    163 邮箱     smtp.163.com:465 SSL
    Gmail        smtp.gmail.com:587 STARTTLS
    阿里云邮件   smtpdm.aliyuncs.com:465 SSL

环境变量：
    SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS
    SMTP_SSL      "1"=直接SSL(465)  "0"=STARTTLS(587)
    MAIL_TO       收件人，多个用逗号分隔
    MAIL_FROM     发件人（默认同 SMTP_USER）

用法：
    python notify_mail.py output/destiny-2026-09-28.txt output/destiny-2026-09-28.html
    python notify_mail.py --subject "测试" --body "hello"       # 纯文本快发

安全提示：任何情况下都不要把授权码写进代码或提交到仓库，一律走环境变量 / CI Secrets。
"""

from __future__ import annotations

import os
import re
import smtplib
import sys
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr

SMTP_HOSTS = {
    "qq.com":     ("smtp.qq.com", 465, True),
    "foxmail.com": ("smtp.qq.com", 465, True),
    "163.com":    ("smtp.163.com", 465, True),
    "126.com":    ("smtp.126.com", 465, True),
    "gmail.com":  ("smtp.gmail.com", 587, False),
    "aliyun.com": ("smtpdm.aliyuncs.com", 465, True),
}


def build_message(subject: str, body: str, html: str | None = None,
                  mail_from: str = "", mail_to: list[str] | None = None,
                  inline_html: bool = True,
                  attach_html: bool = True,
                  attach_src: str | None = None) -> MIMEMultipart:
    """构造邮件。

    inline_html=True 时，HTML 报告直接作为**正文**排版显示，结构为：
        mixed
          └─ alternative
               ├─ text/plain   （不支持 HTML 的客户端 / 纯文本预览）
               └─ text/html    （排版版，主流客户端显示这一个）
          └─ attachment: *.html （留档，可选）

    注意 alternative 里 HTML 必须在纯文本**之后**——按 RFC 2046，
    越靠后的部分表示"更丰富"的版本，客户端会挑它能显示的最后一个。
    早先版本只把 HTML 当附件、正文用纯文本，导致在邮箱里看到的全是干巴巴的文字。
    """
    msg = MIMEMultipart("mixed")
    msg["From"] = mail_from
    msg["To"] = ", ".join(mail_to or [])
    msg["Subject"] = Header(subject, "utf-8")

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body, "plain", "utf-8"))

    raw = None
    if html:
        try:
            with open(html, encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:      # noqa: BLE001
            print(f"[warn] HTML 报告读取失败，仅发送文本：{e}")

    if raw and inline_html:
        # 显式指定 quoted-printable：比 base64 体积小，
        # 且部分国产邮件网关对超长单行 base64 有截断问题
        part = MIMEText(raw, "html", "utf-8")
        part.set_charset("utf-8")
        del part["Content-Transfer-Encoding"]
        try:
            from email.encoders import encode_quopri
            encode_quopri(part)
            part["Content-Transfer-Encoding"] = "quoted-printable"
        except Exception:        # noqa: BLE001
            pass
        alt.attach(part)

    msg.attach(alt)

    if attach_html:
        # 正文和附件可以是两个文件：正文用邮件专用排版版（更轻），
        # 附件留完整的浏览器版（带 grid/flex，打印、存档都好看）
        src = attach_src or html
        payload = raw if (src == html) else None
        if payload is None and src:
            try:
                with open(src, encoding="utf-8") as f:
                    payload = f.read()
            except OSError as e:      # noqa: BLE001
                print(f"[warn] HTML 附件读取失败：{e}")
        if payload:
            part = MIMEText(payload, "html", "utf-8")
            part.add_header("Content-Disposition", "attachment",
                            filename=Header(
                                os.path.basename(src), "utf-8").encode())
            msg.attach(part)
    return msg


def send(msg: MIMEMultipart, verbose: bool = True) -> None:
    host = os.environ.get("SMTP_HOST", "")
    user = os.environ.get("SMTP_USER", "")
    pwd = os.environ.get("SMTP_PASS", "")
    if not all([host, user, pwd]):
        raise SystemExit(
            "[error] 缺少 SMTP 配置。需设置环境变量："
            "SMTP_HOST / SMTP_USER / SMTP_PASS（本机可用 Agent Mail 替代）")

    port = int(os.environ.get("SMTP_PORT", "465"))
    ssl_mode = str(os.environ.get("SMTP_SSL", "1")).lower() in ("1", "true", "yes")

    if ssl_mode:
        srv = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        srv = smtplib.SMTP(host, port, timeout=30)
        srv.starttls()
    try:
        srv.login(user, pwd)
        srv.sendmail(user, msg["To"].split(","), msg.as_string())
        if verbose:
            print(f"[OK] 已发送 -> {msg['To']}")
    finally:
        srv.quit()


def derive_subject(txt_path: str) -> str:
    """从纯文本报告首行提取主题，形如「【每日运势】2026年09月28日 周一 · 乙巳日 · 平顺59分」"""
    try:
        with open(txt_path, encoding="utf-8") as f:
            first = f.readline().strip()
    except OSError:
        return "【每日运势】"
    m = re.match(r"^(\d{4})年(\d{2})月(\d{2})日\s+(\S+)", first)
    gz = re.search(r"([一-龥]{2}日)", first)
    if m:
        subject = f"【每日运势】{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}"
        return subject + (f" · {gz.group(1)}" if gz else "")
    return "【每日运势】" + (first[:24] or "")


def default_mail_from(user: str) -> str:
    name = os.environ.get("MAIL_FROM_NAME", "五术日课")
    return formataddr((str(Header(name, "utf-8")), user))


def main() -> int:
    args = [a for a in sys.argv[1:]]
    dry = "--dry-run" in args
    subject = None
    body_text = None
    for a in list(args):
        if a.startswith("--subject"):
            subject = a.split("=", 1)[-1]
            args.remove(a)
        elif a.startswith("--body"):
            body_text = a.split("=", 1)[-1]
            args.remove(a)
        elif a.startswith("--dry-run"):
            args.remove(a)

    inline = "--no-inline" not in args
    attach = "--no-attach" not in args
    for a in list(args):
        if a in ("--no-inline", "--no-attach"):
            args.remove(a)

    paths = [a for a in args if not a.startswith("-")]
    txt = paths[0] if paths else None
    # 第 2 个参数是「邮件正文」用的排版 HTML；第 3 个（可选）是留档附件。
    # 只传两个时，同一个文件既做正文也做附件。
    html = paths[1] if len(paths) > 1 else None
    attach_src = paths[2] if len(paths) > 2 else html

    if not subject:
        subject = derive_subject(txt) if txt else "【每日运势】"
    if body_text is None and txt:
        try:
            with open(txt, encoding="utf-8") as f:
                body_text = f.read()
        except OSError as e:      # noqa: BLE001
            raise SystemExit(f"[error] 读取文本报告失败：{e}")
    body_text = body_text or ""

    # 未显式指定收件人时，回落到 profile.json 的 Email
    to_raw = os.environ.get("MAIL_TO", "")
    if not to_raw and txt:
        pass
    if not to_raw:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from engine.synthesize import load_profile
            to_raw = load_profile().get("email", "")
        except Exception:        # noqa: BLE001
            to_raw = ""
    if not to_raw:
        raise SystemExit("[error] 未指定收件人：设置 MAIL_TO 或在 profile.json 填 email")

    mail_to = [x.strip() for x in to_raw.split(",") if x.strip()]
    user = os.environ.get("SMTP_USER", "")
    mail_from = os.environ.get("MAIL_FROM") or default_mail_from(user or mail_to[0])

    msg = build_message(subject, body_text, html, mail_from, mail_to,
                        inline_html=inline, attach_html=attach,
                        attach_src=attach_src)
    print(f"[info] 主题：{subject}")
    print(f"[info] 收件：{', '.join(mail_to)}")
    print(f"[info] 正文：{'HTML 排版版' if (inline and html) else '纯文本'}"
          f"（共 {len(body_text)} 字符）")
    if attach and attach_src:
        print(f"[info] 附件：{os.path.basename(attach_src)}")
    if dry:
        print("[dry-run] 未真正发送（缺少 dry-run 以外的发送动作）")
        return 0
    send(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
