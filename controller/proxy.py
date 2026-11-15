"""Streaming HTTP/WebSocket forwarding without exposing internal control routes."""
import asyncio

from aiohttp import WSMsgType, web

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
       "transfer-encoding", "upgrade", "content-length"}


async def relay(request, client, target, headers=None):
    if headers is None:
        headers = {key: value for key, value in request.headers.items() if key.lower() not in HOP}
    if request.headers.get("Upgrade", "").lower() == "websocket":
        headers = {key: value for key, value in headers.items() if not key.lower().startswith("sec-websocket-")}
        async with client.ws_connect(target, headers=headers, max_msg_size=32 * 1024 * 1024) as upstream:
            downstream = web.WebSocketResponse(max_msg_size=32 * 1024 * 1024)
            await downstream.prepare(request)

            async def forward(source, destination):
                async for message in source:
                    if message.type == WSMsgType.TEXT:
                        await destination.send_str(message.data)
                    elif message.type == WSMsgType.BINARY:
                        await destination.send_bytes(message.data)
                    else:
                        break
                await destination.close()

            tasks = [asyncio.create_task(forward(downstream, upstream)), asyncio.create_task(forward(upstream, downstream))]
            try:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            return downstream
    async with client.request(request.method, target, headers=headers,
                              data=request.content if request.can_read_body else None, allow_redirects=False) as upstream:
        response = web.StreamResponse(status=upstream.status)
        for key, value in upstream.headers.items():
            if key.lower() not in HOP:
                response.headers.add(key, value)
        await response.prepare(request)
        async for chunk in upstream.content.iter_chunked(65536):
            await response.write(chunk)
        await response.write_eof()
        return response
