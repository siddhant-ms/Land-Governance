from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        resp.headers.setdefault("Cache-Control", "no-store")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return resp
