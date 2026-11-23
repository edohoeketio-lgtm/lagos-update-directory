# Unified Auth + Progressive Profiling + Moderated Reviews Implementation Plan

**Goal:** Unify general users and vendors under a single identity layer (Firebase Auth: Google & Email/Password), collect CAC/business details progressively only when listing, and provide an admin-moderated reviews system for listings.

---

## 1. Architecture & Mental Model

### A. One Account for Everyone
- Every visitor signs in/up as a **User** via Firebase (Google Sign-In or Email/Password).
- Reviewing a business requires user authentication (prevents spam and bot abuse).
- Listing a business uses **progressive profiling**:
  1. User signs in (or is already signed in).
  2. If they don't have a vendor profile yet, a prompt collects:
     - **Business Name**
     - **CAC RC/BN Number** (Mandatory)
     - **WhatsApp / Contact Phone**
  3. Once saved, they proceed directly to the listing form + payment flow.

### B. Moderated Reviews
- Authenticated users can submit a star rating (1–5) and review text on any listing page.
- Review is stored with status `pending`.
- Admin desk (`admin.html`) includes a **Reviews Moderation** tab to approve or reject reviews.
- Only `approved` reviews appear publicly on listing pages.

---

## 2. Technical Decomposition & Tasks

### Task 1: Environment & Firebase Admin Verification
- Create `server/firebase_auth.py` to verify ID tokens from incoming requests.
- Configure `FIREBASE_PROJECT_ID` and credentials in `.env` / `server/config.py`.

### Task 2: Database Schema & Migration (`server/db.py`)
- Add `users` table: `id`, `firebase_uid`, `email`, `display_name`, `photo_url`, `created_at`.
- Add `vendor_profiles` table: `id`, `user_id` (FK), `business_name`, `cac_number`, `whatsapp`, `created_at`.
- Add `reviews` table: `id`, `user_id`, `listing_id`, `star_rating`, `comment`, `status` (`pending`/`approved`/`rejected`), `admin_notes`, `created_at`.
- Provide query helpers for user upsert, vendor profile creation/fetch, review submission, and admin moderation.

### Task 3: Backend API Endpoints (`server/app.py`)
- `POST /api/auth/verify`: Verifies Firebase ID token, creates/syncs user record, returns profile & vendor status.
- `POST /api/vendor/profile`: Captures CAC & business details for authenticated user.
- `POST /api/reviews`: Submits a new review (`status: pending`).
- `GET /api/listings/<id>/reviews`: Returns approved reviews for public display.
- `GET /api/admin/reviews`: Returns pending reviews for admin desk.
- `POST /api/admin/reviews/<id>/approve` & `reject`: Moderation actions.

### Task 4: Frontend Auth Integration (`js/auth.js`)
- Standardized Firebase Auth module handling Google Sign-In popup and Email/Password auth.
- Exposes `getIdToken()`, `signInWithGoogle()`, `signInWithEmail()`, `signUpWithEmail()`, and `onAuthStateChanged()`.

### Task 5: Progressive Listing Modal Flow (`index.html` & `js/app.js`)
- Step 0 Auth Gate updated with Google Sign-In button and clean tab switcher (Sign In | Register).
- Step 0.5 (Vendor Profile): Shown if user is authenticated but lacks CAC/business profile.
- Seamless transition to Step 1 (Listing details) upon completion.

### Task 6: Reviews UI & Admin Moderation (`listing.html`, `js/reviews.js`, `admin.html`)
- Star rating widget and submission form on listing detail pages.
- Admin portal tab to inspect, approve, or reject reviews with real-time badge counters.

### Task 7: Automated Tests & Verification
- Unit and integration tests in `tests/test_api.py` covering token verification, review moderation, and vendor profile linking.
- Ensure all tests pass cleanly.
