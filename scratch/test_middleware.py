import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from src.middleware.logging import SecurityLoggingMiddleware
from src.middleware.security import RateLimitMiddleware

async def dummy_app(scope, receive, send):
    pass

async def test_logging_middleware():
    mw = SecurityLoggingMiddleware(dummy_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "client": ("127.0.0.1", 5173),
        "headers": []
    }
    
    async def receive():
        return {}
        
    async def send(msg):
        pass
        
    try:
        await mw(scope, receive, send)
        print("SecurityLoggingMiddleware: SUCCESS")
    except Exception as e:
        print("SecurityLoggingMiddleware: FAILED -", type(e), e)

async def test_ratelimit_middleware():
    mw = RateLimitMiddleware(dummy_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/chat",
        "client": ("127.0.0.1", 5173),
        "headers": []
    }
    
    async def receive():
        return {}
        
    async def send(msg):
        pass
        
    try:
        await mw(scope, receive, send)
        print("RateLimitMiddleware: SUCCESS")
    except Exception as e:
        print("RateLimitMiddleware: FAILED -", type(e), e)

if __name__ == "__main__":
    asyncio.run(test_logging_middleware())
    asyncio.run(test_ratelimit_middleware())
