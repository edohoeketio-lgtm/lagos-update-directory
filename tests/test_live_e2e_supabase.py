"""
End-to-end verification of Supabase Google OAuth JWT against a live HTTP socket.
Simulates a Google OAuth JWT hitting:
1. GET /api/vendor/listings
2. GET /api/vendor/me
3. GET /api/vendor/submissions
4. POST /api/submissions
5. POST /api/reviews
Validates that with SUPABASE_KEY="" (Vercel env) and zero prior vendor rows, all return 200/201.
"""
import unittest
import socketserver
import threading
import time
import urllib.request
import json
import uuid
import base64
import os
import sys

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import server.config as config
from server.app import DirectoryAppHandler
from server.db import init_db, get_connection
from server.rate_limiter import limiter

TEST_PORT = 3195

class TestLiveE2ESupabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        limiter.requests.clear()
        cls.orig_key = config.SUPABASE_KEY
        # Enforce empty SUPABASE_KEY to simulate Vercel deployment without service key
        config.SUPABASE_KEY = ""

        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("", TEST_PORT), DirectoryAppHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)
        cls.base_url = f"http://127.0.0.1:{TEST_PORT}"

    @classmethod
    def tearDownClass(cls):
        config.SUPABASE_KEY = cls.orig_key
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def setUp(self):
        # Generate unique user identity
        self.sub = str(uuid.uuid4())
        self.email = f"live_e2e_{self.sub[:8]}@lagos.ng"
        self.name = "Engr. Babatunde Adeleke"

        # Verify absolutely no prior row exists in vendors table
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM vendors WHERE email = ?", (self.email,))
        self.assertIsNone(c.fetchone(), "Vendor must not exist before test")
        conn.close()

        # Build simulated standard Supabase Google OAuth JWT
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": f"{config.SUPABASE_URL.rstrip('/')}/auth/v1",
            "sub": self.sub,
            "aud": "authenticated",
            "role": "authenticated",
            "email": self.email,
            "app_metadata": {"provider": "google", "providers": ["google"]},
            "user_metadata": {
                "full_name": self.name,
                "name": self.name,
                "email": self.email,
                "avatar_url": "https://lh3.googleusercontent.com/avatar"
            },
            "exp": int(time.time()) + 3600,
            "iat": int(time.time())
        }

        def b64url(d):
            return base64.b64encode(json.dumps(d).encode("utf-8")).decode("utf-8").replace("+", "-").replace("/", "_").rstrip("=")

        self.jwt_token = f"{b64url(header)}.{b64url(payload)}.signature_blob"

    def test_01_get_vendor_listings_live(self):
        """1. GET /api/vendor/listings returns 200 OK with empty list for new Google OAuth user."""
        req = urllib.request.Request(
            f"{self.base_url}/api/vendor/listings",
            headers={"Authorization": f"Bearer {self.jwt_token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 200)
            data = json.loads(r.read().decode())
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("listings"), [])

    def test_02_get_vendor_me_live(self):
        """2. GET /api/vendor/me returns 200 OK with vendor profile matching Google OAuth identity."""
        req = urllib.request.Request(
            f"{self.base_url}/api/vendor/me",
            headers={"Authorization": f"Bearer {self.jwt_token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 200)
            data = json.loads(r.read().decode())
            self.assertTrue(data.get("success"))
            vendor = data.get("vendor", {})
            self.assertEqual(vendor.get("email"), self.email)
            self.assertEqual(vendor.get("business_name"), self.name)

    def test_03_get_vendor_submissions_live(self):
        """3. GET /api/vendor/submissions returns 200 OK with empty list for new Google OAuth user."""
        req = urllib.request.Request(
            f"{self.base_url}/api/vendor/submissions",
            headers={"Authorization": f"Bearer {self.jwt_token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 200)
            data = json.loads(r.read().decode())
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("submissions"), [])

    def test_04_post_submissions_live(self):
        """4. POST /api/submissions returns 201 Created and saves application linked to Google user."""
        payload = {
            "business_name": f"Adeleke Marine Charters {self.sub[:6]}",
            "rc_number": "RC 8829104",
            "category": "service",
            "area": "Victoria Island",
            "description": "Luxury private boat charters from VI to Ilashe beach.",
            "price_range": "₦350,000 / day",
            "whatsapp": "08031234567",
            "contact_name": self.name,
            "contact_email": self.email,
            "plan_tier": "verified"
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/submissions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.jwt_token}"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 201)
            data = json.loads(r.read().decode())
            self.assertTrue(data.get("success"))
            self.assertTrue(bool(data.get("submission_id")))

    def test_05_post_reviews_live(self):
        """5. POST /api/reviews returns 201 Created and submits verified customer review for moderation."""
        payload = {
            "listing_id": "eko-hotel-and-suites",
            "star_rating": 5,
            "comment": "Outstanding Sunday brunch and attentive staff at Eko Hotel!"
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/reviews",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.jwt_token}"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 201)
            data = json.loads(r.read().decode())
            self.assertTrue(data.get("success"))
            rev = data.get("review", {})
            self.assertEqual(rev.get("listing_id"), "eko-hotel-and-suites")
            self.assertEqual(rev.get("star_rating"), 5)
            self.assertEqual(rev.get("status"), "pending")

if __name__ == "__main__":
    unittest.main()
