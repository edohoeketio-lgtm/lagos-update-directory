"""
Unit & Integration Tests for Public Reviews & Admin Moderation Desk.
"""
import unittest
import urllib.request
import urllib.parse
import urllib.error
import json
import threading
import time
import os
import uuid

os.environ["LAGOS_TEST_MODE"] = "1"
os.environ["FIREBASE_PROJECT_ID"] = "test-lagos-project"

from server.app import run_server
from server.db import (
    init_db, get_connection, upsert_user, create_user_session,
    create_review, get_public_reviews, get_admin_pending_reviews,
    approve_review, reject_review
)
from server.config import ADMIN_PASSKEY
from server.rate_limiter import limiter

TEST_PORT = 3199
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

class TestReviewsSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        limiter.requests.clear()

        # Clean reviews for hermetic test
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM reviews WHERE listing_id = 'test-listing-rev-1'")
        c.execute("""
        INSERT OR IGNORE INTO listings (id, name, category, area, description, verified, rating)
        VALUES ('test-listing-rev-1', 'Bukas & Grills Lekki', 'Restaurants & Bars', 'Lekki Phase 1', 'Top grills', 1, '4.0')
        """)
        conn.commit()
        conn.close()

        cls.server_thread = threading.Thread(target=run_server, args=(TEST_PORT,), daemon=True)
        cls.server_thread.start()
        time.sleep(1.0)

        # Create a test user and session
        cls.test_uid = f"rev_user_{uuid.uuid4().hex[:6]}"
        cls.test_email = f"{cls.test_uid}@example.com"
        cls.user = upsert_user(
            firebase_uid=cls.test_uid,
            email=cls.test_email,
            display_name="Kolawole Dare",
            photo_url="https://example.com/kola.jpg"
        )
        cls.session_token = create_user_session(cls.user["id"])

    def test_01_submit_review_unauthenticated(self):
        """Unauthenticated submissions to /api/reviews should fail with 401."""
        payload = json.dumps({
            "listing_id": "test-listing-rev-1",
            "star_rating": 5,
            "comment": "Outstanding food and ambiance!"
        }).encode()

        req = urllib.request.Request(
            f"{BASE_URL}/api/reviews",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 401)

    def test_02_submit_review_authenticated(self):
        """Authenticated user submits a review and it gets marked pending."""
        payload = json.dumps({
            "listing_id": "test-listing-rev-1",
            "star_rating": 5,
            "comment": "Outstanding suya and chilled Chapman! Highly recommended."
        }).encode()

        req = urllib.request.Request(
            f"{BASE_URL}/api/reviews",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.session_token}"
            }
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 201)
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("success"))
            self.assertIn("review", data)
            rev = data["review"]
            self.assertEqual(rev["status"], "pending")
            self.assertEqual(rev["star_rating"], 5)
            self.assertEqual(rev["listing_id"], "test-listing-rev-1")
            self.review_id = rev["id"]

    def test_03_public_reviews_excludes_pending(self):
        """Public endpoint should only return approved reviews, not pending."""
        req = urllib.request.Request(f"{BASE_URL}/api/listings/test-listing-rev-1/reviews")
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("success"))
            # Any previously unapproved review shouldn't appear
            reviews = data.get("reviews", [])
            for r in reviews:
                self.assertNotEqual(r.get("comment"), "Outstanding suya and chilled Chapman! Highly recommended.")

    def test_04_admin_view_pending_and_moderation(self):
        """Admin can view pending reviews, approve, and reject."""
        # Check admin unauthorized without key
        req_unauth = urllib.request.Request(f"{BASE_URL}/api/admin/reviews")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_unauth)
        self.assertEqual(ctx.exception.code, 401)

        # Admin authorized
        req = urllib.request.Request(
            f"{BASE_URL}/api/admin/reviews",
            headers={"X-Admin-Key": ADMIN_PASSKEY}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertTrue(data.get("success"))
            self.assertGreaterEqual(data.get("count", 0), 1)
            matching = [r for r in data["reviews"] if r["listing_id"] == "test-listing-rev-1"]
            self.assertTrue(len(matching) > 0)
            target_rev = matching[0]

        # Approve the review
        approve_req = urllib.request.Request(
            f"{BASE_URL}/api/admin/reviews/{target_rev['id']}/approve",
            data=json.dumps({"admin_notes": "Verified authentic customer"}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Admin-Key": ADMIN_PASSKEY
            }
        )
        with urllib.request.urlopen(approve_req) as res:
            self.assertEqual(res.status, 200)
            app_data = json.loads(res.read().decode())
            self.assertTrue(app_data.get("success"))

        # Now public listing reviews should include it
        pub_req = urllib.request.Request(f"{BASE_URL}/api/listings/test-listing-rev-1/reviews")
        with urllib.request.urlopen(pub_req) as res:
            self.assertEqual(res.status, 200)
            pub_data = json.loads(res.read().decode())
            self.assertGreaterEqual(pub_data.get("count", 0), 1)
            self.assertEqual(pub_data["average_rating"], 5.0)
            self.assertEqual(pub_data["reviews"][0]["author_name"], "Kolawole Dare")

    def test_05_admin_reject_review(self):
        """Admin can reject a spam/abusive review."""
        # Create second review to reject
        rev2 = create_review(
            user_id=self.user["id"],
            listing_id="test-listing-rev-1",
            star_rating=1,
            comment="Spam message buy cheap followers"
        )
        reject_req = urllib.request.Request(
            f"{BASE_URL}/api/admin/reviews/{rev2['id']}/reject",
            data=json.dumps({"admin_notes": "Spam"}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Admin-Key": ADMIN_PASSKEY
            }
        )
        with urllib.request.urlopen(reject_req) as res:
            self.assertEqual(res.status, 200)
            rej_data = json.loads(res.read().decode())
            self.assertTrue(rej_data.get("success"))


if __name__ == "__main__":
    unittest.main()
