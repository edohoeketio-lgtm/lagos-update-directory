"""
Lagos Updates Directory — Unified HTTP Server & REST API.
Serves static frontend, handles REST API routes with SQLite and photo uploads.
"""
import http.server
import socketserver
import urllib.parse
import json
import os
import uuid

from .config import PORT, BASE_DIR, FLW_PUBLIC_KEY, FLW_SECRET_KEY, FLW_ENCRYPTION_KEY, ADMIN_PASSKEY, POSTHOG_API_KEY, POSTHOG_API_HOST
from .db import (
    init_db, query_listings, get_listing_by_id,
    insert_submission, get_recent_submission, mark_submission_email_sent,
    get_connection, approve_submission, reject_submission,
    get_all_admin_listings, toggle_listing_active, toggle_listing_promoted, delete_listing,
    register_vendor, authenticate_vendor, get_vendor_by_session, get_vendor_listings, get_vendor_submissions,
    create_vendor_request, get_admin_vendor_requests, resolve_vendor_request, apply_listing_boost,
    save_review_subscriber, record_payment, get_payment_by_tx_ref, get_payment_by_ref_or_id
)
from .flutterwave import verify_flutterwave_transaction
from .validators import validate_submission_payload, process_uploaded_photos
from .email_service import dispatch_submission_email
from .rate_limiter import limiter

class DirectoryAppHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        if 'directory' not in kwargs and len(args) < 4:
            kwargs['directory'] = BASE_DIR
        super().__init__(*args, **kwargs)

    def send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Vendor-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(body)

    def get_authenticated_vendor(self):
        """Extracts Bearer token or X-Vendor-Token header."""
        auth = self.headers.get("Authorization", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth.replace("Bearer ", "").strip()
        else:
            token = self.headers.get("X-Vendor-Token", "").strip()
        if not token:
            return None
        return get_vendor_by_session(token)

    def get_request_path(self):
        raw = self.headers.get("x-forwarded-uri") or self.headers.get("x-matched-path") or self.path
        return urllib.parse.urlparse(raw)

    def is_admin_authorized(self):
        """Validates X-Admin-Key header or admin_key query parameter against ADMIN_PASSKEY."""
        key = self.headers.get("X-Admin-Key", "").strip()
        if not key:
            parsed = self.get_request_path()
            params = urllib.parse.parse_qs(parsed.query)
            key = params.get("admin_key", [""])[0].strip()
        return key == ADMIN_PASSKEY

    def parse_json_body(self, max_size=20*1024*1024):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0 or content_length > max_size:
            return None
        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def do_OPTIONS(self):
        """Handle CORS pre-flight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Vendor-Token")
        self.end_headers()

    def do_GET(self):
        parsed = self.get_request_path()
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # -----------------------------
        # REST API Routes
        # -----------------------------
        if path == "/api/health":
            return self.send_json(200, {"status": "ok", "service": "lagos-directory-backend"})

        if path == "/api/payments/config":
            return self.send_json(200, {
                "success": True,
                "public_key": FLW_PUBLIC_KEY,
                "currency": "NGN"
            })

        if path == "/api/telemetry/config":
            return self.send_json(200, {
                "success": True,
                "api_key": POSTHOG_API_KEY,
                "api_host": POSTHOG_API_HOST
            })

        if path == "/api/listings":
            category = params.get("category", ["all"])[0]
            area = params.get("area", ["all"])[0]
            q = params.get("q", [""])[0]
            verified = params.get("verified", ["0"])[0] in ["1", "true"]
            featured = params.get("featured", ["0"])[0] in ["1", "true"]

            listings = query_listings(category=category, area=area, query=q, verified_only=verified, featured_only=featured)
            return self.send_json(200, {
                "success": True,
                "count": len(listings),
                "listings": listings
            })

        if path.startswith("/api/admin/"):
            if not self.is_admin_authorized():
                return self.send_json(401, {"error": "Unauthorized: Invalid or missing editorial passkey."})

        if path == "/api/admin/listings":
            items = get_all_admin_listings()
            return self.send_json(200, {
                "success": True,
                "count": len(items),
                "listings": items
            })

        if path.startswith("/api/listings/"):
            listing_id = path.replace("/api/listings/", "").strip()
            item = get_listing_by_id(listing_id)
            if not item:
                return self.send_json(404, {"error": "Listing not found"})
            return self.send_json(200, {"success": True, "listing": item})

        if path == "/api/admin/metrics":
            from datetime import datetime
            conn = get_connection()
            cursor = conn.cursor()
            today_str = datetime.now().strftime("%Y-%m-%d")

            cursor.execute("SELECT COUNT(*) AS total FROM listings;")
            total_listings = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS today FROM listings WHERE date(created_at) = date('now', 'localtime') OR date(created_at) = ?;", (today_str,))
            listings_today = cursor.fetchone()["today"]

            cursor.execute("SELECT COUNT(*) AS featured FROM listings WHERE promoted = 1;")
            total_featured = cursor.fetchone()["featured"]

            cursor.execute("SELECT COUNT(*) AS pending FROM submissions WHERE status = 'pending';")
            total_pending = cursor.fetchone()["pending"]

            cursor.execute("SELECT COUNT(*) AS apps_today FROM submissions WHERE date(created_at) = date('now', 'localtime') OR date(created_at) = ?;", (today_str,))
            submissions_today = cursor.fetchone()["apps_today"]

            conn.close()

            return self.send_json(200, {
                "success": True,
                "listings_today": listings_today,
                "total_listings": total_listings,
                "featured_spots": total_featured,
                "total_pending": total_pending,
                "submissions_today": submissions_today
            })

        if path == "/api/admin/submissions":
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM submissions ORDER BY created_at DESC LIMIT 50;")
            rows = cursor.fetchall()
            conn.close()
            submissions = []
            for r in rows:
                item = dict(r)
                try:
                    item["photos"] = json.loads(item.get("photos") or "[]")
                except Exception:
                    item["photos"] = []
                submissions.append(item)
            return self.send_json(200, {"success": True, "count": len(submissions), "submissions": submissions})

        if path == "/api/vendor/me":
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {"error": "Unauthorized. Please log in."})
            return self.send_json(200, {"success": True, "vendor": vendor})

        if path == "/api/vendor/listings":
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {"error": "Unauthorized. Please log in."})
            items = get_vendor_listings(vendor["email"], vendor["business_name"])
            return self.send_json(200, {"success": True, "listings": items})

        if path == "/api/vendor/submissions":
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {"error": "Unauthorized. Please log in."})
            subs = get_vendor_submissions(vendor["email"])
            return self.send_json(200, {"success": True, "submissions": subs})

        if path == "/api/admin/requests":
            reqs = get_admin_vendor_requests()
            return self.send_json(200, {"success": True, "requests": reqs})

        # -----------------------------
        # Static Frontend Route Mapping
        # -----------------------------
        query_str = ('?' + parsed.query) if parsed.query else ''
        if path.rstrip('/') in ['/listing', '/directory', '/admin', '/vendor']:
            self.path = path.rstrip('/') + '.html' + query_str
        elif path == '' or path == '/':
            self.path = '/index.html' + query_str

        return super().do_GET()

    def do_POST(self):
        parsed = self.get_request_path()
        path = parsed.path

        # Flutterwave Payment Verification & Webhooks
        if path == "/api/payments/verify":
            body = self.parse_json_body()
            if not body:
                return self.send_json(400, {"error": "Missing payment verification payload."})

            transaction_id = body.get("transaction_id")
            tx_ref = body.get("tx_ref")
            expected_amount = body.get("expected_amount")
            payment_type = body.get("payment_type", "submission")
            target_id = str(body.get("target_id", ""))
            customer = body.get("customer", {})
            metadata = body.get("metadata", {})

            if not transaction_id:
                return self.send_json(400, {"error": "Transaction ID is required."})

            # Check if this tx_ref or transaction_id has already been processed to avoid double fulfillment
            existing_payment = get_payment_by_ref_or_id(tx_ref=tx_ref, transaction_id=transaction_id)
            if existing_payment and existing_payment.get("status") == "successful":
                return self.send_json(200, {
                    "success": True,
                    "already_processed": True,
                    "message": "Payment was already verified and processed.",
                    "payment_id": existing_payment["id"]
                })

            # Server-side verification with Flutterwave API
            verified, tx_data = verify_flutterwave_transaction(
                transaction_id,
                expected_amount=expected_amount,
                expected_currency="NGN"
            )

            if not verified:
                return self.send_json(400, {
                    "success": False,
                    "error": tx_data.get("error", "Flutterwave transaction verification failed.")
                })

            # Record successful payment in SQLite
            final_tx_ref = tx_ref or tx_data.get("tx_ref") or f"flw_tx_{transaction_id}"
            payment_record = {
                "tx_ref": final_tx_ref,
                "flw_ref": tx_data.get("flw_ref", ""),
                "transaction_id": str(transaction_id),
                "amount": float(tx_data.get("amount", expected_amount or 0.0)),
                "currency": tx_data.get("currency", "NGN"),
                "status": "successful",
                "payment_type": payment_type,
                "target_id": target_id,
                "customer_email": customer.get("email") or tx_data.get("customer", {}).get("email", ""),
                "customer_name": customer.get("name") or tx_data.get("customer", {}).get("name", ""),
                "customer_phone": customer.get("phone") or tx_data.get("customer", {}).get("phone_number", ""),
                "metadata": metadata
            }

            pay_id = record_payment(payment_record)

            return self.send_json(200, {
                "success": True,
                "message": "Payment verified and recorded successfully!",
                "payment_id": pay_id,
                "tx_ref": payment_record["tx_ref"],
                "flw_ref": payment_record["flw_ref"],
                "amount": payment_record["amount"],
                "payment_type": payment_type,
                "target_id": target_id
            })

        if path == "/api/payments/webhook":
            body = self.parse_json_body() or {}
            event = body.get("event")
            data = body.get("data", {})
            if event == "charge.completed" and data.get("status") == "successful":
                tx_ref = data.get("tx_ref")
                if tx_ref:
                    existing = get_payment_by_tx_ref(tx_ref)
                    if not existing:
                        record_payment({
                            "tx_ref": tx_ref,
                            "flw_ref": data.get("flw_ref", ""),
                            "transaction_id": str(data.get("id", "")),
                            "amount": float(data.get("amount", 0.0)),
                            "currency": data.get("currency", "NGN"),
                            "status": "successful",
                            "payment_type": data.get("meta", {}).get("payment_type", "submission"),
                            "target_id": data.get("meta", {}).get("target_id", ""),
                            "customer_email": data.get("customer", {}).get("email", ""),
                            "customer_name": data.get("customer", {}).get("name", ""),
                            "customer_phone": data.get("customer", {}).get("phone_number", ""),
                            "metadata": data.get("meta", {})
                        })
            return self.send_json(200, {"status": "ok"})

        # Vendor Auth Routes
        if path == "/api/vendor/register":
            body = self.parse_json_body()
            if not body or not body.get("email") or not body.get("password") or not body.get("business_name"):
                return self.send_json(400, {"error": "Business name, email, and password are required."})
            vendor_id, err = register_vendor(body["email"], body["password"], body["business_name"], body.get("whatsapp", ""))
            if err:
                return self.send_json(400, {"error": err})
            auth_res, auth_err = authenticate_vendor(body["email"], body["password"])
            return self.send_json(201, {
                "success": True,
                "message": "Account created successfully!",
                "token": auth_res["token"],
                "vendor": auth_res["vendor"]
            })

        if path == "/api/vendor/login":
            body = self.parse_json_body()
            if not body or not body.get("email") or not body.get("password"):
                return self.send_json(400, {"error": "Email and password are required."})
            auth_res, err = authenticate_vendor(body["email"], body["password"])
            if err:
                return self.send_json(401, {"error": err})
            return self.send_json(200, {
                "success": True,
                "message": "Welcome back!",
                "token": auth_res["token"],
                "vendor": auth_res["vendor"]
            })

        # Vendor Listing Actions
        if path.startswith("/api/vendor/listings/") and path.endswith("/request-edit"):
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {"error": "Unauthorized"})
            parts = path.split("/")
            listing_id = parts[4]
            body = self.parse_json_body() or {}
            req_id = create_vendor_request(listing_id, "edit", vendor["email"], vendor.get("whatsapp", ""), body)
            return self.send_json(200, {
                "success": True,
                "request_id": req_id,
                "message": "Your edits have been submitted for Lagos Updates verification. They will go live upon approval."
            })

        if path.startswith("/api/vendor/listings/") and path.endswith("/request-delete"):
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {"error": "Unauthorized"})
            parts = path.split("/")
            listing_id = parts[4]
            body = self.parse_json_body() or {}
            req_id = create_vendor_request(listing_id, "delete", vendor["email"], vendor.get("whatsapp", ""), body)
            return self.send_json(200, {
                "success": True,
                "request_id": req_id,
                "message": "Deletion request received. Lagos Updates admin will verify and complete removal."
            })

        if path.startswith("/api/vendor/listings/") and path.endswith("/renew"):
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {"error": "Unauthorized"})
            parts = path.split("/")
            listing_id = parts[4]
            body = self.parse_json_body() or {}
            req_id = create_vendor_request(listing_id, "renew", vendor["email"], vendor.get("whatsapp", ""), body)
            return self.send_json(200, {
                "success": True,
                "request_id": req_id,
                "message": "Standard listing renewal (₦30,000/month) requested. Lagos Updates team will verify and renew your status."
            })

        if path.startswith("/api/vendor/listings/") and path.endswith("/boost"):
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {"error": "Unauthorized"})
            parts = path.split("/")
            listing_id = parts[4]
            body = self.parse_json_body() or {}
            duration = body.get("duration", "1_month")
            duration_map = {
                "1_week": {"days": 7, "price": "₦35,000", "label": "1-Week Boost"},
                "2_weeks": {"days": 14, "price": "₦60,000", "label": "2-Week Boost"},
                "1_month": {"days": 30, "price": "₦100,000", "label": "1-Month Featured"}
            }
            meta = duration_map.get(duration, duration_map["1_month"])
            payload = {
                "duration": duration,
                "days": meta["days"],
                "price": meta["price"],
                "label": meta["label"]
            }
            req_id = create_vendor_request(listing_id, "boost", vendor["email"], vendor.get("whatsapp", ""), payload)
            return self.send_json(200, {
                "success": True,
                "request_id": req_id,
                "message": f"Boost request ({meta['label']} at {meta['price']}) submitted! Lagos Updates editors will verify and pin your listing."
            })

        # Admin Actions
        if path.startswith("/api/admin/"):
            if not self.is_admin_authorized():
                return self.send_json(401, {"error": "Unauthorized: Invalid or missing editorial passkey."})

        if path.startswith("/api/admin/requests/") and path.endswith("/approve"):
            parts = path.split("/")
            req_id = parts[4]
            ok, err = resolve_vendor_request(req_id, "approve")
            if not ok:
                return self.send_json(404, {"error": err})
            return self.send_json(200, {"success": True, "message": "Request approved and applied."})

        if path.startswith("/api/admin/requests/") and path.endswith("/reject"):
            parts = path.split("/")
            req_id = parts[4]
            ok, err = resolve_vendor_request(req_id, "reject")
            if not ok:
                return self.send_json(404, {"error": err})
            return self.send_json(200, {"success": True, "message": "Request rejected."})

        if path.startswith("/api/admin/listings/") and path.endswith("/boost"):
            parts = path.split("/")
            listing_id = parts[4]
            params = urllib.parse.parse_qs(parsed.query)
            days = int(params.get("days", [30])[0])
            new_boost = apply_listing_boost(listing_id, days)
            return self.send_json(200, {
                "success": True,
                "featured_until": new_boost,
                "message": f"Listing boosted as Featured for {days} days!"
            })
        if path.startswith("/api/listings/") and path.endswith("/notify-reviews"):
            parts = path.split("/")
            listing_id = parts[3]
            body = self.parse_json_body() or {}
            phone = body.get("phone", "").strip()
            if not phone:
                return self.send_json(400, {"error": "Phone number required."})
            sub_id = save_review_subscriber(listing_id, phone)
            return self.send_json(200, {"success": True, "message": "Notification saved! We will notify you via WhatsApp."})

        if path.startswith("/api/admin/submissions/") and path.endswith("/approve"):
            parts = path.split("/")
            # format: /api/admin/submissions/<sub_id>/approve
            sub_id = parts[4]
            # check if make_featured requested in query param or body
            params = urllib.parse.parse_qs(parsed.query)
            featured = params.get("featured", ["0"])[0] in ["1", "true"]

            result = approve_submission(sub_id, make_featured=featured)
            if not result:
                return self.send_json(404, {"error": "Submission not found"})
            return self.send_json(200, {
                "success": True,
                "message": "Business approved and published live to Lagos Updates Directory!",
                "listing_id": result["listing_id"],
                "promoted": result["promoted"]
            })

        if path.startswith("/api/admin/submissions/") and path.endswith("/reject"):
            parts = path.split("/")
            sub_id = parts[4]
            reject_submission(sub_id)
            return self.send_json(200, {"success": True, "message": "Submission rejected."})

        # Admin Listing Controls: Pause / Hide, Feature, Delete
        if path.startswith("/api/admin/listings/") and path.endswith("/toggle-active"):
            parts = path.split("/")
            listing_id = parts[4]
            new_state = toggle_listing_active(listing_id)
            if new_state is None:
                return self.send_json(404, {"error": "Listing not found"})
            return self.send_json(200, {
                "success": True,
                "is_active": bool(new_state),
                "message": "Listing published live" if new_state else "Listing paused / hidden from public directory"
            })

        if path.startswith("/api/admin/listings/") and path.endswith("/toggle-promoted"):
            parts = path.split("/")
            listing_id = parts[4]
            new_state = toggle_listing_promoted(listing_id)
            if new_state is None:
                return self.send_json(404, {"error": "Listing not found"})
            return self.send_json(200, {
                "success": True,
                "promoted": bool(new_state),
                "message": "Listing set as Featured" if new_state else "Listing unfeatured"
            })

        if path.startswith("/api/admin/listings/") and path.endswith("/delete"):
            parts = path.split("/")
            listing_id = parts[4]
            deleted = delete_listing(listing_id)
            if not deleted:
                return self.send_json(404, {"error": "Listing not found"})
            return self.send_json(200, {
                "success": True,
                "message": "Listing permanently deleted"
            })

        if path == "/api/submissions":
            # 1. Rate limiting by IP
            client_ip = self.client_address[0]
            if not limiter.is_allowed(client_ip):
                return self.send_json(429, {
                    "error": "Too many submissions. Please wait an hour before submitting another business."
                })

            # 2. Parse JSON body (allows up to 20MB for base64 photo payloads)
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0 or content_length > 20 * 1024 * 1024:
                return self.send_json(400, {"error": "Invalid payload size (max 20MB)."})

            raw_body = self.rfile.read(content_length)
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                return self.send_json(400, {"error": "Malformed JSON payload."})

            # 3. Validate and cleanse data
            is_valid, cleaned, error_msg = validate_submission_payload(data)
            if not is_valid:
                return self.send_json(422, {"error": error_msg})

            # 4. Idempotency check: prevent duplicate submissions within 5 minutes
            recent = get_recent_submission(cleaned["contact_email"], cleaned["business_name"], minutes=5)
            if recent:
                return self.send_json(200, {
                    "success": True,
                    "submission_id": recent["id"],
                    "message": "We already received your submission! Our team is reviewing it.",
                    "already_submitted": True
                })

            # 5. Process & save base64 uploaded photos to disk
            temp_id = str(uuid.uuid4())
            saved_photos = process_uploaded_photos(cleaned.get("photos_raw", []), temp_id)

            # 6. Save to SQLite database
            try:
                submission_id = insert_submission(cleaned, saved_photos)
            except Exception as e:
                print("[DB Error] Could not save submission:", e)
                return self.send_json(500, {"error": "Failed to save submission. Please try again."})

            # 7. Dispatch Email Notification (fail-safe)
            email_sent = dispatch_submission_email(submission_id, cleaned, saved_photos)
            if email_sent:
                mark_submission_email_sent(submission_id)

            return self.send_json(201, {
                "success": True,
                "submission_id": submission_id,
                "photos_count": len(saved_photos),
                "message": "Application submitted successfully! The Lagos Updates team will review and verify your business within 24 hours.",
                "business_name": cleaned["business_name"]
            })

        return self.send_json(404, {"error": "Endpoint not found."})

def run_server(port=PORT):
    init_db()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), DirectoryAppHandler) as httpd:
        print(f"Lagos Updates Directory production server running on http://localhost:{port}")
        httpd.serve_forever()
