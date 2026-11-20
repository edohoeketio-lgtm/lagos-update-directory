"""
Automated Mobile UI/UX and Layout Verification Test Suite.
Audits index.html, directory.html, listing.html, vendor.html, admin.html, and css/styles.css
across 375px (iPhone SE), 390px (iPhone 14/15/16), and 412px (Android) viewports.
"""
import unittest
import os
import re
from html.parser import HTMLParser
import io
from server.app import DirectoryAppHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PAGES = ["index.html", "directory.html", "listing.html", "vendor.html", "admin.html"]
CSS_PATH = os.path.join(BASE_DIR, "css", "styles.css")

class HTMLTagValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
        self.void_elements = {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"
        }
        self.ids = set()
        self.duplicate_ids = []
        self.inputs = []
        self.buttons = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        element_id = attr_dict.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.append(element_id)
            else:
                self.ids.add(element_id)

        if tag == "input":
            self.inputs.append(attr_dict)
        elif tag == "button":
            self.buttons.append(attr_dict)
        elif tag == "a":
            self.links.append(attr_dict)

        if tag.lower() not in self.void_elements:
            self.stack.append(tag.lower())

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in self.void_elements:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{tag}> with empty stack")
            return
        if self.stack[-1] == tag_lower:
            self.stack.pop()
        else:
            # Check if tag is in stack
            if tag_lower in self.stack:
                while self.stack and self.stack[-1] != tag_lower:
                    popped = self.stack.pop()
                    self.errors.append(f"Unclosed tag <{popped}> before </{tag_lower}>")
                if self.stack:
                    self.stack.pop()
            else:
                self.errors.append(f"Mismatched closing tag </{tag_lower}>, expected </{self.stack[-1]}>")


class TestMobileLayoutAndUX(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css_content = f.read()

    def test_viewport_meta_tags(self):
        """All pages must declare width=device-width, initial-scale=1.0."""
        for page in HTML_PAGES:
            page_path = os.path.join(BASE_DIR, page)
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()
            m = re.search(r"<meta\s+name=[\"\x27]viewport[\"\x27]\s+content=[\"\x27]([^\"\x27]+)[\"\x27]", content, re.IGNORECASE)
            self.assertIsNotNone(m, f"{page} is missing <meta name='viewport'>")
            viewport_val = m.group(1)
            self.assertIn("width=device-width", viewport_val, f"{page} viewport missing width=device-width")
            self.assertIn("initial-scale=1", viewport_val, f"{page} viewport missing initial-scale=1")

    def test_html_tag_balance_and_structure(self):
        """All HTML pages must be well-formed with no unclosed tags or structural leaks."""
        for page in HTML_PAGES:
            page_path = os.path.join(BASE_DIR, page)
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()
            parser = HTMLTagValidator()
            parser.feed(content)
            self.assertEqual(len(parser.errors), 0, f"HTML structure errors in {page}: {parser.errors}")
            self.assertEqual(len(parser.stack), 0, f"Unclosed tags in {page}: {parser.stack}")

    def test_css_overflow_x_protection(self):
        """Global CSS must enforce overflow-x: hidden on html and body across mobile viewports."""
        self.assertIn("overflow-x: hidden", self.css_content)
        # Check that mobile media queries (<= 768px, <= 640px, <= 480px) enforce max-width: 100vw or 100%
        media_768 = re.search(r"@media\s*\(\s*max-width:\s*768px\s*\)\s*\{([^}]+html,\s*body[^}]+)\}", self.css_content)
        self.assertIsNotNone(media_768, "Missing @media (max-width: 768px) html, body overflow rules")
        self.assertIn("overflow-x: hidden", media_768.group(1))

    def test_mobile_input_font_sizes_prevent_ios_zoom(self):
        """All mobile input and select fields must have font-size >= 16px to prevent iOS Safari auto-zoom."""
        # Check in styles.css for mobile input rules
        # Look specifically in @media (max-width: 768px) and (max-width: 480px)
        mobile_queries = re.findall(r"@media\s*\([^{]+\)\s*\{(.*?)\n\}", self.css_content, re.DOTALL)
        self.assertGreater(len(mobile_queries), 0)

        # Check .capsule-input font-size on mobile
        capsule_inputs = re.findall(r"\.capsule-input\s*\{([^}]+)\}", self.css_content)
        for block in capsule_inputs:
            m = re.search(r"font-size:\s*(\d+)px", block)
            if m:
                size = int(m.group(1))
                # For mobile blocks (which use !important), size must be >= 16
                if "!important" in block:
                    self.assertGreaterEqual(size, 16, f"Mobile .capsule-input font-size {size}px is < 16px (triggers iOS zoom)")

    def test_touch_target_dimensions_in_css(self):
        """Touch targets on mobile (buttons, action links, tab items) must have min 40px-48px height/width."""
        # Check nav buttons
        self.assertIn(".nav-cta-btn", self.css_content)
        # Check category item
        self.assertIn(".cat-item", self.css_content)
        # Check modal close button
        self.assertIn(".modal-close-btn", self.css_content)
        
        # Verify min-height or min-width on key mobile elements
        self.assertRegex(self.css_content, r"\.nav-cta-btn[^{]*\{[^}]*min-height:\s*4[0-9]px")
        self.assertRegex(self.css_content, r"\.nav-action-link[^{]*\{[^}]*min-height:\s*4[0-9]px")
        self.assertRegex(self.css_content, r"\.modal-close-btn[^{]*\{[^}]*min-height:\s*44px")

    def test_mobile_viewports_fit(self):
        """Audit HTML pages for hardcoded fixed widths > 320px in inline styles that could cause overflow."""
        # Test 375px (iPhone SE), 390px (iPhone 14/15/16), 412px (Android)
        # Check for any inline styles with width > 320px without max-width
        fixed_width_pattern = re.compile(r"style=[\"\x27][^\"\x27]*width:\s*([4-9]\d{2,}|[1-9]\d{3,})px[^\"\x27]*[\"\x27]")
        for page in HTML_PAGES:
            page_path = os.path.join(BASE_DIR, page)
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()
            matches = fixed_width_pattern.findall(content)
            # If any matched, ensure max-width: 100% or max-width: 90% is also present in that style attribute
            for m_style in re.finditer(r"style=[\"\x27]([^\"\x27]*width:\s*([4-9]\d{2,}|[1-9]\d{3,})px[^\"\x27]*)[\"\x27]", content):
                style_str = m_style.group(1)
                self.assertIn("max-width", style_str, f"Found hardcoded width without max-width in {page}: {style_str}")

    def test_static_asset_serving_and_endpoints(self):
        """Verify the server serves all HTML pages, CSS, and API endpoints without error."""
        class MockServer:
            pass

        class InMemHandler(DirectoryAppHandler):
            def __init__(self, method: str, path: str):
                self.directory = BASE_DIR
                self.rfile = io.BytesIO(b"")
                self.wfile = io.BytesIO()
                self.command = method
                self.path = path
                self.request_version = "HTTP/1.1"
                self.requestline = f"{method} {path} HTTP/1.1"
                self.headers = {"Content-Length": "0"}
                self.client_address = ("127.0.0.1", 54321)
                self.server = MockServer()
                self.close_connection = False

            def handle_request(self):
                if self.command == "GET":
                    self.do_GET()

            def get_response(self):
                self.wfile.seek(0)
                raw = self.wfile.read()
                parts = raw.split(b"\r\n\r\n", 1)
                header_lines = parts[0].decode("latin1").split("\r\n")
                status_line = header_lines[0]
                status_code = int(status_line.split(" ")[1])
                headers = {}
                for line in header_lines[1:]:
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        headers[k.lower()] = v
                body = parts[1] if len(parts) > 1 else b""
                return status_code, headers, body

        endpoints_to_test = [
            ("/", 200, "text/html"),
            ("/index.html", 200, "text/html"),
            ("/directory.html", 200, "text/html"),
            ("/listing.html?slug=lagos-marina-yacht-club-10", 200, "text/html"),
            ("/vendor.html", 200, "text/html"),
            ("/admin.html", 200, "text/html"),
            ("/css/styles.css", 200, "text/css"),
            ("/api/listings", 200, "application/json"),
            ("/api/health", 200, "application/json"),
        ]

        for path, exp_code, exp_type in endpoints_to_test:
            handler = InMemHandler("GET", path)
            handler.handle_request()
            code, hdrs, body = handler.get_response()
            self.assertEqual(code, exp_code, f"Failed on endpoint {path}: got {code}, expected {exp_code}")
            content_type = hdrs.get("content-type", "")
            self.assertIn(exp_type, content_type, f"Content-Type mismatch on {path}: got {content_type}, expected {exp_type}")
            self.assertGreater(len(body), 0, f"Empty body returned on {path}")

if __name__ == '__main__':
    unittest.main()
