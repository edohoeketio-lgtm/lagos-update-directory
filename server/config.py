"""
Configuration for Lagos Updates Directory Backend.
Loads environment variables from os.environ and local .env file.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load local .env file if present (ignored by git)
env_path = os.path.join(BASE_DIR, ".env")
if os.path.isfile(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

DB_PATH = os.environ.get("DB_PATH", os.path.join("/tmp", "directory.db") if os.environ.get("VERCEL") else os.path.join(BASE_DIR, "data", "directory.db"))
DATA_JSON_PATH = os.path.join(BASE_DIR, "data", "listings.json")

PORT = int(os.environ.get("PORT", 3000))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "vendors@lagosupdates.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

# Resend Transactional Email Provider (Primary)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Lagos Updates Directory <onboarding@resend.dev>")

# Mailgun Transactional Email Provider (Optional legacy fallback)
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "")
MAILGUN_FROM_EMAIL = os.environ.get("MAILGUN_FROM_EMAIL", "Lagos Updates Directory <noreply@lagosupdates.com>")

# Firebase Auth Configuration
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "lagos-updates")
FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "")
FIREBASE_AUTH_DOMAIN = os.environ.get("FIREBASE_AUTH_DOMAIN", "lagos-updates.firebaseapp.com")
FIREBASE_APP_ID = os.environ.get("FIREBASE_APP_ID", "")

RATE_LIMIT_SUBMISSIONS_PER_HOUR = int(os.environ.get("RATE_LIMIT_SUBMISSIONS_PER_HOUR", 10))

# Editorial Admin Passkey
ADMIN_PASSKEY = os.environ.get("ADMIN_PASSKEY", "lagosupdates2026")

# Flutterwave Payment Gateway Configuration
FLW_PUBLIC_KEY = os.environ.get("FLW_PUBLIC_KEY") or "FLWPUBK_TEST-907fc3ea1f385d5b0a3bd1c0d725a40d-X"
FLW_SECRET_KEY = os.environ.get("FLW_SECRET_KEY", "")
FLW_SECRET_HASH = os.environ.get("FLW_SECRET_HASH", "")
FLW_ENCRYPTION_KEY = os.environ.get("FLW_ENCRYPTION_KEY", "")
FLW_BASE_URL = os.environ.get("FLW_BASE_URL", "https://api.flutterwave.com/v3")

# PostHog Telemetry Configuration
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY", "")
POSTHOG_API_HOST = os.environ.get("POSTHOG_API_HOST", "https://us.i.posthog.com")

# Supabase Cloud Database & Storage Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://wpfyfommvhopjvwdzjsf.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "listing-photos")
