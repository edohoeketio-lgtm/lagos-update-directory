"""
Phusion Passenger WSGI Entry Point for cPanel ("Setup Python App").
Mounts Lagos Updates Directory cleanly at root (/) or any subpath (e.g. /directory).
"""
import io
import os
import sys
import email.message
from urllib.parse import urlencode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from server.app import DirectoryAppHandler
from server.db import init_db

# Initialize SQLite schema & seed data once on worker boot
try:
    init_db()
except Exception as e:
    print(f"[Passenger WSGI] DB init warning: {e}", file=sys.stderr)


class _WSGIHandler(DirectoryAppHandler):
    """Bridges a WSGI environ directly into DirectoryAppHandler without a raw TCP socket."""

    def __init__(self, method: str, path: str, headers_dict: dict, body: bytes, client_ip: str = "127.0.0.1"):
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.client_address = (client_ip, 0)
        self.server = None
        self.directory = BASE_DIR

        self.headers = email.message.Message()
        for k, v in headers_dict.items():
            self.headers[k] = v

        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self._status_code = 200
        self._status_msg = "OK"
        self._resp_headers = []

    def send_response(self, code, message=None):
        self._status_code = code
        self._status_msg = message or self.responses.get(code, ("",))[0] or "OK"

    def send_header(self, keyword, value):
        self._resp_headers.append((keyword, str(value)))

    def end_headers(self):
        pass

    def log_message(self, format, *args):
        pass

    def execute(self):
        method = self.command.upper()
        if method == "GET":
            self.do_GET()
        elif method == "POST":
            self.do_POST()
        elif method == "OPTIONS":
            self.do_OPTIONS()
        elif method == "HEAD":
            self.do_HEAD()
        else:
            self.send_json(405, {"error": f"Method {method} not allowed"})
        return self._status_code, self._status_msg, self._resp_headers, self.wfile.getvalue()


def _build_subpath_shim(base_path: str) -> bytes:
    """Injects <base> and a fetch/navigation shim when mounted under a subpath like /directory."""
    base = base_path.rstrip("/")
    shim = (
        f'<base href="{base}/">\n'
        f'<script>(function(){{'
        f'var B="{base}";'
        f'window.__APP_BASE__=B;'
        f'var _f=window.fetch;'
        f'window.fetch=function(u,o){{'
        f'if(typeof u==="string"&&u.startsWith("/")&&!u.startsWith(B+"/")&&!u.startsWith("//")){{u=B+u;}}'
        f'return _f.call(this,u,o);'
        f'}};'
        f'document.addEventListener("click",function(e){{'
        f'var a=e.target&&e.target.closest?e.target.closest("a[href]"):null;'
        f'if(!a)return;'
        f'var h=a.getAttribute("href");'
        f'if(h&&h.startsWith("/")&&!h.startsWith(B+"/")&&!h.startsWith("//")){{'
        f'a.setAttribute("href",h==="/"?(B+"/"):(B+h));'
        f'}}'
        f'}},true);'
        f'}})();</script>\n'
    )
    return shim.encode("utf-8")


def application(environ, start_response):
    """Standard WSGI callable required by cPanel Phusion Passenger."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    script_name = (environ.get("SCRIPT_NAME") or "").rstrip("/")
    path_info = environ.get("PATH_INFO") or "/"

    # Normalize subpath ONLY if Passenger passes full path in PATH_INFO (avoid stripping /directory.html!)
    if script_name and (path_info == script_name or path_info.startswith(script_name + "/")):
        path_info = path_info[len(script_name):] or "/"

    # Ensure root directory redirects cleanly to trailing slash when mounted at /directory
    if script_name and path_info == "" and method == "GET":
        start_response("301 Moved Permanently", [("Location", f"{script_name}/")])
        return [b""]

    query_string = environ.get("QUERY_STRING", "")
    full_path = f"{path_info}?{query_string}" if query_string else path_info

    # Extract HTTP headers from WSGI environ
    headers = {}
    if environ.get("CONTENT_TYPE"):
        headers["Content-Type"] = environ["CONTENT_TYPE"]
    if environ.get("CONTENT_LENGTH"):
        headers["Content-Length"] = environ["CONTENT_LENGTH"]
    for key, val in environ.items():
        if key.startswith("HTTP_"):
            h_name = key[5:].replace("_", "-").title()
            # Skip conditional cache headers so SimpleHTTPRequestHandler never emits
            # headerless 304 Not Modified responses (which crash LiteSpeed/Passenger WSGI with 500)
            if h_name.lower() in ("if-modified-since", "if-none-match"):
                continue
            headers[h_name] = val

    # Read request body
    try:
        content_len = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        content_len = 0
    body = environ["wsgi.input"].read(content_len) if content_len > 0 and "wsgi.input" in environ else b""
    client_ip = environ.get("HTTP_X_FORWARDED_FOR", environ.get("REMOTE_ADDR", "127.0.0.1")).split(",")[0].strip()

    handler = _WSGIHandler(method, full_path, headers, body, client_ip=client_ip)
    status_code, status_msg, resp_headers, resp_body = handler.execute()

    # If mounted at a subpath (e.g. /directory), rewrite root-relative assets & inject shim
    if script_name and resp_body:
        ctype = ""
        for k, v in resp_headers:
            if k.lower() == "content-type":
                ctype = v.lower()
                break
        prefix_bytes = script_name.encode("utf-8")
        if "text/html" in ctype:
            # Rewrite static root-relative /img/ and /uploads/ attributes in HTML
            resp_body = resp_body.replace(b'src="/img/', b'src="' + prefix_bytes + b'/img/')
            resp_body = resp_body.replace(b'href="/img/', b'href="' + prefix_bytes + b'/img/')
            resp_body = resp_body.replace(b'src="/uploads/', b'src="' + prefix_bytes + b'/uploads/')
            shim_bytes = _build_subpath_shim(script_name)
            lower_body = resp_body.lower()
            head_idx = lower_body.find(b"<head>")
            if head_idx != -1:
                insert_pos = head_idx + len(b"<head>")
                resp_body = resp_body[:insert_pos] + b"\n" + shim_bytes + resp_body[insert_pos:]
            resp_headers = [(k, v) for k, v in resp_headers if k.lower() != "content-length"]
            resp_headers.append(("Content-Length", str(len(resp_body))))
        elif "application/json" in ctype:
            # Rewrite root-relative image paths inside JSON API payloads (/img/... -> /directory/img/...)
            resp_body = resp_body.replace(b'"/img/', b'"' + prefix_bytes + b'/img/')
            resp_body = resp_body.replace(b'"/uploads/', b'"' + prefix_bytes + b'/uploads/')
            resp_headers = [(k, v) for k, v in resp_headers if k.lower() != "content-length"]
            resp_headers.append(("Content-Length", str(len(resp_body))))

    start_response(f"{status_code} {status_msg}", resp_headers)
    return [resp_body]
