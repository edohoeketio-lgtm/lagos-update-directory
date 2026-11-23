"""
Validators and Normalizers for Lagos Updates Directory.
Pure domain functions following Clean Architecture principles.
"""
import re
import html
import base64
import os
import urllib.request
from .config import BASE_DIR, SUPABASE_URL, SUPABASE_KEY, SUPABASE_STORAGE_BUCKET

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join("/tmp", "uploads") if os.environ.get("VERCEL") else os.path.join(BASE_DIR, "data", "uploads"))

VALID_CATEGORIES = {
    'hotel',
    'apartment',
    'restaurant',
    'lounge',
    'private-chef',
    'personal-security',
    'service',
    'airport-pickup',
    'other',
    'others'
}

VALID_PLANS = {'verified', 'featured', 'featured_1w', 'featured_2w', 'featured_1m', 'standard'}

def sanitize_text(text: str, max_len: int = 1000) -> str:
    """Strip whitespace and escape HTML to prevent XSS."""
    if not text:
        return ""
    cleaned = html.escape(text.strip())
    return cleaned[:max_len]

def normalize_nigerian_phone(phone: str) -> str:
    """
    Normalizes a Nigerian phone number into standard E.164 (+234...).
    Accepts: '08031234567', '+234 803 123 4567', '2348031234567', '090...', '070...', etc.
    Returns: '+2348031234567' or empty string if invalid.
    """
    if not phone:
        return ""
    digits = re.sub(r'[^\d]', '', phone)
    
    if digits.startswith('234') and len(digits) == 13:
        return f"+{digits}"
    elif digits.startswith('0') and len(digits) == 11:
        return f"+234{digits[1:]}"
    elif len(digits) == 10:
        return f"+234{digits}"
    elif digits.startswith('234') and len(digits) > 13:
        return f"+{digits[:13]}"
    elif len(digits) >= 7 and len(digits) <= 15:
        return f"+{digits}"
    return ""

def clean_whatsapp_digits(phone: str) -> str:
    """Returns raw digits suitable for wa.me link (e.g. '2348031234567')."""
    normalized = normalize_nigerian_phone(phone)
    return normalized.replace("+", "")

def clean_instagram_handle(handle: str) -> str:
    """
    Cleans an Instagram handle.
    Converts 'https://instagram.com/mybusiness/' or '@mybusiness' into 'mybusiness'.
    """
    if not handle:
        return ""
    h = handle.strip()
    h = re.sub(r'^(https?:\/\/)?(www\.)?instagram\.com\/', '', h, flags=re.IGNORECASE)
    h = h.lstrip('@').split('/')[0].split('?')[0].strip()
    h = re.sub(r'[^\w.]', '', h)
    return h[:30]

def is_valid_email(email: str) -> bool:
    """Validates email format."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def is_valid_rc_number(rc_number: str) -> bool:
    """
    Validates CAC registration number (RC/BN/IT/LLP/LP).
    Accepts:
      - 'RC 1849201', 'RC-1849201', 'RC1849201'
      - 'BN 9931023', 'BN-9931023', 'BN9931023'
      - 'IT 12345', 'LLP 12345'
      - Bare 5-8 digit registration numbers (e.g. '1849201')
    """
    if not rc_number or not isinstance(rc_number, str):
        return False
    rc = rc_number.strip().upper()
    pattern = r'^(RC|BN|IT|LLP|LP)?[\s\-_]?[0-9]{5,8}$'
    return bool(re.match(pattern, rc))

def upload_to_supabase_storage(raw_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """
    Uploads photo bytes to Supabase Storage and returns the permanent public URL.
    Returns None on failure or if Supabase is unconfigured/in test mode.
    """
    if os.environ.get("LAGOS_TEST_MODE") == "1" or not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{filename}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": content_type
        }
        req = urllib.request.Request(url, data=raw_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            if resp.status in (200, 201):
                return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{filename}"
    except Exception as e:
        print("[Supabase Storage] Upload error, falling back to local file:", e)
    return None

def process_uploaded_photos(photos_raw: list, submission_id: str) -> list[str]:
    """
    Decodes up to 3 base64 image strings, validates magic bytes (JPEG/PNG/WebP),
    uploads to Supabase Storage (permanent cloud CDN) or saves locally to data/uploads/,
    and returns the list of accessible photo URLs.
    """
    if not isinstance(photos_raw, list):
        return []

    saved_paths = []
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    for idx, item in enumerate(photos_raw[:3]):
        if not isinstance(item, str) or not item.strip():
            continue
        try:
            if ',' in item:
                header, b64_data = item.split(',', 1)
            else:
                b64_data = item

            raw_bytes = base64.b64decode(b64_data)
            # Max 6MB check
            if len(raw_bytes) > 6 * 1024 * 1024:
                continue

            # Check magic bytes and determine content type
            ext = ".jpg"
            content_type = "image/jpeg"
            if raw_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                ext = ".png"
                content_type = "image/png"
            elif raw_bytes.startswith(b'RIFF') and b'WEBP' in raw_bytes[:16]:
                ext = ".webp"
                content_type = "image/webp"
            elif raw_bytes.startswith(b'\xff\xd8\xff'):
                ext = ".jpg"
                content_type = "image/jpeg"
            else:
                continue

            clean_id = submission_id.replace('-', '')[:8]
            filename = f"vendor_{clean_id}_{idx + 1}{ext}"

            # 1. First attempt upload to Supabase Cloud Storage
            cloud_url = upload_to_supabase_storage(raw_bytes, filename, content_type)
            if cloud_url:
                saved_paths.append(cloud_url)
                continue

            # 2. Local fallback if offline or in test mode
            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(raw_bytes)

            saved_paths.append(f"/data/uploads/{filename}")
        except Exception as e:
            print("[Upload] Error saving photo:", e)

    return saved_paths

def validate_submission_payload(data: dict) -> tuple[bool, dict, str]:
    """
    Validates and cleanses incoming business submission payload.
    Returns: (is_valid, cleaned_data, error_message)
    """
    if not isinstance(data, dict):
        return False, {}, "Invalid JSON payload"

    business_name = sanitize_text(data.get("business_name", ""), max_len=100)
    rc_number = sanitize_text(data.get("rc_number", ""), max_len=50).upper().strip()
    category = str(data.get("category", "")).strip().lower()
    area = sanitize_text(data.get("area", ""), max_len=80)
    description = sanitize_text(data.get("description", ""), max_len=800)
    price_range = sanitize_text(data.get("price_range", ""), max_len=60)
    whatsapp_raw = str(data.get("whatsapp", "")).strip()
    instagram_raw = str(data.get("instagram", "")).strip()
    drive_link = sanitize_text(data.get("drive_link", ""), max_len=300)
    plan_tier = str(data.get("plan_tier", "verified")).strip().lower()
    contact_name = sanitize_text(data.get("contact_name", ""), max_len=100)
    contact_email = str(data.get("contact_email", "")).strip().lower()
    photos_raw = data.get("photos", [])

    # Honeypot check (anti-bot)
    honeypot = data.get("website_url_hp", "")
    if honeypot:
        return False, {}, "Spam detected."

    if not business_name or len(business_name) < 2:
        return False, {}, "Business name must be at least 2 characters."

    if not rc_number or len(rc_number) < 3:
        return False, {}, "CAC Registration Number (RC or BN Number) is required. Lagos Updates only lists legally registered companies."

    if category not in VALID_CATEGORIES and not category.startswith("other"):
        return False, {}, f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"

    if not area or len(area) < 2:
        return False, {}, "Neighborhood / Area is required (e.g. Ikoyi, Lekki Phase 1)."

    if not description or len(description) < 10:
        return False, {}, "Description must be at least 10 characters."

    phone_normalized = normalize_nigerian_phone(whatsapp_raw)
    if not phone_normalized:
        return False, {}, "Please provide a valid phone or WhatsApp number (e.g. 080... or +234...)."

    if not is_valid_email(contact_email):
        return False, {}, "Please provide a valid contact email address."

    if not contact_name or len(contact_name) < 2:
        return False, {}, "Contact person name is required."

    if plan_tier not in VALID_PLANS:
        plan_tier = "verified"

    cleaned = {
        "business_name": business_name,
        "rc_number": rc_number,
        "category": category,
        "area": area,
        "description": description,
        "price_range": price_range or "Price on request",
        "whatsapp": phone_normalized,
        "whatsapp_digits": clean_whatsapp_digits(whatsapp_raw),
        "instagram": clean_instagram_handle(instagram_raw),
        "drive_link": drive_link,
        "plan_tier": plan_tier,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "photos_raw": photos_raw if isinstance(photos_raw, list) else []
    }

    return True, cleaned, ""
