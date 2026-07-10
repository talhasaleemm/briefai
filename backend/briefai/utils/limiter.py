"""
Rate limiting module -- initializes slowapi Limiter instance.

Key function reads X-Forwarded-For (set by nginx) so rate limits are enforced
per real client IP, not per nginx container IP. Falls back to direct TCP host
if no forwarded header is present (direct connections / local dev).
"""
from starlette.requests import Request
from slowapi import Limiter


def get_forwarded_address(request: Request) -> str:
    """
    Returns the real client IP by reading X-Forwarded-For header first.
    nginx sets this header when proxying; ngrok also forwards real client IPs.
    Falls back to request.client.host for direct connections.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; take the first (original client)
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


# Global limiter instance using real client IP as the rate-limit key
limiter = Limiter(key_func=get_forwarded_address)
