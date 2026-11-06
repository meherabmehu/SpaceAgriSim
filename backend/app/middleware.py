"""Small per-process request guard; edge-level distributed limits remain a deployment concern."""
from collections import defaultdict, deque
from time import monotonic
import logging
from uuid import uuid4

from starlette.responses import JSONResponse

logger = logging.getLogger("uvicorn.error")


class RequestGuard:
    def __init__(self, app, max_body=65536, max_per_minute=180, optimize_per_minute=12):
        self.app=app
        self.max_body=max_body
        self.max_per_minute=max_per_minute
        self.optimize_per_minute=optimize_per_minute
        self.requests=defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"]!="http":
            return await self.app(scope,receive,send)
        start=monotonic()
        address=(scope.get("client") or ("unknown",0))[0]
        path=scope.get("path","")
        bucket="optimize" if path.endswith("/optimize") else "general"
        key=(address,bucket)
        window=self.requests[key]
        while window and window[0] < start-60:
            window.popleft()
        limit=self.optimize_per_minute if bucket=="optimize" else self.max_per_minute
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
                message["headers"]=list(message.get("headers",[]))+[(b"x-request-id",request_id.encode())]
            await send(message)
        try:
            await self.app(scope,receive,tracked_send)
        finally:
            logger.info("request id=%s method=%s path=%s status=%s elapsed_ms=%.2f",request_id,
                        scope.get("method"),path,status,(monotonic()-start)*1000)
