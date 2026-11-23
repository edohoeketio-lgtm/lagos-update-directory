"""
Supabase PostgreSQL & Cloud Data Access Module.
Provides robust REST communication with Supabase using Python's standard library.
Ensures zero-downtime fallback to local SQLite when offline or running automated tests.
"""
import os
import json
import urllib.request
import urllib.parse
from .config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_STORAGE_BUCKET

def is_supabase_enabled() -> bool:
    """Returns True if Supabase credentials are configured and not running in test mode."""
    if os.environ.get("LAGOS_TEST_MODE") == "1":
        return False
    return bool(SUPABASE_URL and SUPABASE_KEY)

def _supabase_request(table: str, method: str = "GET", params: str = "", body: dict | list = None):
    """Executes a PostgREST request against the Supabase project."""
    if not is_supabase_enabled():
        return None

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += f"?{params}"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    if method in ("POST", "PUT", "PATCH"):
        headers["Prefer"] = "return=representation"

    data_bytes = None
    if body is not None:
        data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            content = resp.read().decode("utf-8")
            if content:
                return json.loads(content)
            return []
    except Exception as e:
        print(f"[Supabase REST Error] {method} {table}:", e)
        return None

def supabase_sync_listing(listing_data: dict) -> bool:
    """Upserts a listing to Supabase."""
    res = _supabase_request("listings", method="POST", params="on_conflict=id", body=listing_data)
    return res is not None

def supabase_sync_submission(sub_data: dict) -> bool:
    """Inserts or updates a submission in Supabase."""
    res = _supabase_request("submissions", method="POST", params="on_conflict=id", body=sub_data)
    return res is not None

def supabase_sync_review(review_data: dict) -> bool:
    """Inserts or updates a review in Supabase."""
    res = _supabase_request("reviews", method="POST", params="on_conflict=id", body=review_data)
    return res is not None

def supabase_update_review_status(review_id: str, status: str) -> bool:
    """Updates review status (approved/rejected) in Supabase."""
    res = _supabase_request("reviews", method="PATCH", params=f"id=eq.{review_id}", body={"status": status})
    return res is not None

def supabase_get_public_reviews(listing_id: str) -> list[dict] | None:
    """Fetches approved reviews for a listing from Supabase."""
    return _supabase_request("reviews", method="GET", params=f"listing_id=eq.{listing_id}&status=eq.approved&order=created_at.desc")

def supabase_get_listings(category: str = None, area: str = None) -> list[dict] | None:
    """Fetches active listings from Supabase."""
    params = ["status=eq.active", "order=rating.desc"]
    if category and category != "all":
        params.append(f"category=eq.{urllib.parse.quote(category)}")
    if area and area != "all":
        params.append(f"area=eq.{urllib.parse.quote(area)}")
    
    return _supabase_request("listings", method="GET", params="&".join(params))


def verify_supabase_token(access_token: str) -> dict | None:
    """Verifies a Supabase Auth JWT access token via Supabase /auth/v1/user."""
    if not access_token or not is_supabase_enabled():
        return None
    if os.environ.get("LAGOS_TEST_MODE") == "1":
        return None
    try:
        url = f"{SUPABASE_URL}/auth/v1/user"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "LagosUpdatesDirectory/1.0"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                user = json.loads(resp.read().decode("utf-8"))
                uid = user.get("id")
                email = user.get("email", "")
                if not uid or not email:
                    return None
                meta = user.get("user_metadata") or {}
                return {
                    "uid": uid,
                    "email": email,
                    "name": meta.get("full_name") or meta.get("name") or email.split("@")[0],
                    "picture": meta.get("avatar_url") or meta.get("picture") or ""
                }
    except Exception as e:
        print("[Supabase Auth Verify Error]:", e)
    return None
