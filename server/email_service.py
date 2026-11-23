"""
Email Dispatcher for Lagos Updates Directory.
Sends formatted notifications with photos to vendors@lagosupdates.com.
Non-blocking, fail-safe with file/console fallback.
"""
import smtplib
import re
import json
import urllib.request
import urllib.parse
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from .config import (
    ADMIN_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, BASE_DIR,
    RESEND_API_KEY, RESEND_FROM_EMAIL,
    MAILGUN_API_KEY, MAILGUN_DOMAIN, MAILGUN_FROM_EMAIL
)

LOG_PATH = os.environ.get("LOG_PATH", os.path.join("/tmp", "email_log.txt") if os.environ.get("VERCEL") else os.path.join(BASE_DIR, "data", "email_log.txt"))

def format_email_body(submission_id: str, data: dict, photo_paths: list = None) -> tuple[str, str]:
    """Generates plain text and HTML versions of the notification email."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    photos = photo_paths or []
    drive_link = data.get("drive_link", "")

    photos_text = "None uploaded"
    if photos:
        photos_text = "\n".join([f"  - http://localhost:3000{p}" for p in photos])

    raw_phone = data.get("whatsapp", "")
    wa_digits = data.get("whatsapp_digits") or re.sub(r'\D', '', raw_phone)
    rc_num = data.get("rc_number", "NOT PROVIDED")
    b_name = data.get("business_name", "")
    cat = (data.get("category") or "").upper()
    area = data.get("area", "")
    desc = data.get("description", "")
    price = data.get("price_range", "On Request")
    plan = (data.get("plan_tier") or "verified").upper()
    insta = (data.get("instagram") or "").lstrip("@")
    c_name = data.get("contact_name", "")
    c_email = data.get("contact_email", "")

    text = f"""
=============================================================
NEW BUSINESS LISTING APPLICATION — LAGOS UPDATES DIRECTORY
=============================================================
Reference ID: {submission_id}
Submitted At: {timestamp}

BUSINESS DETAILS:
-----------------
Business Name:  {b_name}
CAC Reg Number: {rc_num} (Verify: https://search.cac.gov.ng)
Category:       {cat}
Area in Lagos:  {area}
Description:    {desc}
Price Range:    {price}

PHOTOS & MEDIA:
---------------
Uploaded Photos ({len(photos)}):
{photos_text}
Google Drive / Dropbox: {drive_link or 'None'}

CONTACT & SOCIALS:
------------------
WhatsApp/Phone: {raw_phone} (https://wa.me/{wa_digits})
Instagram:      @{insta} (https://instagram.com/{insta})

APPLICATION PLAN:
-----------------
Selected Plan:  {plan} LISTING

CONTACT PERSON:
---------------
Name:           {c_name}
Email:          {c_email}

Action Required:
Verify CAC registration number on search.cac.gov.ng.
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
      <div class="badge">{plan} APPLICATION</div>
      <h2>{b_name}</h2>
      <p style="margin: 4px 0 0; color: #aaa; font-size: 13px;">Ref: {submission_id} &middot; {timestamp}</p>
    </div>
    <div class="content">
      <div class="field">
        <div class="label">CAC Registration Number</div>
        <div class="value" style="color: #0066cc; font-weight: 800;">{rc_num} &mdash; <a href="https://search.cac.gov.ng" target="_blank" style="text-decoration: underline; font-size: 13px; color: #0066cc;">Verify on CAC Portal &rarr;</a></div>
      </div>
      <div class="field">
        <div class="label">Category & Area</div>
        <div class="value">{cat} &middot; {area}, Lagos</div>
      </div>
      <div class="field">
        <div class="label">Description / Specialty</div>
        <div class="desc-box">{desc}</div>
      </div>
      <div class="field">
        <div class="label">Rates / Pricing</div>
        <div class="value">{price}</div>
      </div>
      <div class="field">
        <div class="label">Uploaded Photos ({len(photos)})</div>
        {photos_html}
      </div>
      {drive_html}
      <div class="field">
        <div class="label">WhatsApp / Phone</div>
        <div class="value"><a href="https://wa.me/{wa_digits}" style="color: #0066cc;">{raw_phone}</a></div>
      </div>
      <div class="field">
        <div class="label">Instagram</div>
        <div class="value">{f'<a href="https://instagram.com/{insta}" style="color: #0066cc;">@{insta}</a>' if insta else 'Not provided'}</div>
      </div>
      <div class="field">
        <div class="label">Contact Person</div>
        <div class="value">{c_name} &lt;<a href="mailto:{c_email}" style="color: #0066cc;">{c_email}</a>&gt;</div>
      </div>
      <div class="actions">
        <a href="https://wa.me/{wa_digits}?text=Hello%20{c_name},%20this%20is%20Lagos%20Updates%20team%20regarding%20your%20listing%20for%20{b_name}" class="btn">Chat Vendor on WhatsApp &rarr;</a>
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

def send_email(to_email: str, subject: str, text_body: str, html_body: str, reply_to: str = "") -> bool:
    """
    Unified transactional email dispatcher.
    Priority 1: Resend REST API (Preferred modern cloud email delivery)
    Priority 2: Mailgun REST API (Legacy secondary fallback)
    Priority 3: Standard SMTP (Direct server fallback)
    Priority 4: Audit log file & console (fail-safe for development and audit record)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Always log to audit file for compliance & debugging
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n--- [{timestamp}] EMAIL TO: {to_email} | SUBJECT: {subject} ---\n{text_body}\n")
    except Exception as e:
        print("[Email Service] Could not write to log file:", e)

    # 1. Try Resend REST API (Primary)
    if RESEND_API_KEY and os.environ.get("LAGOS_TEST_MODE") != "1":
        try:
            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "User-Agent": "LagosUpdatesDirectory/1.0 (https://lagosupdates.com)",
                "Content-Type": "application/json"
            }
            payload = {
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": text_body
            }
            if reply_to:
                payload["reply_to"] = reply_to

            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 201]:
                    print(f"[Email Service / Resend] Sent email to {to_email} with subject '{subject}'")
                    return True
        except urllib.error.HTTPError as he:
            err_msg = he.read().decode('utf-8', errors='ignore')
            print(f"[Email Service / Resend] HTTP {he.code}: {err_msg}")
            # If custom domain is awaiting DNS verification, fallback to onboarding sandbox address
            if ("domain" in err_msg.lower() or "verify" in err_msg.lower() or "not verified" in err_msg.lower()) and "onboarding@resend.dev" not in RESEND_FROM_EMAIL:
                try:
                    payload["from"] = "Lagos Updates Directory <onboarding@resend.dev>"
                    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    retry_req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
                    with urllib.request.urlopen(retry_req, timeout=10) as retry_resp:
                        if retry_resp.status in [200, 201]:
                            print(f"[Email Service / Resend Sandbox Fallback] Sent email to {to_email}")
                            return True
                except Exception as ex2:
                    print(f"[Email Service / Resend Sandbox Fallback Error]:", ex2)
        except Exception as e:
            print(f"[Email Service / Resend] Resend dispatch error:", e)

    # 2. Try Mailgun REST API (Secondary)
    if MAILGUN_API_KEY and MAILGUN_DOMAIN:
        try:
            url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
            fields = {
                "from": MAILGUN_FROM_EMAIL,
                "to": to_email,
                "subject": subject,
                "text": text_body,
                "html": html_body
            }
            if reply_to:
                fields["h:Reply-To"] = reply_to

            encoded_data = urllib.parse.urlencode(fields).encode("utf-8")
            req = urllib.request.Request(url, data=encoded_data, method="POST")

            auth_string = f"api:{MAILGUN_API_KEY}".encode("utf-8")
            b64_auth = base64.b64encode(auth_string).decode("utf-8")
            req.add_header("Authorization", f"Basic {b64_auth}")

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 201]:
                    print(f"[Email Service / Mailgun] Sent email to {to_email} with subject '{subject}'")
                    return True
        except Exception as e:
            print(f"[Email Service / Mailgun] Mailgun dispatch error:", e)

    # 2. Try SMTP fallback
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = to_email
            if reply_to:
                msg["Reply-To"] = reply_to

            part1 = MIMEText(text_body, "plain")
            part2 = MIMEText(html_body, "html")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [to_email], msg.as_string())
            print(f"[Email Service / SMTP] Successfully emailed {to_email} with subject '{subject}'")
            return True
        except Exception as e:
            print(f"[Email Service / SMTP] SMTP dispatch failed:", e)

    # 3. Log fallback confirmation
    print(f"[Email Service] Dispatch recorded to audit log for: {to_email} (Subject: {subject})")
    return True

def dispatch_submission_email(submission_id: str, data: dict, photo_paths: list = None) -> bool:
    """Sends new submission alert to the Lagos Updates editorial team."""
    text_body, html_body = format_email_body(submission_id, data, photo_paths)
    subject = f"New Listing Application: {data.get('business_name', '')} ({data.get('area', '')})"
    return send_email(ADMIN_EMAIL, subject, text_body, html_body, reply_to=data.get('contact_email', ''))

def send_account_creation_email(vendor_data: dict) -> bool:
    """Welcomes a new vendor upon account creation with their CAC details."""
    b_name = vendor_data.get("business_name", "Vendor Partner")
    rc_num = vendor_data.get("rc_number", "")
    email = vendor_data.get("email", "")
    if not email:
        return False

    subject = f"Welcome to Lagos Updates — Vendor Account Created for {b_name}"
    text_body = f"""
=============================================================
WELCOME TO LAGOS UPDATES DIRECTORY
=============================================================
Hello {b_name},

Your vendor account has been created on the Lagos Updates Verified Operator Network.

ACCOUNT CREDENTIALS:
- Registered Business: {b_name}
- CAC Registration Number: {rc_num or 'Recorded'}
- Account Email: {email}

NEXT STEPS:
1. Log in to your Vendor Dashboard at https://lagos-update-directory.vercel.app/vendor.html
2. Complete your business listing with photos and verify payment.
3. Track editorial reviews, approval status, and visitor views in real time.

All listings are manually vetted by our Lagos editorial desk.
If you have questions, reply directly to this email or chat with our desk on WhatsApp.

Lagos Updates Directory Team
Èkó ò ní bàjẹ́!
=============================================================
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f7f7f7; color: #111827; margin: 0; padding: 24px; }}
  .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 14px; border: 1px solid #e5e7eb; overflow: hidden; }}
  .header {{ background: #000000; color: #ffffff; padding: 28px 24px; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 20px; text-transform: uppercase; letter-spacing: 1px; color: #FFD400; }}
  .content {{ padding: 28px 24px; line-height: 1.6; font-size: 15px; color: #374151; }}
  .box {{ background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; padding: 16px 20px; margin: 20px 0; }}
  .btn {{ display: inline-block; background: #FFD400; color: #111827 !important; font-weight: 800; text-decoration: none; padding: 13px 26px; border-radius: 9999px; margin-top: 14px; font-size: 14px; }}
  .footer {{ background: #f9f9f9; padding: 18px 24px; font-size: 12px; color: #9CA3AF; text-align: center; border-top: 1px solid #eee; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Lagos Updates Directory</h1>
      <p style="margin: 6px 0 0; color: #D1D5DB; font-size: 13px;">Verified Operator Network</p>
    </div>
    <div class="content">
      <h2 style="font-size: 18px; color: #111827; margin-top: 0;">Welcome, {b_name}! 👋</h2>
      <p>Your vendor account has been created on the <strong>Lagos Updates Directory</strong> platform.</p>
      
      <div class="box">
        <div style="font-size: 11px; text-transform: uppercase; color: #6B7280; font-weight: 700; margin-bottom: 6px;">Account Details</div>
        <div><strong>Business:</strong> {b_name}</div>
        <div><strong>CAC Registration:</strong> <span style="color:#0066cc; font-weight:700;">{rc_num or 'On File'}</span></div>
        <div><strong>Email:</strong> {email}</div>
      </div>

      <p>You can now manage your listings, submit high-resolution photos, and monitor visitor impressions in real time.</p>

      <div style="text-align: center; margin: 24px 0;">
        <a href="https://lagos-update-directory.vercel.app/vendor.html" class="btn">Open Vendor Dashboard &rarr;</a>
      </div>
    </div>
    <div class="footer">
      Lagos Updates Directory &bull; Only verified Lagos businesses.
    </div>
  </div>
</body>
</html>
"""
    return send_email(email, subject, text_body, html_body)

def send_submission_rejection_email(to_email: str, business_name: str, rc_number: str, ref_id: str, reason: str) -> bool:
    """Notifies a vendor that their application needs updates with detailed editorial explanation."""
    if not to_email:
        return False

    short_ref = (ref_id or "LU-REF")[:8].upper()
    subject = f"Application Feedback: {business_name} [Ref: {short_ref}] — Lagos Updates Directory"
    editorial_note = reason.strip() if reason and reason.strip() else "Business credentials or CAC registration details could not be verified according to Lagos Updates editorial standards."

    text_body = f"""
=============================================================
APPLICATION REVIEW UPDATE — LAGOS UPDATES DIRECTORY
=============================================================
Hello {business_name},

Thank you for applying to list on the Lagos Updates Directory (Application Ref: {short_ref}).
Our editorial review team has completed an initial review of your submission.

At this time, your application could not be approved due to the following specific reason:

EDITORIAL FEEDBACK:
-------------------------------------------------------------
"{editorial_note}"
-------------------------------------------------------------

CAC REGISTRATION ON FILE: {rc_number or 'Not provided'}

HOW TO RESOLVE THIS & GET APPROVED:
1. Review the feedback provided above by our editorial desk.
2. If your CAC details need updating, verify your legal entity at https://search.cac.gov.ng
3. Sign in to your Vendor Dashboard at https://lagos-update-directory.vercel.app/vendor.html to update your submission.
4. Once updated, your application will be re-queued for immediate review.

If you believe this is a misunderstanding, reply directly to this email or chat with our desk on WhatsApp. We are happy to help you get verified!

Warm regards,
Editorial Verification Desk
Lagos Updates Directory
=============================================================
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f7f7f7; color: #111827; margin: 0; padding: 24px; }}
  .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e5e7eb; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
  .header {{ background: #0B0F19; color: #ffffff; padding: 28px 24px; text-align: center; border-bottom: 3px solid #FFD400; }}
  .header h1 {{ margin: 0; font-size: 19px; letter-spacing: 0.5px; text-transform: uppercase; color: #FFD400; }}
  .content {{ padding: 32px 28px; line-height: 1.6; font-size: 15px; color: #374151; }}
  .badge {{ display: inline-block; background: #FEF3C7; color: #92400E; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; margin-bottom: 16px; }}
  .reason-box {{ background: #FFFBEB; border-left: 4px solid #F59E0B; border-radius: 8px; padding: 18px 20px; margin: 20px 0; color: #1F2937; }}
  .reason-title {{ font-size: 12px; font-weight: 800; text-transform: uppercase; color: #B45309; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .reason-text {{ font-size: 15px; line-height: 1.6; color: #1F2937; white-space: pre-line; }}
  .steps-box {{ background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; padding: 18px 20px; margin: 24px 0; }}
  .step-item {{ margin-bottom: 10px; font-size: 14px; color: #4B5563; }}
  .step-item strong {{ color: #111827; }}
  .btn-primary {{ display: inline-block; background: #FFD400; color: #111827 !important; font-weight: 800; text-decoration: none; padding: 13px 26px; border-radius: 9999px; font-size: 14px; margin: 6px; }}
  .btn-secondary {{ display: inline-block; background: #F3F4F6; color: #374151 !important; font-weight: 700; text-decoration: none; padding: 13px 22px; border-radius: 9999px; font-size: 14px; margin: 6px; }}
  .footer {{ background: #F9FAFB; padding: 20px 24px; font-size: 12px; color: #9CA3AF; text-align: center; border-top: 1px solid #E5E7EB; line-height: 1.5; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Lagos Updates Directory</h1>
      <p style="margin: 6px 0 0; color: #9CA3AF; font-size: 13px;">Editorial Verification Desk &bull; Ref: {short_ref}</p>
    </div>
    <div class="content">
      <span class="badge">Application Review Update</span>
      <h2 style="font-size: 20px; color: #111827; margin: 0 0 14px;">Hello {business_name},</h2>
      <p>Thank you for your interest in joining the <strong>Lagos Updates Directory</strong>. Our editorial team has completed a review of your business listing submission.</p>
      
      <p>At this time, we were unable to approve the application due to the following feedback:</p>

      <div class="reason-box">
        <div class="reason-title">Feedback from Editorial Review Desk:</div>
        <div class="reason-text">"{editorial_note}"</div>
      </div>

      <div class="steps-box">
        <div style="font-size: 13px; font-weight: 700; color: #111827; text-transform: uppercase; margin-bottom: 8px;">How to resolve this & get listed:</div>
        <div class="step-item">1. <strong>Update Details:</strong> Review and correct the items highlighted in the editorial note above.</div>
        <div class="step-item">2. <strong>CAC Verification:</strong> Ensure your registered business name matches official records at <a href="https://search.cac.gov.ng" target="_blank" style="color: #0066cc;">search.cac.gov.ng</a>. (Current RC on file: <code>{rc_number or 'Unspecified'}</code>).</div>
        <div class="step-item">3. <strong>Re-Submit:</strong> Log into your Vendor Dashboard to update your profile and photos.</div>
      </div>

      <div style="text-align: center; margin: 26px 0;">
        <a href="https://lagos-update-directory.vercel.app/vendor.html" class="btn-primary">Update in Vendor Dashboard &rarr;</a>
      </div>

      <p style="font-size: 13px; color: #6B7280; text-align: center;">
        Have questions or think we made an error? Reply directly to this email or chat with our desk on WhatsApp.
      </p>
    </div>
    <div class="footer">
      Lagos Updates Directory &bull; Curating Lagos's most trusted businesses.<br>
      Notice sent to {to_email} &middot; Ref: {short_ref}
    </div>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, text_body, html_body)

def send_submission_accepted_email(to_email: str, business_name: str, sub_id: str, plan_tier: str = "verified", amount_ngn: int = 30000, payment_url: str = "") -> bool:
    """Notifies a vendor that their application was approved and provides the activation payment link."""
    if not to_email:
        return False

    short_ref = (sub_id or "LU-REF")[:8].upper()
    tier_label = "⭐ Featured Placement (Top of Directory)" if plan_tier in ["featured", "featured_1w"] else "✓ Verified Business Listing"
    fee_formatted = f"₦{amount_ngn:,}"
    checkout_url = payment_url or f"https://lagos-update-directory.vercel.app/vendor.html?action=pay&sub_id={sub_id}"
    subject = f"🎉 Application Approved: {business_name} [Ref: {short_ref}] — Complete Activation to Go Live"

    text_body = f"""
=============================================================
CONGRATULATIONS! APPLICATION APPROVED — LAGOS UPDATES
=============================================================
Hello {business_name},

Great news! Your business application (Ref: {short_ref}) has been officially APPROVED by our Lagos editorial review team.

Your CAC registration and business details meet our directory standards.

ACTIVATION DETAILS:
- Registered Business: {business_name}
- Selected Tier: {tier_label}
- Activation Fee: {fee_formatted} (One-Time Verification & Placement)
- Reference ID: {short_ref}

NEXT STEP — ACTIVATE & GO LIVE:
To complete your listing activation and publish your spot live to thousands of Lagos customers and visitors, click the secure link below to complete your payment:

{checkout_url}

Payment Options via Flutterwave:
Card, Bank Transfer, USSD, or Barter.

As soon as payment is confirmed, your listing goes live immediately, and you will receive a direct link to your live page.

Editorial Review Desk,
Lagos Updates Directory
Èkó ò ní bàjẹ́!
=============================================================
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f7f7f7; color: #111827; margin: 0; padding: 24px; }}
  .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e5e7eb; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
  .header {{ background: #0B0F19; color: #ffffff; padding: 32px 24px; text-align: center; border-bottom: 3px solid #FFD400; }}
  .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 0.5px; text-transform: uppercase; color: #FFD400; }}
  .content {{ padding: 32px 28px; line-height: 1.6; font-size: 15px; color: #374151; }}
  .badge {{ display: inline-block; background: #DCFCE7; color: #166534; font-size: 12px; font-weight: 700; padding: 5px 12px; border-radius: 9999px; text-transform: uppercase; margin-bottom: 16px; border: 1px solid #86EFAC; }}
  .invoice-box {{ background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px; padding: 20px; margin: 22px 0; }}
  .invoice-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #F3F4F6; font-size: 14px; }}
  .invoice-row:last-child {{ border-bottom: none; padding-top: 12px; font-size: 16px; font-weight: 800; color: #111827; }}
  .btn-pay {{ display: inline-block; background: #FFD400; color: #111827 !important; font-weight: 800; text-decoration: none; padding: 15px 32px; border-radius: 9999px; font-size: 15px; box-shadow: 0 4px 14px rgba(255, 212, 0, 0.4); }}
  .footer {{ background: #F9FAFB; padding: 20px 24px; font-size: 12px; color: #9CA3AF; text-align: center; border-top: 1px solid #E5E7EB; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Lagos Updates Directory</h1>
      <p style="margin: 6px 0 0; color: #9CA3AF; font-size: 13px;">Official Application Acceptance &bull; Ref: {short_ref}</p>
    </div>
    <div class="content">
      <span class="badge">✓ Application Approved</span>
      <h2 style="font-size: 22px; color: #111827; margin: 0 0 12px;">Congratulations, {business_name}! 🎉</h2>
      <p>We are delighted to inform you that your business application has officially passed our editorial vetting and CAC compliance review.</p>
      
      <p>To activate your listing and publish your spot live to thousands of Lagos consumers and visitors, please complete your one-time placement fee:</p>

      <div class="invoice-box">
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #6B7280; margin-bottom: 10px;">Activation Summary</div>
        <div class="invoice-row">
          <span>Business Name:</span>
          <strong>{business_name}</strong>
        </div>
        <div class="invoice-row">
          <span>Selected Placement:</span>
          <strong>{tier_label}</strong>
        </div>
        <div class="invoice-row">
          <span>Reference Number:</span>
          <code>{short_ref}</code>
        </div>
        <div class="invoice-row">
          <span>Total Activation Fee:</span>
          <span style="color: #008A05;">{fee_formatted}</span>
        </div>
      </div>

      <div style="text-align: center; margin: 30px 0;">
        <a href="{checkout_url}" class="btn-pay">Pay Fee & Go Live Now &rarr;</a>
      </div>

      <p style="font-size: 13px; color: #6B7280; text-align: center; line-height: 1.5;">
        Secure payments powered by <strong>Flutterwave</strong> (Bank Transfer, Card, USSD).<br>
        Your listing will be published automatically the moment payment is confirmed.
      </p>
    </div>
    <div class="footer">
      Lagos Updates Directory &bull; Curating Lagos's most trusted businesses.<br>
      Notice sent to {to_email}
    </div>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, text_body, html_body)

def send_submission_approved_email(to_email: str, business_name: str, listing_id: str, plan_tier: str) -> bool:
    """Notifies a vendor that their listing is now live on the directory."""
    if not to_email:
        return False

    listing_url = f"https://lagos-update-directory.vercel.app/listing.html?id={listing_id}"
    subject = f"Congratulations! {business_name} is now LIVE on Lagos Updates"

    text_body = f"""
=============================================================
YOUR LISTING IS NOW LIVE — LAGOS UPDATES DIRECTORY
=============================================================
Hello {business_name},

Great news! Your listing has been approved by our editorial review team.
It is now published and visible to thousands of Lagos residents and travelers.

LISTING DETAILS:
- Name: {business_name}
- Plan: {(plan_tier or 'verified').upper()}
- Live Link: {listing_url}

Track your listing's real-time impressions, visitor views, and manage details in your Vendor Dashboard.

Lagos Updates Directory Desk
=============================================================
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f7f7f7; color: #111827; margin: 0; padding: 24px; }}
  .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 14px; border: 1px solid #e5e7eb; overflow: hidden; }}
  .header {{ background: #065F46; color: #ffffff; padding: 28px 24px; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 20px; }}
  .content {{ padding: 28px 24px; line-height: 1.6; font-size: 15px; color: #374151; }}
  .btn {{ display: inline-block; background: #FFD400; color: #111827 !important; font-weight: 800; text-decoration: none; padding: 13px 26px; border-radius: 9999px; margin-top: 14px; font-size: 14px; }}
  .footer {{ background: #f9f9f9; padding: 18px 24px; font-size: 12px; color: #9CA3AF; text-align: center; border-top: 1px solid #eee; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>✓ Your Spot is Live!</h1>
      <p style="margin: 6px 0 0; color: #A7F3D0; font-size: 13px;">{business_name} is published on Lagos Updates</p>
    </div>
    <div class="content">
      <h2 style="margin-top: 0; color: #111827;">Congratulations, {business_name}! 🎉</h2>
      <p>Your listing has passed our editorial verification and is now live on the <strong>Lagos Updates Directory</strong>.</p>
      
      <p>Users can now discover your services, browse your photo gallery, and reach out directly to your WhatsApp.</p>

      <div style="text-align: center; margin: 26px 0;">
        <a href="{listing_url}" class="btn">View Live Listing &rarr;</a>
      </div>
    </div>
    <div class="footer">
      Lagos Updates Directory &bull; Èkó ò ní bàjẹ́!
    </div>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, text_body, html_body)

def send_vendor_offer_email(to_email: str, business_name: str, offer_title: str, offer_details: str, promo_code: str = "") -> bool:
    """Sends exclusive promotional offers or placement opportunities to vendors."""
    if not to_email:
        return False

    subject = f"Exclusive Vendor Offer for {business_name}: {offer_title}"
    promo_text = f"Promo Code: {promo_code}\n" if promo_code else ""

    text_body = f"""
=============================================================
SPECIAL VENDOR OFFER — LAGOS UPDATES DIRECTORY
=============================================================
Hello {business_name},

We have an exclusive offer for verified operators on Lagos Updates:

{offer_title}
-------------------------------------------------------------
{offer_details}
{promo_text}
Upgrade or boost your placement directly from your Vendor Dashboard:
https://lagos-update-directory.vercel.app/vendor.html

Lagos Updates Growth Team
=============================================================
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f7f7f7; color: #111827; margin: 0; padding: 24px; }}
  .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 14px; border: 1px solid #e5e7eb; overflow: hidden; }}
  .header {{ background: #000000; color: #ffffff; padding: 28px 24px; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 20px; color: #FFD400; }}
  .content {{ padding: 28px 24px; line-height: 1.6; font-size: 15px; color: #374151; }}
  .offer-box {{ background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 10px; padding: 18px 20px; margin: 20px 0; }}
  .btn {{ display: inline-block; background: #FFD400; color: #111827 !important; font-weight: 800; text-decoration: none; padding: 13px 26px; border-radius: 9999px; margin-top: 14px; font-size: 14px; }}
  .footer {{ background: #f9f9f9; padding: 18px 24px; font-size: 12px; color: #9CA3AF; text-align: center; border-top: 1px solid #eee; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Exclusive Partner Offer</h1>
      <p style="margin: 6px 0 0; color: #D1D5DB; font-size: 13px;">Special promotion for {business_name}</p>
    </div>
    <div class="content">
      <h2 style="margin-top: 0; color: #111827;">{offer_title}</h2>
      <div class="offer-box">
        {offer_details}
        {f'<div style="margin-top:12px; font-weight:800; color:#B45309;">Use Code: <code style="background:#FEF3C7; padding:2px 8px; border-radius:4px;">{promo_code}</code></div>' if promo_code else ''}
      </div>

      <div style="text-align: center; margin: 24px 0;">
        <a href="https://lagos-update-directory.vercel.app/vendor.html" class="btn">Claim in Vendor Dashboard &rarr;</a>
      </div>
    </div>
    <div class="footer">
      Lagos Updates Directory &bull; Partnership &amp; Growth
    </div>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, text_body, html_body)
