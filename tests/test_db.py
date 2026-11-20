"""
Database persistence and query tests (Uncle Bob Gauntlet).
"""
import unittest
import os
import tempfile
import sqlite3
from server.db import get_connection, init_db, query_listings, insert_submission, get_recent_submission
from server import config

class TestDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize DB
        init_db()

    def test_database_has_seeded_listings(self):
        listings = query_listings()
        self.assertGreaterEqual(len(listings), 20)
        # Promoted listings should be at the front
        self.assertTrue(listings[0]["promoted"])

    def test_query_filter_by_category(self):
        hotels = query_listings(category="hotel")
        self.assertTrue(all(h["category"] == "hotel" for h in hotels))
        self.assertGreater(len(hotels), 0)

    def test_query_filter_by_area(self):
        ikoyi_places = query_listings(area="Ikoyi")
        self.assertTrue(all("ikoyi" in p["area"].lower() for p in ikoyi_places))

    def test_submission_lifecycle(self):
        test_payload = {
            "business_name": "Gauntlet Test Suites",
            "category": "apartment",
            "area": "Victoria Island",
            "description": "5-star luxury test suites for validation.",
            "price_range": "₦180,000 / night",
            "whatsapp": "+2348011223344",
            "instagram": "gauntlet_suites",
            "plan_tier": "verified",
            "contact_name": "Engr. Tester",
            "contact_email": "tester@lagosupdates.com"
        }

        sub_id = insert_submission(test_payload)
        self.assertTrue(bool(sub_id))

        recent = get_recent_submission("tester@lagosupdates.com", "Gauntlet Test Suites")
        self.assertIsNotNone(recent)
        self.assertEqual(recent["status"], "pending")
        self.assertEqual(recent["business_name"], "Gauntlet Test Suites")

if __name__ == '__main__':
    unittest.main()
