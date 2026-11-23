"""
Unit & Integration Tests for Unified Firebase Auth & Progressive Profiling.
"""
import unittest
import urllib.request
import urllib.parse
import json
import threading
import time
import os
import uuid

# Set test environment
os.environ["LAGOS_TEST_MODE"] = "1"
os.environ["FIREBASE_PROJECT_ID"] = "test-lagos-project"

from server.app import run_server
from server.db import init_db, get_connection

TEST_PORT = 3198
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

class TestUnifiedAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.server_thread = threading.Thread(target=run_server, args=(TEST_PORT,), daemon=True)
        cls.server_thread.start()
        time.sleep(1.0)

    def test_01_auth_config(self):
        req = urllib.request.Request(f"{BASE_URL}/api/auth/config")
        with urllib.request.urlopen(req, timeout=5) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("success"))
            self.assertTrue(bool(data.get("projectId")))

    def test_02_firebase_token_verify_and_user_creation(self):
        test_uid = f"fb_user_{uuid.uuid4().hex[:8]}"
        test_email = f"{test_uid}@example.com"
        mock_token = f"mock_token_{test_uid}:{test_email}:Adebayo Johnson"

        payload = json.dumps({"id_token": mock_token}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/auth/verify",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("success"))
            self.assertIn("session_token", data)
            user = data.get("user", {})
            self.assertEqual(user.get("email"), test_email)
            self.assertEqual(user.get("display_name"), "Adebayo Johnson")
            self.assertFalse(user.get("has_vendor_profile"))

    def test_03_progressive_vendor_profile(self):
        # 1. Sign in as new user
        test_uid = f"fb_vendor_{uuid.uuid4().hex[:8]}"
        test_email = f"{test_uid}@example.com"
        mock_token = f"mock_token_{test_uid}:{test_email}:Folake Martins"

        payload = json.dumps({"id_token": mock_token}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/auth/verify",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            auth_data = json.loads(res.read().decode())
            session_token = auth_data["session_token"]

        # 2. Add progressive vendor details (CAC, business name, whatsapp)
        profile_payload = json.dumps({
            "business_name": "Folake Gourmet Catering Ltd",
            "cac_number": "RC 8829104",
            "whatsapp": "08031234567"
        }).encode()

        req_profile = urllib.request.Request(
            f"{BASE_URL}/api/vendor/profile",
            data=profile_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {session_token}"
            }
        )
        with urllib.request.urlopen(req_profile, timeout=5) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("success"))
            vp = data.get("vendor_profile", {})
            self.assertEqual(vp.get("business_name"), "Folake Gourmet Catering Ltd")
            self.assertEqual(vp.get("cac_number"), "RC 8829104")

        # 3. Check /api/auth/me reflects the vendor profile
        req_me = urllib.request.Request(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        with urllib.request.urlopen(req_me, timeout=5) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("user", {}).get("has_vendor_profile"))

    def test_04_submission_with_unified_profile(self):
        from server.rate_limiter import limiter
        limiter.requests.clear()
        # 1. Sign in & add vendor profile
        test_uid = f"fb_lister_{uuid.uuid4().hex[:8]}"
        test_email = f"{test_uid}@example.com"
        mock_token = f"mock_token_{test_uid}:{test_email}:Tariq Alabi"

        payload = json.dumps({"id_token": mock_token}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/auth/verify",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            session_token = json.loads(res.read().decode())["session_token"]

        # 2. Add CAC profile
        req_profile = urllib.request.Request(
            f"{BASE_URL}/api/vendor/profile",
            data=json.dumps({
                "business_name": "Eko Prime Executive Suites",
                "cac_number": "BN 9931023",
                "whatsapp": "08098765432"
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {session_token}"
            }
        )
        with urllib.request.urlopen(req_profile, timeout=5) as res:
            self.assertEqual(res.status, 200)

        # 3. Submit Listing
        sub_payload = json.dumps({
            "business_name": "Eko Prime Executive Suites",
            "rc_number": "BN 9931023",
            "category": "apartment",
            "area": "Victoria Island",
            "description": "Premium 2-bedroom serviced apartments on Victoria Island with waterfront views and 24/7 security.",
            "price_range": "₦120,000 / night",
            "whatsapp": "08098765432",
            "instagram": "@ekoprime",
            "plan_tier": "verified",
            "contact_name": "Tariq Alabi",
            "contact_email": test_email
        }).encode()

        req_sub = urllib.request.Request(
            f"{BASE_URL}/api/submissions",
            data=sub_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {session_token}"
            }
        )
        with urllib.request.urlopen(req_sub, timeout=5) as res:
            self.assertIn(res.status, [200, 201])
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("success"))

if __name__ == '__main__':
    unittest.main()
