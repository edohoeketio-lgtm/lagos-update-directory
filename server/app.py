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

from .config import (
    PORT, BASE_DIR, FLW_PUBLIC_KEY, FLW_SECRET_KEY, FLW_ENCRYPTION_KEY, ADMIN_PASSKEY, POSTHOG_API_KEY, POSTHOG_API_HOST,
    FIREBASE_PROJECT_ID, FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_APP_ID
)
from .db import (
    init_db, query_listings, get_listing_by_id, increment_listing_views,
    insert_submission, get_recent_submission, mark_submission_email_sent,
    get_connection, approve_submission, reject_submission,
    get_all_admin_listings, toggle_listing_active, toggle_listing_promoted, delete_listing,
    register_vendor, authenticate_vendor, get_vendor_by_session, get_vendor_listings, get_vendor_submissions,
    create_vendor_request, get_admin_vendor_requests, resolve_vendor_request, apply_listing_boost,
    save_review_subscriber, record_payment, get_payment_by_tx_ref, get_payment_by_ref_or_id,
    upsert_user, get_user_by_id, get_user_by_firebase_uid, get_user_by_session,
    get_vendor_profile_by_user_id, save_vendor_profile, create_user_session
)
from .flutterwave import verify_flutterwave_transaction
from .validators import validate_submission_payload, process_uploaded_photos, is_valid_rc_number
from .firebase_auth import verify_firebase_token
from .email_service import (
    dispatch_submission_email,
    send_account_creation_email,
    send_submission_rejection_email,
    send_submission_approved_email,
    send_vendor_offer_email
)
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
        """Extracts Bearer token, X-Vendor-Token header, or vendor_token query parameter."""
        auth = self.headers.get("Authorization", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth.replace("Bearer ", "").strip()
        elif self.headers.get("X-Vendor-Token"):
            token = self.headers.get("X-Vendor-Token", "").strip()
        else:
            parsed = self.get_request_path()
            params = urllib.parse.parse_qs(parsed.query)
            token = params.get("vendor_token", [""])[0].strip()
        if not token:
            return None
        vendor = get_vendor_by_session(token)
        if vendor:
            return vendor
        fb = verify_firebase_token(token)
        if fb:
            user = upsert_user(firebase_uid=fb["uid"], email=fb["email"], display_name=fb.get("name", ""), photo_url=fb.get("picture", ""))
            vp = get_vendor_profile_by_user_id(user["id"])
            if vp:
                return {
                    "id": user["id"],
                    "user_id": user["id"],
                    "email": user["email"],
                    "business_name": vp.get("business_name", ""),
                    "whatsapp": vp.get("whatsapp", ""),
                    "rc_number": vp.get("cac_number", ""),
                    "cac_number": vp.get("cac_number", "")
                }
        return None

    def get_authenticated_user(self):
        """Extracts Bearer token or X-Vendor-Token header and returns user or vendor."""
        auth = self.headers.get("Authorization", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth.replace("Bearer ", "").strip()
        elif self.headers.get("X-Vendor-Token"):
            token = self.headers.get("X-Vendor-Token", "").strip()
        else:
            parsed = self.get_request_path()
            params = urllib.parse.parse_qs(parsed.query)
            token = params.get("vendor_token", [""])[0].strip()
        if not token:
            return None

        user = get_user_by_session(token)
        if user:
            return user

        firebase_user = verify_firebase_token(token)
        if firebase_user:
            return upsert_user(
                firebase_uid=firebase_user["uid"],
                email=firebase_user["email"],
                display_name=firebase_user.get("name", ""),
                photo_url=firebase_user.get("picture", "")
            )

        vendor = get_vendor_by_session(token)
        if vendor:
            return vendor
        return None

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

        if path == "/api/auth/config":
            return self.send_json(200, {
                "success": True,
                "apiKey": FIREBASE_API_KEY,
                "authDomain": FIREBASE_AUTH_DOMAIN,
                "projectId": FIREBASE_PROJECT_ID,
                "appId": FIREBASE_APP_ID
            })

        if path == "/api/auth/me":
            user = self.get_authenticated_user()
            if not user:
                return self.send_json(401, {"error": "Not authenticated."})
            user_id = user.get("id") or user.get("user_id")
            vendor_profile = get_vendor_profile_by_user_id(user_id) if user_id else None
            return self.send_json(200, {
                "success": True,
                "user": {
                    "id": user_id,
                    "email": user.get("email"),
                    "display_name": user.get("display_name") or user.get("business_name", ""),
                    "photo_url": user.get("photo_url", ""),
                    "has_vendor_profile": bool(vendor_profile or user.get("business_name")),
                    "vendor_profile": vendor_profile or ({
                        "business_name": user.get("business_name", ""),
                        "cac_number": user.get("rc_number", ""),
                        "whatsapp": user.get("whatsapp", "")
                    } if user.get("business_name") else None)
                }
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

            cursor.execute("SELECT COUNT(*) AS pending FROM submissions WHERE status = 'pending' AND payment_status = 'paid';")
            total_pending = cursor.fetchone()["pending"]

            cursor.execute("SELECT COUNT(*) AS apps_today FROM submissions WHERE (date(created_at) = date('now', 'localtime') OR date(created_at) = ?) AND payment_status = 'paid';", (today_str,))
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
            cursor.execute("SELECT * FROM submissions WHERE payment_status = 'paid' ORDER BY created_at DESC LIMIT 50;")
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

            # If this is a paid business listing application, dispatch admin email notification now
            if payment_type == "submission" and target_id:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM submissions WHERE id = ?", (target_id,))
                    sub_row = cursor.fetchone()
                    conn.close()
                    if sub_row and not sub_row["email_sent"]:
                        photos_list = []
                        try:
                            photos_list = json.loads(sub_row["photos"] or "[]")
                        except Exception:
                            pass
                        if dispatch_submission_email(target_id, dict(sub_row), photos_list):
                            mark_submission_email_sent(target_id)
                except Exception as ex:
                    print("[Payment Notification Error]:", ex)

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

        # Unified User Authentication & Progressive Profiling
        if path == "/api/auth/verify":
            body = self.parse_json_body() or {}
            id_token = body.get("id_token")
            if not id_token:
                auth = self.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    id_token = auth.replace("Bearer ", "").strip()
            if not id_token:
                return self.send_json(400, {"error": "Missing id_token."})

            decoded = verify_firebase_token(id_token)
            if not decoded:
                return self.send_json(401, {"error": "Invalid or expired Firebase token."})

            email = decoded.get("email") or body.get("email", "")
            name = decoded.get("name") or body.get("display_name", "")
            picture = decoded.get("picture") or body.get("photo_url", "")
            user = upsert_user(
                firebase_uid=decoded["uid"],
                email=email,
                display_name=name,
                photo_url=picture
            )

            vendor_profile = get_vendor_profile_by_user_id(user["id"])
            session_token = create_user_session(user["id"])

            return self.send_json(200, {
                "success": True,
                "session_token": session_token,
                "user": {
                    "id": user["id"],
                    "firebase_uid": user["firebase_uid"],
                    "email": user["email"],
                    "display_name": user["display_name"],
                    "photo_url": user["photo_url"],
                    "has_vendor_profile": bool(vendor_profile),
                    "vendor_profile": vendor_profile
                }
            })

        if path == "/api/vendor/profile":
            user = self.get_authenticated_user()
            if not user:
                return self.send_json(401, {"error": "Authentication required to create a vendor profile."})
            body = self.parse_json_body()
            if not body:
                return self.send_json(400, {"error": "Missing vendor profile payload."})

            business_name = (body.get("business_name") or "").strip()
            cac_number = (body.get("cac_number") or body.get("rc_number") or "").strip()
            whatsapp = (body.get("whatsapp") or "").strip()

            if len(business_name) < 2:
                return self.send_json(422, {"error": "Business name is required (minimum 2 characters)."})
            if not is_valid_rc_number(cac_number):
                return self.send_json(422, {"error": "Valid CAC RC or BN number is required (e.g. RC 1849201 or BN 3829104)."})
            if not whatsapp:
                return self.send_json(422, {"error": "Valid WhatsApp contact number is required."})

            user_id = user.get("id") or user.get("user_id")
            profile = save_vendor_profile(
                user_id=user_id,
                business_name=business_name,
                cac_number=cac_number,
                whatsapp=whatsapp
            )

            return self.send_json(200, {
                "success": True,
                "vendor_profile": profile
            })

        # Vendor Auth Routes
        if path == "/api/vendor/register":
            body = self.parse_json_body()
            if not body or not body.get("email") or not body.get("password") or not body.get("business_name"):
                return self.send_json(400, {"error": "Business name, email, and password are required."})
            vendor_id, err = register_vendor(
                body["email"],
                body["password"],
                body["business_name"],
                body.get("whatsapp", ""),
                rc_number=body.get("rc_number", "")
            )
            if err:
                return self.send_json(400, {"error": err})
            auth_res, auth_err = authenticate_vendor(body["email"], body["password"])
            try:
                send_account_creation_email({
                    "business_name": body["business_name"],
                    "rc_number": body.get("rc_number", ""),
                    "email": body["email"]
                })
            except Exception as e:
                print("[Email Error - Account Creation]:", e)

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
        # Listing View Counter (Jiji-style impression tracking)
        if path.startswith("/api/listings/") and path.endswith("/view"):
            parts = path.split("/")
            # format: /api/listings/<listing_id>/view
            if len(parts) >= 4:
                listing_id = parts[3]
                new_views = increment_listing_views(listing_id)
                return self.send_json(200, {
                    "success": True,
                    "listing_id": listing_id,
                    "views_count": new_views
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

            # Dispatch live confirmation email to vendor
            try:
                send_submission_approved_email(
                    result.get("contact_email", ""),
                    result.get("business_name", ""),
                    result.get("listing_id", ""),
                    result.get("plan_tier", "verified")
                )
            except Exception as ex:
                print("[Email Error - Approved Notification]:", ex)

            return self.send_json(200, {
                "success": True,
                "message": "Business approved and published live to Lagos Updates Directory!",
                "listing_id": result["listing_id"],
                "promoted": result["promoted"]
            })

        if path.startswith("/api/admin/submissions/") and path.endswith("/reject"):
            parts = path.split("/")
            sub_id = parts[4]
            body = self.parse_json_body() or {}
            reason = body.get("reason", "Business does not meet Lagos Updates directory verification requirements or CAC registration could not be verified.")
            rej_info = reject_submission(sub_id, reason=reason)
            if rej_info and rej_info.get("contact_email"):
                try:
                    send_submission_rejection_email(
                        rej_info["contact_email"],
                        rej_info["business_name"],
                        rej_info.get("rc_number", ""),
                        rej_info.get("ref_id", sub_id[:8]),
                        reason
                    )
                except Exception as ex:
                    print("[Email Error - Rejection Notification]:", ex)

            return self.send_json(200, {"success": True, "message": "Submission rejected."})

        if path == "/api/admin/offers/send":
            body = self.parse_json_body() or {}
            to_email = body.get("to_email", "").strip()
            business_name = body.get("business_name", "").strip()
            offer_title = body.get("offer_title", "").strip()
            offer_details = body.get("offer_details", "").strip()
            promo_code = body.get("promo_code", "").strip()

            if not to_email or not offer_title or not offer_details:
                return self.send_json(400, {"error": "to_email, offer_title, and offer_details are required."})

            sent = send_vendor_offer_email(to_email, business_name, offer_title, offer_details, promo_code)
            return self.send_json(200, {
                "success": bool(sent),
                "message": f"Promotional offer email dispatched to {to_email}."
            })

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
            # 1. Require Authenticated Vendor Account
            vendor = self.get_authenticated_vendor()
            if not vendor:
                return self.send_json(401, {
                    "error": "Vendor account required. Please create an account or sign in to list your business."
                })

            # 2. Rate limiting by IP
            client_ip = self.client_address[0]
            if not limiter.is_allowed(client_ip):
                return self.send_json(429, {
                    "error": "Too many submissions. Please wait an hour before submitting another business."
                })

            # 3. Parse JSON body (allows up to 20MB for base64 photo payloads)
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0 or content_length > 20 * 1024 * 1024:
                return self.send_json(400, {"error": "Invalid payload size (max 20MB)."})

            raw_body = self.rfile.read(content_length)
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                return self.send_json(400, {"error": "Malformed JSON payload."})

            # 4. Validate and cleanse data (requires CAC RC/BN number)
            is_valid, cleaned, error_msg = validate_submission_payload(data)
            if not is_valid:
                return self.send_json(422, {"error": error_msg})

            # 5. Idempotency check: prevent duplicate submissions within 5 minutes
            recent = get_recent_submission(cleaned["contact_email"], cleaned["business_name"], minutes=5)
            if recent:
                return self.send_json(200, {
                    "success": True,
                    "submission_id": recent["id"],
                    "message": "We already received your submission! Please complete payment to send it to review.",
                    "already_submitted": True
                })

            # 6. Process & save base64 uploaded photos to disk
            temp_id = str(uuid.uuid4())
            saved_photos = process_uploaded_photos(cleaned.get("photos_raw", []), temp_id)

            # 7. Save to SQLite database (starts as 'unpaid'; only reaches admin dashboard when paid)
            try:
                submission_id = insert_submission(cleaned, saved_photos, vendor_id=vendor["id"])
            except Exception as e:
                print("[DB Error] Could not save submission:", e)
                return self.send_json(500, {"error": "Failed to save submission. Please try again."})

            return self.send_json(201, {
                "success": True,
                "submission_id": submission_id,
                "photos_count": len(saved_photos),
                "message": "Application draft created. Please complete payment to submit your business for verification.",
                "business_name": cleaned["business_name"],
                "rc_number": cleaned.get("rc_number", "")
            })

        return self.send_json(404, {"error": "Endpoint not found."})

def run_server(port=PORT):
    init_db()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), DirectoryAppHandler) as httpd:
        print(f"Lagos Updates Directory production server running on http://localhost:{port}")
        httpd.serve_forever()
