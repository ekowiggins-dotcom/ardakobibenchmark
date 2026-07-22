from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from pipeline.rebuild_seen_item_index import build_seen_index, clean, normalize_title, write_seen_index
from utils.recent_mvp import is_active
from utils.source_health import classify_source_health
from utils.mastercard_blocked_mode import DATA_DIR as BLOCKED_DATA_DIR, read_csv as read_blocked_csv, should_skip_mastercard_weekly_source


FALLBACK_INSTITUTIONS = ["Garanti BBVA", "İş Bankası", "Yapı Kredi", "QNB Finansbank", "Visa"]
PERMANENT_CUTOFF = date(2026, 5, 1)
STATE_PATH = DATA_DIR / "pipeline_run_state.json"
RUNS_PATH = DATA_DIR / "pipeline_runs.csv"
REVISIONS_PATH = DATA_DIR / "recent_item_revisions.csv"

WEEKLY_SOURCE_TYPES = {
    "Official Press Release Page",
    "Official Campaign Page",
    "Regulator",
    "Industry Association",
    "News Site",
    "Fintech News",
    "Business News",
    "Resmi Basın Bülteni Sayfası",
    "Resmi Kampanya Sayfası",
    "Regülatör",
    "Sektör Birliği",
    "Haber Sitesi",
    "Fintech Haberi",
    "İş/Ekonomi Haberi",
}

ACTIVE_FILES = [
    "raw_documents_metadata.csv",
    "recent_item_extraction_audit.csv",
    "recent_items.csv",
    "recent_item_summaries.csv",
    "recent_item_review_queue.csv",
    "management_awareness_queue.csv",
    "recent_item_archive.csv",
    "development_clusters.csv",
    "development_cluster_review_queue.csv",
    "weekly_developments.csv",
    "source_registry.csv",
    "pipeline_runs.csv",
    "pipeline_run_state.json",
    "seen_item_index.csv",
    "recent_item_revisions.csv",
]

RUN_COLUMNS = [
    "run_id",
    "run_type",
    "started_at",
    "completed_at",
    "duration_seconds",
    "institutions_requested",
    "sources_requested",
    "sources_checked",
    "sources_succeeded",
    "sources_failed",
    "unchanged_sources",
    "changed_sources",
    "candidate_links_found",
    "detail_pages_fetched",
    "new_items_created",
    "duplicates_skipped",
    "old_items_rejected",
    "undated_items_rejected",
    "end_date_only_items_rejected",
    "non_developments_rejected",
    "summaries_created",
    "summaries_skipped_existing",
    "json_parse_failures",
    "llm_rewrite_count",
    "review_queue_additions",
    "management_awareness_additions",
    "archive_additions",
    "clusters_created",
    "cluster_queue_additions",
    "estimated_input_characters",
    "estimated_output_characters",
    "estimated_llm_calls",
    "final_status",
    "error_summary",
    "report_path",
]

REVISION_COLUMNS = [
    "revision_id",
    "recent_item_id",
    "source_id",
    "previous_content_hash",
    "new_content_hash",
    "previous_item_text",
    "new_item_text",
    "change_summary",
    "material_change",
    "detected_at",
    "requires_resummarization",
    "previous_summary_id",
    "new_summary_id",
    "revision_status",
]


@dataclass
class StageResult:
    name: str
    command: list[str]
    returncode: int
    output: str
    duration_seconds: float

    @property
    def failed(self) -> bool:
        return self.returncode != 0


@dataclass
class RunMetrics:
    sources_requested: int = 0
    sources_checked: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    unchanged_sources: int = 0
    changed_sources: int = 0
    candidate_links_found: int = 0
    detail_pages_fetched: int = 0
    new_items_created: int = 0
    duplicates_skipped: int = 0
    old_items_rejected: int = 0
    undated_items_rejected: int = 0
    end_date_only_items_rejected: int = 0
    non_developments_rejected: int = 0
    summaries_created: int = 0
    summaries_skipped_existing: int = 0
    json_parse_failures: int = 0
    llm_rewrite_count: int = 0
    review_queue_additions: int = 0
    management_awareness_additions: int = 0
    archive_additions: int = 0
    clusters_created: int = 0
    cluster_queue_additions: int = 0
    estimated_input_characters: int = 0
    estimated_output_characters: int = 0
    estimated_llm_calls: int = 0
    stage_failures: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    operational_notes: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id_default() -> str:
    return "weekly_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def read_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig").fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def write_csv(filename: str, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path = DATA_DIR / filename
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df.reindex(columns=columns)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def ensure_operational_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not RUNS_PATH.exists():
        write_csv("pipeline_runs.csv", pd.DataFrame(columns=RUN_COLUMNS), RUN_COLUMNS)
    if not REVISIONS_PATH.exists():
        write_csv("recent_item_revisions.csv", pd.DataFrame(columns=REVISION_COLUMNS), REVISION_COLUMNS)
    if not STATE_PATH.exists():
        atomic_write_json(
            STATE_PATH,
            {
                "global": {
                    "last_successful_weekly_run": "",
                    "last_run_duration_seconds": 0,
                    "last_new_items_count": 0,
                    "last_new_summaries_count": 0,
                    "last_queue_additions_count": 0,
                    "last_cluster_additions_count": 0,
                },
                "pipeline": {},
                "sources": {},
            },
        )


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {"global": {}, "pipeline": {}, "sources": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"global": {}, "pipeline": {}, "sources": {}}


def active_weekly_institutions(registry: pd.DataFrame) -> list[str]:
    if registry.empty:
        return FALLBACK_INSTITUTIONS.copy()
    required = [
        "active",
        "mvp_active",
        "collection_method",
        "extraction_mode",
        "source_type",
        "institution_name",
    ]
    for column in required:
        if column not in registry.columns:
            registry[column] = ""
    eligible = registry[
        registry["active"].apply(lambda value: is_active(value) or truthy(value))
        & registry["mvp_active"].apply(truthy)
        & registry["collection_method"].astype(str).str.strip().str.casefold().eq("static_scrape")
        & registry["extraction_mode"].astype(str).str.strip().str.casefold().isin(["weekly_development", "both"])
        & registry["source_type"].astype(str).isin(WEEKLY_SOURCE_TYPES)
    ].copy()
    institutions = [
        clean(value)
        for value in eligible["institution_name"].dropna().astype(str).drop_duplicates().tolist()
        if clean(value)
    ]
    return institutions or FALLBACK_INSTITUTIONS.copy()


def split_institutions(value: str | None, registry: pd.DataFrame | None = None) -> list[str]:
    if not value:
        return active_weekly_institutions(registry if registry is not None else pd.DataFrame())
    return [item.strip() for item in value.split(",") if item.strip()]


def effective_start_date(args: argparse.Namespace) -> date:
    if args.start_date:
        requested = pd.to_datetime(args.start_date, errors="raise").date()
        return max(PERMANENT_CUTOFF, requested)
    rolling = datetime.now(timezone.utc).date() - timedelta(days=args.lookback_days)
    return max(PERMANENT_CUTOFF, rolling)


def truthy(value) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "evet", "aktif"}


def eligible_sources(registry: pd.DataFrame, institutions: list[str], force_source: str = "") -> pd.DataFrame:
    if registry.empty:
        return pd.DataFrame()
    for column in [
        "active",
        "collection_method",
        "extraction_mode",
        "source_type",
        "institution_name",
        "institution_id",
        "source_id",
        "monitoring_mode",
        "weekly_collection_enabled",
        "mvp_active",
    ]:
        if column not in registry.columns:
            registry[column] = ""
    institution_keys = {item.casefold() for item in institutions}
    mask = (
        registry["active"].apply(lambda value: is_active(value) or truthy(value))
        & registry["mvp_active"].apply(truthy)
        & registry["collection_method"].astype(str).str.strip().str.casefold().eq("static_scrape")
        & registry["extraction_mode"].astype(str).str.strip().str.casefold().isin(["weekly_development", "both"])
        & registry["source_type"].astype(str).isin(WEEKLY_SOURCE_TYPES)
        & (
            registry["institution_name"].astype(str).str.casefold().isin(institution_keys)
            | registry["institution_id"].astype(str).str.casefold().isin(institution_keys)
        )
    )
    sources = registry[mask].copy()
    if not sources.empty:
        sources = sources[~sources.apply(should_skip_mastercard_weekly_source, axis=1)].copy()
    if force_source:
        forced = registry[registry["source_id"].astype(str).eq(force_source)].copy()
        if not forced.empty:
            sources = pd.concat([forced, sources], ignore_index=True).drop_duplicates("source_id")
    return sources


def includes_mastercard(institutions: list[str]) -> bool:
    return any(item.casefold() == "mastercard" for item in institutions)


def mastercard_blocked_report(metrics: RunMetrics) -> None:
    watch = read_blocked_csv(BLOCKED_DATA_DIR / "mastercard_source_recovery_watch.csv")
    inbox = read_blocked_csv(BLOCKED_DATA_DIR / "mastercard_manual_official_evidence_inbox.csv")
    verified = read_blocked_csv(BLOCKED_DATA_DIR / "mastercard_manual_verified_candidates.csv")
    next_retry = ""
    if not watch.empty and "next_retry_at" in watch.columns:
        next_retry = min([value for value in watch["next_retry_at"].astype(str) if value] or [""])
    new_manual = 0
    if not inbox.empty and "intake_status" in inbox.columns:
        new_manual = int(inbox["intake_status"].astype(str).isin(["", "New", "Validation Required"]).sum())
    verified_count = len(verified)
    metrics.operational_notes.append(
        "Mastercard: resmi güncel içerikler otomatik erişime kapalı; "
        f"manuel kanıt kuyruğu {new_manual}, verified aday {verified_count}, sonraki erişim kontrolü {next_retry or 'planlanmadı'}."
    )


def metric_from_log(text: str, label: str) -> int:
    matches = re.findall(rf"{re.escape(label)}:\s*(\d+)", text, flags=re.IGNORECASE)
    return int(matches[-1]) if matches else 0


def run_step(name: str, args: list[str]) -> StageResult:
    started = time.time()
    command = [sys.executable, *args]
    print(f"\n[{name}] {' '.join(args)}")
    proc = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return StageResult(name, args, proc.returncode, output, time.time() - started)


def count_rows(filename: str) -> int:
    return len(read_csv(filename))


def latest_metadata_for(source_id: str) -> pd.Series | None:
    metadata = read_csv("raw_documents_metadata.csv")
    if metadata.empty or "source_id" not in metadata.columns:
        return None
    subset = metadata[metadata["source_id"].astype(str).eq(source_id)].copy()
    if subset.empty:
        return None
    subset["_fetched_dt"] = pd.to_datetime(subset.get("fetched_at", ""), errors="coerce", utc=True)
    subset = subset.sort_values("_fetched_dt")
    return subset.iloc[-1]


def file_backups(run_id: str) -> Path:
    backup_dir = DATA_DIR / "run_backups" / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    for filename in ACTIVE_FILES:
        src = DATA_DIR / filename
        if src.exists():
            shutil.copy2(src, backup_dir / filename)
    return backup_dir


def create_snapshot(run_id: str, save_raw: bool = False) -> Path:
    snapshot_dir = DATA_DIR / "snapshots" / datetime.now(timezone.utc).date().isoformat() / run_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for filename in ACTIVE_FILES:
        src = DATA_DIR / filename
        if src.exists():
            shutil.copy2(src, snapshot_dir / filename)
    if save_raw:
        raw_dir = DATA_DIR / "raw_documents"
        if raw_dir.exists():
            shutil.copytree(raw_dir, snapshot_dir / "raw_documents", dirs_exist_ok=True)
    return snapshot_dir


def before_after_counts() -> dict[str, int]:
    return {
        "items": count_rows("recent_items.csv"),
        "summaries": count_rows("recent_item_summaries.csv"),
        "queue": count_rows("recent_item_review_queue.csv"),
        "awareness": count_rows("management_awareness_queue.csv"),
        "archive": count_rows("recent_item_archive.csv"),
        "clusters": count_rows("development_clusters.csv"),
        "cluster_queue": count_rows("development_cluster_review_queue.csv"),
    }


def delta(after: dict[str, int], before: dict[str, int], key: str) -> int:
    return max(0, after.get(key, 0) - before.get(key, 0))


def update_metrics_from_extract(metrics: RunMetrics, output: str) -> None:
    metrics.candidate_links_found += metric_from_log(output, "Candidate links found")
    metrics.detail_pages_fetched += metric_from_log(output, "Detail pages fetched")
    metrics.new_items_created += metric_from_log(output, "Recent items created")
    metrics.duplicates_skipped += metric_from_log(output, "Duplicates skipped")
    metrics.old_items_rejected += metric_from_log(output, "Rejected old items")
    metrics.undated_items_rejected += metric_from_log(output, "Rejected undated items")
    metrics.end_date_only_items_rejected += metric_from_log(output, "Rejected because only campaign_end_date existed")
    metrics.non_developments_rejected += metric_from_log(output, "Rejected non-developments")


def update_metrics_from_summary(metrics: RunMetrics, output: str) -> None:
    candidates = metric_from_log(output, "Recent item candidates")
    created = metric_from_log(output, "Summaries created")
    rewrites = metric_from_log(output, "Language rewrite attempts")
    metrics.summaries_created += created
    metrics.summaries_skipped_existing += max(0, candidates - created)
    metrics.json_parse_failures += metric_from_log(output, "JSON parse failures")
    metrics.llm_rewrite_count += rewrites
    item_chars = metric_from_log(output, "Estimated item chars used")
    prompt_chars = metric_from_log(output, "Estimated prompt/repair chars used")
    metrics.estimated_input_characters += item_chars + prompt_chars
    metrics.estimated_output_characters += created * 1400
    metrics.estimated_llm_calls += created + rewrites


def source_report_row(source: pd.Series, latest: pd.Series | None, candidate_count: int, errors: list[str], state: dict) -> dict[str, str]:
    source_id = clean(source.get("source_id"))
    previous = state.get("sources", {}).get(source_id, {})
    latest_status = clean(latest.get("status")) if latest is not None else ""
    status_code = clean(latest.get("status_code")) if latest is not None else ""
    content_hash = clean(latest.get("content_hash")) if latest is not None else ""
    previous_hash = clean(previous.get("last_source_content_hash") or previous.get("last_document_hash"))
    change_status = clean(latest.get("change_status")) if latest is not None else ""
    error_message = clean(latest.get("error_message")) if latest is not None else ""
    consecutive_failures = int(previous.get("consecutive_failures", 0) or 0)
    if latest_status == "fetched":
        consecutive_failures = 0
    elif latest_status == "error":
        consecutive_failures += 1

    displayed_candidate_count = "" if change_status == "unchanged" and candidate_count == 0 else str(candidate_count)
    health = classify_source_health(
        latest_status=latest_status,
        status_code=status_code,
        content_length=len(content_hash),
        candidate_item_count=displayed_candidate_count,
        consecutive_failures=consecutive_failures,
        last_success_at=clean(previous.get("last_success_at")),
        last_changed_at=clean(previous.get("last_changed_at")),
        collection_method=source.get("collection_method", ""),
        extraction_mode=source.get("extraction_mode", ""),
    )
    return {
        "source_id": source_id,
        "institution_name": clean(source.get("institution_name")),
        "source_name": clean(source.get("source_name")),
        "url": clean(source.get("url")),
        "status": latest_status or "not_checked",
        "http_status": status_code,
        "change_status": change_status,
        "current_hash": content_hash,
        "previous_hash": previous_hash,
        "candidate_item_count": displayed_candidate_count,
        "last_error": error_message or "; ".join(errors),
        "consecutive_failures": str(consecutive_failures),
        "health_status": health.status,
        "health_reason": health.reason,
    }


def update_state(run_id: str, started_at: str, completed_at: str, duration: float, final_status: str, metrics: RunMetrics, source_reports: list[dict[str, str]], error_summary: str) -> None:
    state = read_state()
    state.setdefault("global", {})
    state.setdefault("pipeline", {})
    state.setdefault("sources", {})

    pipeline = state["pipeline"]
    pipeline.update(
        {
            "last_run_id": run_id,
            "last_started_at": started_at,
            "last_completed_at": completed_at,
            "last_status": final_status,
            "last_error": error_summary,
        }
    )
    if final_status in {"Başarılı", "Kısmi Başarılı", "Yeni Gelişme Yok", "Başarılı — Değişiklik Yok"}:
        pipeline["last_successful_at"] = completed_at
        state["global"]["last_successful_weekly_run"] = run_id

    state["global"].update(
        {
            "last_run_duration_seconds": round(duration, 2),
            "last_new_items_count": metrics.new_items_created,
            "last_new_summaries_count": metrics.summaries_created,
            "last_queue_additions_count": metrics.review_queue_additions + metrics.management_awareness_additions,
            "last_cluster_additions_count": metrics.cluster_queue_additions,
        }
    )

    for report in source_reports:
        source_id = report["source_id"]
        previous = state["sources"].get(source_id, {})
        current_hash = report.get("current_hash", "")
        source_state = {
            "last_run_id": run_id,
            "last_started_at": started_at,
            "last_completed_at": completed_at,
            "last_status": report.get("status", ""),
            "last_error": report.get("last_error", ""),
            "last_document_hash": current_hash,
            "last_source_content_hash": current_hash,
            "last_seen_item_date": previous.get("last_seen_item_date", ""),
            "consecutive_failures": int(report.get("consecutive_failures", 0) or 0),
            "items_discovered_total": int(previous.get("items_discovered_total", 0) or 0) + int(report.get("candidate_item_count", 0) or 0),
            "items_created_total": int(previous.get("items_created_total", 0) or 0),
            "last_http_status": report.get("http_status", ""),
            "source_health": report.get("health_status", ""),
        }
        if report.get("status") == "fetched":
            source_state["last_success_at"] = completed_at
        else:
            source_state["last_success_at"] = previous.get("last_success_at", "")
        if report.get("change_status") in {"new_source", "changed"}:
            source_state["last_changed_at"] = completed_at
        else:
            source_state["last_changed_at"] = previous.get("last_changed_at", "")
        state["sources"][source_id] = source_state

    atomic_write_json(STATE_PATH, state)


def append_run_log(row: dict[str, str]) -> None:
    existing = read_csv("pipeline_runs.csv")
    updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    write_csv("pipeline_runs.csv", updated, RUN_COLUMNS)


def previous_successful_runs() -> pd.DataFrame:
    runs = read_csv("pipeline_runs.csv")
    if runs.empty:
        return runs
    runs = runs[runs.get("final_status", "").astype(str).isin(["Başarılı", "Yeni Gelişme Yok", "Başarılı — Değişiklik Yok"])].copy()
    return runs.tail(5)


def is_clean_noop(metrics: RunMetrics, fatal_error: str = "") -> bool:
    return (
        not fatal_error
        and not metrics.stage_failures
        and metrics.sources_failed == 0
        and metrics.sources_checked > 0
        and metrics.changed_sources == 0
        and metrics.unchanged_sources == metrics.sources_checked
        and metrics.new_items_created == 0
        and metrics.summaries_created == 0
        and metrics.review_queue_additions == 0
        and metrics.management_awareness_additions == 0
        and metrics.archive_additions == 0
        and metrics.cluster_queue_additions == 0
    )


def add_anomaly_alerts(metrics: RunMetrics, institutions: list[str]) -> None:
    if is_clean_noop(metrics):
        return
    previous = previous_successful_runs()
    if previous.empty:
        return

    def avg(column: str) -> float:
        if column not in previous.columns:
            return 0.0
        return float(pd.to_numeric(previous[column], errors="coerce").fillna(0).mean())

    candidate_avg = avg("candidate_links_found")
    if candidate_avg > 0 and metrics.candidate_links_found > candidate_avg * 3:
        metrics.alerts.append("Aday link hacmi önceki başarılı koşuların 3 katından fazla.")
    if candidate_avg > 0 and metrics.candidate_links_found == 0 and metrics.changed_sources > 0:
        metrics.alerts.append("Aday link sayısı önceki başarılı koşulara göre beklenmedik biçimde sıfır.")
    if metrics.candidate_links_found and metrics.duplicates_skipped / max(1, metrics.candidate_links_found) > 0.60:
        metrics.alerts.append("Duplicate oranı %60 üzerinde.")
    routed_total = metrics.review_queue_additions + metrics.management_awareness_additions + metrics.archive_additions
    if routed_total and metrics.archive_additions / routed_total > 0.90:
        metrics.alerts.append("Arşiv oranı %90 üzerinde; kaynak gürültüsü artmış olabilir.")
    queue_avg = avg("review_queue_additions")
    if queue_avg > 0 and metrics.review_queue_additions > queue_avg * 3:
        metrics.alerts.append("Review queue hacmi önceki başarılı koşuların 3 katından fazla.")
    llm_avg = avg("estimated_llm_calls")
    if llm_avg > 0 and metrics.estimated_llm_calls > llm_avg * 3:
        metrics.alerts.append("LLM çağrı hacmi önceki başarılı koşuların 3 katından fazla.")
    if institutions and metrics.sources_succeeded == 0:
        metrics.alerts.append("Seçili kurumlar için başarılı kaynak sonucu yok.")


def final_status_for(args: argparse.Namespace, metrics: RunMetrics, fatal_error: str) -> str:
    if args.dry_run:
        return "Dry Run"
    if fatal_error and metrics.sources_succeeded == 0:
        return "Başarısız"
    if is_clean_noop(metrics, fatal_error):
        return "Başarılı — Değişiklik Yok"
    if metrics.stage_failures or metrics.alerts or metrics.sources_failed:
        return "Kısmi Başarılı"
    activity = (
        metrics.new_items_created
        + metrics.summaries_created
        + metrics.review_queue_additions
        + metrics.management_awareness_additions
        + metrics.cluster_queue_additions
    )
    if activity == 0:
        return "Başarılı — Değişiklik Yok"
    return "Başarılı"


def write_report(
    run_id: str,
    started_at: str,
    completed_at: str,
    duration: float,
    institutions: list[str],
    final_status: str,
    metrics: RunMetrics,
    source_reports: list[dict[str, str]],
    llm_provider: str,
    llm_model: str,
    api_key_found: bool,
    effective_start: date,
    backup_dir: Path | None,
    snapshot_dir: Path | None,
) -> Path:
    path = DATA_DIR / f"weekly_operations_report_{run_id}.md"
    source_lines = []
    for report in source_reports:
        candidate_label = report.get("candidate_item_count", "") or "ölçülmedi"
        source_lines.append(
            "- {institution} | {source} | {health} | HTTP {http} | {change} | aday {candidates}{error}".format(
                institution=report.get("institution_name", ""),
                source=report.get("source_name", ""),
                health=report.get("health_status", ""),
                http=report.get("http_status", "") or "-",
                change=report.get("change_status", "") or report.get("status", ""),
                candidates=candidate_label,
                error=f" | hata: {report.get('last_error')}" if report.get("last_error") else "",
            )
        )
    if not source_lines:
        source_lines = ["- Kaynak kontrolü yapılmadı."]

    alerts = metrics.alerts + [f"Stage failed: {name}" for name in metrics.stage_failures]
    next_action = "Yeni gelişme bulunmadı; işlem gerekmiyor."
    workload = metrics.review_queue_additions + metrics.management_awareness_additions + metrics.cluster_queue_additions
    if workload:
        next_action = f"{workload} yeni madde analist incelemesi bekliyor."
    if metrics.sources_failed:
        next_action += " Başarısız kaynaklar kaynak sağlığı ekranından kontrol edilmeli."

    content = [
        "# Weekly Operations Report",
        "",
        "## Run Summary",
        "",
        f"- run ID: `{run_id}`",
        f"- started: {started_at}",
        f"- completed: {completed_at}",
        f"- duration: {duration:.2f}s",
        f"- institutions checked: {', '.join(institutions)}",
        f"- effective extraction start date: {effective_start.isoformat()}",
        f"- final status: {final_status}",
        f"- backup: `{backup_dir.relative_to(ROOT_DIR) if backup_dir else '-'}`",
        f"- snapshot: `{snapshot_dir.relative_to(ROOT_DIR) if snapshot_dir else '-'}`",
        "",
        "## New This Run",
        "",
        f"- new developments: {metrics.new_items_created}",
        f"- new Claude summaries: {metrics.summaries_created}",
        f"- new strategic/BD queue items: {metrics.review_queue_additions}",
        f"- new management-awareness items: {metrics.management_awareness_additions}",
        f"- new archived items: {metrics.archive_additions}",
        f"- new clusters: {metrics.clusters_created}",
        "- revised existing items: 0",
        "",
        "## Source Health",
        "",
        *source_lines,
        "",
        "## Rejections",
        "",
        f"- duplicates: {metrics.duplicates_skipped}",
        f"- old items: {metrics.old_items_rejected}",
        f"- undated items: {metrics.undated_items_rejected}",
        f"- campaign-end-date-only items: {metrics.end_date_only_items_rejected}",
        f"- non-developments: {metrics.non_developments_rejected}",
        f"- static/noise pages: {max(0, metrics.candidate_links_found - metrics.detail_pages_fetched - metrics.duplicates_skipped)}",
        "",
        "## LLM Usage",
        "",
        f"- provider: {llm_provider}",
        f"- model: {llm_model}",
        f"- API key found: {api_key_found}",
        f"- eligible items: {metrics.summaries_created + metrics.summaries_skipped_existing}",
        f"- calls made: {metrics.estimated_llm_calls}",
        f"- parse failures: {metrics.json_parse_failures}",
        f"- rewrite calls: {metrics.llm_rewrite_count}",
        f"- input character estimate: {metrics.estimated_input_characters}",
        f"- output character estimate: {metrics.estimated_output_characters}",
        "",
        "## Analyst Workload",
        "",
        f"- items newly entering review: {metrics.review_queue_additions}",
        f"- management-awareness items: {metrics.management_awareness_additions}",
        "- revised items needing review: 0",
        f"- clusters needing review: {metrics.cluster_queue_additions}",
        f"- expected analyst workload count: {workload}",
        "",
        "## Alerts",
        "",
        *(f"- {alert}" for alert in alerts),
        *(["- Anlamlı alarm yok."] if not alerts else []),
        "",
        "## Operational Notes",
        "",
        *(f"- {note}" for note in metrics.operational_notes),
        *(["- Ek operasyon notu yok."] if not metrics.operational_notes else []),
        "",
        "## Recommended Next Action",
        "",
        next_action,
        "",
    ]
    path.write_text("\n".join(content), encoding="utf-8")
    return path


def latest_summary_model_info() -> tuple[str, str, bool]:
    summaries = read_csv("recent_item_summaries.csv")
    model = ""
    if not summaries.empty and "llm_model" in summaries.columns:
        model = clean(summaries["llm_model"].dropna().astype(str).tail(1).iloc[0]) if len(summaries["llm_model"].dropna()) else ""
    try:
        from utils.llm_client import get_llm_config

        config = get_llm_config()
        return config.provider, model or config.model, bool(config.has_api_key)
    except Exception:
        return "unknown", model or "unknown", False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the safe incremental weekly MVP pipeline.")
    parser.add_argument("--institutions", default=None, help="Comma-separated institution list. Defaults to all active weekly static sources in source_registry.csv.")
    parser.add_argument("--start-date", default=None, help="Override extraction start date, preserving the 2026-05-01 MVP cutoff.")
    parser.add_argument("--lookback-days", type=int, default=45, help="Rolling lookback days for default extraction start date.")
    parser.add_argument("--source-limit", type=int, default=None, help="Process only first N eligible sources.")
    parser.add_argument("--item-limit", type=int, default=None, help="Limit extraction/summarization items per source/institution.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without fetching, extracting, summarizing, or writing active data.")
    parser.add_argument("--skip-llm", action="store_true", help="Skip Claude summarization stages.")
    parser.add_argument("--skip-clustering", action="store_true", help="Skip cluster rebuild/summarization/queue update.")
    parser.add_argument("--force-source", default="", help="Force processing for a source_id even if unchanged.")
    parser.add_argument("--force-item", default="", help="Force resummarization path for a known recent_item_id when possible.")
    parser.add_argument("--save-raw", action="store_true", help="Keep raw LLM responses and include raw documents in snapshot.")
    parser.add_argument("--run-id", default=None, help="Explicit run id.")
    parser.add_argument("--rehearsal", action="store_true", help="Run production-like rehearsal mode; never publishes and caps first-pass Claude calls.")
    parser.add_argument("--rehearsal-allow-claude", action="store_true", help="Allow controlled Claude calls during rehearsal; otherwise rehearsal skips Claude.")
    parser.add_argument("--max-claude-calls", type=int, default=3, help="Maximum controlled Claude calls when --rehearsal-allow-claude is used.")
    parser.add_argument("--include-browser", action="store_true", help="Accepted for rehearsal compatibility; only production-ready browser sources may run.")
    parser.add_argument("--llm-limit", type=int, default=None, help="Separate summarization limit; defaults to 10 in rehearsal mode.")
    parser.add_argument("--debug", action="store_true", help="Print extra rehearsal/debug context.")
    args = parser.parse_args()

    ensure_operational_files()

    run_id = args.run_id or run_id_default()
    registry = read_csv("source_registry.csv")
    institutions = split_institutions(args.institutions, registry)
    start_dt = effective_start_date(args)
    started_at = now_iso()
    metrics = RunMetrics()
    stage_results: list[StageResult] = []
    source_reports: list[dict[str, str]] = []
    fatal_error = ""
    backup_dir: Path | None = None
    snapshot_dir: Path | None = None
    before = before_after_counts()
    before_items = read_csv("recent_items.csv")
    before_item_ids = set(before_items.get("recent_item_id", pd.Series(dtype=str)).astype(str)) if not before_items.empty else set()

    sources = eligible_sources(registry, institutions, args.force_source)
    if args.source_limit is not None:
        sources = sources.head(args.source_limit)
    metrics.sources_requested = len(sources)

    print(f"Run ID: {run_id}")
    print(f"Institutions: {', '.join(institutions)}")
    print(f"Effective extraction start date: {start_dt.isoformat()}")
    print(f"Eligible weekly static sources: {len(sources)}")
    if args.rehearsal:
        print("Rehearsal mode: automatic publishing disabled; analyst decisions preserved; publish preview must be generated separately.")
        if args.include_browser:
            print("Rehearsal include-browser requested; no blocked/manual browser sources will enter static weekly collection.")
    if includes_mastercard(institutions):
        print("Mastercard blocked official-source mode: weekly source fetch suppressed; manual evidence gate only.")
        mastercard_blocked_report(metrics)
    if sources.empty:
        metrics.alerts.append("Seçili kurumlar için aktif weekly_development/both static_scrape kaynağı bulunamadı.")

    try:
        if not args.dry_run:
            backup_dir = file_backups(run_id)
            print(f"Backup directory: {backup_dir.relative_to(ROOT_DIR)}")

        state = read_state()
        source_errors: dict[str, list[str]] = {}

        for _, source in sources.iterrows():
            source_id = clean(source.get("source_id"))
            metrics.sources_checked += 1
            source_errors[source_id] = []
            if args.dry_run:
                print(f"[dry-run] Would check {source_id} | {source.get('institution_name')} | {source.get('source_name')} | {source.get('url')}")
                source_reports.append(source_report_row(source, latest_metadata_for(source_id), 0, [], state))
                continue

            collect = run_step("collect", ["pipeline/collect_static_pages.py", "--source-id", source_id])
            stage_results.append(collect)
            if collect.failed:
                metrics.stage_failures.append(f"collect:{source_id}")
                source_errors[source_id].append(collect.output[-500:])

            detect = run_step("detect_changes", ["pipeline/detect_changes.py"])
            stage_results.append(detect)
            if detect.failed:
                metrics.stage_failures.append("detect_changes")

            latest = latest_metadata_for(source_id)
            latest_status = clean(latest.get("status")) if latest is not None else ""
            change_status = clean(latest.get("change_status")) if latest is not None else ""
            if latest_status == "fetched":
                metrics.sources_succeeded += 1
            else:
                metrics.sources_failed += 1

            if change_status == "unchanged":
                metrics.unchanged_sources += 1
            elif change_status in {"new_source", "changed"}:
                metrics.changed_sources += 1

            should_extract = latest_status == "fetched" and (
                change_status in {"new_source", "changed"} or source_id == args.force_source
            )
            source_candidate_count = 0
            if should_extract:
                extract_args = [
                    "pipeline/extract_recent_items.py",
                    "--source-id",
                    source_id,
                    "--fetch-detail-pages",
                    "--start-date",
                    start_dt.isoformat(),
                ]
                if args.item_limit is not None:
                    extract_args.extend(["--limit", str(args.item_limit)])
                if source_id == args.force_source:
                    extract_args.append("--force")
                extract = run_step("extract", extract_args)
                stage_results.append(extract)
                update_metrics_from_extract(metrics, extract.output)
                source_candidate_count = metric_from_log(extract.output, "Candidate links found")
                if extract.failed:
                    metrics.stage_failures.append(f"extract:{source_id}")
                    source_errors[source_id].append(extract.output[-500:])
            else:
                print(f"[skip] {source_id} unchanged or failed; detail extraction skipped.")

            source_reports.append(source_report_row(source, latest, source_candidate_count, source_errors[source_id], state))

        if includes_mastercard(institutions) and not args.dry_run:
            manual_validation = run_step(
                "validate_manual_official_evidence",
                ["pipeline/validate_manual_official_evidence.py", "--institution", "Mastercard"],
            )
            stage_results.append(manual_validation)
            if manual_validation.failed:
                metrics.stage_failures.append("validate_manual_official_evidence:Mastercard")

        allow_llm_this_run = not args.skip_llm and (not args.rehearsal or args.rehearsal_allow_claude)
        if args.rehearsal and not args.rehearsal_allow_claude and not args.skip_llm:
            print("[skip] Rehearsal Claude summarization disabled; pass --rehearsal-allow-claude for controlled calls.")
        if not args.dry_run and allow_llm_this_run:
            remaining_controlled_calls = max(0, args.max_claude_calls)
            for institution in institutions:
                if args.rehearsal and args.rehearsal_allow_claude and remaining_controlled_calls <= 0:
                    print("[skip] Controlled rehearsal Claude call cap reached.")
                    break
                if institution.casefold() == "mastercard":
                    print("[skip] Mastercard Claude summarization skipped; source is in blocked/manual-evidence mode.")
                    continue
                summary_args = [
                    "pipeline/summarize_recent_items.py",
                    "--institution",
                    institution,
                    "--start-date",
                    start_dt.isoformat(),
                ]
                if args.rehearsal and args.rehearsal_allow_claude:
                    summary_args.extend(["--limit", str(min(remaining_controlled_calls, args.item_limit or args.llm_limit or 3))])
                    summary_args.append("--rehearsal-allow-source-override")
                elif args.item_limit is not None:
                    summary_args.extend(["--limit", str(args.item_limit)])
                elif args.llm_limit is not None:
                    summary_args.extend(["--limit", str(args.llm_limit)])
                elif args.rehearsal:
                    summary_args.extend(["--limit", "10"])
                if args.save_raw:
                    summary_args.append("--save-raw")
                if args.force_item:
                    summaries = read_csv("recent_item_summaries.csv")
                    forced = summaries[summaries.get("recent_item_id", pd.Series(dtype=str)).astype(str).eq(args.force_item)] if not summaries.empty else pd.DataFrame()
                    if not forced.empty:
                        summary_args.extend(["--reprocess-summary-id", clean(forced.iloc[0].get("summary_id"))])
                summary = run_step("summarize", summary_args)
                stage_results.append(summary)
                created_this_summary = metric_from_log(summary.output, "Summaries created")
                update_metrics_from_summary(metrics, summary.output)
                if args.rehearsal and args.rehearsal_allow_claude:
                    remaining_controlled_calls -= created_this_summary
                if summary.failed:
                    metrics.stage_failures.append(f"summarize:{institution}")
        elif args.skip_llm:
            print("[skip] Claude summarization skipped by --skip-llm.")

        if not args.dry_run:
            queue = run_step("update_recent_item_review_queue", ["pipeline/update_recent_item_review_queue.py"])
            stage_results.append(queue)
            if queue.failed:
                metrics.stage_failures.append("update_recent_item_review_queue")

            retriage = run_step("retriage_recent_item_summaries", ["pipeline/retriage_recent_item_summaries.py"])
            stage_results.append(retriage)
            if retriage.failed:
                metrics.stage_failures.append("retriage_recent_item_summaries")

            should_run_clustering = not args.skip_clustering and (
                metrics.new_items_created > 0 or metrics.summaries_created > 0
            )
            if args.rehearsal and args.rehearsal_allow_claude:
                should_run_clustering = False
                print("[skip] Clustering skipped for controlled Claude rehearsal; item-level triage only.")
            if should_run_clustering:
                cluster = run_step("cluster_recent_developments", ["pipeline/cluster_recent_developments.py"])
                stage_results.append(cluster)
                metrics.clusters_created = metric_from_log(cluster.output, "Clusters created")
                if cluster.failed:
                    metrics.stage_failures.append("cluster_recent_developments")

                if allow_llm_this_run:
                    cluster_summary = run_step("summarize_development_clusters", ["pipeline/summarize_development_clusters.py"])
                    stage_results.append(cluster_summary)
                    if cluster_summary.failed:
                        metrics.stage_failures.append("summarize_development_clusters")
                else:
                    print("[skip] Cluster Claude synthesis skipped because LLM is disabled for this rehearsal.")

                cluster_queue = run_step("update_cluster_review_queue", ["pipeline/update_cluster_review_queue.py"])
                stage_results.append(cluster_queue)
                metrics.cluster_queue_additions = metric_from_log(cluster_queue.output, "New cluster review rows")
                if cluster_queue.failed:
                    metrics.stage_failures.append("update_cluster_review_queue")
            elif args.skip_clustering:
                print("[skip] Clustering skipped by --skip-clustering.")
            else:
                print("[skip] Clustering skipped because no new items or summaries were created.")

            index = build_seen_index(run_id)
            write_seen_index(index)

        after = before_after_counts()
        metrics.new_items_created = delta(after, before, "items")
        metrics.summaries_created = max(metrics.summaries_created, delta(after, before, "summaries"))
        metrics.review_queue_additions = delta(after, before, "queue")
        metrics.management_awareness_additions = delta(after, before, "awareness")
        metrics.archive_additions = delta(after, before, "archive")
        metrics.clusters_created = max(metrics.clusters_created, delta(after, before, "clusters"))
        metrics.cluster_queue_additions = max(metrics.cluster_queue_additions, delta(after, before, "cluster_queue"))
        recent_items_after = read_csv("recent_items.csv")
        if not recent_items_after.empty and "recent_item_id" in recent_items_after.columns:
            new_items = recent_items_after[
                ~recent_items_after["recent_item_id"].astype(str).isin(before_item_ids)
            ].copy()
            if not new_items.empty and "institution_name" in new_items.columns:
                for institution, count in new_items["institution_name"].astype(str).value_counts().items():
                    if count > 15:
                        metrics.alerts.append(
                            f"{institution} için tek koşuda {count} yeni aday üretildi; kaynak gürültüsü kontrol edilmeli."
                        )

    except Exception as exc:
        fatal_error = str(exc)
        metrics.stage_failures.append("fatal")
        print(f"FATAL: {fatal_error}")

    completed_at = now_iso()
    duration = (pd.to_datetime(completed_at) - pd.to_datetime(started_at)).total_seconds()
    add_anomaly_alerts(metrics, institutions)
    if args.rehearsal and args.rehearsal_allow_claude and metrics.estimated_llm_calls <= args.max_claude_calls:
        metrics.alerts = [alert for alert in metrics.alerts if "LLM çağrı hacmi" not in alert]
    final_status = final_status_for(args, metrics, fatal_error)
    error_summary = "; ".join(metrics.stage_failures + metrics.alerts)
    llm_provider, llm_model, api_key_found = latest_summary_model_info()

    if not args.dry_run:
        update_state(run_id, started_at, completed_at, duration, final_status, metrics, source_reports, error_summary)

    report_path = write_report(
        run_id,
        started_at,
        completed_at,
        duration,
        institutions,
        final_status,
        metrics,
        source_reports,
        llm_provider,
        llm_model,
        api_key_found,
        start_dt,
        backup_dir,
        snapshot_dir,
    )

    row = {
        "run_id": run_id,
        "run_type": "dry_run" if args.dry_run else ("weekly_rehearsal" if args.rehearsal else "weekly_incremental_mvp"),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": f"{duration:.2f}",
        "institutions_requested": ",".join(institutions),
        "sources_requested": metrics.sources_requested,
        "sources_checked": metrics.sources_checked,
        "sources_succeeded": metrics.sources_succeeded,
        "sources_failed": metrics.sources_failed,
        "unchanged_sources": metrics.unchanged_sources,
        "changed_sources": metrics.changed_sources,
        "candidate_links_found": metrics.candidate_links_found,
        "detail_pages_fetched": metrics.detail_pages_fetched,
        "new_items_created": metrics.new_items_created,
        "duplicates_skipped": metrics.duplicates_skipped,
        "old_items_rejected": metrics.old_items_rejected,
        "undated_items_rejected": metrics.undated_items_rejected,
        "end_date_only_items_rejected": metrics.end_date_only_items_rejected,
        "non_developments_rejected": metrics.non_developments_rejected,
        "summaries_created": metrics.summaries_created,
        "summaries_skipped_existing": metrics.summaries_skipped_existing,
        "json_parse_failures": metrics.json_parse_failures,
        "llm_rewrite_count": metrics.llm_rewrite_count,
        "review_queue_additions": metrics.review_queue_additions,
        "management_awareness_additions": metrics.management_awareness_additions,
        "archive_additions": metrics.archive_additions,
        "clusters_created": metrics.clusters_created,
        "cluster_queue_additions": metrics.cluster_queue_additions,
        "estimated_input_characters": metrics.estimated_input_characters,
        "estimated_output_characters": metrics.estimated_output_characters,
        "estimated_llm_calls": metrics.estimated_llm_calls,
        "final_status": final_status,
        "error_summary": error_summary or fatal_error,
        "report_path": str(report_path.relative_to(ROOT_DIR)),
    }
    append_run_log(row)

    if not args.dry_run and final_status in {"Başarılı", "Kısmi Başarılı", "Yeni Gelişme Yok", "Başarılı — Değişiklik Yok"}:
        snapshot_dir = create_snapshot(run_id, save_raw=args.save_raw)
        update_state(run_id, started_at, completed_at, duration, final_status, metrics, source_reports, error_summary)
        # Refresh the report with the now-known snapshot path.
        report_path = write_report(
            run_id,
            started_at,
            completed_at,
            duration,
            institutions,
            final_status,
            metrics,
            source_reports,
            llm_provider,
            llm_model,
            api_key_found,
            start_dt,
            backup_dir,
            snapshot_dir,
        )

    print("\nWeekly incremental MVP run complete")
    print(f"final_status: {final_status}")
    print(f"sources_checked: {metrics.sources_checked}")
    print(f"sources_succeeded: {metrics.sources_succeeded}")
    print(f"sources_failed: {metrics.sources_failed}")
    print(f"new_items_created: {metrics.new_items_created}")
    print(f"summaries_created: {metrics.summaries_created}")
    print(f"review_queue_additions: {metrics.review_queue_additions}")
    print(f"management_awareness_additions: {metrics.management_awareness_additions}")
    print(f"archive_additions: {metrics.archive_additions}")
    print(f"cluster_queue_additions: {metrics.cluster_queue_additions}")
    print(f"report_path: {report_path.relative_to(ROOT_DIR)}")
    if backup_dir:
        print(f"backup_dir: {backup_dir.relative_to(ROOT_DIR)}")
    if snapshot_dir:
        print(f"snapshot_dir: {snapshot_dir.relative_to(ROOT_DIR)}")

    if final_status == "Başarısız":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
