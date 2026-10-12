"""Thin LINE Messaging API client (stdlib only). Swapped out in tests via settings.LINE_CLIENT."""
import hashlib
import hmac
import base64
import json
import urllib.error
import urllib.request

from django.conf import settings

DEFAULT_API = "https://api.line.me/v2/bot/message"


class LineError(Exception):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


def verify_signature(body: bytes, signature: str) -> bool:
    """LINE signs the raw webhook body with the channel secret (HMAC-SHA256, base64)."""
    secret = settings.LINE_CHANNEL_SECRET
    if not secret or not signature:
        return False
    digest = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(digest, signature)


class LineClient:
    def _post(self, path: str, payload: dict, retry_key: str | None = None) -> None:
        headers = {"Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}", "Content-Type": "application/json"}
        if retry_key:
            headers["X-Line-Retry-Key"] = retry_key
        req = urllib.request.Request(f"{getattr(settings, 'LINE_API_BASE', DEFAULT_API)}/{path}", data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10):
                return
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:200]
            # 429 and 5xx are worth retrying. 4xx otherwise means a bad token, a blocked user or a bad request.
            raise LineError(f"HTTP {e.code}: {detail}", retryable=e.code == 429 or e.code >= 500) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LineError(f"network: {e}", retryable=True) from e

    def push(self, to: str, text: str, retry_key: str) -> None:
        self._post("push", {"to": to, "messages": [{"type": "text", "text": text[:4900]}]}, retry_key)

    def reply(self, reply_token: str, text: str) -> None:
        """Replies are free of the push quota. Token is valid for about a minute."""
        self._post("reply", {"replyToken": reply_token, "messages": [{"type": "text", "text": text[:4900]}]})
