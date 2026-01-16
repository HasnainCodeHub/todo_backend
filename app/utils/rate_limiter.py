"""Rate limiter implementation for MCP Server."""

import time
from collections import defaultdict
from typing import Dict
from threading import Lock


class RateLimiter:
    """Per-user rate limiter to prevent abuse of MCP tools."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per user per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)  # user_id -> list of timestamps
        self.lock = Lock()

    def is_allowed(self, user_id: str) -> bool:
        """
        Check if a request from the user is allowed.

        Args:
            user_id: Unique identifier for the user

        Returns:
            True if request is allowed, False otherwise
        """
        with self.lock:
            now = time.time()
            # Remove requests older than the window
            self.requests[user_id] = [
                timestamp for timestamp in self.requests[user_id]
                if timestamp > now - self.window_seconds
            ]

            # Check if we're under the limit
            if len(self.requests[user_id]) < self.max_requests:
                # Add current request
                self.requests[user_id].append(now)
                return True

            # Rate limit exceeded
            return False


# Global rate limiter instance
rate_limiter = RateLimiter()