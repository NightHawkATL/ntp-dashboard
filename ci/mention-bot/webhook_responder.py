#!/usr/bin/env python3
"""Gitea webhook responder that uses OpenWebUI to reply when the bot is mentioned."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import traceback
import urllib.error
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = os.getenv("BOT_HOST", "0.0.0.0")
PORT = int(os.getenv("BOT_PORT", "8095"))

GITEA_SERVER = os.getenv("GITEA_SERVER", "").rstrip("/")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")
GITEA_WEBHOOK_SECRET = os.getenv("GITEA_WEBHOOK_SECRET", "")

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "").rstrip("/")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")
OPENWEBUI_MODEL = os.getenv("OPENWEBUI_MODEL", "qwen2-5-coder:3b")
SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")

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


def _extract_pr_context(payload: dict) -> tuple[dict, dict, dict, str]:
    repo = payload.get("repository") or {}
    pr = payload.get("issue") or payload.get("pull_request") or {}
    comment = payload.get("comment") or payload.get("review") or {}
    sender = ((payload.get("sender") or {}).get("login") or "unknown").strip()
    return repo, pr, comment, sender


def _should_handle(event: str, payload: dict) -> tuple[bool, str]:
    allowed_events = {
        "issue_comment",
        "pull_request_review",
        "pull_request_review_comment",
    }
    if event not in allowed_events:
        return False, f"Ignoring event {event}"

    action = (payload.get("action") or "").lower()
    if action not in {"created", "edited", "submitted"}:
        return False, f"Ignoring action {action}"

    _, pr, comment, sender = _extract_pr_context(payload)
    if not pr:
        return False, "Ignoring event without PR context"

    if event == "issue_comment" and not pr.get("pull_request"):
        return False, "Ignoring non-PR issue comment"

    body = (comment.get("body") or "")
    if BOT_MENTION not in body.lower():
        return False, "No bot mention found"

    if sender.lower() == BOT_USERNAME.lower():
        return False, "Ignoring bot's own comment"

    return True, "ok"


def _search_web(query: str, max_results: int = 3) -> str:
    """Query SearxNG and return top results as formatted context."""
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "categories": "general"})
        url = f"{SEARXNG_URL}/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "gitea-ollama-mention-bot"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = (data.get("results") or [])[:max_results]
        if not results:
            return ""
        lines = ["### Web search context (via SearxNG):"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            content = r.get("content", "")
            result_url = r.get("url", "")
            lines.append(f"{i}. Title: {title}")
            if result_url:
                lines.append(f"   URL: {result_url}")
            if content:
                lines.append(f"   Summary: {content}")
        return "\n".join(lines)
    except Exception as exc:  # pylint: disable=broad-except
        _log(f"[search] warning: {exc}")
        return ""


def _build_prompt(payload: dict) -> str:
    repo, pr, comment, sender = _extract_pr_context(payload)

    comment_body = comment.get("body") or ""
    # Isolate the question by stripping the bot mention token for the search query.
    question = comment_body.lower().replace(BOT_MENTION, "").strip()

    search_context = _search_web(question) if question and SEARXNG_URL else ""

    parts = [
        "You are a repository code review assistant for Gitea PR discussions. "
        "Reply directly to the user's question in a concise, actionable way. "
        "Only state what you can directly verify from the provided context or search results. "
        "If you rely on web search results, cite the relevant source URLs you used in a final 'Sources:' section. "
        "Do not cite URLs you did not use. "
        "If context is missing, say what is missing and ask one clarifying question.\n",
        f"Repository: {repo.get('full_name', '')}",
        f"PR #{pr.get('number')}: {pr.get('title', '')}",
        f"Author asking: @{sender}",
        "",
        "PR description:",
        pr.get("body") or "(none)",
        "",
        "Comment that mentioned you:",
        comment_body,
    ]
    if search_context:
        parts += ["", search_context]
    return "\n".join(parts)


def _ask_openwebui(prompt: str) -> str:
    if not OPENWEBUI_URL:
        raise RuntimeError("OPENWEBUI_URL is not set")
    url = f"{OPENWEBUI_URL}/api/chat/completions"
    headers: dict = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "gitea-ollama-mention-bot",
    }
    if OPENWEBUI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENWEBUI_API_KEY}"
    payload = {
        "model": OPENWEBUI_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful code review assistant in a Gitea pull request discussion. "
                    "Answer only what you can verify from the provided context or search results. "
                    "Do not speculate about code not shown to you. "
                    "When you use web-search context, end with a 'Sources:' section listing the specific URLs that support your answer."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, method="POST", headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = (((body.get("choices") or [{}])[0]).get("message") or {}).get("content", "").strip()
        if not content:
            raise RuntimeError("OpenWebUI returned empty content")
        if len(content) > MAX_REPLY_CHARS:
            content = content[:MAX_REPLY_CHARS] + "\n\n[truncated]"
        return content
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from OpenWebUI: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenWebUI request failed: {exc}") from exc


def _post_reply(payload: dict, reply: str) -> None:
    repo, pr, _, sender = _extract_pr_context(payload)

    owner = (repo.get("owner") or {}).get("login")
    name = repo.get("name")
    number = pr.get("number")

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
            reply = _ask_openwebui(prompt)
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
    _log(f"Using OpenWebUI model: {OPENWEBUI_MODEL} at {OPENWEBUI_URL}")
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
