from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

RECENT_ITEM_COLUMNS = [
    "recent_item_id",
    "document_id",
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "source_name",
    "source_type",
    "source_url",
    "item_title",
    "item_date",
    "item_url",
    "item_text",
    "item_hash",
    "canonical_item_url",
    "normalized_title",
    "content_fingerprint",
    "detected_at",
    "extraction_method",
    "relevance_status",
    "item_quality",
    "publication_date",
    "announcement_date",
    "campaign_start_date",
    "campaign_end_date",
    "event_date_type",
    "recency_basis_date",
    "recency_basis_type",
    "recency_basis_reason",
    "is_active_campaign",
    "active_campaign_reason",
    "cluster_published",
    "cluster_id",
    "normalized_item_date",
    "date_confidence",
    "date_source",
    "is_recent",
    "recency_cutoff",
    "recency_reason",
    "development_candidate_type",
    "is_actual_development",
    "actual_development_reason",
]

SUMMARY_COLUMNS = [
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_id",
    "institution_name",
    "item_title",
    "item_date",
    "item_url",
    "content_role",
    "relevance_status",
    "strategic_theme",
    "product_area",
    "development_type",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "confidence_level",
    "extracted_facts_json",
    "open_questions_json",
    "created_at",
    "llm_model",
    "review_status",
    "raw_llm_response_path",
    "error_message",
    "cluster_id",
    "cluster_status",
    "covered_by_cluster",
    "suppress_individual_review",
    "suppression_reason",
    "language_lint_score",
    "language_lint_warnings",
    "needs_language_review",
    "needs_rewrite",
]

QUEUE_COLUMNS = [
    "review_id",
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_name",
    "item_title",
    "item_date",
    "strategic_theme",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "confidence_level",
    "cluster_id",
    "cluster_status",
    "covered_by_cluster",
    "suppress_individual_review",
    "suppression_reason",
    "item_url",
    "source_url",
    "review_status",
    "reviewer",
    "review_notes",
    "approved_at",
    "analyst_note",
    "reviewed_at",
]

ARCHIVE_COLUMNS = [
    "archive_id",
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_name",
    "item_title",
    "item_date",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "confidence_level",
    "triage_status",
    "triage_reason",
    "archived_at",
]

WEEKLY_COLUMNS = [
    "development_id",
    "date",
    "institution_id",
    "institution_name",
    "headline",
    "strategic_theme",
    "product_area",
    "development_type",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "source_id",
    "analyst_note",
    "tags",
    "summary_id",
    "recent_item_id",
    "cluster_id",
    "related_item_ids",
    "source_urls",
    "source_url",
    "item_url",
    "section",
    "published_at",
]

SOURCE_COLUMNS = [
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "source_name",
    "source_type",
    "url",
    "collection_method",
    "update_frequency",
    "reliability_level",
    "strategic_themes",
    "active",
    "notes",
    "extraction_mode",
    "coverage_scope",
    "coverage_priority",
    "sme_relevance",
    "source_validation_status",
    "collector_capability",
    "mvp_active",
    "claude_eligible",
    "mvp_status",
    "customer_segment",
    "institution_group",
    "display_name",
    "legal_name",
    "exclusion_reason",
    "last_validated_at",
]

METADATA_COLUMNS = [
    "document_id",
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "source_name",
    "url",
    "title",
    "fetched_at",
    "content_hash",
    "cleaned_text_path",
    "raw_html_path",
    "status_code",
    "status",
    "change_status",
    "error_message",
]

AUDIT_COLUMNS = [
    "audit_id",
    "run_id",
    "institution_name",
    "source_id",
    "source_name",
    "candidate_title",
    "candidate_url",
    "canonical_item_url",
    "normalized_title",
    "content_fingerprint",
    "raw_date_text",
    "publication_date",
    "announcement_date",
    "campaign_start_date",
    "campaign_end_date",
    "event_date_type",
    "recency_basis_date",
    "recency_basis_type",
    "recency_basis_reason",
    "is_active_campaign",
    "active_campaign_reason",
    "normalized_item_date",
    "date_confidence",
    "date_source",
    "is_recent",
    "recency_cutoff",
    "recency_reason",
    "development_candidate_type",
    "is_actual_development",
    "actual_development_reason",
    "item_quality",
    "saved_to_recent_items",
    "rejected_reason",
    "duplicate_of_recent_item_id",
    "checked_at",
]

CLUSTER_COLUMNS = [
    "cluster_id",
    "institution_name",
    "cluster_title",
    "cluster_summary",
    "cluster_core_assessment",
    "strategic_theme",
    "product_area",
    "development_type",
    "recommended_action",
    "impact_on_us",
    "importance_level",
    "confidence_level",
    "cluster_start_date",
    "cluster_end_date",
    "item_count",
    "item_ids",
    "item_titles",
    "source_urls",
    "created_at",
    "review_status",
    "analyst_note",
]

CLUSTER_QUEUE_COLUMNS = [
    "cluster_id",
    "institution_name",
    "cluster_title",
    "cluster_summary",
    "cluster_core_assessment",
    "why_it_matters",
    "competitor_intent",
    "recommended_action",
    "impact_on_us",
    "importance_level",
    "confidence_level",
    "management_takeaway",
    "item_count",
    "item_ids",
    "item_titles",
    "source_urls",
    "review_status",
    "analyst_note",
    "reviewer",
    "reviewed_at",
    "created_at",
    "language_lint_score",
    "language_lint_warnings",
    "needs_language_review",
]

MANAGEMENT_AWARENESS_COLUMNS = [
    "awareness_id",
    "summary_id",
    "recent_item_id",
    "institution_name",
    "item_title",
    "item_date",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "confidence_level",
    "strategic_theme",
    "product_area",
    "development_type",
    "awareness_reason",
    "source_url",
    "item_url",
    "review_status",
    "analyst_note",
    "reviewer",
    "reviewed_at",
    "created_at",
]


def read_csv_safe(filename: str, columns: list[str]) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        st.warning(f"`data/{filename}` bulunamadı. Sayfa boş veriyle açıldı.")
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        st.warning(f"`data/{filename}` boş. Sayfa boş veriyle açıldı.")
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df


def write_csv_safe(df: pd.DataFrame, filename: str, columns: list[str] | None = None) -> None:
    path = DATA_DIR / filename
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df.reindex(columns=columns)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def parse_date_series(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", dayfirst=True, utc=True)
    return parsed.dt.tz_localize(None)


def non_empty(value) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def clean_text(value, fallback: str = "-") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def parse_json_list(value) -> list[str]:
    if pd.isna(value) or str(value).strip() == "":
        return []
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass
    return [str(value)]


def is_active(value) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "evet", "aktif"}


def real_published_weekly(weekly: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        return weekly.copy()
    mask = (
        weekly["recent_item_id"].apply(non_empty)
        | weekly["summary_id"].apply(non_empty)
        | weekly["cluster_id"].apply(non_empty)
    )
    return weekly[mask].copy()


def add_sort_columns(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    out = df.copy()
    impact_rank = {"Yüksek": 3, "Orta": 2, "Düşük": 1, "High": 3, "Medium": 2, "Low": 1}
    importance_rank = {"Critical": 4, "Kritik": 4, "Yüksek": 3, "Orta": 2, "Düşük": 1, "High": 3, "Medium": 2, "Low": 1}
    out["_date"] = parse_date_series(out.get(date_column, pd.Series([], dtype=object))).fillna(pd.Timestamp("1970-01-01"))
    out["_impact_rank"] = out.get("impact_on_us", "").map(impact_rank).fillna(0)
    out["_importance_rank"] = out.get("importance_level", "").map(importance_rank).fillna(0)
    return out


def link_markdown(label: str, url: str) -> str:
    url = clean_text(url, "")
    if not url.startswith("http"):
        return ""
    return f"[{label}]({url})"


def build_unified_developments() -> pd.DataFrame:
    items = read_csv_safe("recent_items.csv", RECENT_ITEM_COLUMNS)
    summaries = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
    queue = read_csv_safe("recent_item_review_queue.csv", QUEUE_COLUMNS)
    awareness = read_csv_safe("management_awareness_queue.csv", MANAGEMENT_AWARENESS_COLUMNS)
    archive = read_csv_safe("recent_item_archive.csv", ARCHIVE_COLUMNS)
    weekly = real_published_weekly(read_csv_safe("weekly_developments.csv", WEEKLY_COLUMNS))

    if items.empty:
        return pd.DataFrame(columns=RECENT_ITEM_COLUMNS + SUMMARY_COLUMNS + ["status", "date_dt"])

    base = items.copy()
    if not summaries.empty:
        summary_cols = [
            c
            for c in SUMMARY_COLUMNS
            if c in summaries.columns
            and c
            not in {
                "recent_item_id",
                "document_id",
                "source_id",
                "institution_id",
                "institution_name",
                "item_title",
                "item_date",
                "item_url",
            }
        ]
        base = base.merge(
            summaries[["recent_item_id", *summary_cols]],
            on="recent_item_id",
            how="left",
            suffixes=("", "_summary"),
        )
    else:
        for column in SUMMARY_COLUMNS:
            if column not in base.columns:
                base[column] = ""

    published_ids = set(weekly["recent_item_id"].dropna().astype(str))
    queue_ids = set(queue["recent_item_id"].dropna().astype(str))
    awareness_ids = set(awareness["recent_item_id"].dropna().astype(str))
    archive_ids = set(archive["recent_item_id"].dropna().astype(str))
    summary_ids = set(summaries["recent_item_id"].dropna().astype(str))

    def status_for(item_id: str) -> str:
        item_id = str(item_id)
        if item_id in published_ids:
            return "Yayınlandı"
        if item_id in queue_ids:
            return "İncelemede"
        if item_id in awareness_ids:
            return "Yönetici Bilgilendirme"
        if item_id in archive_ids:
            return "Düşük Öncelik / Arşiv"
        if item_id in summary_ids:
            return "Özetlendi"
        return "Henüz Özetlenmedi"

    base["status"] = base["recent_item_id"].apply(status_for)
    base["date_dt"] = parse_date_series(base["item_date"]).fillna(parse_date_series(base["detected_at"]))
    return base


def archive_id_for(recent_item_id: str, summary_id: str) -> str:
    digest = hashlib.sha1(str(recent_item_id or summary_id).encode("utf-8")).hexdigest()[:12]
    return f"RIA-{digest}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
