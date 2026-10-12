"""The real LineClient against a local stand-in for api.line.me."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from maehai.notifications.line import LineClient, LineError


@pytest.fixture
def server(settings):
    seen, status = [], {"code": 200}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.path, dict(self.headers), body))
            self.send_response(status["code"]); self.end_headers(); self.wfile.write(b'{"message":"x"}')

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    settings.LINE_API_BASE = f"http://127.0.0.1:{srv.server_port}/v2/bot/message"
    settings.LINE_CHANNEL_ACCESS_TOKEN = "tok123"
    yield seen, status
    srv.shutdown()


def test_push_request_shape(server):
    seen, _ = server
    LineClient().push("U1", "สวัสดี", "11111111-1111-1111-1111-111111111111")
    path, headers, body = seen[0]
    assert path.endswith("/push") and headers["Authorization"] == "Bearer tok123"
    assert headers["X-Line-Retry-Key"] == "11111111-1111-1111-1111-111111111111"
    assert body == {"to": "U1", "messages": [{"type": "text", "text": "สวัสดี"}]}


def test_reply_has_no_retry_key(server):
    seen, _ = server
    LineClient().reply("rt", "ok")
    assert seen[0][2]["replyToken"] == "rt" and "X-Line-Retry-Key" not in seen[0][1]


@pytest.mark.parametrize("code, retryable", [(429, True), (500, True), (503, True), (400, False), (401, False), (403, False)])
def test_error_classification(server, code, retryable):
    _, status = server
    status["code"] = code
    with pytest.raises(LineError) as e:
        LineClient().push("U1", "x", "11111111-1111-1111-1111-111111111111")
    assert e.value.retryable is retryable


def test_network_error_is_retryable(settings):
    settings.LINE_API_BASE = "http://127.0.0.1:9/v2/bot/message"   # nothing listens here
    with pytest.raises(LineError) as e:
        LineClient().push("U1", "x", "11111111-1111-1111-1111-111111111111")
    assert e.value.retryable


def test_long_text_is_truncated(server):
    seen, _ = server
    LineClient().push("U1", "ก" * 6000, "11111111-1111-1111-1111-111111111111")
    assert len(seen[0][2]["messages"][0]["text"]) == 4900
