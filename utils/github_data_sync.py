from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

import requests


ROOT_DIR = Path(__file__).resolve().parents[1]

DEFAULT_SYNC_FILES = [
    "data/recent_item_review_queue.csv",
    "data/recent_item_summaries.csv",
    "data/weekly_developments.csv",
    "data/recent_item_archive.csv",
    "data/development_cluster_review_queue.csv",
    "data/development_clusters.csv",
    "data/recent_items.csv",
    "data/management_awareness_queue.csv",
]


def _streamlit_secret(name: str) -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, "")
        return str(value).strip() if value else ""
    except Exception:
        return ""


def _config_value(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
        value = _streamlit_secret(name)
        if value:
            return value
    return ""


def _git_remote_url() -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def _repo_from_remote_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    patterns = [
        r"github\.com[:/](?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?$",
        r"https://[^@]+@github\.com/(?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group("repo")
    return ""


def _repo_slug() -> str:
    configured = _config_value("GITHUB_SYNC_REPOSITORY", "GITHUB_REPOSITORY", "GITHUB_REPO")
    if configured:
        return configured.removeprefix("https://github.com/").removesuffix(".git").strip("/")
    return _repo_from_remote_url(_git_remote_url())


def _branch_name() -> str:
    return _config_value("GITHUB_SYNC_BRANCH", "GITHUB_REF_NAME") or "main"


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("utf-8") + b"\0" + content).hexdigest()


def _request_json(method: str, url: str, token: str, **kwargs) -> dict:
    response = requests.request(method, url, headers=_github_headers(token), timeout=20, **kwargs)
    response.raise_for_status()
    return response.json()


def sync_files_to_github(
    files: Iterable[str] = DEFAULT_SYNC_FILES,
    *,
    commit_message: str = "Update analyst-approved radar data",
) -> tuple[bool, str]:
    token = _config_value("GITHUB_SYNC_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
    if not token:
        return False, "GitHub veri senkronu kapalı: Analyst app secret içinde GITHUB_SYNC_TOKEN yok."

    repo = _repo_slug()
    if not repo or "/" not in repo:
        return False, "GitHub veri senkronu kapalı: repo adresi bulunamadı."

    branch = _branch_name()
    api = f"https://api.github.com/repos/{repo}"

    try:
        ref = _request_json("GET", f"{api}/git/ref/heads/{branch}", token)
        base_commit_sha = ref["object"]["sha"]
        base_commit = _request_json("GET", f"{api}/git/commits/{base_commit_sha}", token)
        base_tree_sha = base_commit["tree"]["sha"]

        tree_entries = []
        changed_paths = []
        for relative_path in files:
            path = ROOT_DIR / relative_path
            if not path.exists():
                continue
            content = path.read_bytes()
            local_sha = _git_blob_sha(content)
            remote_sha = ""
            remote = requests.get(
                f"{api}/contents/{relative_path}",
                headers=_github_headers(token),
                params={"ref": branch},
                timeout=20,
            )
            if remote.status_code == 200:
                remote_sha = str(remote.json().get("sha", ""))
            elif remote.status_code != 404:
                remote.raise_for_status()
            if local_sha == remote_sha:
                continue
            tree_entries.append(
                {
                    "path": relative_path,
                    "mode": "100644",
                    "type": "blob",
                    "content": content.decode("utf-8-sig"),
                }
            )
            changed_paths.append(relative_path)

        if not tree_entries:
            return True, "GitHub veri senkronu: değişen dosya yok."

        tree = _request_json(
            "POST",
            f"{api}/git/trees",
            token,
            json={"base_tree": base_tree_sha, "tree": tree_entries},
        )
        commit = _request_json(
            "POST",
            f"{api}/git/commits",
            token,
            json={
                "message": commit_message,
                "tree": tree["sha"],
                "parents": [base_commit_sha],
            },
        )
        _request_json("PATCH", f"{api}/git/refs/heads/{branch}", token, json={"sha": commit["sha"]})
        return True, f"GitHub veri senkronu tamamlandı: {len(changed_paths)} dosya commitlendi."
    except Exception as exc:
        return False, f"GitHub veri senkronu başarısız: {exc}"


def sync_review_outputs_to_github(reason: str) -> tuple[bool, str]:
    return sync_files_to_github(commit_message=f"Update analyst review decisions: {reason}")
