"""
SQLite Data Access Layer for Lagos Updates Directory.
Clean Architecture with parameterized queries, auto-migration, and image support.
"""
import sqlite3
import json
import os
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from .config import DB_PATH, DATA_JSON_PATH

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=25.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=25000;")
    except Exception:
        pass
    return conn

def init_db():
    """Initializes tables, migrates schemas, and seeds initial data from listings.json if empty."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        area TEXT NOT NULL,
        description TEXT NOT NULL,
        price_range TEXT,
        rating TEXT DEFAULT '4.9',
        verified INTEGER DEFAULT 0,
        promoted INTEGER DEFAULT 0,
        phone TEXT,
        whatsapp TEXT,
        instagram TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id TEXT PRIMARY KEY,
        business_name TEXT NOT NULL,
        category TEXT NOT NULL,
        area TEXT NOT NULL,
        description TEXT NOT NULL,
        price_range TEXT,
        whatsapp TEXT NOT NULL,
        instagram TEXT,
        drive_link TEXT DEFAULT '',
        photos TEXT DEFAULT '[]',
        plan_tier TEXT DEFAULT 'verified',
        contact_name TEXT NOT NULL,
        contact_email TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        email_sent INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listing_requests (
        id TEXT PRIMARY KEY,
        listing_id TEXT NOT NULL,
        request_type TEXT NOT NULL,
        vendor_email TEXT NOT NULL,
        vendor_whatsapp TEXT,
        payload TEXT DEFAULT '{}',
        status TEXT DEFAULT 'pending',
        admin_notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        resolved_at TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendors (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        business_name TEXT,
        whatsapp TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        vendor_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_subscribers (
        id TEXT PRIMARY KEY,
        listing_id TEXT NOT NULL,
        phone TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        tx_ref TEXT UNIQUE NOT NULL,
        flw_ref TEXT,
        transaction_id TEXT,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'NGN',
        status TEXT DEFAULT 'successful',
        payment_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_name TEXT,
        customer_phone TEXT,
        metadata TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        verified_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Safe column migrations if table already existed without photos / drive_link / is_active / owner_email / expires_at
    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN is_active INTEGER DEFAULT 1;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN owner_email TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN expires_at TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN plan_tier TEXT DEFAULT 'verified';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN subscription_status TEXT DEFAULT 'active';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN featured_until TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN image TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE submissions ADD COLUMN photos TEXT DEFAULT '[]';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE submissions ADD COLUMN drive_link TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE submissions ADD COLUMN payment_status TEXT DEFAULT 'unpaid';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE submissions ADD COLUMN payment_tx_ref TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE submissions ADD COLUMN payment_amount REAL DEFAULT 0.0;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listing_requests ADD COLUMN payment_status TEXT DEFAULT 'unpaid';")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE listing_requests ADD COLUMN payment_tx_ref TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

    # Check if listings table is empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM listings;")
    count = cursor.fetchone()['cnt']

    if count == 0 and os.path.exists(DATA_JSON_PATH):
        try:
            with open(DATA_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    cursor.execute("""
                    INSERT OR IGNORE INTO listings (
                        id, name, category, area, description,
                        price_range, rating, verified, promoted,
                        phone, whatsapp, instagram, image
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item.get('id'),
                        item.get('name'),
                        item.get('category'),
                        item.get('area'),
                        item.get('description'),
                        item.get('priceRange'),
                        item.get('rating', '4.9'),
                        1 if item.get('verified') else 0,
                        1 if item.get('promoted') else 0,
                        item.get('phone', ''),
                        item.get('whatsapp', ''),
                        item.get('instagram', ''),
                        item.get('image', '')
                    ))
            conn.commit()
            print(f"Auto-seeded {len(data)} listings from listings.json into SQLite.")
        except Exception as e:
            print("Notice: could not auto-seed listings.json:", e)

    conn.commit()
    conn.close()

def query_listings(category=None, area=None, query=None, verified_only=False, featured_only=False):
    """Fetch listings with flexible filtering and promoted sorting. Only returns active (unpaused) listings."""
    conn = get_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM listings WHERE (is_active = 1 OR is_active IS NULL)"
    params = []

    if category and category != 'all':
        sql += " AND category = ?"
        params.append(category)

    if area and area != 'all':
        sql += " AND LOWER(area) LIKE ?"
        params.append(f"%{area.lower()}%")

    if verified_only:
        sql += " AND verified = 1"

    if featured_only:
        sql += " AND promoted = 1"

    if query:
        q = f"%{query.lower()}%"
        sql += " AND (LOWER(name) LIKE ? OR LOWER(area) LIKE ? OR LOWER(description) LIKE ?)"
        params.extend([q, q, q])

    sql += " ORDER BY promoted DESC, name ASC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "area": r["area"],
            "description": r["description"],
            "priceRange": r["price_range"],
            "rating": r["rating"],
            "verified": bool(r["verified"]),
            "promoted": bool(r["promoted"]),
            "phone": r["phone"],
            "whatsapp": r["whatsapp"],
            "instagram": r["instagram"],
            "image": r["image"] if "image" in r.keys() else ""
        })
    return result

def get_listing_by_id(listing_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "area": row["area"],
        "description": row["description"],
        "priceRange": row["price_range"],
        "rating": row["rating"],
        "verified": bool(row["verified"]),
        "promoted": bool(row["promoted"]),
        "featured": bool(row["promoted"]),
        "featuredUntil": row["featured_until"] if "featured_until" in row.keys() else "",
        "phone": row["phone"],
        "whatsapp": row["whatsapp"],
        "instagram": row["instagram"],
        "image": row["image"] if "image" in row.keys() else ""
    }

def insert_submission(cleaned_data: dict, saved_photos: list = None) -> str:
    """Inserts a new business application into SQLite with photos & drive link."""
    conn = get_connection()
    cursor = conn.cursor()
    submission_id = str(uuid.uuid4())
    photos_json = json.dumps(saved_photos or [])

    cursor.execute("""
    INSERT INTO submissions (
        id, business_name, category, area, description,
        price_range, whatsapp, instagram, drive_link, photos,
        plan_tier, contact_name, contact_email, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
    """, (
        submission_id,
        cleaned_data["business_name"],
        cleaned_data["category"],
        cleaned_data["area"],
        cleaned_data["description"],
        cleaned_data["price_range"],
        cleaned_data["whatsapp"],
        cleaned_data["instagram"],
        cleaned_data.get("drive_link", ""),
        photos_json,
        cleaned_data["plan_tier"],
        cleaned_data["contact_name"],
        cleaned_data["contact_email"]
    ))

    conn.commit()
    conn.close()
    return submission_id

def mark_submission_email_sent(submission_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE submissions SET email_sent = 1 WHERE id = ?", (submission_id,))
    conn.commit()
    conn.close()

def slugify(text: str) -> str:
    import re
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    return s.strip('-')

def approve_submission(submission_id: str, make_featured: bool = False):
    """Approves a submission, creates an active listing in SQLite, and marks approved."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,))
    sub = cursor.fetchone()
    if not sub:
        conn.close()
        return None

    base_slug = slugify(sub["business_name"]) or "listing"
    listing_id = base_slug
    idx = 1
    while True:
        cursor.execute("SELECT id FROM listings WHERE id = ?", (listing_id,))
        if not cursor.fetchone():
            break
        idx += 1
        listing_id = f"{base_slug}-{idx}"

    is_promoted = 1 if (make_featured or sub["plan_tier"] in ["featured", "featured_1w"]) else 0
    days = 30
    if sub["plan_tier"] == "featured_1w":
        days = 7
    featured_until = (datetime.now() + timedelta(days=days)).isoformat() if is_promoted else ""
    expires_at = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    owner_email = (sub["contact_email"] or "").lower().strip()

    cursor.execute("""
    INSERT INTO listings (
        id, name, category, area, description,
        price_range, rating, verified, promoted,
        phone, whatsapp, instagram, owner_email,
        plan_tier, expires_at, featured_until, is_active
    ) VALUES (?, ?, ?, ?, ?, ?, '4.9', 1, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        listing_id,
        sub["business_name"],
        sub["category"],
        sub["area"],
        sub["description"],
        sub["price_range"],
        is_promoted,
        sub["whatsapp"],
        sub["whatsapp"],
        sub["instagram"],
        owner_email,
        sub["plan_tier"],
        expires_at,
        featured_until
    ))

    cursor.execute("UPDATE submissions SET status = 'approved' WHERE id = ?", (submission_id,))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "listing_id": listing_id,
        "promoted": bool(is_promoted)
    }

def reject_submission(submission_id: str):
    """Marks a submission as rejected."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE submissions SET status = 'rejected' WHERE id = ?", (submission_id,))
    conn.commit()
    conn.close()
    return True

def get_all_admin_listings():
    """Returns all listings for editorial administration, including paused/hidden ones."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings ORDER BY promoted DESC, name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "area": r["area"],
        "priceRange": r["price_range"],
        "verified": bool(r["verified"]),
        "promoted": bool(r["promoted"]),
        "featured_until": r["featured_until"] if ("featured_until" in r.keys() and r["featured_until"]) else "",
        "is_active": bool(r["is_active"]) if ("is_active" in r.keys() and r["is_active"] is not None) else True,
        "phone": r["phone"],
        "whatsapp": r["whatsapp"],
        "instagram": r["instagram"]
    } for r in rows]

def toggle_listing_active(listing_id: str):
    """Pauses/hides or unhides a listing from the public directory."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM listings WHERE id = ?", (listing_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    current = row["is_active"] if row["is_active"] is not None else 1
    new_state = 0 if current == 1 else 1
    cursor.execute("UPDATE listings SET is_active = ? WHERE id = ?", (new_state, listing_id))
    conn.commit()
    conn.close()
    return new_state

def toggle_listing_promoted(listing_id: str):
    """Features or unfeatures a listing."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT promoted FROM listings WHERE id = ?", (listing_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    new_state = 0 if row["promoted"] == 1 else 1
    cursor.execute("UPDATE listings SET promoted = ? WHERE id = ?", (new_state, listing_id))
    conn.commit()
    conn.close()
    return new_state

def delete_listing(listing_id: str):
    """Permanently deletes a listing from the directory."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_recent_submission(email: str, business_name: str, minutes: int = 5):
    """Finds if this email submitted this business name recently (idempotency check)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM submissions 
    WHERE contact_email = ? AND LOWER(business_name) = LOWER(?)
    ORDER BY created_at DESC LIMIT 1
    """, (email, business_name))
    row = cursor.fetchone()
    conn.close()
    return row

# ==========================================
# VENDOR AUTH & DASHBOARD DATA ACCESS
# ==========================================

def hash_password(password: str, salt: str = None):
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return hashed, salt

def register_vendor(email: str, password: str, business_name: str, whatsapp: str = ''):
    """Registers a vendor with a hashed password/passcode."""
    conn = get_connection()
    cursor = conn.cursor()
    vendor_id = str(uuid.uuid4())
    pw_hash, salt = hash_password(password)

    try:
        cursor.execute("""
        INSERT INTO vendors (id, email, password_hash, salt, business_name, whatsapp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (vendor_id, email.lower().strip(), pw_hash, salt, business_name.strip(), whatsapp.strip()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return None, "Email is already registered. Please log in."

    # Associate any existing listings with same business email or name
    cursor.execute("""
    UPDATE listings SET owner_email = ? 
    WHERE LOWER(owner_email) = ? OR LOWER(name) = ?
    """, (email.lower().strip(), email.lower().strip(), business_name.lower().strip()))
    conn.commit()

    conn.close()
    return vendor_id, None

def authenticate_vendor(email: str, password: str):
    """Verifies email and password/passcode, generates 30-day session token."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vendors WHERE LOWER(email) = ?", (email.lower().strip(),))
    vendor = cursor.fetchone()

    if not vendor:
        conn.close()
        return None, "No account found with this email."

    calc_hash, _ = hash_password(password, vendor["salt"])
    if calc_hash != vendor["password_hash"]:
        conn.close()
        return None, "Incorrect password or passcode."

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()

    cursor.execute("""
    INSERT INTO sessions (token, vendor_id, expires_at)
    VALUES (?, ?, ?)
    """, (token, vendor["id"], expires_at))
    conn.commit()
    conn.close()

    return {
        "token": token,
        "vendor": {
            "id": vendor["id"],
            "email": vendor["email"],
            "business_name": vendor["business_name"],
            "whatsapp": vendor["whatsapp"]
        }
    }, None

def get_vendor_by_session(token: str):
    """Retrieves authenticated vendor by valid session token."""
    if not token:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT v.*, s.expires_at FROM sessions s
    JOIN vendors v ON s.vendor_id = v.id
    WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    try:
        exp = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > exp:
            return None
    except Exception:
        pass

    return {
        "id": row["id"],
        "email": row["email"],
        "business_name": row["business_name"],
        "whatsapp": row["whatsapp"]
    }

def get_vendor_listings(email: str, business_name: str = ""):
    """Gets listings owned by vendor, plus any pending requests on them."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Query matching owner_email or name
    cursor.execute("""
    SELECT * FROM listings 
    WHERE LOWER(owner_email) = ? OR LOWER(name) = ?
    ORDER BY created_at DESC
    """, (email.lower().strip(), business_name.lower().strip()))
    rows = cursor.fetchall()

    result = []
    for r in rows:
        lid = r["id"]
        # Fetch pending requests for this listing
        cursor.execute("""
        SELECT * FROM listing_requests 
        WHERE listing_id = ? AND status = 'pending'
        ORDER BY created_at DESC
        """, (lid,))
        reqs = cursor.fetchall()

        pending_req = None
        if reqs:
            p = reqs[0]
            pending_req = {
                "id": p["id"],
                "type": p["request_type"],
                "payload": json.loads(p["payload"]) if p["payload"] else {},
                "created_at": p["created_at"]
            }

        featured_until_val = r["featured_until"] if "featured_until" in r.keys() and r["featured_until"] else ""
        days_left = 0
        if featured_until_val:
            try:
                exp_dt = datetime.fromisoformat(featured_until_val)
                days_left = max(0, (exp_dt - datetime.now()).days)
            except Exception:
                pass

        result.append({
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "area": r["area"],
            "description": r["description"],
            "price_range": r["price_range"],
            "rating": r["rating"],
            "verified": bool(r["verified"]),
            "promoted": bool(r["promoted"]),
            "featured_until": featured_until_val,
            "boost_days_left": days_left,
            "is_active": bool(r["is_active"]) if r["is_active"] is not None else True,
            "phone": r["phone"],
            "whatsapp": r["whatsapp"],
            "instagram": r["instagram"],
            "expires_at": r["expires_at"] or (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
            "plan_tier": r["plan_tier"] or "verified",
            "subscription_status": r["subscription_status"] or "active",
            "pending_request": pending_req
        })

    conn.close()
    return result

def get_vendor_submissions(email: str):
    """Retrieves business applications submitted by this vendor email."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, business_name, category, area, description, price_range,
           whatsapp, plan_tier, status, payment_status, payment_amount, created_at
    FROM submissions 
    WHERE LOWER(contact_email) = ?
    ORDER BY created_at DESC
    """, (email.lower().strip(),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_vendor_request(listing_id: str, request_type: str, vendor_email: str, vendor_whatsapp: str, payload: dict):
    """Creates a vendor edit, delete, or renewal request awaiting admin verification."""
    conn = get_connection()
    cursor = conn.cursor()
    req_id = f"req-{uuid.uuid4().hex[:8]}"

    cursor.execute("""
    INSERT INTO listing_requests (id, listing_id, request_type, vendor_email, vendor_whatsapp, payload, status)
    VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (req_id, listing_id, request_type, vendor_email, vendor_whatsapp, json.dumps(payload)))
    
    conn.commit()
    conn.close()
    return req_id

def get_admin_vendor_requests():
    """Fetches all pending vendor edit, delete, and renewal requests for Lagos Updates Admin."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT lr.*, l.name AS listing_name, l.area, l.category
    FROM listing_requests lr
    LEFT JOIN listings l ON lr.listing_id = l.id
    WHERE lr.status = 'pending'
    ORDER BY lr.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [{
        "id": r["id"],
        "listing_id": r["listing_id"],
        "listing_name": r["listing_name"] or "Unknown Listing",
        "area": r["area"] or "",
        "category": r["category"] or "",
        "request_type": r["request_type"],
        "vendor_email": r["vendor_email"],
        "vendor_whatsapp": r["vendor_whatsapp"],
        "payload": json.loads(r["payload"]) if r["payload"] else {},
        "created_at": r["created_at"],
        "status": r["status"]
    } for r in rows]

def resolve_vendor_request(req_id: str, action: str):
    """Admin approves or rejects vendor edit/delete/renew request."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listing_requests WHERE id = ?", (req_id,))
    req = cursor.fetchone()
    if not req:
        conn.close()
        return False, "Request not found"

    listing_id = req["listing_id"]
    req_type = req["request_type"]
    payload = json.loads(req["payload"]) if req["payload"] else {}

    now_iso = datetime.now().isoformat()

    if action == "approve":
        if req_type == "delete":
            cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        elif req_type == "edit":
            cursor.execute("""
            UPDATE listings SET
                name = COALESCE(?, name),
                category = COALESCE(?, category),
                area = COALESCE(?, area),
                description = COALESCE(?, description),
                price_range = COALESCE(?, price_range),
                phone = COALESCE(?, phone),
                whatsapp = COALESCE(?, whatsapp),
                instagram = COALESCE(?, instagram),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (
                payload.get("name"),
                payload.get("category"),
                payload.get("area"),
                payload.get("description"),
                payload.get("price_range"),
                payload.get("phone"),
                payload.get("whatsapp"),
                payload.get("instagram"),
                listing_id
            ))
        elif req_type == "renew":
            # Renew standard ₦30k/mo subscription (30 days)
            new_exp = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute("""
            UPDATE listings SET
                expires_at = ?,
                subscription_status = 'active',
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (new_exp, listing_id))
        elif req_type == "boost":
            # Apply paid featured boost (7, 14, or 30 days)
            days = int(payload.get("days", 30))
            new_boost_until = (datetime.now() + timedelta(days=days)).isoformat()
            cursor.execute("""
            UPDATE listings SET
                promoted = 1,
                featured_until = ?,
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (new_boost_until, listing_id))

        cursor.execute("UPDATE listing_requests SET status = 'approved', resolved_at = ? WHERE id = ?", (now_iso, req_id))
    else:
        cursor.execute("UPDATE listing_requests SET status = 'rejected', resolved_at = ? WHERE id = ?", (now_iso, req_id))

    conn.commit()
    conn.close()
    return True, None

def apply_listing_boost(listing_id: str, days: int):
    """Directly sets or extends a featured boost for a listing (7, 14, or 30 days)."""
    conn = get_connection()
    cursor = conn.cursor()
    new_boost_until = (datetime.now() + timedelta(days=days)).isoformat()
    cursor.execute("""
    UPDATE listings SET
        promoted = 1,
        featured_until = ?,
        is_active = 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (new_boost_until, listing_id))
    conn.commit()
    conn.close()
    return new_boost_until

def save_review_subscriber(listing_id: str, phone: str):
    """Saves user phone notification request for when verified reviews launch."""
    conn = get_connection()
    cursor = conn.cursor()
    sub_id = str(uuid.uuid4())
    cursor.execute("""
    INSERT INTO review_subscribers (id, listing_id, phone)
    VALUES (?, ?, ?)
    """, (sub_id, listing_id, phone.strip()))
    conn.commit()
    conn.close()
    return sub_id

# ==========================================
# FLUTTERWAVE PAYMENT DATA ACCESS FUNCTIONS
# ==========================================

def record_payment(payment: dict) -> str:
    """Inserts a verified payment record into SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    pay_id = str(uuid.uuid4())
    tx_ref = payment.get("tx_ref", f"tx_{pay_id[:8]}")
    flw_ref = payment.get("flw_ref", "")
    transaction_id = str(payment.get("transaction_id", ""))
    amount = float(payment.get("amount", 0.0))
    currency = payment.get("currency", "NGN")
    status = payment.get("status", "successful")
    payment_type = payment.get("payment_type", "submission")
    target_id = str(payment.get("target_id", ""))
    customer_email = payment.get("customer_email", "")
    customer_name = payment.get("customer_name", "")
    customer_phone = payment.get("customer_phone", "")
    metadata_json = json.dumps(payment.get("metadata", {}))

    cursor.execute("""
    INSERT INTO payments (
        id, tx_ref, flw_ref, transaction_id, amount, currency, status,
        payment_type, target_id, customer_email, customer_name, customer_phone,
        metadata, created_at, verified_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        pay_id, tx_ref, flw_ref, transaction_id, amount, currency, status,
        payment_type, target_id, customer_email, customer_name, customer_phone,
        metadata_json
    ))

    # Side-effect updates according to payment type
    if payment_type == "submission" and target_id:
        cursor.execute("""
        UPDATE submissions SET
            payment_status = 'paid',
            payment_tx_ref = ?,
            payment_amount = ?
        WHERE id = ?
        """, (tx_ref, amount, target_id))

    elif payment_type == "boost" and target_id:
        # Determine days
        duration = payment.get("metadata", {}).get("duration", "1_month")
        days = 30
        if duration == "1_week":
            days = 7
        elif duration == "2_weeks":
            days = 14
        new_boost_until = (datetime.now() + timedelta(days=days)).isoformat()
        cursor.execute("""
        UPDATE listings SET
            promoted = 1,
            featured_until = ?,
            is_active = 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (new_boost_until, target_id))

    elif payment_type == "renewal" and target_id:
        new_exp = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        cursor.execute("""
        UPDATE listings SET
            expires_at = ?,
            subscription_status = 'active',
            is_active = 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (new_exp, target_id))

    conn.commit()
    conn.close()
    return pay_id

def get_payment_by_tx_ref(tx_ref: str):
    """Retrieves a payment record by unique tx_ref."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE tx_ref = ?", (tx_ref,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_payment_by_ref_or_id(tx_ref: str = None, transaction_id: str = None):
    """Checks payments table by tx_ref or transaction_id."""
    conn = get_connection()
    cursor = conn.cursor()
    if tx_ref:
        cursor.execute("SELECT * FROM payments WHERE tx_ref = ?", (tx_ref,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)
    if transaction_id:
        cursor.execute("SELECT * FROM payments WHERE transaction_id = ?", (str(transaction_id),))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)
    conn.close()
    return None

