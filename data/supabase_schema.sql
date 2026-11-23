-- Supabase PostgreSQL Schema for Lagos Updates Directory
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

INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('1', 'The Wheatbaker Hotel', 'hotel', 'Ikoyi', 'Boutique luxury hotel offering world-class suites, a rooftop pool, and an award-winning restaurant in the heart of Ikoyi. Known for exceptional service and understated elegance.', '+234 802 000 1001', '+234 802 000 1001', '@thewheatbaker', 1, 1, 'Top Rated', '₦350,000 / night', '/img/listings/the-wheatbaker-hotel.jpg', '["/img/listings/the-wheatbaker-hotel.jpg", "/img/listings/eko-hotel-and-suites.jpg", "/img/listings/radisson-blu-hotel.jpg"]', 2229)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('2', 'Eko Hotel & Suites', 'hotel', 'Victoria Island', 'Lagos''s most iconic hotel. Five-star amenities, multiple restaurants, convention centre, and a legendary swimming pool complex on the VI waterfront.', '+234 802 000 1002', '+234 802 000 1002', '@ekohotel', 1, 1, 'Iconic', '₦280,000 / night', '/img/listings/eko-hotel-and-suites.jpg', '["/img/listings/eko-hotel-and-suites.jpg", "/img/listings/the-wheatbaker-hotel.jpg", "/img/listings/radisson-blu-hotel.jpg"]', 1148)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('3', 'Nok by Alara', 'restaurant', 'Victoria Island', 'Contemporary African fine dining in a stunning design space. The menu fuses traditional Nigerian flavours with modern technique. Book in advance — always full.', '+234 804 000 3001', '+234 804 000 3001', '@nokbyalara', 1, 1, 'Fine Dining', '₦45,000 - ₦75,000 avg', '/img/listings/nok-by-alara.jpg', '["/img/listings/nok-by-alara.jpg", "/img/listings/craft-grill.jpg", "/img/listings/yellow-chilli.jpg"]', 971)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('4', 'Chef Tunde Private Kitchen', 'private-chef', 'Lagos Island & Lekki', 'Award-winning private chef available for dinner parties, corporate events, and weekly meal prep. Specialises in elevated Nigerian cuisine and continental menus. Fully insured, references available.', '+234 808 000 7001', '+234 808 000 7001', '@cheftunde_ng', 1, 1, 'Award Winning', '₦150,000 / day', '/img/listings/chef-tunde-private-kitchen.jpg', '["/img/listings/chef-tunde-private-kitchen.jpg", "/img/listings/madam-kofo-private-chef.jpg", "/img/listings/the-lagos-table.jpg"]', 2438)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('5', 'Sky Bar Lagos', 'lounge', 'Victoria Island', 'Rooftop lounge with panoramic views of Victoria Island and the Atlantic Ocean. Live DJ every Friday and Saturday. Dress code enforced. Best sunset spot in Lagos.', '+234 805 000 4001', '+234 805 000 4001', '@skybarlagos', 1, 1, 'Top View', '₦30,000 - ₦60,000 avg', '/img/listings/sky-bar-lagos.jpg', '["/img/listings/sky-bar-lagos.jpg", "/img/listings/escape-lounge-and-bar.jpg", "/img/listings/hard-rock-cafe-lagos.jpg"]', 1483)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('6', 'Vanguard Protection Services', 'personal-security', 'Citywide', 'Licensed personal security detail for high-net-worth individuals, executives, and visiting dignitaries. Close protection officers, armoured vehicle escorts, and event security. Discreet and professional.', '+234 809 000 8001', '+234 809 000 8001', '@vanguardprotect_ng', 1, 1, 'Licensed', '₦120,000 / day', '/img/listings/vanguard-protection-services.jpg', '["/img/listings/vanguard-protection-services.jpg", "/img/listings/eagle-eye-security.jpg"]', 1421)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('7', 'Radisson Blu Hotel', 'hotel', 'Lagos Island', 'Contemporary business hotel with stunning harbour views, a rooftop bar, spa facilities, and modern conference rooms. Close to the financial district.', '+234 802 000 1003', '+234 802 000 1003', '@radissonblulagos', 1, 0, 'Business Pick', '₦180,000 / night', '/img/listings/radisson-blu-hotel.jpg', '["/img/listings/radisson-blu-hotel.jpg", "/img/listings/the-wheatbaker-hotel.jpg", "/img/listings/eko-hotel-and-suites.jpg"]', 408)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('8', 'Lagos Continental Hotel', 'hotel', 'Victoria Island', 'Premium 5-star hotel with 358 rooms, stunning ocean views, multiple dining options, and a full-service spa. A landmark on Victoria Island.', '+234 802 000 1004', '+234 802 000 1004', '@lagoscontinental', 1, 0, '5 Star', '₦250,000 / night', '/img/listings/lagos-continental-hotel.jpg', '["/img/listings/lagos-continental-hotel.jpg", "/img/listings/the-wheatbaker-hotel.jpg", "/img/listings/eko-hotel-and-suites.jpg"]', 322)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('9', 'Circa Lagos', 'hotel', 'Lekki Phase 1', 'Chic boutique hotel with 20 individually designed rooms, a lush courtyard garden, and a popular bar. The go-to spot for creatives visiting Lagos.', '+234 802 000 1005', '+234 802 000 1005', '@circalagos', 1, 0, 'Boutique Pick', '₦140,000 / night', '/img/listings/circa-lagos.jpg', '["/img/listings/circa-lagos.jpg", "/img/listings/the-wheatbaker-hotel.jpg", "/img/listings/eko-hotel-and-suites.jpg"]', 284)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('10', 'Eden Heights Apartments', 'apartment', 'Lekki Phase 1', 'Fully serviced 2 and 3 bedroom apartments with 24/7 power supply, high-speed wifi, gym, swimming pool and a concierge team. Short and long stay available.', '+234 803 000 2001', '+234 803 000 2001', '@edenheightslagos', 1, 0, 'Best Value', '₦120,000 / night', '/img/listings/eden-heights-apartments.jpg', '["/img/listings/eden-heights-apartments.jpg", "/img/listings/magnolia-suites.jpg", "/img/listings/harbour-point-residences.jpg"]', 872)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('11', 'Magnolia Suites', 'apartment', 'Ikeja GRA', 'Elegant serviced apartments near Murtala Muhammed Airport. Ideal for business travellers. Includes daily cleaning, breakfast, and airport transfers.', '+234 803 000 2002', '+234 803 000 2002', '@magnoliasuites_ng', 1, 0, 'Airport Close', '₦75,000 / night', '/img/listings/magnolia-suites.jpg', '["/img/listings/magnolia-suites.jpg", "/img/listings/eden-heights-apartments.jpg", "/img/listings/harbour-point-residences.jpg"]', 738)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('12', 'Harbour Point Residences', 'apartment', 'Victoria Island', 'Luxury waterfront serviced apartments with panoramic ocean views. 1-4 bedroom options available with premium finishes and hotel-grade amenities.', '+234 803 000 2003', '+234 803 000 2003', '@harbourpointvi', 0, 0, 'Waterfront', '₦320,000 / night', '/img/listings/harbour-point-residences.jpg', '["/img/listings/harbour-point-residences.jpg", "/img/listings/eden-heights-apartments.jpg", "/img/listings/magnolia-suites.jpg"]', 269)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('13', 'Nomad Lagos', 'apartment', 'Yaba', 'Modern co-living and short-stay apartments designed for the digital nomad. Fast fibre internet, co-working space, and a vibrant community of young professionals.', '+234 803 000 2004', '+234 803 000 2004', '@nomadlagos', 1, 0, 'Digital Nomad', '₦45,000 / night', '/img/listings/nomad-lagos.jpg', '["/img/listings/nomad-lagos.jpg", "/img/listings/eden-heights-apartments.jpg", "/img/listings/magnolia-suites.jpg"]', 784)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('14', 'Craft Grill', 'restaurant', 'Lekki Phase 1', 'Upscale grill restaurant known for its dry-aged Nigerian beef, wood-fired dishes, and excellent craft cocktail bar. The suya-style ribeye is unmatched in Lagos.', '+234 804 000 3002', '+234 804 000 3002', '@craftgrilllagos', 1, 0, 'Must Try', '₦25,000 - ₦45,000 avg', '/img/listings/craft-grill.jpg', '["/img/listings/craft-grill.jpg", "/img/listings/nok-by-alara.jpg", "/img/listings/yellow-chilli.jpg"]', 612)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('15', 'Yellow Chilli', 'restaurant', 'Victoria Island', 'Celebrity chef''s signature restaurant serving elevated Nigerian classics. The signature egusi soup and jollof rice have drawn visitors from around the world.', '+234 804 000 3003', '+234 804 000 3003', '@yellowchillilagos', 1, 0, 'Nigerian Classic', '₦20,000 - ₦35,000 avg', '/img/listings/yellow-chilli.jpg', '["/img/listings/yellow-chilli.jpg", "/img/listings/nok-by-alara.jpg", "/img/listings/craft-grill.jpg"]', 212)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('16', 'Escape Lounge & Bar', 'lounge', 'Lekki', 'Popular upscale lounge with an Afrobeats-heavy playlist, bottle service, and an extensive cocktail menu. The shisha terrace is the most booked spot on weekends.', '+234 805 000 4002', '+234 805 000 4002', '@escapelounge_ng', 1, 0, 'Weekend Favourite', '₦25,000 - ₦50,000 avg', '/img/listings/escape-lounge-and-bar.jpg', '["/img/listings/escape-lounge-and-bar.jpg", "/img/listings/sky-bar-lagos.jpg", "/img/listings/hard-rock-cafe-lagos.jpg"]', 210)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('17', 'Hard Rock Cafe Lagos', 'lounge', 'Victoria Island', 'The legendary global brand comes to Lagos. Rock memorabilia, burgers, cocktails, and live music performances. A reliable night out for locals and tourists alike.', '+234 805 000 4003', '+234 805 000 4003', '@hardrockcafelagos', 1, 0, 'Global Brand', '₦25,000 - ₦45,000 avg', '/img/listings/hard-rock-cafe-lagos.jpg', '["/img/listings/hard-rock-cafe-lagos.jpg", "/img/listings/sky-bar-lagos.jpg", "/img/listings/escape-lounge-and-bar.jpg"]', 275)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('18', 'Lagos Clean Ride', 'airport-pickup', 'Citywide', 'Premium airport pickup and drop-off service. Clean, air-conditioned vehicles. Flight tracking included so they''re always on time. Book 2 hours before arrival.', '+234 806 000 5001', '+234 806 000 5001', '@lagoscleanride', 1, 0, 'Most Reliable', '₦25,000 / trip', '/img/listings/lagos-clean-ride.jpg', '["/img/listings/lagos-clean-ride.jpg", "/img/listings/firstclass-transfers-ng.jpg", "/img/listings/airport-mover-lagos.jpg"]', 403)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('19', 'FirstClass Transfers NG', 'airport-pickup', 'Citywide', 'Executive airport transfers in Mercedes and Toyota Venza fleets. Professional chauffeurs, meet-and-greet at arrivals, and real-time WhatsApp updates throughout your journey.', '+234 806 000 5002', '+234 806 000 5002', '@firstclasstransfers_ng', 1, 0, 'Executive', '₦45,000 / trip', '/img/listings/firstclass-transfers-ng.jpg', '["/img/listings/firstclass-transfers-ng.jpg", "/img/listings/lagos-clean-ride.jpg", "/img/listings/airport-mover-lagos.jpg"]', 418)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('20', 'Airport Mover Lagos', 'airport-pickup', 'MMIA — Ikeja', 'Affordable and reliable airport transfers from Murtala Muhammed Airport to any part of Lagos. Shared and private options. 24/7 operations, no hidden charges.', '+234 806 000 5003', '+234 806 000 5003', '@airportmoverlagos', 0, 0, 'Budget Pick', '₦12,000 / trip', '/img/listings/airport-mover-lagos.jpg', '["/img/listings/airport-mover-lagos.jpg", "/img/listings/lagos-clean-ride.jpg", "/img/listings/firstclass-transfers-ng.jpg"]', 697)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('21', 'Lagos Plumbing Pros', 'service', 'Lagos Island', 'Licensed plumbers available 24/7 for emergency and scheduled work. Specialising in residential and commercial plumbing, pipe repairs, and bathroom installation.', '+234 807 000 6001', '+234 807 000 6001', '@lagosplumbingpros', 1, 0, '24/7', '₦20,000 callout', '/img/listings/lagos-plumbing-pros.jpg', '["/img/listings/lagos-plumbing-pros.jpg", "/img/listings/coolbreeze-ac-services.jpg", "/img/listings/glowup-studio.jpg"]', 796)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('22', 'CoolBreeze AC Services', 'service', 'Lekki & Ajah', 'Air conditioning installation, service, and repair. All major brands covered. Home and office visits. Quick response times and transparent pricing with no surprise charges.', '+234 807 000 6002', '+234 807 000 6002', '@coolbreezeac_ng', 1, 0, 'Transparent Pricing', '₦25,000 service', '/img/listings/coolbreeze-ac-services.jpg', '["/img/listings/coolbreeze-ac-services.jpg", "/img/listings/lagos-plumbing-pros.jpg", "/img/listings/glowup-studio.jpg"]', 207)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('23', 'GlowUp Studio', 'service', 'Yaba', 'Full-service beauty studio — hair, makeup, nails, and skincare. Walk-ins welcome. Known for natural hair care and flawless bridal makeup. Booked weeks in advance for events.', '+234 807 000 6003', '+234 807 000 6003', '@glowupstudio_ng', 1, 0, 'Beauty Pick', '₦18,000 session', '/img/listings/glowup-studio.jpg', '["/img/listings/glowup-studio.jpg", "/img/listings/lagos-plumbing-pros.jpg", "/img/listings/coolbreeze-ac-services.jpg"]', 754)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('24', 'Lagos Dispatch Riders', 'service', 'Citywide', 'Same-day package and document delivery across all of Lagos. Tracking via WhatsApp. Trusted by over 500 businesses for reliable, fast dispatch services.', '+234 807 000 6004', '+234 807 000 6004', '@lagosdispatch_ng', 1, 0, 'Fast Delivery', '₦3,500 / delivery', '/img/listings/lagos-dispatch-riders.jpg', '["/img/listings/lagos-dispatch-riders.jpg", "/img/listings/lagos-plumbing-pros.jpg", "/img/listings/coolbreeze-ac-services.jpg"]', 383)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('25', 'Sheraton Lagos Hotel', 'hotel', 'Ikeja', 'Full-service Marriott hotel adjacent to Lagos airport with 4 restaurants, rooftop pool, fitness centre, and extensive conference facilities. The top choice for business travellers flying in.', '+234 802 000 1006', '+234 802 000 1006', '@sheratonlagos', 1, 0, 'Airport Hotel', '₦165,000 / night', '/img/listings/sheraton-lagos-hotel.jpg', '["/img/listings/sheraton-lagos-hotel.jpg", "/img/listings/the-wheatbaker-hotel.jpg", "/img/listings/eko-hotel-and-suites.jpg"]', 845)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('26', 'Madam Kofo Private Chef', 'private-chef', 'Lekki & Victoria Island', 'Experienced private chef specialising in authentic Yoruba cuisine and healthy meal prep. Available for weekly cooking sessions, dinner parties, and special occasions. Groceries sourced fresh daily.', '+234 808 000 7002', '+234 808 000 7002', '@madamkofo_chef', 1, 0, 'Authentic', '₦80,000 / day', '/img/listings/madam-kofo-private-chef.jpg', '["/img/listings/madam-kofo-private-chef.jpg", "/img/listings/chef-tunde-private-kitchen.jpg", "/img/listings/the-lagos-table.jpg"]', 738)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('27', 'The Lagos Table', 'private-chef', 'Ikoyi & VI', 'Luxury private dining experiences brought to your home. Curated multi-course menus, trained servers, and full setup included. Popular for proposals, anniversaries, and corporate client dinners.', '+234 808 000 7003', '+234 808 000 7003', '@thelagostable', 0, 0, 'Luxury Experience', '₦250,000 / day', '/img/listings/the-lagos-table.jpg', '["/img/listings/the-lagos-table.jpg", "/img/listings/chef-tunde-private-kitchen.jpg", "/img/listings/madam-kofo-private-chef.jpg"]', 609)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('28', 'Eagle Eye Security', 'personal-security', 'Lagos Mainland & Island', 'Trained personal security operatives for individuals and families. Home protection, travel escorts, and event security. All officers are ex-military with active licenses.', '+234 809 000 8002', '+234 809 000 8002', '@eagleeyesecurity_ng', 1, 0, 'Ex-Military', '₦75,000 / day', '/img/listings/eagle-eye-security.jpg', '["/img/listings/eagle-eye-security.jpg", "/img/listings/vanguard-protection-services.jpg"]', 405)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.listings (id, name, category, area, description, phone, whatsapp, instagram, verified, promoted, rating, price_range, image, photos, views_count)
VALUES ('29', 'Volt Electrical NG', 'service', 'Surulere & Yaba', 'Certified electricians for home and office. Rewiring, inverter installation, generator maintenance, and solar panel setup. COREN-registered professionals.', '+234 807 000 6005', '+234 807 000 6005', '@voltelectrical_ng', 0, 0, 'Certified', '₦20,000 callout', '/img/listings/volt-electrical-ng.jpg', '["/img/listings/volt-electrical-ng.jpg", "/img/listings/lagos-plumbing-pros.jpg", "/img/listings/coolbreeze-ac-services.jpg"]', 639)
ON CONFLICT (id) DO NOTHING;