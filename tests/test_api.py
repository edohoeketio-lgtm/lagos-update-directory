"""
In-memory integration tests for DirectoryAppHandler (Zero socket dependencies).
Tests HTTP routing, request parsing, database integration, and responses.
"""
import unittest
import io
import json
import uuid
from server.app import DirectoryAppHandler
from server.db import init_db

class MockServer:
    """Mock socketserver for handler instantiation."""
    pass

class FakeSocket:
    def makefile(self, *args, **kwargs):
        return io.BytesIO()

class InMemHandler(DirectoryAppHandler):
    """Subclass of DirectoryAppHandler that reads from and writes to in-memory buffers."""
    def __init__(self, method: str, path: str, body: bytes = b"", headers: dict = None):
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.requestline = f"{method} {path} HTTP/1.1"
        self.headers = {
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "X-Admin-Key": "lagosupdates2026"
        }
        if headers:
            self.headers.update(headers)
        self.client_address = ("127.0.0.1", 54321)
        self.server = MockServer()
        self.close_connection = False

    def handle_request(self):
        if self.command == "GET":
            self.do_GET()
        elif self.command == "POST":
            self.do_POST()

    def get_response(self):
        self.wfile.seek(0)
        raw = self.wfile.read()
        # Separate headers and body
        parts = raw.split(b"\r\n\r\n", 1)
        headers_raw = parts[0].decode('utf-8')
        body_raw = parts[1] if len(parts) > 1 else b""
        status_line = headers_raw.splitlines()[0]
        status_code = int(status_line.split(" ")[1])
        try:
            body_json = json.loads(body_raw.decode('utf-8'))
        except Exception:
            body_json = body_raw.decode('utf-8')
        return status_code, body_json

class TestAPIInMemory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_health_check(self):
        h = InMemHandler("GET", "/api/health")
        h.handle_request()
        status, data = h.get_response()
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_get_listings_api(self):
        h = InMemHandler("GET", "/api/listings")
        h.handle_request()
        status, data = h.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 20)

    def test_get_listings_with_category_filter(self):
        h = InMemHandler("GET", "/api/listings?category=hotel")
        h.handle_request()
        status, data = h.get_response()
        self.assertEqual(status, 200)
        for item in data["listings"]:
            self.assertEqual(item["category"], "hotel")

    def test_submit_valid_listing_application(self):
        payload = {
            "business_name": "In-Memory Test Villa",
            "category": "apartment",
            "area": "Ikoyi",
            "description": "Stunning private villa in the heart of Ikoyi.",
            "price_range": "₦300,000 / night",
            "whatsapp": "08033334444",
            "instagram": "@ikoyivilla",
            "plan_tier": "featured",
            "contact_name": "Madam Kemi",
            "contact_email": "kemi@ikoyivilla.ng"
        }
        body = json.dumps(payload).encode('utf-8')
        h = InMemHandler("POST", "/api/submissions", body=body)
        h.handle_request()
        status, data = h.get_response()
        self.assertIn(status, [200, 201])
        self.assertTrue(data["success"])
        self.assertTrue(bool(data.get("submission_id")))

    def test_submit_invalid_payload_returns_422(self):
        payload = {
            "business_name": "", # empty
            "category": "invalid-cat",
            "area": "Ikoyi"
        }
        body = json.dumps(payload).encode('utf-8')
        h = InMemHandler("POST", "/api/submissions", body=body)
        h.handle_request()
        status, data = h.get_response()
        self.assertEqual(status, 422)
        self.assertIn("error", data)

    def test_admin_approve_and_reject_flow(self):
        # 1. Create a submission
        payload = {
            "business_name": "Admin Test Bistro",
            "category": "restaurant",
            "area": "Victoria Island",
            "description": "Exquisite dining experience for admin testing.",
            "price_range": "₦25,000 avg spend",
            "whatsapp": "08099887766",
            "contact_name": "Bistro Owner",
            "contact_email": "owner@adminbistro.ng",
            "plan_tier": "verified"
        }
        body = json.dumps(payload).encode('utf-8')
        h = InMemHandler("POST", "/api/submissions", body=body)
        h.handle_request()
        _, data = h.get_response()
        sub_id = data["submission_id"]

        # 2. Approve submission as featured spot
        h_approve = InMemHandler("POST", f"/api/admin/submissions/{sub_id}/approve?featured=1")
        h_approve.handle_request()
        status, approve_data = h_approve.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(approve_data["success"])
        self.assertTrue(approve_data["promoted"])
        self.assertTrue(bool(approve_data["listing_id"]))

        # 3. Verify it is now live in GET /api/listings
        h_list = InMemHandler("GET", "/api/listings?category=restaurant")
        h_list.handle_request()
        _, list_data = h_list.get_response()
        live_ids = [item["id"] for item in list_data["listings"]]
        self.assertIn(approve_data["listing_id"], live_ids)

    def test_admin_metrics_api(self):
        h = InMemHandler("GET", "/api/admin/metrics")
        h.handle_request()
        status, data = h.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertIn("listings_today", data)
        self.assertIn("featured_spots", data)
        self.assertIn("total_pending", data)
        self.assertIn("submissions_today", data)

    def test_vendor_auth_and_dashboard_flow(self):
        # 1. Register vendor with unique email
        test_email = f"vendor_{uuid.uuid4().hex[:6]}@lekki.ng"
        vendor_payload = {
            "business_name": "Lekki Luxury Suites",
            "email": test_email,
            "whatsapp": "08012349988",
            "password": "secure_vendor_pwd"
        }
        body = json.dumps(vendor_payload).encode('utf-8')
        h_reg = InMemHandler("POST", "/api/vendor/register", body=body)
        h_reg.handle_request()
        status, reg_data = h_reg.get_response()
        self.assertEqual(status, 201)
        self.assertTrue(reg_data["success"])
        self.assertTrue(bool(reg_data.get("token")))
        token = reg_data["token"]

        # 2. Login vendor
        login_payload = {
            "email": test_email,
            "password": "secure_vendor_pwd"
        }
        body = json.dumps(login_payload).encode('utf-8')
        h_login = InMemHandler("POST", "/api/vendor/login", body=body)
        h_login.handle_request()
        status, login_data = h_login.get_response()
        self.assertEqual(status, 200)
        self.assertEqual(login_data["vendor"]["email"], test_email)

        # 3. Create a listing for this vendor via submission + approve
        sub_payload = {
            "business_name": "Lekki Luxury Suites",
            "category": "apartment",
            "area": "Lekki Phase 1",
            "description": "Original description before vendor edit.",
            "price_range": "₦200,000 / night",
            "whatsapp": "08012349988",
            "contact_name": "Vendor Manager",
            "contact_email": test_email
        }
        sub_body = json.dumps(sub_payload).encode('utf-8')
        h_sub = InMemHandler("POST", "/api/submissions", body=sub_body)
        h_sub.handle_request()
        _, sub_data = h_sub.get_response()
        sub_id = sub_data["submission_id"]

        # Admin approves it
        h_app = InMemHandler("POST", f"/api/admin/submissions/{sub_id}/approve")
        h_app.handle_request()
        _, app_data = h_app.get_response()
        listing_id = app_data["listing_id"]

        # 4. Vendor queries their listings
        h_my_listings = InMemHandler("GET", "/api/vendor/listings", headers={"Authorization": f"Bearer {token}"})
        h_my_listings.handle_request()
        status, my_data = h_my_listings.get_response()
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(my_data["listings"]), 1)
        self.assertEqual(my_data["listings"][0]["id"], listing_id)

        # 5. Vendor submits an edit request
        edit_payload = {
            "description": "Updated luxury suite with private rooftop pool.",
            "price_range": "₦250,000 / night"
        }
        edit_body = json.dumps(edit_payload).encode('utf-8')
        h_edit = InMemHandler("POST", f"/api/vendor/listings/{listing_id}/request-edit", body=edit_body, headers={"Authorization": f"Bearer {token}"})
        h_edit.handle_request()
        status, edit_data = h_edit.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(edit_data["success"])
        req_id = edit_data["request_id"]

        # 6. Admin views pending vendor requests
        h_admin_reqs = InMemHandler("GET", "/api/admin/requests")
        h_admin_reqs.handle_request()
        status, reqs_data = h_admin_reqs.get_response()
        self.assertEqual(status, 200)
        req_ids = [r["id"] for r in reqs_data["requests"]]
        self.assertIn(req_id, req_ids)

        # 7. Admin approves the edit
        h_approve_req = InMemHandler("POST", f"/api/admin/requests/{req_id}/approve")
        h_approve_req.handle_request()
        status, approve_req_data = h_approve_req.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(approve_req_data["success"])

        # 8. Check that listing now has updated description in public API
        h_pub = InMemHandler("GET", f"/api/listings/{listing_id}")
        h_pub.handle_request()
        status, pub_data = h_pub.get_response()
        self.assertEqual(status, 200)
        self.assertEqual(pub_data["listing"]["description"], "Updated luxury suite with private rooftop pool.")
        self.assertEqual(pub_data["listing"]["priceRange"], "₦250,000 / night")

    def test_payment_config_endpoint(self):
        h = InMemHandler("GET", "/api/payments/config")
        h.handle_request()
        status, data = h.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["currency"], "NGN")
        self.assertTrue(data["public_key"].startswith("FLWPUBK_TEST-"))

    def test_payment_verification_for_submission(self):
        # 1. Create a submission first
        payload = {
            "business_name": "Flutterwave Test Beach Club",
            "category": "lounge",
            "area": "Oniru",
            "description": "Premium oceanfront beach lounge with sunset views.",
            "price_range": "₦30,000 avg spend",
            "whatsapp": "08011223344",
            "plan_tier": "featured_1w",
            "contact_name": "Club Manager",
            "contact_email": "manager@onirubeach.ng"
        }
        body = json.dumps(payload).encode('utf-8')
        h_sub = InMemHandler("POST", "/api/submissions", body=body)
        h_sub.handle_request()
        _, sub_data = h_sub.get_response()
        sub_id = sub_data["submission_id"]

        # 2. Verify payment for submission
        tx_ref = f"flw_sub_tx_{uuid.uuid4().hex[:8]}"
        tx_id = f"test_flw_{uuid.uuid4().hex[:8]}"
        verify_payload = {
            "transaction_id": tx_id,
            "tx_ref": tx_ref,
            "payment_type": "submission",
            "target_id": sub_id,
            "expected_amount": 35000.0,
            "customer": {
                "email": "manager@onirubeach.ng",
                "name": "Club Manager",
                "phone": "08011223344"
            }
        }
        h_ver = InMemHandler("POST", "/api/payments/verify", body=json.dumps(verify_payload).encode('utf-8'))
        h_ver.handle_request()
        status, ver_data = h_ver.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(ver_data["success"])
        self.assertEqual(ver_data["amount"], 35000.0)

        # 3. Test idempotency: second submission of same tx_ref returns already_processed
        h_ver2 = InMemHandler("POST", "/api/payments/verify", body=json.dumps(verify_payload).encode('utf-8'))
        h_ver2.handle_request()
        status2, ver_data2 = h_ver2.get_response()
        self.assertEqual(status2, 200)
        self.assertTrue(ver_data2["already_processed"])

    def test_payment_verification_for_boost(self):
        # 1. Create and approve listing
        payload = {
            "business_name": "Lagos Marina Yacht Club",
            "category": "service",
            "area": "Victoria Island",
            "description": "Private yacht charters and boat cruises.",
            "price_range": "₦500,000 / day",
            "whatsapp": "08099001122",
            "contact_name": "Captain Dan",
            "contact_email": "dan@lagosmarina.ng"
        }
        h_sub = InMemHandler("POST", "/api/submissions", body=json.dumps(payload).encode('utf-8'))
        h_sub.handle_request()
        _, sub_data = h_sub.get_response()
        sub_id = sub_data["submission_id"]

        h_app = InMemHandler("POST", f"/api/admin/submissions/{sub_id}/approve")
        h_app.handle_request()
        _, app_data = h_app.get_response()
        listing_id = app_data["listing_id"]

        # 2. Pay for 1-Week Boost (₦35,000)
        tx_ref = f"flw_boost_tx_{uuid.uuid4().hex[:8]}"
        tx_id = f"test_flw_{uuid.uuid4().hex[:8]}"
        boost_payload = {
            "transaction_id": tx_id,
            "tx_ref": tx_ref,
            "payment_type": "boost",
            "target_id": listing_id,
            "expected_amount": 35000.0,
            "metadata": {
                "duration": "1_week",
                "days": 7
            },
            "customer": {
                "email": "dan@lagosmarina.ng",
                "name": "Captain Dan",
                "phone": "08099001122"
            }
        }
        h_boost = InMemHandler("POST", "/api/payments/verify", body=json.dumps(boost_payload).encode('utf-8'))
        h_boost.handle_request()
        status, boost_data = h_boost.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(boost_data["success"])

        # 3. Check that listing is now featured and has active featured_until
        h_listing = InMemHandler("GET", f"/api/listings/{listing_id}")
        h_listing.handle_request()
        status, l_data = h_listing.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(l_data["listing"]["featured"])
        self.assertTrue(bool(l_data["listing"]["featuredUntil"]))

    def test_admin_auth_rejection_without_passkey(self):
        # Admin request without valid X-Admin-Key should return 401
        h = InMemHandler("GET", "/api/admin/metrics", headers={"X-Admin-Key": "wrong_key"})
        h.handle_request()
        status, data = h.get_response()
        self.assertEqual(status, 401)
        self.assertIn("error", data)

    def test_vendor_submissions_endpoint(self):
        # 1. Register a vendor
        test_email = f"pending_vendor_{uuid.uuid4().hex[:6]}@lekki.ng"
        v_payload = {
            "business_name": "Pending Verification Bistro",
            "email": test_email,
            "password": "passcode_secure"
        }
        h_reg = InMemHandler("POST", "/api/vendor/register", body=json.dumps(v_payload).encode('utf-8'))
        h_reg.handle_request()
        _, reg_data = h_reg.get_response()
        token = reg_data["token"]

        # 2. Submit a business with that email
        sub_payload = {
            "business_name": "Pending Verification Bistro",
            "category": "restaurant",
            "area": "Ikeja",
            "description": "Fine dining awaiting approval.",
            "price_range": "₦20,000 avg",
            "whatsapp": "08011223344",
            "contact_name": "Chef Ngozi",
            "contact_email": test_email
        }
        h_sub = InMemHandler("POST", "/api/submissions", body=json.dumps(sub_payload).encode('utf-8'))
        h_sub.handle_request()

        # 3. Vendor queries their submissions
        h_subs = InMemHandler("GET", "/api/vendor/submissions", headers={"Authorization": f"Bearer {token}"})
        h_subs.handle_request()
        status, data = h_subs.get_response()
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["submissions"]), 1)
        self.assertEqual(data["submissions"][0]["business_name"], "Pending Verification Bistro")

    def test_approve_submission_sets_owner_and_plan(self):
        test_email = f"owner_{uuid.uuid4().hex[:6]}@yaba.ng"
        sub_payload = {
            "business_name": "Yaba Tech Hub Lounge",
            "category": "lounge",
            "area": "Yaba",
            "description": "Coworking lounge with artisanal coffee.",
            "price_range": "₦5,000",
            "whatsapp": "08055443322",
            "plan_tier": "featured_1w",
            "contact_name": "Founder Tunde",
            "contact_email": test_email
        }
        h_sub = InMemHandler("POST", "/api/submissions", body=json.dumps(sub_payload).encode('utf-8'))
        h_sub.handle_request()
        _, sub_data = h_sub.get_response()
        sub_id = sub_data["submission_id"]

        h_app = InMemHandler("POST", f"/api/admin/submissions/{sub_id}/approve")
        h_app.handle_request()
        _, app_data = h_app.get_response()
        listing_id = app_data["listing_id"]

        # Register vendor with this email and verify they immediately see this listing
        v_payload = {
            "business_name": "Yaba Tech Hub Lounge",
            "email": test_email,
            "password": "mypassword123"
        }
        h_reg = InMemHandler("POST", "/api/vendor/register", body=json.dumps(v_payload).encode('utf-8'))
        h_reg.handle_request()
        _, reg_data = h_reg.get_response()
        token = reg_data["token"]

        h_my = InMemHandler("GET", "/api/vendor/listings", headers={"Authorization": f"Bearer {token}"})
        h_my.handle_request()
        status, my_data = h_my.get_response()
        self.assertEqual(status, 200)
        my_ids = [item["id"] for item in my_data["listings"]]
        self.assertIn(listing_id, my_ids)

if __name__ == '__main__':
    unittest.main()
