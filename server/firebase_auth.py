"""
Firebase Auth Token Verification for Lagos Updates Directory.
Validates Firebase ID tokens using Google's public tokeninfo endpoint,
with zero external runtime dependencies.
"""
import urllib.request
import urllib.parse
import json
import os
from .config import FIREBASE_PROJECT_ID

def verify_firebase_token(id_token: str) -> dict | None:
    """
    Verifies a Firebase ID token.
    Returns decoded token dictionary with 'uid', 'email', 'name', 'picture' if valid,
    or None if verification fails.
    """
    if not id_token or not isinstance(id_token, str):
        return None

    id_token = id_token.strip()
    if not id_token:
        return None

    # Handle test / mock tokens strictly in test mode for local testing and CI
    if os.environ.get("LAGOS_TEST_MODE") == "1" and id_token.startswith("mock_token_"):
        parts = id_token.split(":")
        uid = parts[0].replace("mock_token_", "")
        email = parts[1] if len(parts) > 1 else f"{uid}@example.com"
        name = parts[2] if len(parts) > 2 else "Test User"
        return {
            "uid": uid,
            "email": email,
            "name": name,
            "picture": ""
        }

    # Verify live token with Google's public tokeninfo service
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(id_token)}"
        req = urllib.request.Request(url, headers={"User-Agent": "LagosUpdatesDirectory/1.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                uid = payload.get("sub") or payload.get("user_id")
                if not uid:
                    return None

                # Check audience against Firebase Project ID if configured
                aud = payload.get("aud")
                if FIREBASE_PROJECT_ID and aud and aud != FIREBASE_PROJECT_ID:
                    # Some Firebase tokens provide project in firebase claim
                    firebase_claim = payload.get("firebase", {})
                    token_project = firebase_claim.get("project_id")
                    if token_project and token_project != FIREBASE_PROJECT_ID:
                        return None

                return {
                    "uid": uid,
                    "email": payload.get("email", ""),
                    "name": payload.get("name", ""),
                    "picture": payload.get("picture", "")
                }
    except Exception as e:
        print("[Firebase Auth] Token verification failed:", e)
        return None

    return None
