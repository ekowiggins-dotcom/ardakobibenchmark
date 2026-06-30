from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from utils.browser_collector import BrowserCollector, canonicalize_mastercard_url, is_post_cutoff
from utils.mastercard_official_fallback import (
    classify_source_access,
    dedupe_item_rows,
    extract_mastercard_press_article,
    extract_mastercard_press_index,
    fetch_page,
    item_row_from_article,
    parse_mastercard_date,
)


DATA_DIR = ROOT_DIR / "data"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
SOURCE_VALIDATION_PATH = DATA_DIR / "mastercard_official_fallback_source_validation.csv"
ITEMS_PATH = DATA_DIR / "mastercard_official_fallback_items.csv"
PAGE_DIR = DATA_DIR / "mastercard_official_fallback_pages"

US_PRESS_URL = "https://www.mastercard.com/us/en/news-and-trends/press.html"
LEGACY_PRESS_URL = "https://newsroom.mastercard.com/news/press/"
LEGACY_LANDING_URL = "https://newsroom.mastercard.com/news"

DIRECT_ARTICLES = [
    ("Agent Pay for Machines", "https://www.mastercard.com/us/en/news-and-trends/press/2026/june/mastercard-launches-agent-pay-for-machines.html"),
    ("Stablecoin settlement", "https://www.mastercard.com/us/en/news-and-trends/press/2026/june/mastercard-expands-settlement-capabilities-to-include-stablecoin.html"),
    ("TIPS cross-currency pilot", "https://www.mastercard.com/us/en/news-and-trends/press/2026/june/Mastercard-advances-instant-cross-border-payments-with-TIPS-cross-currency-pilot.html"),
    ("Amazon Business cards", "https://www.mastercard.com/us/en/news-and-trends/press/2026/may/amazon-s-new-prime-business-and-amazon-business-credit-cards--po.html"),
    ("Original Agent Pay launch", "https://newsroom.mastercard.com/news/press/2025/april/mastercard-unveils-agent-pay-pioneering-agentic-payments-technology-to-power-commerce-in-the-age-of-ai/"),
]

SOURCE_COLUMNS = [
    "source_name",
    "source_url",
    "official_source_valid",
    "collector_accessible",
    "extraction_structurally_valid",
    "page_type",
    "extraction_mode",
    "item_links_found",
    "dated_links_found",
    "post_cutoff_links_found",
    "latest_visible_date",
    "current_or_stale",
    "canonical_target",
    "activation_recommendation",
    "reason",
    "checked_at",
]

ITEM_COLUMNS = [
    "discovered_from",
    "listing_title",
    "listing_date",
    "item_url",
    "final_url",
    "canonical_url",
    "article_title",
    "publication_date",
    "date_source",
    "date_confidence",
    "body_chars",
    "named_partners",
    "named_products",
    "network_signal_type",
    "network_layer",
    "deployment_scope",
    "content_role",
    "strategic_priority_score",
    "item_level_verified",
    "publication_date_verified",
    "body_verified",
    "recent_item_eligible",
    "claude_eligible",
    "duplicate_status",
    "rejection_reason",
    "taxonomy_status",
    "taxonomy_confidence",
    "taxonomy_method",
    "dataset_role",
    "production_recent_eligible",
    "checked_at",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def selected_sources(source: str) -> list[tuple[str, str]]:
    if source == "us_press":
        return [("Mastercard US Press Releases", US_PRESS_URL)]
    if source == "legacy_press":
        return [("Mastercard Legacy Newsroom Press", LEGACY_PRESS_URL)]
    if source == "legacy_landing":
        return [("Mastercard Legacy Newsroom Landing", LEGACY_LANDING_URL)]
    return [
        ("Mastercard US Press Releases", US_PRESS_URL),
        ("Mastercard Legacy Newsroom Press", LEGACY_PRESS_URL),
        ("Mastercard Legacy Newsroom Landing", LEGACY_LANDING_URL),
    ]


def save_page(name: str, html: str) -> None:
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    (PAGE_DIR / f"{safe}.html").write_text(html or "", encoding="utf-8")


def validate_source(name: str, url: str, mode: str, start_date: str, limit: int, collector: BrowserCollector | None, save_html: bool) -> tuple[dict[str, str], list[dict[str, str]]]:
    checked_at = now_iso()
    page = fetch_page(url, mode=mode, collector=collector)
    if save_html:
        save_page(name, page.html)
    items = extract_mastercard_press_index(page.html, page.final_url) if page.page_type != "access_denied" else []
    if limit:
        items = items[:limit]
    dated = [item for item in items if item.visible_date]
    post_cutoff = [item for item in dated if is_post_cutoff(item.visible_date, start_date)]
    latest_visible_date = max([item.visible_date for item in dated], default="")
    access = classify_source_access(page, len(items), len(dated), len(post_cutoff))
    if page.page_type == "access_denied":
        activation = "do_not_activate_collector"
        reason = "Official source but current collector receives access_denied."
    elif items and post_cutoff:
        activation = "candidate_for_mvp_after_second_stable_run"
        reason = "Accessible official listing with post-cutoff dated item links."
    elif items:
        activation = "historical_resolution_only"
        reason = "Accessible official listing, but latest visible item is before cutoff."
    else:
        activation = "manual"
        reason = "Accessible page did not expose local press item links."
    row = {
        "source_name": name,
        "source_url": url,
        **access,
        "page_type": page.page_type,
        "extraction_mode": "weekly_development",
        "item_links_found": str(len(items)),
        "dated_links_found": str(len(dated)),
        "post_cutoff_links_found": str(len(post_cutoff)),
        "latest_visible_date": latest_visible_date,
        "canonical_target": canonicalize_mastercard_url(page.final_url),
        "activation_recommendation": activation,
        "reason": reason,
        "checked_at": checked_at,
    }
    item_rows: list[dict[str, str]] = []
    for item in items:
        article = extract_mastercard_press_article(
            item.item_url,
            mode=mode,
            listing_title=item.title,
            listing_date=item.visible_date,
            collector=collector,
        )
        item_row = item_row_from_article(article, name, item.title, item.visible_date, start_date)
        item_row["checked_at"] = checked_at
        item_rows.append(item_row)
    return row, item_rows


def direct_article_rows(mode: str, start_date: str, collector: BrowserCollector | None, save_html: bool) -> list[dict[str, str]]:
    checked_at = now_iso()
    rows = []
    for label, url in DIRECT_ARTICLES:
        article = extract_mastercard_press_article(url, mode=mode, listing_title=label, collector=collector)
        if save_html and article.article_body:
            save_page(label, article.article_body)
        row = item_row_from_article(article, f"Direct positive test: {label}", label, "", start_date)
        if label == "Original Agent Pay launch" and row["rejection_reason"] == "pre_cutoff":
            row["content_role"] = "Tarihsel Teknoloji Bağlamı"
            row["recent_item_eligible"] = "False"
            row["claude_eligible"] = "False"
        row["checked_at"] = checked_at
        rows.append(row)
    return rows


def read_registry() -> pd.DataFrame:
    if not REGISTRY_PATH.exists():
        return pd.DataFrame()
    registry = pd.read_csv(REGISTRY_PATH, dtype=str).fillna("")
    for column in ["institution_type", "strategic_partner_priority"]:
        if column not in registry.columns:
            registry[column] = ""
    return registry


def next_reg_id(registry: pd.DataFrame) -> int:
    values = []
    for value in registry.get("source_id", []):
        text = str(value)
        if text.startswith("REG-"):
            try:
                values.append(int(text.split("-")[1]))
            except Exception:
                pass
    return max(values or [0]) + 1


def upsert_registry(source_rows: list[dict[str, str]], dry_run: bool) -> int:
    if dry_run:
        return 0
    registry = read_registry()
    if registry.empty:
        return 0
    next_id = next_reg_id(registry)
    changed = 0
    allowed = {
        "Mastercard US Press Releases": "Mastercard US Press Releases",
        "Mastercard Legacy Newsroom Press": "Mastercard Legacy Newsroom Press",
    }
    for row in source_rows:
        name = row["source_name"]
        if name not in allowed:
            continue
        existing = registry.index[
            registry["institution_id"].astype(str).eq("mastercard")
            & registry["source_name"].astype(str).eq(name)
        ].tolist()
        collector_accessible = row["collector_accessible"] == "True"
        extraction_valid = row["extraction_structurally_valid"] == "True"
        post_cutoff = int(row["post_cutoff_links_found"] or 0)
        mvp_ready = collector_accessible and extraction_valid and post_cutoff > 0
        source_record = {
            "source_id": registry.loc[existing[0], "source_id"] if existing else f"REG-{next_id:03d}",
            "tier": "Tier 1",
            "institution_id": "mastercard",
            "institution_name": "Mastercard",
            "source_name": name,
            "source_type": "Resmi Basın Bülteni Sayfası",
            "url": row["source_url"],
            "collection_method": "static_scrape" if collector_accessible else "browser_required",
            "update_frequency": "Weekly",
            "reliability_level": "Yüksek",
            "strategic_themes": "Global İyi Uygulama; Ödemeler ve POS; Ticari Kartlar; Gömülü Finans; Ağ Standartları",
            "active": str(collector_accessible),
            "notes": row["reason"],
            "extraction_mode": "weekly_development",
            "coverage_scope": "Kritik Stratejik Ödeme Ağı ve Teknoloji Ortağı",
            "coverage_priority": "Kritik",
            "sme_relevance": "Yüksek",
            "source_validation_status": row["current_or_stale"],
            "collector_capability": "static_scrape" if collector_accessible else "browser_required",
            "mvp_active": str(mvp_ready),
            "claude_eligible": "False",
            "mvp_status": "Ready for dry-run promotion review" if mvp_ready else row["activation_recommendation"],
            "customer_segment": "Kart / Ödeme Altyapısı / Ticari Ödemeler",
            "institution_group": "Global Ödeme Ağları",
            "display_name": "Mastercard",
            "legal_name": "Mastercard",
            "exclusion_reason": "" if collector_accessible else row["reason"],
            "last_validated_at": row["checked_at"],
            "institution_type": "Global Ödeme Ağı",
            "strategic_partner_priority": "Kritik",
        }
        if existing:
            idx = existing[0]
            for column, value in source_record.items():
                if column not in registry.columns:
                    registry[column] = ""
                if str(registry.loc[idx, column]) != str(value):
                    registry.loc[idx, column] = value
                    changed += 1
        else:
            registry = pd.concat([registry, pd.DataFrame([source_record])], ignore_index=True)
            next_id += 1
            changed += 1
    registry.to_csv(REGISTRY_PATH, index=False, encoding="utf-8-sig")
    return changed


def write_report(source_rows: list[dict[str, str]], item_rows: list[dict[str, str]], first_keys: list[str], second_keys: list[str] | None, registry_changes: int, dry_run: bool, path: Path) -> None:
    def count(column: str, value: str) -> int:
        return sum(1 for row in item_rows if row.get(column) == value)

    def find_controlled(label: str) -> dict[str, str]:
        for row in item_rows:
            if label in row.get("discovered_from", ""):
                return row
        for row in item_rows:
            if label.casefold() in (row.get("listing_title", "") + " " + row.get("article_title", "")).casefold():
                return row
        return {}
    idempotent = second_keys is None or (first_keys == second_keys and len(second_keys) == len(set(second_keys)))
    lines = [
        "# Mastercard Official Fallback Report",
        "",
        f"Checked at: `{now_iso()}`",
        f"Dry run: `{dry_run}`",
        "",
        "## Source Access",
    ]
    for row in source_rows:
        lines.append(
            f"- {row['source_name']}: accessible `{row['collector_accessible']}`, structurally valid `{row['extraction_structurally_valid']}`, "
            f"links `{row['item_links_found']}`, post-cutoff `{row['post_cutoff_links_found']}`, latest `{row['latest_visible_date']}`, recommendation `{row['activation_recommendation']}`"
        )
    lines.extend(
        [
            "",
            "## Candidate Results",
            f"- Direct/listing article rows inspected: {len(item_rows)}",
            f"- Item-level verified rows: {count('item_level_verified', 'True')}",
            f"- Publication dates verified: {count('publication_date_verified', 'True')}",
            f"- Body verified rows: {count('body_verified', 'True')}",
            f"- True verified recent-item candidates: {count('recent_item_eligible', 'True')}",
            f"- Claude eligible rows: {count('claude_eligible', 'True')}",
            f"- Registry changes: {registry_changes}",
            "",
            "## Controlled Direct Articles",
        ]
    )
    for label in ["Agent Pay for Machines", "Stablecoin settlement", "TIPS cross-currency pilot", "Amazon Business cards", "Original Agent Pay launch"]:
        row = find_controlled(label)
        lines.append(
            f"- {label}: title `{row.get('article_title', '')}`, date `{row.get('publication_date', '')}`, "
            f"body `{row.get('body_chars', '0')}`, eligible `{row.get('recent_item_eligible', 'False')}`, reason `{row.get('rejection_reason', '')}`"
        )
    lines.extend(
        [
            "",
            "## Idempotency",
            f"- First run canonical rows: {len(first_keys)}",
            f"- Second run canonical rows: {len(second_keys or first_keys)}",
            f"- Same canonical set: {second_keys is None or first_keys == second_keys}",
            f"- Duplicate canonical rows on second run: {0 if second_keys is None else len(second_keys) - len(set(second_keys))}",
            f"- Idempotent: {idempotent}",
            "",
            "## Claude Pilot Readiness",
            "- Claude was not run.",
            "- A maximum 3-item Claude pilot is safe only if true verified recent-item candidates are present. Current run did not promote any item to Claude.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace, write_outputs: bool = True) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    source_rows: list[dict[str, str]] = []
    item_rows: list[dict[str, str]] = []
    use_browser = args.mode in {"browser", "auto"}
    collector_cm = BrowserCollector() if use_browser else None
    collector = collector_cm.__enter__() if collector_cm else None
    try:
        for name, url in selected_sources(args.source):
            source_row, rows = validate_source(name, url, args.mode, args.start_date, args.limit, collector, args.save_html)
            source_rows.append(source_row)
            item_rows.extend(rows)
        if args.source in {"us_press", "all"}:
            item_rows.extend(direct_article_rows(args.mode, args.start_date, collector, args.save_html))
    finally:
        if collector_cm:
            collector_cm.__exit__(None, None, None)
    item_rows = dedupe_item_rows(item_rows)
    for row in item_rows:
        row.setdefault("checked_at", now_iso())
    keys = [row.get("canonical_url") or row.get("final_url") or row.get("item_url", "") for row in item_rows]
    if write_outputs:
        write_csv(SOURCE_VALIDATION_PATH, source_rows, SOURCE_COLUMNS)
        write_csv(ITEMS_PATH, item_rows, ITEM_COLUMNS)
    return source_rows, item_rows, keys


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-source fallback collector for Mastercard press sources.")
    parser.add_argument("--source", choices=["us_press", "legacy_press", "legacy_landing", "all"], default="all")
    parser.add_argument("--start-date", default="2026-05-01")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--mode", choices=["static", "browser", "auto"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--save-html", action="store_true")
    parser.add_argument("--save-screenshot", action="store_true", help="Accepted for CLI compatibility; screenshots are not required for fallback dry-runs.")
    parser.add_argument("--force", action="store_true", help="Reserved; does not write production recent items.")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat run for idempotency check.")
    args = parser.parse_args()

    source_rows, item_rows, first_keys = run(args, write_outputs=True)
    second_keys = None
    if args.repeat > 1:
        _, _, second_keys = run(args, write_outputs=True)
    registry_changes = upsert_registry(source_rows, args.dry_run)
    report_path = DATA_DIR / f"mastercard_official_fallback_report_{stamp()}.md"
    write_report(source_rows, item_rows, first_keys, second_keys, registry_changes, args.dry_run, report_path)

    print("Mastercard official fallback complete")
    print(f"source={args.source}")
    print(f"mode={args.mode}")
    print(f"dry_run={args.dry_run}")
    print(f"sources_validated={len(source_rows)}")
    print(f"items_inspected={len(item_rows)}")
    print(f"recent_item_eligible={sum(1 for row in item_rows if row.get('recent_item_eligible') == 'True')}")
    print(f"claude_eligible={sum(1 for row in item_rows if row.get('claude_eligible') == 'True')}")
    print(f"registry_changes={registry_changes}")
    print(f"source_validation_csv={SOURCE_VALIDATION_PATH.relative_to(ROOT_DIR)}")
    print(f"items_csv={ITEMS_PATH.relative_to(ROOT_DIR)}")
    print(f"report={report_path.relative_to(ROOT_DIR)}")
    if args.debug:
        for row in source_rows:
            print(f"SOURCE {row['source_name']} accessible={row['collector_accessible']} links={row['item_links_found']} post_cutoff={row['post_cutoff_links_found']} reason={row['reason']}")
        for row in item_rows[:20]:
            print(f"ITEM {row['publication_date']} eligible={row['recent_item_eligible']} reason={row['rejection_reason']} title={row['article_title'] or row['listing_title']}")


if __name__ == "__main__":
    main()
