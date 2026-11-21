"""Bound untrusted history request bodies before JSON decoding (including chunked)."""
from starlette.responses import JSONResponse

MAX_HISTORY_BODY = 1_000_000


class DrawBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        protected = scope['type'] == 'http' and scope.get('method') == 'POST' and path.startswith('/api/v1/') and (path.endswith('/statistics/from-draws') or path.endswith('/assistant/from-draws'))
        if not protected:
            await self.app(scope, receive, send)
            return
        body = bytearray()
        size = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            if message['type'] != 'http.request':
                continue
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > MAX_HISTORY_BODY:
                await JSONResponse({'detail': 'Corpo da requisição excede 1.000.000 bytes.'}, status_code=413)(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, replay, send)
