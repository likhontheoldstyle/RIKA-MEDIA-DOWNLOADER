async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    body = b"Rika raw ASGI alive"
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain"),
                    (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})
