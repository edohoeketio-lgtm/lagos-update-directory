"""
Unit Tests for Email Dispatcher and Mailgun Integration.
"""
import unittest
from unittest.mock import patch, MagicMock
import os

from server.email_service import send_email, format_email_body

class TestEmailService(unittest.TestCase):
    def test_format_email_body(self):
        text, html = format_email_body("SUB-1234", {
            "business_name": "Test Lounge",
            "rc_number": "RC 123456",
            "category": "lounge",
            "area": "Ikoyi",
            "description": "Exclusive rooftop lounge in Ikoyi",
            "whatsapp": "08012345678",
            "plan_tier": "featured"
        })
        self.assertIn("Test Lounge", text)
        self.assertIn("RC 123456", text)
        self.assertIn("Test Lounge", html)
        self.assertIn("RC 123456", html)

    @patch("urllib.request.urlopen")
    def test_mailgun_dispatch_success(self, mock_urlopen):
        # Mock successful Mailgun HTTP 200 response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch("server.email_service.MAILGUN_API_KEY", "key-test-fake-mailgun-key"), \
             patch("server.email_service.MAILGUN_DOMAIN", "mg.lagosupdates.com"):
            success = send_email(
                to_email="test@example.com",
                subject="Welcome to Lagos Updates",
                text_body="Hello from Lagos Updates",
                html_body="<p>Hello from Lagos Updates</p>"
            )
            self.assertTrue(success)
            self.assertTrue(mock_urlopen.called)

    def test_fallback_logging_when_no_credentials(self):
        with patch("server.email_service.MAILGUN_API_KEY", ""), \
             patch("server.email_service.SMTP_HOST", ""):
            success = send_email(
                to_email="audit@example.com",
                subject="Local Fallback Test",
                text_body="Fallback logging test",
                html_body="<p>Fallback logging test</p>"
            )
            self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()
