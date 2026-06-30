from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from pipeline.validate_mastercard_sources import classify_mastercard_item, canonicalize_mastercard_url
from utils.browser_collector import is_generic_product_root_url, is_item_level_mastercard_url, is_official_mastercard_domain, is_search_page_url


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
PERMANENT_CUTOFF = "2026-05-01"
MASTERCARD_ID = "mastercard"
MASTERCARD_NAME = "Mastercard"

MONITORING_MODES = {
    "production_weekly",
    "benchmark_monitoring",
    "historical_resolution",
    "blocked_source_watch",
    "manual_official_evidence",
    "disabled",
}

SOURCE_RECOVERY_STATUSES = {
    "Accessible",
    "Temporarily Blocked",
    "Persistently Blocked",
    "Manual Evidence Required",
    "Recovery Candidate",
}

MANUAL_INBOX_COLUMNS = [
    "intake_id",
    "submitted_at",
    "submitted_by",
    "official_url",
    "institution_name",
    "proposed_title",
    "proposed_publication_date",
    "copied_official_text",
    "uploaded_evidence_path",
    "evidence_capture_method",
    "official_domain_verified",
    "analyst_date_verified",
    "analyst_body_verified",
    "article_type",
    "named_partner",
    "proposed_network_signal_type",
    "proposed_network_layer",
    "proposed_deployment_scope",
    "notes",
    "intake_status",
    "validation_error",
]

MANUAL_VERIFIED_COLUMNS = [
    "intake_id",
    "official_url",
    "canonical_url",
    "title",
    "publication_date",
    "date_source",
    "date_confidence",
    "body_chars",
    "body_hash",
    "named_partners",
    "named_products",
    "network_signal_type",
    "network_layer",
    "deployment_scope",
    "akbank_relevance",
    "transferability",
    "time_horizon",
    "content_role",
    "proposed_destination",
    "strategic_priority_score",
    "item_level_verified",
    "publication_date_verified",
    "body_verified",
    "recent_item_eligible",
    "claude_eligible",
    "duplicate_status",
    "verification_method",
    "verified_by",
    "verified_at",
    "rejection_reason",
]

RECOVERY_WATCH_COLUMNS = [
    "source_id",
    "source_name",
    "representative_source",
    "source_family",
    "official_url",
    "monitoring_mode",
    "source_recovery_status",
    "retry_cadence",
    "last_retry_at",
    "next_retry_at",
    "last_access_result",
    "consecutive_access_denied",
    "last_success_at",
    "mvp_active",
    "claude_eligible",
    "notes",
]

EXPLICIT_TOKENIZATION_RE = re.compile(r"\b(tokenization|network token|token credentials?|credential lifecycle|one credential)\b", re.I)
EXPLICIT_STABLECOIN_RE = re.compile(r"\b(stablecoin|digital asset settlement|blockchain settlement|USDC|digital currency)\b", re.I)
EXPLICIT_FRAUD_RE = re.compile(r"\b(fraud|cybersecurity|cyber risk|identity theft|authentication attack|transaction monitoring)\b", re.I)
NOISE_RE = re.compile(
    r"(priceless|sports|football|sponsorship|music|festival|celebrity|tourism|travel|destination|culinary|"
    r"executive appointment|chief financial officer|employer|workplace|csr|donation|art|entertainment|lifestyle)",
    re.I,
)


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


def bool_text(value: bool) -> str:
    return "True" if value else "False"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def default_next_retry(days: int = 30) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
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


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column not in output.columns:
            output[column] = ""
    return output


def body_hash(text: str) -> str:
    return hashlib.sha1(clean(text).encode("utf-8")).hexdigest()[:16]


def high_precision_historical_taxonomy(title: str, url: str = "", text: str = "", products: str = "") -> dict[str, str]:
    blob = " ".join([clean(title), clean(url), clean(text), clean(products)])
    if EXPLICIT_TOKENIZATION_RE.search(blob):
        return {
            "network_signal_type": "Aktarılabilir Mastercard Kabiliyeti",
            "network_layer": "Tokenizasyon",
            "deployment_scope": "Global",
            "taxonomy_status": "Provisional",
            "taxonomy_confidence": "Orta",
            "taxonomy_method": "deterministic_high_precision",
        }
    if EXPLICIT_STABLECOIN_RE.search(blob):
        return {
            "network_signal_type": "Aktarılabilir Mastercard Kabiliyeti",
            "network_layer": "Dijital Varlıklar / Stablecoin",
            "deployment_scope": "Global",
            "taxonomy_status": "Provisional",
            "taxonomy_confidence": "Orta",
            "taxonomy_method": "deterministic_high_precision",
        }
    if EXPLICIT_FRAUD_RE.search(blob):
        return {
            "network_signal_type": "Aktarılabilir Mastercard Kabiliyeti",
            "network_layer": "Fraud ve Siber Güvenlik",
            "deployment_scope": "Global",
            "taxonomy_status": "Provisional",
            "taxonomy_confidence": "Orta",
            "taxonomy_method": "deterministic_high_precision",
        }
    return {
        "network_signal_type": "",
        "network_layer": "",
        "deployment_scope": "",
        "taxonomy_status": "Unclassified",
        "taxonomy_confidence": "Düşük",
        "taxonomy_method": "none",
    }


def should_skip_mastercard_weekly_source(row: pd.Series | dict) -> bool:
    institution = clean(row.get("institution_id") or row.get("institution_name")).casefold()
    if institution not in {"mastercard"}:
        return False
    if clean(row.get("weekly_collection_enabled")).casefold() == "false":
        return True
    mode = clean(row.get("monitoring_mode")).casefold()
    return mode in {"blocked_source_watch", "historical_resolution", "manual_official_evidence", "disabled", "benchmark_monitoring"}


def recovery_check_due(row: pd.Series | dict, today: date | None = None) -> bool:
    today_value = today or datetime.now(timezone.utc).date()
    next_retry = clean(row.get("next_retry_at"))
    if not next_retry:
        return True
    try:
        return datetime.fromisoformat(next_retry[:10]).date() <= today_value
    except ValueError:
        return True


def official_evidence_supplied(row: pd.Series | dict) -> bool:
    method = clean(row.get("evidence_capture_method")).casefold()
    if method == "unsupported":
        return False
    if method in {"analyst_copy_from_official_page", "official_pdf", "official_email_newsletter", "official_saved_html"}:
        return True
    if method == "official_screenshot":
        return len(clean(row.get("copied_official_text"))) >= 900
    if method == "official_url":
        return False
    return bool(clean(row.get("uploaded_evidence_path")) or clean(row.get("copied_official_text")))


def existing_manual_duplicate_keys(verified: pd.DataFrame, recent_items: pd.DataFrame | None = None) -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    titles: set[str] = set()
    for df in [verified, recent_items if recent_items is not None else pd.DataFrame()]:
        if df is None or df.empty:
            continue
        for column in ["official_url", "canonical_url", "item_url", "canonical_item_url", "source_url"]:
            if column in df.columns:
                urls.update(canonicalize_mastercard_url(value) for value in df[column].astype(str) if clean(value))
        for column in ["title", "item_title", "headline"]:
            if column in df.columns:
                titles.update(normalize_title(value) for value in df[column].astype(str) if clean(value))
    return urls, titles


def normalize_title(value: str) -> str:
    text = clean(value).casefold()
    text = re.sub(r"[^\w\sçğıöşüİı]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def passes_manual_official_evidence_gate(
    row: pd.Series | dict,
    existing_urls: set[str] | None = None,
    existing_titles: set[str] | None = None,
    start_date: str = PERMANENT_CUTOFF,
) -> tuple[bool, str, dict[str, str]]:
    existing_urls = existing_urls or set()
    existing_titles = existing_titles or set()
    institution = clean(row.get("institution_name"))
    official_url = canonicalize_mastercard_url(clean(row.get("official_url")))
    title = clean(row.get("proposed_title"))
    publication_date = clean(row.get("proposed_publication_date"))
    copied_text = clean(row.get("copied_official_text"))
    verified_by = clean(row.get("submitted_by"))
    method = clean(row.get("evidence_capture_method"))
    uploaded_path = clean(row.get("uploaded_evidence_path"))

    def candidate(reason: str = "") -> dict[str, str]:
        cls = classify_mastercard_item(title, official_url, copied_text, publication_date) if title or copied_text else {}
        return {
            "intake_id": clean(row.get("intake_id")),
            "official_url": official_url,
            "canonical_url": official_url,
            "title": title,
            "publication_date": publication_date,
            "date_source": "analyst_verified_official_evidence" if publication_date else "",
            "date_confidence": "Yüksek" if publication_date else "",
            "body_chars": str(len(copied_text)),
            "body_hash": body_hash(copied_text) if copied_text else "",
            "named_partners": clean(row.get("named_partner")),
            "named_products": "",
            "network_signal_type": clean(row.get("proposed_network_signal_type")) or clean(cls.get("network_signal_type", "")),
            "network_layer": clean(row.get("proposed_network_layer")) or clean(cls.get("network_layer", "")),
            "deployment_scope": clean(row.get("proposed_deployment_scope")) or clean(cls.get("deployment_scope", "")),
            "akbank_relevance": clean(cls.get("akbank_relevance", "")),
            "transferability": clean(cls.get("transferability", "")),
            "time_horizon": clean(cls.get("time_horizon", "")),
            "content_role": clean(cls.get("content_role", "")),
            "proposed_destination": clean(cls.get("proposed_destination", "")),
            "strategic_priority_score": clean(cls.get("strategic_priority_score", "")),
            "item_level_verified": "True",
            "publication_date_verified": bool_text(bool(publication_date)),
            "body_verified": bool_text(len(copied_text) >= 500 or bool(uploaded_path)),
            "recent_item_eligible": "False",
            "claude_eligible": "False",
            "duplicate_status": "",
            "verification_method": method,
            "verified_by": verified_by,
            "verified_at": now_iso(),
            "rejection_reason": reason,
        }

    if institution != MASTERCARD_NAME:
        return False, "institution_not_mastercard", candidate("institution_not_mastercard")
    if not official_url or not is_official_mastercard_domain(official_url):
        return False, "not_official_mastercard_domain", candidate("not_official_mastercard_domain")
    if not truthy(row.get("official_domain_verified")):
        return False, "official_domain_not_analyst_verified", candidate("official_domain_not_analyst_verified")
    if not title:
        return False, "missing_title", candidate("missing_title")
    if official_url in existing_urls or normalize_title(title) in existing_titles:
        blocked = candidate("duplicate_manual_or_recent_item")
        blocked["duplicate_status"] = "duplicate_manual_or_recent_item"
        return False, "duplicate_manual_or_recent_item", blocked
    if is_search_page_url(official_url) or is_generic_product_root_url(official_url):
        return False, "not_item_level_recent_url", candidate("not_item_level_recent_url")
    if not is_item_level_mastercard_url(official_url):
        return False, "not_item_level_mastercard_url", candidate("not_item_level_mastercard_url")
    if not publication_date:
        return False, "missing_publication_date", candidate("missing_publication_date")
    if publication_date < start_date:
        return False, "pre_cutoff", candidate("pre_cutoff")
    if not truthy(row.get("analyst_date_verified")):
        return False, "date_not_analyst_verified", candidate("date_not_analyst_verified")
    if not truthy(row.get("analyst_body_verified")):
        return False, "body_not_analyst_verified", candidate("body_not_analyst_verified")
    if not official_evidence_supplied(row):
        return False, "insufficient_official_evidence", candidate("insufficient_official_evidence")
    if len(copied_text) < 500 and not uploaded_path:
        return False, "body_too_short", candidate("body_too_short")
    if NOISE_RE.search(f"{title} {copied_text[:1000]}"):
        return False, "brand_lifestyle_or_corporate_noise", candidate("brand_lifestyle_or_corporate_noise")

    output = candidate("")
    if output["network_signal_type"] == "Kapsam Dışı" or output["content_role"] == "Kapsam Dışı":
        output["rejection_reason"] = "no_mastercard_strategic_relevance_signal"
        return False, "no_mastercard_strategic_relevance_signal", output
    output["recent_item_eligible"] = "True"
    output["claude_eligible"] = "True"
    output["duplicate_status"] = "canonical_unique"
    return True, "", output


def mastercard_registry_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty or "institution_id" not in df.columns:
        return pd.Series([], dtype=bool)
    return df["institution_id"].astype(str).str.casefold().eq(MASTERCARD_ID)
