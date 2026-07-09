"""
Rate limiting module — initializes slowapi Limiter instance.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Global limiter instance using client IP as key
limiter = Limiter(key_func=get_remote_address)
