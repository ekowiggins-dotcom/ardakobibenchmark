from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

TRACKED_FILES = [
    "source_registry.csv",
    "recent_items.csv",
    "recent_item_summaries.csv",
    "recent_item_review_queue.csv",
    "management_awareness_queue.csv",
    "recent_item_archive.csv",
    "weekly_developments.csv",
    "benchmark_facts.csv",
    "raw_documents_metadata.csv",
    "seen_item_index.csv",
    "recent_item_revisions.csv",
    "pipeline_runs.csv",
    "pipeline_run_state.json",
    "development_clusters.csv",
    "development_cluster_review_queue.csv",
    "mastercard_source_recovery_watch.csv",
    "mastercard_manual_official_evidence_inbox.csv",
    "mastercard_manual_verified_candidates.csv",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig", on_bad_lines="skip").fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df.reindex(columns=columns)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def truthy(value) -> bool:
    return clean(value).casefold() in {"true", "1", "yes", "evet", "aktif"}


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_metadata(filename: str) -> dict[str, object]:
    path = DATA_DIR / filename
    meta = {"exists": path.exists(), "hash": file_hash(path), "rows": 0, "modified_at": ""}
    if path.exists():
        meta["modified_at"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
        if path.suffix.lower() == ".csv":
            meta["rows"] = len(read_csv(path))
    return meta


def table_ids(filename: str) -> set[str]:
    df = read_csv(DATA_DIR / filename)
    if df.empty:
        return set()
    candidates = {
        "recent_items.csv": "recent_item_id",
        "recent_item_summaries.csv": "summary_id",
        "recent_item_review_queue.csv": "review_id",
        "management_awareness_queue.csv": "awareness_id",
        "recent_item_archive.csv": "archive_id",
        "weekly_developments.csv": "development_id",
        "benchmark_facts.csv": "fact_id",
        "seen_item_index.csv": "recent_item_id",
        "recent_item_revisions.csv": "revision_id",
        "development_clusters.csv": "cluster_id",
        "development_cluster_review_queue.csv": "cluster_id",
    }
    column = candidates.get(filename)
    if not column or column not in df.columns:
        return set()
    return {clean(value) for value in df[column].astype(str) if clean(value)}


def protected_decisions() -> dict[str, list[dict[str, str]]]:
    outputs: dict[str, list[dict[str, str]]] = {}
    for filename, id_col in [
        ("recent_item_review_queue.csv", "review_id"),
        ("management_awareness_queue.csv", "awareness_id"),
        ("development_cluster_review_queue.csv", "cluster_id"),
    ]:
        df = read_csv(DATA_DIR / filename)
        cols = [column for column in [id_col, "review_status", "reviewer", "reviewed_at", "approved_at", "analyst_note", "review_notes"] if column in df.columns]
        outputs[filename] = df[cols].to_dict("records") if cols else []
    return outputs


def published_ids() -> list[str]:
    weekly = read_csv(DATA_DIR / "weekly_developments.csv")
    if weekly.empty:
        return []
    for column in ["development_id", "recent_item_id", "source_item_id"]:
        if column in weekly.columns:
            return [clean(value) for value in weekly[column].astype(str) if clean(value)]
    return []


def create_rehearsal_snapshot(run_id: str) -> dict[str, object]:
    snapshot_dir = DATA_DIR / "rehearsal_snapshots" / run_id
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "run_id": run_id,
        "created_at": now_iso(),
        "snapshot_path": str(snapshot_dir.relative_to(ROOT_DIR)),
        "files": {},
        "ids": {},
        "analyst_decisions": protected_decisions(),
        "published_ids": published_ids(),
    }
    for filename in TRACKED_FILES:
        src = DATA_DIR / filename
        if src.exists():
            shutil.copy2(src, snapshot_dir / filename)
        manifest["files"][filename] = file_metadata(filename)
        manifest["ids"][filename] = sorted(table_ids(filename))
    (snapshot_dir / "snapshot_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_snapshot_manifest(run_id: str) -> dict[str, object]:
    path = DATA_DIR / "rehearsal_snapshots" / run_id / "snapshot_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing rehearsal snapshot manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_url(value: str) -> str:
    parsed = urlparse(clean(value))
    keep = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=False):
        if key.lower().startswith(("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")):
            continue
        keep.append((key, val))
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower().removeprefix("www."), parsed.path.rstrip("/"), "", urlencode(keep), ""))


def validate_registry() -> pd.DataFrame:
    registry = read_csv(DATA_DIR / "source_registry.csv")
    if registry.empty:
        return pd.DataFrame(columns=["severity", "source_id", "institution_name", "issue_type", "details"])
    for column in [
        "source_id",
        "institution_id",
        "institution_name",
        "source_name",
        "url",
        "active",
        "collection_method",
        "collector_capability",
        "extraction_mode",
        "mvp_active",
        "claude_eligible",
        "weekly_collection_enabled",
        "monitoring_mode",
    ]:
        if column not in registry.columns:
            registry[column] = ""
    issues: list[dict[str, str]] = []

    def add(row: pd.Series, issue_type: str, details: str, severity: str = "warning") -> None:
        issues.append(
            {
                "severity": severity,
                "source_id": clean(row.get("source_id")),
                "institution_name": clean(row.get("institution_name")),
                "issue_type": issue_type,
                "details": details,
            }
        )

    dup_ids = registry["source_id"][registry["source_id"].duplicated(keep=False)]
    for _, row in registry[registry["source_id"].isin(dup_ids)].iterrows():
        add(row, "duplicate_source_id", clean(row.get("source_id")), "error")

    registry["_canonical_url"] = registry["url"].apply(canonical_url)
    dup_urls = registry.loc[registry["_canonical_url"].ne(""), "_canonical_url"]
    dup_urls = dup_urls[dup_urls.duplicated(keep=False)]
    for _, row in registry[registry["_canonical_url"].isin(dup_urls)].iterrows():
        add(row, "duplicate_canonical_url", clean(row.get("url")), "warning")

    for _, row in registry.iterrows():
        active = truthy(row.get("active"))
        method = clean(row.get("collection_method")).casefold()
        capability = clean(row.get("collector_capability"))
        weekly_enabled = clean(row.get("weekly_collection_enabled")).casefold()
        mvp_active = truthy(row.get("mvp_active"))
        claude = truthy(row.get("claude_eligible"))
        monitoring = clean(row.get("monitoring_mode")).casefold()
        institution = clean(row.get("institution_id")).casefold()
        if not clean(row.get("institution_id")) or not clean(row.get("institution_name")):
            add(row, "invalid_institution_alias", "missing institution_id or institution_name", "error")
        if active and not capability and method in {"", "static_scrape", "browser_required"}:
            add(row, "active_missing_collector_capability", "active source lacks collector_capability")
        if mvp_active and weekly_enabled == "false":
            add(row, "mvp_active_weekly_disabled", "mvp_active=True but weekly_collection_enabled=False", "error")
        if claude and not mvp_active:
            add(row, "claude_without_mvp_ready", "claude_eligible=True while mvp_active is not True", "error")
        if active and method == "browser_required" and monitoring != "production_weekly":
            add(row, "browser_source_skipped_from_static_collection", "browser_required source should not enter static collection")
        if active and method == "manual":
            add(row, "manual_source_skipped_from_automation", "manual source should not be fetched automatically")
        if institution == "mastercard" and monitoring == "blocked_source_watch" and weekly_enabled != "false":
            add(row, "mastercard_blocked_enters_weekly", "blocked Mastercard source has weekly_collection_enabled not False", "error")
    return pd.DataFrame(issues)


def ids_added_since_snapshot(snapshot: dict[str, object], filename: str) -> set[str]:
    before = set(snapshot.get("ids", {}).get(filename, []))
    return table_ids(filename) - before


def before_after(snapshot: dict[str, object]) -> dict[str, object]:
    files_before = snapshot.get("files", {})
    out = {
        "run_id": snapshot.get("run_id"),
        "snapshot_path": snapshot.get("snapshot_path"),
        "before": {},
        "after": {},
        "new_ids": {},
        "removed_ids": {},
        "changed_files": {},
        "analyst_decisions_changed": False,
        "published_rows_changed": False,
    }
    for filename in TRACKED_FILES:
        before_meta = files_before.get(filename, {})
        after_meta = file_metadata(filename)
        out["before"][filename] = before_meta
        out["after"][filename] = after_meta
        before_ids = set(snapshot.get("ids", {}).get(filename, []))
        after_ids = table_ids(filename)
        out["new_ids"][filename] = sorted(after_ids - before_ids)
        out["removed_ids"][filename] = sorted(before_ids - after_ids)
        if before_meta.get("hash") != after_meta.get("hash"):
            out["changed_files"][filename] = {"before_hash": before_meta.get("hash", ""), "after_hash": after_meta.get("hash", "")}
    before_decisions = snapshot.get("analyst_decisions", {})
    after_decisions = protected_decisions()
    decision_changed = False
    for filename, rows in before_decisions.items():
        current_rows = after_decisions.get(filename, [])
        id_col = {
            "recent_item_review_queue.csv": "review_id",
            "management_awareness_queue.csv": "awareness_id",
            "development_cluster_review_queue.csv": "cluster_id",
        }.get(filename, "")
        if not id_col:
            continue
        current_by_id = {clean(row.get(id_col)): row for row in current_rows}
        for row in rows:
            row_id = clean(row.get(id_col))
            if row_id and current_by_id.get(row_id) != row:
                decision_changed = True
                break
        if decision_changed:
            break
    out["analyst_decisions_changed"] = decision_changed
    out["published_rows_changed"] = published_ids() != snapshot.get("published_ids", [])
    return out
