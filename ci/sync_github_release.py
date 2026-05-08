import os
import sys
from typing import Any, Dict, Tuple

import requests

REQUEST_TIMEOUT: Tuple[int, int] = (5, 30)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_default_release(tag: str) -> Dict[str, Any]:
    return {
        "name": tag,
        "body": f"Mirrored release for {tag} from primary Gitea repository.",
        "draft": False,
        "prerelease": False,
    }


def get_gitea_release(
    session: requests.Session,
    gitea_server: str,
    gitea_repo: str,
    gitea_token: str,
    tag: str,
) -> Dict[str, Any]:
    url = f"{gitea_server}/api/v1/repos/{gitea_repo}/releases/tags/{tag}"
    headers = {
        "Authorization": f"token {gitea_token}",
        "Accept": "application/json",
    }

    response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return build_default_release(tag)
    response.raise_for_status()

    payload = response.json()
    return {
        "name": payload.get("name") or tag,
        "body": payload.get("body") or "",
        "draft": bool(payload.get("draft", False)),
        "prerelease": bool(payload.get("prerelease", False)),
    }


def upsert_github_release(
    session: requests.Session,
    github_repo: str,
    github_token: str,
    tag: str,
    release_payload: Dict[str, Any],
) -> None:
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    get_url = f"https://api.github.com/repos/{github_repo}/releases/tags/{tag}"
    current = session.get(get_url, headers=headers, timeout=REQUEST_TIMEOUT)

    body = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": release_payload["name"],
        "body": release_payload["body"],
        "draft": release_payload["draft"],
        "prerelease": release_payload["prerelease"],
    }

    if current.status_code == 404:
        create_url = f"https://api.github.com/repos/{github_repo}/releases"
        created = session.post(create_url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
        created.raise_for_status()
        print(f"Created GitHub release for tag {tag}")
        return

    current.raise_for_status()
    release_id = current.json()["id"]
    update_url = f"https://api.github.com/repos/{github_repo}/releases/{release_id}"
    updated = session.patch(update_url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
    updated.raise_for_status()
    print(f"Updated GitHub release for tag {tag}")


def main() -> int:
    try:
        gitea_server = require_env("GITEA_SERVER").rstrip("/")
        gitea_token = require_env("GITEA_TOKEN")
        github_token = require_env("GITHUB_MIRROR_TOKEN")
        github_repo = require_env("GITHUB_MIRROR_REPO")
        gitea_repo = require_env("DRONE_REPO")
        tag = require_env("DRONE_TAG")

        with requests.Session() as session:
            release_payload = get_gitea_release(
                session,
                gitea_server,
                gitea_repo,
                gitea_token,
                tag,
            )
            upsert_github_release(
                session,
                github_repo,
                github_token,
                tag,
                release_payload,
            )

        return 0
    except requests.RequestException as exc:
        print(f"HTTP error while syncing GitHub release: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to sync GitHub release: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
