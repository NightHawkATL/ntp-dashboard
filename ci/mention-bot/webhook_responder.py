#!/usr/bin/env python3
"""Gitea webhook responder that uses Ollama to reply when the bot is mentioned."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = os.getenv("BOT_HOST", "0.0.0.0")
PORT = int(os.getenv("BOT_PORT", "8095"))

GITEA_SERVER = os.getenv("GITEA_SERVER", "").rstrip("/")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")
GITEA_WEBHOOK_SECRET = os.getenv("GITEA_WEBHOOK_SECRET", "")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")

BOT_USERNAME = os.getenv("BOT_USERNAME", "ollama-review-bot").strip()
BOT_MENTION = os.getenv("BOT_MENTION", f"@{BOT_USERNAME}").strip().lower()

# Keep replies concise for PR discussion quality.
MAX_REPLY_CHARS = int(os.getenv("MAX_REPLY_CHARS", "4000"))


def _log(msg: str) -> None:
    print(msg, flush=True)


def _json_request(method: str, url: str, payload: dict | None = None, token: str | None = None) -> dict | list:
    headers = {
        "Accept": "application/json",
        "User-Agent": "gitea-ollama-mention-bot",
    }
    data = None
    if token:
        headers["Authorization"] = f"token {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error for {url}: {exc}") from exc


def _verify_signature(raw: bytes, signature_header: str) -> bool:
    if not GITEA_WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False

    # Gitea typically sends a raw hex digest; tolerate optional sha256= prefix too.
    sent = signature_header.strip().lower()
    if sent.startswith("sha256="):
        sent = sent.split("=", 1)[1]

    digest = hmac.new(
        GITEA_WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(sent, digest)


def _should_handle(event: str, payload: dict) -> tuple[bool, str]:
    if event != "issue_comment":
        return False, f"Ignoring event {event}"

    action = (payload.get("action") or "").lower()
    if action not in {"created", "edited"}:
        return False, f"Ignoring action {action}"

    issue = payload.get("issue") or {}
    if not issue.get("pull_request"):
        return False, "Ignoring non-PR issue comment"

    comment = payload.get("comment") or {}
    body = (comment.get("body") or "")
    if BOT_MENTION not in body.lower():
        return False, "No bot mention found"

    sender = ((payload.get("sender") or {}).get("login") or "").strip().lower()
    if sender == BOT_USERNAME.lower():
        return False, "Ignoring bot's own comment"

    return True, "ok"


def _build_prompt(payload: dict) -> str:
    repo = payload["repository"]
    issue = payload["issue"]
    comment = payload["comment"]
    sender = (payload.get("sender") or {}).get("login", "unknown")

    return (
        "You are a repository code review assistant for Gitea PR discussions. "
        "Reply directly to the user's question in a concise, actionable way. "
        "If context is missing, say what is missing and ask one clarifying question.\n\n"
        f"Repository: {repo.get('full_name', '')}\n"
        f"PR #{issue.get('number')}: {issue.get('title', '')}\n"
        f"Author asking: @{sender}\n\n"
        "PR description:\n"
        f"{issue.get('body') or '(none)'}\n\n"
        "Comment that mentioned you:\n"
        f"{comment.get('body') or ''}\n"
    )


def _ask_ollama(prompt: str) -> str:
    url = f"{OLLAMA_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful code review bot in a Gitea pull request discussion.",
            },
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.2},
    }
    resp = _json_request("POST", url, payload=payload)
    content = ((resp or {}).get("message") or {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Ollama returned empty content")
    if len(content) > MAX_REPLY_CHARS:
        content = content[:MAX_REPLY_CHARS] + "\n\n[truncated]"
    return content


def _post_reply(payload: dict, reply: str) -> None:
    repo = payload["repository"]
    issue = payload["issue"]
    sender = (payload.get("sender") or {}).get("login", "unknown")

    owner = (repo.get("owner") or {}).get("login")
    name = repo.get("name")
    number = issue.get("number")

    if not owner or not name or not number:
        raise RuntimeError("Missing repository/issue fields in webhook payload")

    body = (
        f"@{sender}\n\n"
        "Thanks for the mention. Here is my response:\n\n"
        f"{reply}"
    )

    url = f"{GITEA_SERVER}/api/v1/repos/{owner}/{name}/issues/{number}/comments"
    _json_request("POST", url, payload={"body": body}, token=GITEA_TOKEN)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args):
        _log(f"[http] {self.address_string()} - {fmt % args}")

    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)

        sig = self.headers.get("X-Gitea-Signature", "")
        if not _verify_signature(raw, sig):
            _log("Webhook signature validation failed")
            self.send_response(403)
            self.end_headers()
            return

        event = self.headers.get("X-Gitea-Event", "")

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        ok, reason = _should_handle(event, payload)
        if not ok:
            _log(reason)
            self.send_response(202)
            self.end_headers()
            return

        if not GITEA_SERVER or not GITEA_TOKEN:
            _log("Missing GITEA_SERVER or GITEA_TOKEN")
            self.send_response(500)
            self.end_headers()
            return

        try:
            prompt = _build_prompt(payload)
            reply = _ask_ollama(prompt)
            _post_reply(payload, reply)
            _log("Posted mention response")
            self.send_response(200)
            self.end_headers()
        except Exception as exc:  # pylint: disable=broad-except
            _log(f"Error handling webhook: {exc}")
            _log(traceback.format_exc())
            self.send_response(500)
            self.end_headers()


def main() -> int:
    _log(f"Starting mention bot on {HOST}:{PORT}")
    _log(f"Using Ollama model: {OLLAMA_MODEL}")
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
