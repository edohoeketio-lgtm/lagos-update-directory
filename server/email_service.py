"""
Email Dispatcher for Lagos Updates Directory.
Sends formatted notifications with photos to vendors@lagosupdates.com.
Non-blocking, fail-safe with file/console fallback.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from .config import ADMIN_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, BASE_DIR

LOG_PATH = os.environ.get("LOG_PATH", os.path.join("/tmp", "email_log.txt") if os.environ.get("VERCEL") else os.path.join(BASE_DIR, "data", "email_log.txt"))

def format_email_body(submission_id: str, data: dict, photo_paths: list = None) -> tuple[str, str]:
    """Generates plain text and HTML versions of the notification email."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    photos = photo_paths or []
    drive_link = data.get("drive_link", "")

    photos_text = "None uploaded"
    if photos:
        photos_text = "\n".join([f"  - http://localhost:3000{p}" for p in photos])

    text = f"""
=============================================================
NEW BUSINESS LISTING APPLICATION — LAGOS UPDATES DIRECTORY
=============================================================
Reference ID: {submission_id}
Submitted At: {timestamp}

BUSINESS DETAILS:
-----------------
Business Name:  {data['business_name']}
Category:       {data['category'].upper()}
Area in Lagos:  {data['area']}
Description:    {data['description']}
Price Range:    {data['price_range']}

PHOTOS & MEDIA:
---------------
Uploaded Photos ({len(photos)}):
{photos_text}
Google Drive / Dropbox: {drive_link or 'None'}

CONTACT & SOCIALS:
------------------
WhatsApp/Phone: {data['whatsapp']} (https://wa.me/{data['whatsapp_digits']})
Instagram:      @{data['instagram']} (https://instagram.com/{data['instagram']})

APPLICATION PLAN:
-----------------
Selected Plan:  {data['plan_tier'].upper()} LISTING

CONTACT PERSON:
---------------
Name:           {data['contact_name']}
Email:          {data['contact_email']}

Action Required:
Review photos, business credibility and Instagram profile.
Contact vendor on WhatsApp to confirm details or arrange verification.
=============================================================
"""

    photos_html = "<p style='color:#888; font-size:13px;'>No photos uploaded directly.</p>"
    if photos:
        imgs = "".join([f"<a href='http://localhost:3000{p}' target='_blank'><img src='http://localhost:3000{p}' style='width:120px; height:120px; object-fit:cover; border-radius:8px; border:1px solid #ddd; margin-right:8px; margin-bottom:8px;'></a>" for p in photos])
        photos_html = f"<div style='display:flex; flex-wrap:wrap; margin-top:8px;'>{imgs}</div>"

    drive_html = ""
    if drive_link:
        drive_html = f"<div class='field'><div class='label'>Cloud Drive Link</div><div class='value'><a href='{drive_link}' target='_blank' style='color:#0066cc;'>Open Google Drive / Dropbox Folder &rarr;</a></div></div>"

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: 'Inter', -apple-system, sans-serif; background: #f7f7f7; padding: 24px; color: #222; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; overflow: hidden; }}
    .header {{ background: #000000; color: #ffffff; padding: 24px; }}
    .header h2 {{ margin: 0; font-size: 20px; font-weight: 800; }}
    .badge {{ display: inline-block; background: #FFD400; color: #000; font-weight: 800; font-size: 11px; padding: 4px 8px; border-radius: 4px; text-transform: uppercase; margin-bottom: 8px; }}
    .content {{ padding: 24px; }}
    .field {{ margin-bottom: 16px; }}
    .label {{ font-size: 11px; text-transform: uppercase; color: #717171; font-weight: 700; letter-spacing: 1px; margin-bottom: 4px; }}
    .value {{ font-size: 15px; font-weight: 600; color: #222222; }}
    .desc-box {{ background: #f9f9f9; border: 1px solid #ebebeb; padding: 14px; border-radius: 8px; font-size: 14px; line-height: 1.5; color: #444; }}
    .actions {{ margin-top: 28px; padding-top: 20px; border-top: 1px solid #ebebeb; }}
    .btn {{ display: inline-block; background: #25D366; color: #ffffff; text-decoration: none; font-weight: 700; font-size: 14px; padding: 12px 20px; border-radius: 9999px; }}
    .footer {{ background: #f9f9f9; border-top: 1px solid #e5e5e5; padding: 16px 24px; font-size: 12px; color: #888; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="badge">{data['plan_tier'].upper()} APPLICATION</div>
      <h2>{data['business_name']}</h2>
      <p style="margin: 4px 0 0; color: #aaa; font-size: 13px;">Ref: {submission_id} &middot; {timestamp}</p>
    </div>
    <div class="content">
      <div class="field">
        <div class="label">Category & Area</div>
        <div class="value">{data['category'].capitalize()} &middot; {data['area']}, Lagos</div>
      </div>
      <div class="field">
        <div class="label">Description / Specialty</div>
        <div class="desc-box">{data['description']}</div>
      </div>
      <div class="field">
        <div class="label">Rates / Pricing</div>
        <div class="value">{data['price_range']}</div>
      </div>
      <div class="field">
        <div class="label">Uploaded Photos ({len(photos)})</div>
        {photos_html}
      </div>
      {drive_html}
      <div class="field">
        <div class="label">WhatsApp / Phone</div>
        <div class="value"><a href="https://wa.me/{data['whatsapp_digits']}" style="color: #0066cc;">{data['whatsapp']}</a></div>
      </div>
      <div class="field">
        <div class="label">Instagram</div>
        <div class="value">{f'<a href="https://instagram.com/{data["instagram"]}" style="color: #0066cc;">@{data["instagram"]}</a>' if data['instagram'] else 'Not provided'}</div>
      </div>
      <div class="field">
        <div class="label">Contact Person</div>
        <div class="value">{data['contact_name']} &lt;<a href="mailto:{data['contact_email']}" style="color: #0066cc;">{data['contact_email']}</a>&gt;</div>
      </div>
      <div class="actions">
        <a href="https://wa.me/{data['whatsapp_digits']}?text=Hello%20{data['contact_name']},%20this%20is%20Lagos%20Updates%20team%20regarding%20your%20listing%20for%20{data['business_name']}" class="btn">Chat Vendor on WhatsApp &rarr;</a>
      </div>
    </div>
    <div class="footer">
      Lagos Updates Directory &middot; Notification to {ADMIN_EMAIL}
    </div>
  </div>
</body>
</html>
"""
    return text, html

def dispatch_submission_email(submission_id: str, data: dict, photo_paths: list = None) -> bool:
    """
    Attempts to send email via SMTP to vendors@lagosupdates.com.
    Logs to file & stdout as fallback. Never raises an uncaught exception.
    """
    text_body, html_body = format_email_body(submission_id, data, photo_paths)

    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(text_body + "\n\n")
    except Exception as e:
        print("[Email Service] Could not write to log file:", e)

    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"New Listing Application: {data['business_name']} ({data['area']})"
            msg["From"] = SMTP_USER
            msg["To"] = ADMIN_EMAIL
            msg["Reply-To"] = data['contact_email']

            part1 = MIMEText(text_body, "plain")
            part2 = MIMEText(html_body, "html")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [ADMIN_EMAIL], msg.as_string())
            print(f"[Email Service] Successfully emailed notification for {submission_id} to {ADMIN_EMAIL}")
            return True
        except Exception as e:
            print(f"[Email Service] SMTP dispatch failed (logged to audit file):", e)
            return False
    else:
        print(f"[Email Service] SMTP not configured. Notification recorded to audit log for: {data['business_name']} -> {ADMIN_EMAIL}")
        return True
