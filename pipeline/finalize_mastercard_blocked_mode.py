from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from utils.browser_collector import is_generic_product_root_url, is_search_page_url
from utils.mastercard_blocked_mode import (
    DATA_DIR,
    MANUAL_INBOX_COLUMNS,
    MANUAL_VERIFIED_COLUMNS,
    MASTERCARD_ID,
    RECOVERY_WATCH_COLUMNS,
    bool_text,
    clean,
    default_next_retry,
    high_precision_historical_taxonomy,
    read_csv,
    should_skip_mastercard_weekly_source,
    today_iso,
    write_csv,
)


REGISTRY_PATH = DATA_DIR / "source_registry.csv"
CANDIDATE_INSPECTION_PATH = DATA_DIR / "mastercard_candidate_inspection_table.csv"
BROWSER_INSPECTION_PATH = DATA_DIR / "mastercard_browser_candidate_inspection.csv"
SEED_RESOLUTION_PATH = DATA_DIR / "mastercard_browser_seed_resolution.csv"
FALLBACK_ITEMS_PATH = DATA_DIR / "mastercard_official_fallback_items.csv"
RECOVERY_WATCH_PATH = DATA_DIR / "mastercard_source_recovery_watch.csv"
MANUAL_INBOX_PATH = DATA_DIR / "mastercard_manual_official_evidence_inbox.csv"
MANUAL_VERIFIED_PATH = DATA_DIR / "mastercard_manual_verified_candidates.csv"

REGISTRY_BLOCKED_COLUMNS = [
    "official_source_valid",
    "collector_accessible",
    "extraction_structurally_valid",
    "monitoring_mode",
    "weekly_collection_enabled",
    "source_recovery_status",
    "retry_cadence",
    "next_retry_at",
    "consecutive_access_denied",
    "last_access_denied_at",
    "last_success_at",
    "source_recovery_representative",
    "blocked_status_notes",
]

INSPECTION_EXTRA_COLUMNS = [
    "seed_date_hint",
    "seed_date_hint_source",
    "seed_date_verified",
    "retained_as_evidence",
    "item_level_verified",
    "benchmark_eligible",
    "context_eligible",
    "recent_item_eligible",
    "claude_eligible",
    "accepted_deprecated",
    "intake_status",
]

FALLBACK_EXTRA_COLUMNS = [
    "taxonomy_status",
    "taxonomy_confidence",
    "taxonomy_method",
    "dataset_role",
    "production_recent_eligible",
]


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column not in output.columns:
            output[column] = ""
    return output


def is_mastercard_registry_row(row: pd.Series) -> bool:
    return clean(row.get("institution_id")).casefold() == MASTERCARD_ID


def row_is_legacy(row: pd.Series) -> bool:
    name = clean(row.get("source_name")).casefold()
    url = clean(row.get("url")).casefold()
    return "legacy newsroom" in name or "newsroom.mastercard.com" in url


def row_is_services_benchmark(row: pd.Series) -> bool:
    url = clean(row.get("url")).casefold()
    mode = clean(row.get("extraction_mode")).casefold()
    source_type = clean(row.get("source_type")).casefold()
    return "mastercardservices.com" in url or mode == "benchmark_fact" or "ürün" in source_type or "urun" in source_type


def clean_registry() -> tuple[int, dict[str, int]]:
    registry = read_csv(REGISTRY_PATH)
    if registry.empty:
        return 0, {}
    registry = ensure_columns(registry, REGISTRY_BLOCKED_COLUMNS)
    before = registry.copy()
    counts = {
        "mastercard_rows": 0,
        "blocked_rows": 0,
        "historical_rows": 0,
        "benchmark_rows": 0,
        "weekly_suppressed": 0,
    }
    for idx, row in registry.iterrows():
        if not is_mastercard_registry_row(row):
            continue
        counts["mastercard_rows"] += 1
        registry.loc[idx, "official_source_valid"] = registry.loc[idx, "official_source_valid"] or "True"
        registry.loc[idx, "mvp_active"] = "False"
        registry.loc[idx, "claude_eligible"] = "False"
        registry.loc[idx, "weekly_collection_enabled"] = "False"
        registry.loc[idx, "strategic_partner_priority"] = "Kritik"
        registry.loc[idx, "coverage_priority"] = "Kritik"
        registry.loc[idx, "institution_type"] = "Global Ödeme Ağı"
        registry.loc[idx, "institution_group"] = "Global Ödeme Ağları"
        registry.loc[idx, "coverage_scope"] = "Kritik Stratejik Ödeme Ağı ve Teknoloji Ortağı"

        if row_is_legacy(row):
            counts["historical_rows"] += 1
            registry.loc[idx, "active"] = "True"
            registry.loc[idx, "collection_method"] = "static_scrape"
            registry.loc[idx, "collector_capability"] = "static_scrape"
            registry.loc[idx, "collector_accessible"] = "True"
            registry.loc[idx, "extraction_structurally_valid"] = "True"
            registry.loc[idx, "source_validation_status"] = "stale_or_pre_cutoff"
            registry.loc[idx, "mvp_status"] = "historical_resolution_only"
            registry.loc[idx, "monitoring_mode"] = "historical_resolution"
            registry.loc[idx, "source_recovery_status"] = "Accessible"
            registry.loc[idx, "retry_cadence"] = ""
            registry.loc[idx, "blocked_status_notes"] = "Legacy resolver only; excluded from weekly recent-item discovery."
            continue

        if row_is_services_benchmark(row):
            counts["benchmark_rows"] += 1
            registry.loc[idx, "active"] = registry.loc[idx, "active"] or "True"
            registry.loc[idx, "monitoring_mode"] = "benchmark_monitoring"
            registry.loc[idx, "source_recovery_status"] = "Accessible"
            registry.loc[idx, "weekly_collection_enabled"] = "False"
            registry.loc[idx, "collector_accessible"] = registry.loc[idx, "collector_accessible"] or "True"
            registry.loc[idx, "extraction_structurally_valid"] = registry.loc[idx, "extraction_structurally_valid"] or "True"
            registry.loc[idx, "mvp_status"] = "Benchmark only"
            registry.loc[idx, "blocked_status_notes"] = "Benchmark/capability surface; never creates recent developments by itself."
            continue

        counts["blocked_rows"] += 1
        registry.loc[idx, "monitoring_mode"] = "blocked_source_watch"
        registry.loc[idx, "source_recovery_status"] = "Persistently Blocked"
        registry.loc[idx, "weekly_collection_enabled"] = "False"
        registry.loc[idx, "collector_accessible"] = "False"
        registry.loc[idx, "extraction_structurally_valid"] = "False"
        registry.loc[idx, "collector_capability"] = registry.loc[idx, "collector_capability"] or "browser_required"
        registry.loc[idx, "collection_method"] = registry.loc[idx, "collection_method"] or "browser_required"
        registry.loc[idx, "retry_cadence"] = registry.loc[idx, "retry_cadence"] or "monthly"
        registry.loc[idx, "next_retry_at"] = registry.loc[idx, "next_retry_at"] or default_next_retry(30)
        registry.loc[idx, "consecutive_access_denied"] = registry.loc[idx, "consecutive_access_denied"] or "2"
        registry.loc[idx, "last_access_denied_at"] = registry.loc[idx, "last_access_denied_at"] or today_iso()
        registry.loc[idx, "mvp_status"] = "blocked_official_source"
        registry.loc[idx, "blocked_status_notes"] = (
            "Official Mastercard current-source route is persistently access-denied; monitor via manual official evidence "
            "and representative monthly recovery checks."
        )
        if should_skip_mastercard_weekly_source(registry.loc[idx]):
            counts["weekly_suppressed"] += 1

    changed_cells = int((before.astype(str) != registry.astype(str)).sum().sum())
    write_csv(REGISTRY_PATH, registry)
    return changed_cells, counts


def migrate_inspection_table(path: Path) -> tuple[int, int]:
    df = read_csv(path)
    if df.empty:
        write_csv(path, pd.DataFrame(columns=INSPECTION_EXTRA_COLUMNS))
        return 0, 0
    original_columns = list(df.columns)
    df = ensure_columns(df, INSPECTION_EXTRA_COLUMNS)
    before = df.copy()
    cleared_dates = 0
    for idx, row in df.iterrows():
        url = clean(row.get("item_url") or row.get("candidate_url") or row.get("seed_url") or row.get("resolved_item_url"))
        role = clean(row.get("content_role"))
        notes = clean(row.get("notes"))
        old_date = clean(row.get("publication_date"))
        unverified_seed = (
            is_search_page_url(url)
            or role == "Keşif Seed'i"
            or "dry-run seed" in notes.casefold()
            or clean(row.get("publication_date_verified")).casefold() == "false"
            or clean(row.get("date_verified")).casefold() == "false"
        )
        product_root = is_generic_product_root_url(url) or role in {"Benchmark Fact", "Benchmark Bilgisi"}
        context = role in {"Bağlamsal Veri", "Tarihsel Bağlam", "Tarihsel Teknoloji Bağlamı"}
        noise = role == "Kapsam Dışı" or clean(row.get("rejection_reason")) in {"brand_lifestyle_or_consumer_noise", "brand_lifestyle_or_corporate_noise"}

        if old_date and unverified_seed:
            df.loc[idx, "seed_date_hint"] = df.loc[idx, "seed_date_hint"] or old_date
            df.loc[idx, "seed_date_hint_source"] = df.loc[idx, "seed_date_hint_source"] or "unverified_seed_or_search_surface"
            df.loc[idx, "seed_date_verified"] = "False"
            for column in ["publication_date", "launch_date", "recency_basis_date", "recency_basis_type", "date_confidence"]:
                if column in df.columns:
                    df.loc[idx, column] = ""
            cleared_dates += 1
        elif "seed_date_verified" in df.columns:
            df.loc[idx, "seed_date_verified"] = df.loc[idx, "seed_date_verified"] or "False"

        df.loc[idx, "retained_as_evidence"] = "False" if noise else bool_text(unverified_seed or product_root or context or True)
        df.loc[idx, "item_level_verified"] = "False" if unverified_seed or product_root else clean(row.get("item_level_verified")) or "False"
        df.loc[idx, "benchmark_eligible"] = bool_text(product_root)
        df.loc[idx, "context_eligible"] = bool_text(context and not product_root)
        df.loc[idx, "recent_item_eligible"] = "False"
        df.loc[idx, "claude_eligible"] = "False"
        previous_accepted = clean(row.get("accepted"))
        if "accepted" in df.columns:
            df.loc[idx, "accepted"] = "False"
        df.loc[idx, "accepted_deprecated"] = clean(row.get("accepted_deprecated")) or previous_accepted or "False"
        df.loc[idx, "intake_status"] = "Rejected" if noise else ("Unresolved" if unverified_seed else ("Benchmark" if product_root else "Context"))
        if "strategic_priority_score" in df.columns and unverified_seed:
            df.loc[idx, "strategic_priority_score"] = "0"

    changed_cells = int((before.astype(str) != df.astype(str)).sum().sum())
    preferred = original_columns + [column for column in INSPECTION_EXTRA_COLUMNS if column not in original_columns]
    write_csv(path, df, preferred)
    return changed_cells, cleared_dates


def clean_fallback_items() -> tuple[int, dict[str, int]]:
    df = read_csv(FALLBACK_ITEMS_PATH)
    if df.empty:
        write_csv(FALLBACK_ITEMS_PATH, pd.DataFrame(columns=FALLBACK_EXTRA_COLUMNS))
        return 0, {}
    original_columns = list(df.columns)
    df = ensure_columns(df, FALLBACK_EXTRA_COLUMNS)
    before = df.copy()
    counts = {"unclassified": 0, "provisional": 0, "recent_item_eligible": 0}
    for idx, row in df.iterrows():
        recent = clean(row.get("recent_item_eligible")) == "True"
        df.loc[idx, "dataset_role"] = "historical_resolution"
        df.loc[idx, "production_recent_eligible"] = "False"
        if recent:
            counts["recent_item_eligible"] += 1
            continue
        taxonomy = high_precision_historical_taxonomy(
            clean(row.get("article_title") or row.get("listing_title")),
            clean(row.get("canonical_url") or row.get("item_url")),
            "",
            clean(row.get("named_products")),
        )
        for key, value in taxonomy.items():
            df.loc[idx, key] = value
        df.loc[idx, "strategic_priority_score"] = "0"
        df.loc[idx, "recent_item_eligible"] = "False"
        df.loc[idx, "claude_eligible"] = "False"
        if taxonomy["taxonomy_status"] == "Unclassified":
            counts["unclassified"] += 1
            df.loc[idx, "network_signal_type"] = ""
            df.loc[idx, "network_layer"] = ""
            df.loc[idx, "deployment_scope"] = ""
        else:
            counts["provisional"] += 1
    changed_cells = int((before.astype(str) != df.astype(str)).sum().sum())
    preferred = original_columns + [column for column in FALLBACK_EXTRA_COLUMNS if column not in original_columns]
    write_csv(FALLBACK_ITEMS_PATH, df, preferred)
    return changed_cells, counts


def registry_row_by_source_id(registry: pd.DataFrame, source_id: str) -> pd.Series | None:
    if registry.empty or "source_id" not in registry.columns:
        return None
    subset = registry[registry["source_id"].astype(str).eq(source_id)]
    if subset.empty:
        return None
    return subset.iloc[0]


def create_recovery_watch() -> tuple[int, int]:
    registry = read_csv(REGISTRY_PATH)
    existing = read_csv(RECOVERY_WATCH_PATH)
    existing_by_id = {clean(row.get("source_id")): row.to_dict() for _, row in existing.iterrows()} if not existing.empty else {}
    reps = [
        ("REG-071", "EEMEA Newsroom", "EEMEA Newsroom"),
        ("REG-230", "Global/US Press", "Global/US Press"),
        ("REG-211", "Direct article route", "Merchant Cloud direct route"),
        ("REG-206", "Product route", "Commercial product route"),
    ]
    rows = []
    for source_id, representative, family in reps:
        source = registry_row_by_source_id(registry, source_id)
        previous = existing_by_id.get(source_id, {})
        source_name = clean(source.get("source_name")) if source is not None else previous.get("source_name", "")
        url = clean(source.get("url")) if source is not None else previous.get("official_url", "")
        mode = clean(source.get("monitoring_mode")) if source is not None else "blocked_source_watch"
        status = clean(source.get("source_recovery_status")) if source is not None else "Persistently Blocked"
        if source_id == "REG-206":
            status = "Accessible"
            mode = "benchmark_monitoring"
        row = {
            "source_id": source_id,
            "source_name": source_name,
            "representative_source": representative,
            "source_family": family,
            "official_url": url,
            "monitoring_mode": mode or "blocked_source_watch",
            "source_recovery_status": status or "Persistently Blocked",
            "retry_cadence": previous.get("retry_cadence") or ("monthly" if source_id != "REG-206" else "quarterly"),
            "last_retry_at": previous.get("last_retry_at", ""),
            "next_retry_at": previous.get("next_retry_at") or default_next_retry(30),
            "last_access_result": previous.get("last_access_result") or ("accessible_benchmark_only" if source_id == "REG-206" else "access_denied"),
            "consecutive_access_denied": previous.get("consecutive_access_denied") or ("0" if source_id == "REG-206" else "2"),
            "last_success_at": previous.get("last_success_at", "") or (today_iso() if source_id == "REG-206" else ""),
            "mvp_active": "False",
            "claude_eligible": "False",
            "notes": previous.get("notes")
            or (
                "Representative recovery row; do not fan out to all blocked Mastercard sources unless this recovers."
                if source_id != "REG-206"
                else "Representative product route for benchmark access only; not a weekly development source."
            ),
        }
        rows.append(row)
    output = pd.DataFrame(rows)
    before = existing.reindex(columns=RECOVERY_WATCH_COLUMNS).fillna("") if not existing.empty else pd.DataFrame(columns=RECOVERY_WATCH_COLUMNS)
    changed = int(not before.equals(output.reindex(columns=RECOVERY_WATCH_COLUMNS).fillna("")))
    write_csv(RECOVERY_WATCH_PATH, output, RECOVERY_WATCH_COLUMNS)
    return changed, len(output)


def ensure_manual_artifacts() -> tuple[int, int]:
    created = 0
    for path, columns in [(MANUAL_INBOX_PATH, MANUAL_INBOX_COLUMNS), (MANUAL_VERIFIED_PATH, MANUAL_VERIFIED_COLUMNS)]:
        if not path.exists():
            write_csv(path, pd.DataFrame(columns=columns), columns)
            created += 1
            continue
        df = read_csv(path)
        before_columns = list(df.columns)
        write_csv(path, df, columns)
        if before_columns != columns:
            created += 1
    return created, len(read_csv(MANUAL_VERIFIED_PATH))


def run() -> dict[str, object]:
    registry_changes, registry_counts = clean_registry()
    inspection_changes, inspection_dates = migrate_inspection_table(CANDIDATE_INSPECTION_PATH)
    browser_changes, browser_dates = migrate_inspection_table(BROWSER_INSPECTION_PATH)
    seed_changes, seed_dates = migrate_inspection_table(SEED_RESOLUTION_PATH)
    fallback_changes, fallback_counts = clean_fallback_items()
    watch_changed, watch_rows = create_recovery_watch()
    manual_artifact_changes, verified_manual_candidates = ensure_manual_artifacts()
    return {
        "registry_changes": registry_changes,
        "registry_counts": registry_counts,
        "inspection_changes": inspection_changes,
        "browser_changes": browser_changes,
        "seed_changes": seed_changes,
        "synthetic_dates_removed": inspection_dates + browser_dates + seed_dates,
        "fallback_changes": fallback_changes,
        "fallback_counts": fallback_counts,
        "recovery_watch_changed": watch_changed,
        "recovery_watch_rows": watch_rows,
        "manual_artifact_changes": manual_artifact_changes,
        "verified_manual_candidates": verified_manual_candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize Mastercard in blocked official-source operating mode.")
    parser.add_argument("--repeat", type=int, default=1, help="Run the idempotent cleanup multiple times.")
    args = parser.parse_args()
    result = {}
    for idx in range(args.repeat):
        result = run()
        print(f"Run {idx + 1}:")
        for key, value in result.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
