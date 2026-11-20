"""
Simple In-Memory Rate Limiter.
Protects POST /api/submissions from spam flooding.
"""
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, limit: int = 10, window_seconds: int = 3600):
        self.limit = limit
        self.window = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        timestamps = self.requests[ip]
        # Keep only timestamps within the sliding window
        self.requests[ip] = [ts for ts in timestamps if now - ts < self.window]

        if len(self.requests[ip]) >= self.limit:
            return False

        self.requests[ip].append(now)
        return True

limiter = RateLimiter(limit=10, window_seconds=3600)
