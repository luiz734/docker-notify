import os
import smtplib
import ssl
import html
from email.message import EmailMessage

def send(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = os.environ["SMTP_TO"]
    msg.set_content(body)
    msg.add_alternative(
        '<pre style="font-family: ui-monospace, Menlo, Consolas, '
        f'\'DejaVu Sans Mono\', monospace; font-size: 13px;">{html.escape(body)}</pre>',
        subtype="html",
    )

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    ctx = ssl.create_default_context()

    s = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) if port == 465 \
        else smtplib.SMTP(host, port, timeout=30)
    with s:
        if port != 465:
            s.starttls(context=ctx)
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)