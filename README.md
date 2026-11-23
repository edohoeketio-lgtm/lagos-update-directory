# Lagos Update Directory

The premier civic and lifestyle verified business directory for Lagos State, Nigeria. Featuring hand-vetted listings for luxury hotels, serviced apartments, fine dining, lounges, private chefs, personal security, airport transfers, and bespoke services across Ikoyi, Victoria Island, Lekki, Ikeja GRA, and beyond.

## Features

- **Airbnb-Style Discovery**: Responsive 6-column grid with live search, neighborhood capsule filters, price tier filters, and instant category navigation.
- **Multi-Step Onboarding**: Smooth 3-step business application questionnaire with instant Flutterwave payments, photo upload previews, and automatic vendor profile autofill.
- **Vendor Portal (`/vendor.html`)**: Complete vendor dashboard to manage listings, track pending editorial verifications, request edits, renew monthly subscriptions (₦30,000/mo), and trigger top-of-feed featured boosts.
- **Editorial Admin Desk (`/admin.html`)**: Passkey-secured admin dashboard (`ADMIN_PASSKEY`) to review, verify, approve, edit, or reject business submissions with live metrics.
- **Flutterwave Checkout**: Built-in payment gateway for listing verification fees, monthly subscriptions, and featured boosts.
- **PostHog Telemetry**: Privacy-conscious product analytics tracking lead conversions (WhatsApp, direct calls, Instagram), search queries, and onboarding funnels.
- **Clean Architecture**: Python standard library backend with SQLite (WAL mode + busy timeout), strict input validation, rate limiting, and zero external runtime dependencies.

## Quick Start

### 1. Start the Server
```bash
python3 main.py
```
The server will start on `http://localhost:3000`.

### 2. Run Tests
```bash
python3 -m unittest discover tests
```

## Project Structure

```
├── admin.html          # Editorial Admin Desk
├── directory.html      # Full directory view with search & filters
├── index.html          # Main landing page & onboarding modal
├── listing.html        # Individual listing detail page
├── vendor.html         # Vendor portal & dashboard
├── main.py             # Server entry point
├── css/
│   └── styles.css      # Core styles & design system
├── js/
│   ├── app.js          # Client-side router & UI logic
│   ├── payments.js     # Flutterwave integration wrapper
│   └── telemetry.js    # PostHog analytics engine
├── img/                # Brand assets & logos
├── data/
│   └── listings.json   # Seed data for initial listings
├── server/
│   ├── app.py          # HTTP server & REST API handlers
│   ├── config.py       # Configuration & environment variables
│   ├── db.py           # SQLite database layer & schema migrations
│   ├── email_service.py# Notification & dispatch service
│   ├── flutterwave.py  # Flutterwave transaction verification
│   └── validators.py   # Input sanitation & schema validation
└── tests/              # Full unit & integration test suite
```

## License

All rights reserved © Lagos Updates Directory.

---

## 📌 Current Roadmap & Action Items (What We Need Done)

### 1. Mailgun Transactional Email Integration
- [ ] Add the following environment variables to your deployment environment (Vercel & `.env`):
  - `MAILGUN_API_KEY`: Mailgun Private API Key (`key-...`).
  - `MAILGUN_DOMAIN`: Configured sending domain (e.g. `sandbox<id>.mailgun.org` or custom domain).
  - `MAILGUN_FROM_EMAIL`: From address (e.g. `Lagos Updates <support@yourdomain.com>`).
- [ ] Verify recipient authorization in Mailgun dashboard if testing on a sandbox domain.

### 2. Unified User Accounts & Progressive Profiling
- [ ] Migrate separate vendor registration into a single unified User account system (Google Sign-In + Email/Password via Firebase Auth).
- [ ] **Progressive Profiling**: Standard users sign up with minimal friction (Name & Email); business info (CAC RC/BN number, business name, WhatsApp) is only requested when submitting a listing.

### 3. Public Reviews & Admin Moderation
- [ ] Add public reviews component on listing detail pages (`listing.html`) allowing authenticated users to submit star ratings and feedback.
- [ ] Add a **Reviews Moderation** tab to `/admin.html` so reviews stay pending until approved by the editorial team.

