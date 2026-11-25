"""Bound untrusted history request bodies before JSON decoding (including chunked)."""
from starlette.responses import JSONResponse

MAX_HISTORY_BODY = 1_000_000
MAX_SIMULATION_BODY = 2_000_000


def _body_limit(scope):
    if scope.get('type') != 'http' or scope.get('method') != 'POST':
        return None
    path = scope.get('path', '')
    if not path.startswith('/api/v1/'):
        return None
    if path.endswith(('/simulate', '/simulate/history', '/history-number-search')):
        return MAX_SIMULATION_BODY
    if path.endswith(('/statistics/from-draws', '/assistant/from-draws')):
        return MAX_HISTORY_BODY
    return None


class DrawBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        limit = _body_limit(scope)
        if limit is None:
            await self.app(scope, receive, send)
            return
        content_length = next(
            (value for name, value in scope.get('headers', []) if name.lower() == b'content-length'),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    await self._reject(scope, receive, send, limit)
                    return
            except ValueError:
                pass
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
            if size > limit:
                await self._reject(scope, receive, send, limit)
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

    @staticmethod
    async def _reject(scope, receive, send, limit):
        await JSONResponse(
            {'detail': f'Corpo da requisição excede {limit:,} bytes.'.replace(',', '.')},
            status_code=413,
        )(scope, receive, send)
