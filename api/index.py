import importlib.util
import os
import traceback

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "rika_bundle", os.path.join(here, "_bundle.py"))
_bundle = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(_bundle)
    app = _bundle.app
except Exception:
    _err = traceback.format_exc()

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        body = ("RIKA STARTUP CRASH\n\n" + _err).encode("utf-8", "replace")
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                        (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
