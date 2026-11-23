"""
Unit and Integration tests for Supabase Google OAuth JWT authentication across all auth-protected endpoints:
- /api/vendor/listings
- /api/vendor/me
- /api/vendor/submissions
- /api/submissions
- /api/reviews

Validates:
1. Endpoints succeed (200/201) when given a Supabase Google OAuth JWT.
2. Succeeded even when SUPABASE_KEY is unset ("") as in Vercel environment.
3. Succeeded even when the user has no prior row in the vendors table.
4. Token extraction from Bearer header, X-Vendor-Token, X-Session-Token, and query parameters.
"""
import unittest
import json
import base64
import time
import uuid
import io
from server.app import DirectoryAppHandler
from server.db import init_db, get_connection
import server.config as config

def create_simulated_supabase_jwt(sub: str, email: str, name: str = "Google User", exp_in_seconds: int = 3600) -> str:
    """Creates a standard simulated Supabase Auth JWT without external dependencies."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": f"{config.SUPABASE_URL.rstrip('/')}/auth/v1",
        "sub": sub,
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        "app_metadata": {
            "provider": "google",
            "providers": ["google"]
        },
        "user_metadata": {
            "full_name": name,
            "name": name,
            "email": email,
            "avatar_url": "https://lh3.googleusercontent.com/test_avatar"
        },
        "exp": int(time.time()) + exp_in_seconds,
        "iat": int(time.time())
    }

    def b64url(data: dict) -> str:
        b = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return base64.b64encode(b).decode("utf-8").replace("+", "-").replace("/", "_").rstrip("=")

    h_b64 = b64url(header)
    p_b64 = b64url(payload)
    sig_b64 = "simulated_signature_blob"
    return f"{h_b64}.{p_b64}.{sig_b64}"

class InMemRequestHandler(DirectoryAppHandler):
    """Subclass of DirectoryAppHandler for zero-socket in-memory testing."""
    def __init__(self, method: str, path: str, body: bytes = b"", headers: dict = None):
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.requestline = f"{method} {path} HTTP/1.1"
        self.headers = {
            "Content-Length": str(len(body)),
            "Content-Type": "application/json"
        }
        if headers:
            self.headers.update(headers)
        self.client_address = ("127.0.0.1", 54321)
        self.server = None
        self.close_connection = False

    def handle_request(self):
        if self.command == "GET":
            self.do_GET()
        elif self.command == "POST":
            self.do_POST()
        elif self.command == "OPTIONS":
            self.do_OPTIONS()

    def get_response(self):
        self.wfile.seek(0)
        raw = self.wfile.read()
        parts = raw.split(b"\r\n\r\n", 1)
        header_text = parts[0].decode("utf-8", errors="replace")
        status_line = header_text.splitlines()[0]
        status_code = int(status_line.split(" ")[1])
        body_json = {}
        if len(parts) > 1 and parts[1]:
            try:
                body_json = json.loads(parts[1].decode("utf-8"))
            except Exception:
                body_json = {"raw": parts[1].decode("utf-8", errors="replace")}
        return status_code, body_json, header_text

class TestSupabaseAuthEndpoints(unittest.TestCase):
    def setUp(self):
        init_db()
        self.original_supabase_key = config.SUPABASE_KEY
        # Explicitly ensure SUPABASE_KEY is empty to simulate Vercel deployment without key
        config.SUPABASE_KEY = ""
        self.test_sub = str(uuid.uuid4())
        self.test_email = f"google_user_{self.test_sub[:8]}@gmail.com"
        self.test_name = "Chief Google User"
        self.jwt_token = create_simulated_supabase_jwt(self.test_sub, self.test_email, self.test_name)

    def tearDown(self):
        config.SUPABASE_KEY = self.original_supabase_key

    def test_vendor_me_with_supabase_jwt_no_prior_vendor_row(self):
        """GET /api/vendor/me succeeds (200) with Supabase Google OAuth JWT when user has no prior vendor record."""
        handler = InMemRequestHandler("GET", "/api/vendor/me", headers={
            "Authorization": f"Bearer {self.jwt_token}"
        })
        handler.handle_request()
        status, body, _ = handler.get_response()

        self.assertEqual(status, 200, f"Expected 200, got {status}: {body}")
        self.assertTrue(body.get("success"))
        vendor = body.get("vendor", {})
        self.assertEqual(vendor.get("email"), self.test_email)
        self.assertEqual(vendor.get("business_name"), self.test_name)

    def test_vendor_listings_with_supabase_jwt_no_prior_vendor_row(self):
        """GET /api/vendor/listings succeeds (200) with empty listings list."""
        handler = InMemRequestHandler("GET", "/api/vendor/listings", headers={
            "Authorization": f"Bearer {self.jwt_token}"
        })
        handler.handle_request()
        status, body, _ = handler.get_response()

        self.assertEqual(status, 200, f"Expected 200, got {status}: {body}")
        self.assertTrue(body.get("success"))
        self.assertIsInstance(body.get("listings"), list)

    def test_vendor_submissions_with_supabase_jwt_no_prior_vendor_row(self):
        """GET /api/vendor/submissions succeeds (200) with empty submissions list."""
        handler = InMemRequestHandler("GET", "/api/vendor/submissions", headers={
            "Authorization": f"Bearer {self.jwt_token}"
        })
        handler.handle_request()
        status, body, _ = handler.get_response()

        self.assertEqual(status, 200, f"Expected 200, got {status}: {body}")
        self.assertTrue(body.get("success"))
        self.assertIsInstance(body.get("submissions"), list)

    def test_submissions_post_with_supabase_jwt_no_prior_vendor_row(self):
        """POST /api/submissions succeeds (201) with draft submission created."""
        payload = {
            "business_name": f"Google Vendor Business {self.test_sub[:6]}",
            "rc_number": "RC 8829104",
            "category": "restaurant",
            "area": "Victoria Island",
            "description": "Premium dining experience along Adeola Odeku.",
            "price_range": "₦25,000 - ₦60,000",
            "whatsapp": "08031234567",
            "contact_name": self.test_name,
            "contact_email": self.test_email,
            "plan_tier": "verified"
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        handler = InMemRequestHandler("POST", "/api/submissions", body=body_bytes, headers={
            "Authorization": f"Bearer {self.jwt_token}"
        })
        handler.handle_request()
        status, body, _ = handler.get_response()

        self.assertEqual(status, 201, f"Expected 201, got {status}: {body}")
        self.assertTrue(body.get("success"))
        self.assertTrue(body.get("submission_id"))

    def test_reviews_post_with_supabase_jwt(self):
        """POST /api/reviews succeeds (201) when authenticated via Supabase Google OAuth JWT."""
        payload = {
            "listing_id": "eko-hotel-and-suites",
            "star_rating": 5,
            "comment": "Exceptional hospitality, security, and dining in Victoria Island."
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        handler = InMemRequestHandler("POST", "/api/reviews", body=body_bytes, headers={
            "Authorization": f"Bearer {self.jwt_token}"
        })
        handler.handle_request()
        status, body, _ = handler.get_response()

        self.assertEqual(status, 201, f"Expected 201, got {status}: {body}")
        self.assertTrue(body.get("success"))
        review = body.get("review", {})
        self.assertEqual(review.get("listing_id"), "eko-hotel-and-suites")
        self.assertEqual(review.get("star_rating"), 5)

    def test_token_via_x_vendor_token_header(self):
        """Verifies authentication succeeds when JWT is passed via X-Vendor-Token."""
        handler = InMemRequestHandler("GET", "/api/vendor/me", headers={
            "X-Vendor-Token": self.jwt_token
        })
        handler.handle_request()
        status, body, _ = handler.get_response()
        self.assertEqual(status, 200)
        self.assertEqual(body["vendor"]["email"], self.test_email)

    def test_token_via_x_session_token_header(self):
        """Verifies authentication succeeds when JWT is passed via X-Session-Token."""
        handler = InMemRequestHandler("GET", "/api/vendor/me", headers={
            "X-Session-Token": self.jwt_token
        })
        handler.handle_request()
        status, body, _ = handler.get_response()
        self.assertEqual(status, 200)
        self.assertEqual(body["vendor"]["email"], self.test_email)

    def test_token_via_query_param(self):
        """Verifies authentication succeeds when JWT is passed via ?vendor_token query param."""
        handler = InMemRequestHandler("GET", f"/api/vendor/me?vendor_token={self.jwt_token}")
        handler.handle_request()
        status, body, _ = handler.get_response()
        self.assertEqual(status, 200)
        self.assertEqual(body["vendor"]["email"], self.test_email)

    def test_cors_options_preflight_allows_x_session_token(self):
        """Verifies OPTIONS pre-flight returns 204 and allows X-Session-Token header."""
        handler = InMemRequestHandler("OPTIONS", "/api/vendor/me")
        handler.handle_request()
        status, _, header_text = handler.get_response()
        self.assertEqual(status, 204)
        self.assertIn("X-Session-Token", header_text)

if __name__ == "__main__":
    unittest.main()
