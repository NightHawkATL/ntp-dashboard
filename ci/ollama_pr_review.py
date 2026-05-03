#!/usr/bin/env python3
"""Post an automated PR review comment in Gitea using a local Ollama model."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"token {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def request_text(method: str, url: str, *, token: str | None = None) -> str:
    headers = {"Accept": "text/plain"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def get_pr_diff(api_base: str, owner: str, repo: str, pr_number: str, token: str) -> str:
    # Gitea exposes unified diff for PRs via .diff endpoint.
    diff_url = f"{api_base}/repos/{owner}/{repo}/pulls/{pr_number}.diff"
    diff_text = request_text("GET", diff_url, token=token)
    return diff_text.strip()


def get_pr_files(api_base: str, owner: str, repo: str, pr_number: str, token: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"page": page, "limit": 50})
        url = f"{api_base}/repos/{owner}/{repo}/pulls/{pr_number}/files?{query}"
        batch = request_json("GET", url, token=token)
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected response shape from pull files endpoint")
        if not batch:
            break
        files.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return files


def build_diff_payload(files: list[dict[str, Any]], max_chars: int = 24000) -> str:
    chunks: list[str] = []
    for item in files:
        filename = item.get("filename", "unknown")
        status = item.get("status", "modified")
        additions = item.get("additions", 0)
        deletions = item.get("deletions", 0)
        patch = item.get("patch", "") or ""
        chunk = (
            f"FILE: {filename}\n"
            f"STATUS: {status} (+{additions}/-{deletions})\n"
            f"PATCH:\n{patch}\n"
            "---\n"
        )
        chunks.append(chunk)

    output = "".join(chunks)
    if len(output) > max_chars:
        output = output[:max_chars] + "\n[truncated]\n"
    return output


def ask_ollama(ollama_url: str, model: str, repo: str, pr_number: str, diff_text: str) -> str:
    endpoint = ollama_url.rstrip("/") + "/api/chat"
    system_prompt = (
        "You are a senior code reviewer. Analyze only the diff provided. "
        "Report only findings that are directly observable in the changed lines — do not infer, "
        "assume, or hallucinate behavior about code not present in the diff. "
        "If a concern depends on context outside the diff, note it as 'unverifiable without full context'. "
        "Do not report issues that are already handled in the diff. "
        "Focus on: correctness bugs, real security flaws (cite the specific line), "
        "performance regressions, and missing error handling for shown code paths. "
        "If no high-confidence issues exist, say so explicitly."
    )
    user_prompt = (
        f"Repository: {repo}\n"
        f"PR: {pr_number}\n\n"
        "Review the following diff and provide:\n"
        "1) Critical/High findings first\n"
        "2) Medium findings\n"
        "3) A short summary\n"
        "If no high-confidence issues exist, say that explicitly.\n\n"
        f"DIFF:\n{diff_text}"
    )

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {"temperature": 0.1},
    }
    response = request_json("POST", endpoint, payload=payload)
    message = (response or {}).get("message", {})
    content = message.get("content", "").strip()
    if not content:
        raise RuntimeError("Ollama returned an empty response")
    return content


def post_issue_comment(api_base: str, owner: str, repo: str, pr_number: str, token: str, body: str) -> None:
    url = f"{api_base}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    request_json("POST", url, token=token, payload={"body": body})


def main() -> int:
    try:
        pr_number = env("DRONE_PULL_REQUEST")
        if pr_number == "0":
            print("Not a pull request event; skipping.")
            return 0

        owner = env("DRONE_REPO_NAMESPACE")
        repo = env("DRONE_REPO_NAME")

        gitea_server = env("GITEA_SERVER").rstrip("/")
        api_base = gitea_server + "/api/v1"
        gitea_token = env("GITEA_TOKEN")

        ollama_url = env("OLLAMA_URL")
        ollama_model = env("OLLAMA_MODEL")

        files = get_pr_files(api_base, owner, repo, pr_number, gitea_token)
        if not files:
            print("No changed files returned by Gitea API; skipping review comment.")
            return 0

        diff_text = get_pr_diff(api_base, owner, repo, pr_number, gitea_token)
        if not diff_text:
            # Fallback for instances where diff endpoint is unavailable.
            diff_text = build_diff_payload(files)

        if not diff_text.strip():
            print("No diff content available; skipping review comment.")
            return 0

        if len(diff_text) > 24000:
            diff_text = diff_text[:24000] + "\n[truncated]\n"

        review = ask_ollama(ollama_url, ollama_model, f"{owner}/{repo}", pr_number, diff_text)

        comment = (
            "### Ollama Automated Review\n\n"
            "_Generated by Drone CI using a local Ollama model._\n\n"
            f"{review}\n"
        )
        post_issue_comment(api_base, owner, repo, pr_number, gitea_token, comment)
        print(f"Posted review comment to PR #{pr_number}")
        return 0
    except Exception as exc:  # pylint: disable=broad-except
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
