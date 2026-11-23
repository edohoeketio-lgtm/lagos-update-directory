import json
import os

base_dir = r"C:\Users\sk\Documents\lagos-update-directory"
listings_path = os.path.join(base_dir, "data", "listings.json")
out_path = os.path.join(base_dir, "data", "supabase_schema.sql")

with open(listings_path, "r", encoding="utf-8") as f:
    listings = json.load(f)

sql = []
sql.append("""-- Supabase PostgreSQL Schema for Lagos Updates Directory
-- Paste and Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS public.listings (
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
    rc_number TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    owner_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    plan_tier TEXT DEFAULT 'verified',
    subscription_status TEXT DEFAULT 'active',
    featured_until TEXT DEFAULT '',
    image TEXT DEFAULT '',
    photos TEXT DEFAULT '[]',
    views_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.submissions (
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
    payment_status TEXT DEFAULT 'unpaid',
    contact_name TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    notes TEXT,
    email_sent INTEGER DEFAULT 0,
    rc_number TEXT DEFAULT '',
    vendor_id TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.listing_requests (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL,
    request_type TEXT NOT NULL,
    vendor_email TEXT NOT NULL,
    vendor_whatsapp TEXT,
    payload TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    admin_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.users (
    id TEXT PRIMARY KEY,
    firebase_uid TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT,
    photo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.vendor_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL,
    cac_number TEXT NOT NULL,
    whatsapp TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.vendors (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    business_name TEXT,
    whatsapp TEXT,
    rc_number TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.sessions (
    token TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.review_subscribers (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL,
    phone TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.reviews (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    listing_id TEXT NOT NULL REFERENCES public.listings(id) ON DELETE CASCADE,
    star_rating INTEGER NOT NULL,
    comment TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    admin_notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.payments (
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE public.listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vendor_profiles ENABLE ROW LEVEL SECURITY;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'listings' AND policyname = 'Allow public read on listings') THEN
        CREATE POLICY "Allow public read on listings" ON public.listings FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'Allow public read on approved reviews') THEN
        CREATE POLICY "Allow public read on approved reviews" ON public.reviews FOR SELECT USING (status = 'approved');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'listings' AND policyname = 'Service role full access on listings') THEN
        CREATE POLICY "Service role full access on listings" ON public.listings USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'Service role full access on reviews') THEN
        CREATE POLICY "Service role full access on reviews" ON public.reviews USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'submissions' AND policyname = 'Service role full access on submissions') THEN
        CREATE POLICY "Service role full access on submissions" ON public.submissions USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'users' AND policyname = 'Service role full access on users') THEN
        CREATE POLICY "Service role full access on users" ON public.users USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'vendor_profiles' AND policyname = 'Service role full access on vendor_profiles') THEN
        CREATE POLICY "Service role full access on vendor_profiles" ON public.vendor_profiles USING (true) WITH CHECK (true);
    END IF;
END $$;

-- Seed Initial Listings
""")

for item in listings:
    lid = str(item.get("id", ""))
    name = item.get("name", "").replace("'", "''")
    cat = item.get("category", "").replace("'", "''")
    area = item.get("area", "").replace("'", "''")
    desc = item.get("description", "").replace("'", "''")
    phone = item.get("phone", "").replace("'", "''")
    wa = item.get("whatsapp", "").replace("'", "''")
    ig = item.get("instagram", "").replace("'", "''")
    ver = 1 if item.get("verified") else 0
    prom = 1 if item.get("promoted") else 0
    rating = str(item.get("rating", "4.9")).replace("'", "''")
    price = item.get("priceRange", "").replace("'", "''")
    img = item.get("image", "").replace("'", "''")
    photos = json.dumps(item.get("photos", [])).replace("'", "''")
    views = int(item.get("views_count", 180))

    sql.append(f"""INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('{lid}', '{name}', '{cat}', '{area}', '{desc}', '{phone}', '{wa}', '{ig}', {ver}, {prom}, '{rating}', '{price}', '{img}', '{photos}', {views})
ON CONFLICT (id) DO NOTHING;""")

with open(out_path, "w", encoding="utf-8") as out:
    out.write("\n".join(sql))

print(f"Generated {out_path} successfully. Total lines: {len(sql)}")
