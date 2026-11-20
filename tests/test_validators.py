"""
Unit tests for validators and domain functions (Uncle Bob Gauntlet).
"""
import unittest
from server.validators import (
    normalize_nigerian_phone,
    clean_whatsapp_digits,
    clean_instagram_handle,
    is_valid_email,
    sanitize_text,
    validate_submission_payload,
    process_uploaded_photos
)

class TestValidators(unittest.TestCase):

    def test_nigerian_phone_normalization(self):
        # Standard local formats
        self.assertEqual(normalize_nigerian_phone("08031234567"), "+2348031234567")
        self.assertEqual(normalize_nigerian_phone("09099998888"), "+2349099998888")
        self.assertEqual(normalize_nigerian_phone("07011112222"), "+2347011112222")

        # Formats with country code or spaces/dashes
        self.assertEqual(normalize_nigerian_phone("+234 803 123 4567"), "+2348031234567")
        self.assertEqual(normalize_nigerian_phone("2348031234567"), "+2348031234567")
        self.assertEqual(normalize_nigerian_phone("234-803-123-4567"), "+2348031234567")

        # WhatsApp raw digits
        self.assertEqual(clean_whatsapp_digits("08031234567"), "2348031234567")

        # Invalid cases
        self.assertEqual(normalize_nigerian_phone("123"), "")
        self.assertEqual(normalize_nigerian_phone(""), "")
        self.assertEqual(normalize_nigerian_phone("abcd"), "")

    def test_instagram_handle_cleaning(self):
        self.assertEqual(clean_instagram_handle("@my_business"), "my_business")
        self.assertEqual(clean_instagram_handle("my_business"), "my_business")
        self.assertEqual(clean_instagram_handle("https://instagram.com/my_business/"), "my_business")
        self.assertEqual(clean_instagram_handle("https://www.instagram.com/chef_michael?igsh=123"), "chef_michael")
        self.assertEqual(clean_instagram_handle(""), "")

    def test_email_validation(self):
        self.assertTrue(is_valid_email("owner@lagosupdates.com"))
        self.assertTrue(is_valid_email("test.name+label@gmail.com"))
        self.assertFalse(is_valid_email("invalid-email"))
        self.assertFalse(is_valid_email("test@domain"))
        self.assertFalse(is_valid_email(""))

    def test_xss_sanitization(self):
        raw = "<script>alert('hack')</script> Hello & Welcome"
        cleaned = sanitize_text(raw)
        self.assertNotIn("<script>", cleaned)
        self.assertIn("&lt;script&gt;", cleaned)

    def test_valid_submission_payload(self):
        payload = {
            "business_name": "The Lekki Penthouse",
            "category": "hotel",
            "area": "Lekki Phase 1",
            "description": "Exclusive oceanfront luxury serviced penthouse.",
            "price_range": "₦250,000 / night",
            "whatsapp": "08031234567",
            "instagram": "@lekkipenthouse",
            "plan_tier": "featured",
            "contact_name": "Tunde Bakare",
            "contact_email": "tunde@example.com"
        }
        is_valid, cleaned, err = validate_submission_payload(payload)
        self.assertTrue(is_valid)
        self.assertEqual(err, "")
        self.assertEqual(cleaned["whatsapp"], "+2348031234567")
        self.assertEqual(cleaned["instagram"], "lekkipenthouse")
        self.assertEqual(cleaned["plan_tier"], "featured")

    def test_honeypot_spam_rejection(self):
        payload = {
            "business_name": "Spam Bot Co",
            "category": "hotel",
            "area": "Ikoyi",
            "description": "Legit text description here.",
            "whatsapp": "08031234567",
            "contact_name": "Bot",
            "contact_email": "bot@spam.com",
            "website_url_hp": "http://spamsite.com"  # Honeypot filled!
        }
        is_valid, _, err = validate_submission_payload(payload)
        self.assertFalse(is_valid)
        self.assertIn("Spam detected", err)

    def test_invalid_category_rejection(self):
        payload = {
            "business_name": "Valid Name",
            "category": "crypto-trading",  # Invalid
            "area": "Victoria Island",
            "description": "Valid description length.",
            "whatsapp": "08031234567",
            "contact_name": "John",
            "contact_email": "john@example.com"
        }
        is_valid, _, err = validate_submission_payload(payload)
        self.assertFalse(is_valid)
        self.assertIn("Invalid category", err)

    def test_process_uploaded_photos(self):
        # 1x1 transparent PNG in base64
        sample_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        saved = process_uploaded_photos([sample_png], "test-sub-123")
        self.assertEqual(len(saved), 1)
        self.assertTrue(saved[0].endswith(".png"))
        self.assertTrue(saved[0].startswith("/data/uploads/"))

if __name__ == '__main__':
    unittest.main()
