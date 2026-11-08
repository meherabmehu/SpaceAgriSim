"""Per-process request guard.

The budgets are per client address per minute, so the correctness of the address matters as much
as the budget: behind a managed gateway every request arrives from the proxy, and counting those
together would let one caller spend the entire allowance. `trusted_proxy_hops` decides whether the
forwarding chain is believed. It defaults to 0 because an unconfigured service that believes a
client-supplied X-Forwarded-For can be given a fresh budget on every request.
"""
from collections import defaultdict, deque
from time import monotonic
import logging
import json
from uuid import uuid4

from starlette.responses import JSONResponse
from app.config.settings import settings
from app.observability import record

logger = logging.getLogger("uvicorn.error")

HEADER = b"x-forwarded-for"


def _client_address(scope) -> str:
    """The address the request budget is charged to.

    With `trusted_proxy_hops` set, the entry that many places from the right of X-Forwarded-For is
    used: each trusted proxy appends the address it saw, so the rightmost entries are the ones the
    operator can vouch for. Anything further left is caller-supplied and ignored.
    """
    direct = (scope.get("client") or ("unknown", 0))[0]
    hops = getattr(settings, "trusted_proxy_hops", 0)
    if hops <= 0:
        return direct
    header = ""
    for name, value in scope.get("headers") or ():
        if name.lower() == HEADER:
            header = value.decode("latin-1")
            break
    if not header:
        return direct
    chain = [part.strip() for part in header.split(",") if part.strip()]
    if len(chain) < hops:
        return direct
    return chain[-hops]


class RequestGuard:
    def __init__(self, app, max_body=65536, max_per_minute=None, optimize_per_minute=12):
        # An explicit constructor value wins, so tests can pin a tight budget. With
        # no explicit value the operator setting decides, which is how the browser
        # suite gets headroom without weakening the shipped default.
        self.app=app
        self.max_body=max_body
        self.max_per_minute=max_per_minute
        self.optimize_per_minute=optimize_per_minute
        self.requests=defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"]!="http":
            return await self.app(scope,receive,send)
        start=monotonic()
        address=_client_address(scope)
        path=scope.get("path","")
        bucket="auth" if "/auth/" in path else ("optimize" if path.endswith("/optimize") else "general")
        key=(address,bucket)
        window=self.requests[key]
        while window and window[0] < start-60:
            window.popleft()
        limit=(settings.auth_rate_limit_per_minute if bucket=="auth" else
               self.optimize_per_minute if bucket=="optimize"
               else (self.max_per_minute or settings.general_rate_limit_per_minute))
        if len(window)>=limit:
            response=JSONResponse({"error":"rate_limit","message":"Request limit reached; retry after one minute"},
                                  status_code=429,headers={"Retry-After":"60"})
            return await response(scope,receive,send)
        window.append(start)
        if len(self.requests)>10000:
            self.requests={k:v for k,v in self.requests.items() if v and v[-1]>=start-60}
            self.requests=defaultdict(deque,self.requests)
        if scope.get("method") in {"POST","PUT","PATCH"}:
            body=bytearray()
            while True:
                message=await receive()
                if message["type"]=="http.disconnect":
                    return
                body.extend(message.get("body",b""))
                if len(body)>self.max_body:
                    response=JSONResponse({"error":"body_too_large","message":"Request body exceeds 64 KiB"},status_code=413)
                    return await response(scope,receive,send)
                if not message.get("more_body",False):
                    break
            delivered=False
            original_receive=receive
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered=True
                    return {"type":"http.request","body":bytes(body),"more_body":False}
                return await original_receive()
            receive=replay
        request_id=str(uuid4())
        status=500
        async def tracked_send(message):
            nonlocal status
            if message["type"]=="http.response.start":
                status=message["status"]
                headers=list(message.get("headers",[]))
                headers.extend([
                    (b"x-request-id",request_id.encode()),
                    (b"x-content-type-options",b"nosniff"),
                    (b"x-frame-options",b"DENY"),
                    (b"referrer-policy",b"no-referrer"),
                    (b"permissions-policy",b"geolocation=(), microphone=(), camera=()"),
                ])
                if "/auth/" in path or path.endswith("/scenarios"):
                    headers.append((b"cache-control",b"no-store"))
                message["headers"]=headers
            await send(message)
        try:
            await self.app(scope,receive,tracked_send)
        finally:
            record(path, status)
            logger.info(json.dumps({"event":"request_complete","request_id":request_id,
                        "method":scope.get("method"),"path":path,"status":status,
                        "elapsed_ms":round((monotonic()-start)*1000,2)}))
