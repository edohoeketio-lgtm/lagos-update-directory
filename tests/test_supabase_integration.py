"""
Tests for Supabase Cloud Database & Storage Integration.
Verifies payload preparation, fallback mechanisms, and Supabase client safety.
"""
import unittest
import os
from server.supabase_db import (
    is_supabase_enabled,
    supabase_sync_listing,
    supabase_sync_submission,
    supabase_sync_review,
    supabase_update_review_status,
    supabase_get_listings
)
from server.validators import upload_to_supabase_storage, process_uploaded_photos

class TestSupabaseIntegration(unittest.TestCase):
    def setUp(self):
        # By default in tests, LAGOS_TEST_MODE is set
        os.environ["LAGOS_TEST_MODE"] = "1"

    def test_supabase_disabled_in_test_mode(self):
        """Ensures tests do not hit production Supabase when LAGOS_TEST_MODE is active."""
        self.assertFalse(is_supabase_enabled())
        self.assertIsNone(upload_to_supabase_storage(b"test", "test.jpg"))

    def test_local_storage_fallback_in_test_mode(self):
        """Ensures photo processing falls back cleanly to local uploads when Supabase is disabled."""
        dummy_base64_jpeg = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
        paths = process_uploaded_photos([dummy_base64_jpeg], "sub-test-123")
        self.assertEqual(len(paths), 1)
        self.assertTrue(paths[0].startswith("/data/uploads/vendor_subtest1_1.jpg"))

if __name__ == "__main__":
    unittest.main()
