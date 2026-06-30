from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from pipeline.validate_mastercard_sources import classify_mastercard_item
from utils.browser_collector import (
    BrowserCollector,
    canonicalize_mastercard_url,
    clean_html_text,
    detect_mastercard_page_type,
    extract_article_links_from_page,
    is_generic_product_root_url,
    is_item_level_mastercard_url,
    is_post_cutoff,
    is_search_page_url,
    mastercard_url_key,
    passes_mastercard_article_gate,
    resolve_mastercard_seed_to_articles,
    title_from_html,
)


DATA_DIR = ROOT_DIR / "data"
RESOLUTION_PATH = DATA_DIR / "mastercard_browser_seed_resolution.csv"
INSPECTION_PATH = DATA_DIR / "mastercard_browser_candidate_inspection.csv"

RESOLUTION_COLUMNS = [
    "source_family",
    "discovery_stage",
    "page_type",
    "discovery_origin",
    "expected_title",
    "seed_url",
    "resolved_item_url",
    "seed_page_type",
    "links_discovered",
    "candidate_title",
    "candidate_url",
    "title_match_score",
    "candidate_page_type",
    "final_canonical_url",
    "publication_date",
    "date_source",
    "date_confidence",
    "body_chars",
    "resolution_status",
    "discovery_seed_accepted",
    "item_level_verified",
    "publication_date_verified",
    "body_verified",
    "recent_item_eligible",
    "claude_eligible",
    "rejection_reason",
    "checked_at",
]

INSPECTION_COLUMNS = [
    "source_family",
    "discovery_stage",
    "discovery_origin",
    "seed_url",
    "resolved_item_url",
    "discovery_seed_accepted",
    "item_title",
    "item_url",
    "canonical_url",
    "publication_date",
    "date_verified",
    "page_type",
    "body_chars",
    "named_partner",
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
    "proposed_destination",
    "duplicate_status",
    "notes",
]

SMOKE_TARGETS = [
    {
        "source_family": "Merchant Cloud",
        "expected_title": "Network International Jordan launches Click to Pay through Mastercard Merchant Cloud",
        "seed_url": "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2026/may/network-international-jordan-launches-click-to-pay-through-mastercard-merchant-cloud-expanding-access-to-secure-digital-payments/",
        "expected_keywords": ["Network International Jordan", "Click to Pay", "Merchant Cloud", "Mastercard"],
        "origin": "manual_seed",
    },
    {
        "source_family": "Agent Pay",
        "expected_title": "Mastercard launches Agent Pay as agentic AI reshapes digital commerce",
        "seed_url": "https://www.mastercard.com/news/press/?q=Agent+Pay",
        "expected_keywords": ["Agent Pay", "agentic AI", "digital commerce", "Mastercard"],
        "origin": "manual_seed",
    },
    {
        "source_family": "Tokenization and Network Credentials",
        "expected_title": "Mastercard expands network token and credential lifecycle capabilities for issuers and merchants",
        "seed_url": "https://www.mastercard.com/news/press/?q=tokenization+network+credentials",
        "expected_keywords": ["tokenization", "token", "credential lifecycle", "issuers", "merchants", "network credentials"],
        "origin": "manual_seed",
    },
    {
        "source_family": "EEMEA Newsroom",
        "expected_title": "Mastercard EEMEA newsroom listing",
        "seed_url": "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/",
        "expected_keywords": ["Mastercard", "EEMEA", "press release"],
        "origin": "newsroom_listing",
    },
    {
        "source_family": "Global Newsroom",
        "expected_title": "Mastercard global newsroom listing",
        "seed_url": "https://www.mastercard.com/news/press/",
        "expected_keywords": ["Mastercard", "press release"],
        "origin": "newsroom_listing",
    },
    {
        "source_family": "Commercial Cards / Virtual Cards",
        "expected_title": "Mastercard commercial cards and virtual cards support supplier payment automation",
        "seed_url": "https://www.mastercard.com/global/en/business/payment-solutions/virtual-cards.html",
        "expected_keywords": ["commercial cards", "virtual cards", "supplier payments"],
        "origin": "product_related_content",
    },
]


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def named_partner_for(title: str, text: str) -> str:
    blob = f"{title} {text}"
    if re.search(r"network international jordan", blob, re.I):
        return "Network International Jordan"
    for pattern in [r"\bSantander\b", r"\bOpenAI\b", r"\bMicrosoft\b", r"\bVisa\b", r"\bGaranti BBVA\b", r"\bAkbank\b"]:
        match = re.search(pattern, blob, re.I)
        if match:
            return match.group(0)
    return ""


def discovery_stage_for(seed_url: str, page_type: str, gate_passed: bool, product_benchmark: bool, unresolved: bool) -> str:
    if product_benchmark:
        return "Product Benchmark"
    if gate_passed:
        return "Resolved Article"
    if unresolved and (is_search_page_url(seed_url) or page_type in {"search_page", "listing_page", "access_denied"}):
        return "Seed"
    if page_type == "listing_page":
        return "Listing Candidate"
    if page_type in {"access_denied", "empty_shell", "unknown"}:
        return "Rejected"
    return "Context Only"


def inspection_row_for_resolution(target: dict[str, object], resolution: dict[str, str], verified: list[dict[str, object]]) -> list[dict[str, str]]:
    rows = []
    source_family = str(target["source_family"])
    seed_url = str(target["seed_url"])
    product_benchmark = is_generic_product_root_url(seed_url)
    if verified:
        for item in verified:
            page = item["page"]
            gate = item["gate"]
            body = clean_html_text(page.html) or page.body_text
            cls = classify_mastercard_item(gate.title, gate.canonical_url, body, gate.publication_date)
            recent = bool(gate.passed)
            rows.append(
                {
                    "source_family": source_family,
                    "discovery_stage": "Resolved Article",
                    "discovery_origin": str(target.get("origin", "")),
                    "seed_url": seed_url,
                    "resolved_item_url": gate.canonical_url,
                    "discovery_seed_accepted": "True",
                    "item_title": gate.title,
                    "item_url": page.final_url,
                    "canonical_url": gate.canonical_url,
                    "publication_date": gate.publication_date,
                    "date_verified": str(bool(gate.publication_date and is_post_cutoff(gate.publication_date))),
                    "page_type": page.page_type,
                    "body_chars": str(gate.body_chars),
                    "named_partner": named_partner_for(gate.title, body),
                    "network_signal_type": str(cls["network_signal_type"]),
                    "network_layer": str(cls["network_layer"]),
                    "deployment_scope": str(cls["deployment_scope"]),
                    "content_role": str(cls["content_role"]),
                    "strategic_priority_score": str(cls["strategic_priority_score"]),
                    "item_level_verified": "True",
                    "publication_date_verified": str(bool(gate.publication_date and is_post_cutoff(gate.publication_date))),
                    "body_verified": str(gate.body_chars >= 500),
                    "recent_item_eligible": str(recent),
                    "claude_eligible": "False",
                    "proposed_destination": str(cls["proposed_destination"]),
                    "duplicate_status": "canonical_unique",
                    "notes": "Verified by browser smoke test; not written to production recent_items.",
                }
            )
        return rows

    title = resolution.get("candidate_title") or str(target["expected_title"])
    canonical_url = resolution.get("final_canonical_url") or canonicalize_mastercard_url(seed_url)
    publication_date = resolution.get("publication_date", "")
    page_type = resolution.get("candidate_page_type") or resolution.get("seed_page_type", "unknown")
    if product_benchmark:
        content_role = "Benchmark Bilgisi"
        destination = "Benchmark Fact"
        stage_note = "Evergreen product page; outside recent-development flow."
        score = "0"
        signal = "Aktarılabilir Mastercard Kabiliyeti"
        layer = "Ticari Kartlar"
        deployment = "Global"
    else:
        content_role = "Keşif Seed'i"
        destination = "Keşif / Çözümleme Bekliyor"
        stage_note = f"Not article-verified: {resolution.get('rejection_reason', '')}"
        score = "0"
        signal = "Kapsam Dışı"
        layer = "Diğer"
        deployment = "Belirsiz"
    rows.append(
        {
            "source_family": source_family,
            "discovery_stage": "Product Benchmark" if product_benchmark else "Seed",
            "discovery_origin": str(target.get("origin", "")),
            "seed_url": seed_url,
            "resolved_item_url": "",
            "discovery_seed_accepted": "True",
            "item_title": title,
            "item_url": seed_url,
            "canonical_url": canonical_url,
            "publication_date": publication_date,
            "date_verified": "False",
            "page_type": page_type,
            "body_chars": resolution.get("body_chars", "0"),
            "named_partner": "",
            "network_signal_type": signal,
            "network_layer": layer,
            "deployment_scope": deployment,
            "content_role": content_role,
            "strategic_priority_score": score,
            "item_level_verified": "False",
            "publication_date_verified": "False",
            "body_verified": "False",
            "recent_item_eligible": "False",
            "claude_eligible": "False",
            "proposed_destination": destination,
            "duplicate_status": "seed_or_benchmark_only",
            "notes": stage_note,
        }
    )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def dedupe_inspection_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    dedup: dict[str, dict[str, str]] = {}
    family_tags: dict[str, set[str]] = {}
    for row in rows:
        key = mastercard_url_key(row.get("canonical_url") or row.get("item_url", ""))
        existing = dedup.get(key)
        if existing is None:
            dedup[key] = dict(row)
            family_tags[key] = {row["source_family"]}
            continue
        family_tags[key].add(row["source_family"])
        if row.get("item_level_verified") == "True" and existing.get("item_level_verified") != "True":
            dedup[key] = dict(row)
        elif int(row.get("strategic_priority_score", "0") or 0) > int(existing.get("strategic_priority_score", "0") or 0):
            dedup[key] = dict(row)
    out = []
    for key, row in dedup.items():
        tags = sorted(family_tags.get(key, []))
        if len(tags) > 1:
            row["notes"] = clean(f"{row.get('notes', '')} Source-family tags: {', '.join(tags)}.")
            row["duplicate_status"] = "canonical_collapsed_multi_family"
        out.append(row)
    return sorted(out, key=lambda row: (row["source_family"], row["item_title"]))


def run_once(wait_seconds: float) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    resolution_rows: list[dict[str, str]] = []
    inspection_rows: list[dict[str, str]] = []
    engine = ""
    with BrowserCollector(wait_seconds=wait_seconds) as collector:
        engine = collector.engine
        for target in SMOKE_TARGETS:
            seed_url = str(target["seed_url"])
            source_family = str(target["source_family"])
            expected_title = str(target["expected_title"])
            keywords = list(target["expected_keywords"])  # type: ignore[arg-type]
            if source_family in {"EEMEA Newsroom", "Global Newsroom"}:
                page = collector.get_page(seed_url)
                links = extract_article_links_from_page(page) if page.page_type not in {"access_denied", "empty_shell"} else []
                resolution = {
                    "source_family": source_family,
                    "discovery_stage": "Listing Candidate" if links else "Seed",
                    "page_type": page.page_type,
                    "discovery_origin": str(target.get("origin", "")),
                    "expected_title": expected_title,
                    "seed_url": seed_url,
                    "resolved_item_url": "",
                    "seed_page_type": page.page_type,
                    "links_discovered": str(len(links)),
                    "candidate_title": "",
                    "candidate_url": "",
                    "title_match_score": "0.000",
                    "candidate_page_type": page.page_type,
                    "final_canonical_url": canonicalize_mastercard_url(page.final_url),
                    "publication_date": "",
                    "date_source": "",
                    "date_confidence": "",
                    "body_chars": str(len(clean_html_text(page.html) or page.body_text)),
                    "resolution_status": "Listing Extracted" if links else "Unresolved",
                    "discovery_seed_accepted": "True",
                    "item_level_verified": "False",
                    "publication_date_verified": "False",
                    "body_verified": "False",
                    "recent_item_eligible": "False",
                    "claude_eligible": "False",
                    "rejection_reason": "" if links else f"{page.page_type}_no_article_links",
                    "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                }
                resolution_rows.append(resolution)
                inspection_rows.extend(inspection_row_for_resolution(target, resolution, []))
                continue

            resolution, verified = resolve_mastercard_seed_to_articles(
                collector,
                seed_url=seed_url,
                expected_title=expected_title,
                expected_keywords=keywords,
                source_family=source_family,
            )
            product_benchmark = is_generic_product_root_url(seed_url)
            gate_passed = bool(verified)
            resolution["discovery_stage"] = discovery_stage_for(
                seed_url,
                resolution.get("candidate_page_type") or resolution.get("seed_page_type", "unknown"),
                gate_passed,
                product_benchmark,
                resolution.get("resolution_status") == "Unresolved",
            )
            resolution["page_type"] = resolution.get("candidate_page_type") or resolution.get("seed_page_type", "unknown")
            resolution["discovery_origin"] = str(target.get("origin", ""))
            resolution["resolved_item_url"] = resolution.get("final_canonical_url", "") if gate_passed else ""
            resolution["discovery_seed_accepted"] = "True"
            resolution["item_level_verified"] = str(gate_passed)
            resolution["publication_date_verified"] = str(bool(gate_passed and resolution.get("publication_date") and is_post_cutoff(resolution.get("publication_date", ""))))
            resolution["body_verified"] = str(bool(gate_passed and int(resolution.get("body_chars", "0") or 0) >= 500))
            resolution["claude_eligible"] = "False"
            resolution_rows.append(resolution)
            inspection_rows.extend(inspection_row_for_resolution(target, resolution, verified))
    return resolution_rows, dedupe_inspection_rows(inspection_rows), engine


def write_report(
    path: Path,
    first_resolution: list[dict[str, str]],
    first_inspection: list[dict[str, str]],
    second_resolution: list[dict[str, str]],
    second_inspection: list[dict[str, str]],
    engine: str,
) -> None:
    def count(rows: list[dict[str, str]], column: str, value: str) -> int:
        return sum(1 for row in rows if row.get(column) == value)

    first_keys = sorted(mastercard_url_key(row.get("canonical_url") or row.get("item_url", "")) for row in first_inspection)
    second_keys = sorted(mastercard_url_key(row.get("canonical_url") or row.get("item_url", "")) for row in second_inspection)
    idempotent = first_keys == second_keys and len(second_keys) == len(set(second_keys))
    true_recent = [row for row in second_inspection if row.get("recent_item_eligible") == "True"]
    lines = [
        "# Mastercard Browser Refinement Report",
        "",
        f"Checked at: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`",
        f"Browser engine used: `{engine}`",
        "",
        "## Smoke-Test Pages",
    ]
    for row in second_resolution:
        lines.append(
            f"- {row['source_family']}: page_type `{row['seed_page_type']}`, links `{row['links_discovered']}`, "
            f"status `{row['resolution_status']}`, recent `{row['recent_item_eligible']}`, reason `{row['rejection_reason']}`"
        )
    lines.extend(
        [
            "",
            "## Decisions",
            f"- Pages attempted: {len(second_resolution)}",
            f"- Pages successfully rendered as article: {count(second_inspection, 'item_level_verified', 'True')}",
            f"- Search seeds resolved: {sum(1 for row in second_resolution if row.get('resolution_status') == 'Resolved')}",
            f"- Real article URLs found: {count(second_inspection, 'item_level_verified', 'True')}",
            f"- Publication dates verified: {count(second_inspection, 'date_verified', 'True')}",
            f"- Article bodies verified: {sum(1 for row in second_inspection if int(row.get('body_chars', '0') or 0) >= 500 and row.get('item_level_verified') == 'True')}",
            f"- Current true recent-item candidate count: {len(true_recent)}",
            f"- Sources promoted to mvp_active: 0",
            f"- Sources promoted to claude_eligible: 0",
            "",
            "## Controlled Outcomes",
        ]
    )
    for row in second_inspection:
        lines.append(
            f"- {row['source_family']} | {row['item_title']} | page `{row['page_type']}` | "
            f"item_verified `{row['item_level_verified']}` | recent `{row['recent_item_eligible']}` | "
            f"Claude `{row['claude_eligible']}` | {row['notes']}"
        )
    lines.extend(
        [
            "",
            "## Idempotency",
            f"- First run records: {len(first_inspection)}",
            f"- Second run records: {len(second_inspection)}",
            f"- Same canonical set: {first_keys == second_keys}",
            f"- Duplicate canonical records on second run: {len(second_keys) - len(set(second_keys))}",
            f"- Idempotent: {idempotent}",
            "",
            "## Claude Pilot Readiness",
            "- Claude was not run.",
            "- A 3-item Claude pilot is not safe yet because Mastercard official pages returned access-denied in the browser smoke test and no article body/date could be verified.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_browser_smoke_log(rows: list[dict[str, str]]) -> Path:
    log_dir = DATA_DIR / "mastercard_discovery_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "browser_smoke.log"
    lines = ["DRY RUN ONLY - Mastercard browser smoke test"]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"source_family={row.get('source_family', '')}",
                    f"discovery_stage={row.get('discovery_stage', '')}",
                    f"page_type={row.get('page_type', row.get('seed_page_type', ''))}",
                    f"seed_url={row.get('seed_url', '')}",
                    f"resolved_item_url={row.get('resolved_item_url', '')}",
                    f"discovery_seed_accepted={row.get('discovery_seed_accepted', '')}",
                    f"item_level_verified={row.get('item_level_verified', '')}",
                    f"publication_date={row.get('publication_date', '')}",
                    f"publication_date_verified={row.get('publication_date_verified', '')}",
                    f"body_chars={row.get('body_chars', '')}",
                    f"body_verified={row.get('body_verified', '')}",
                    f"recent_item_eligible={row.get('recent_item_eligible', '')}",
                    f"claude_eligible={row.get('claude_eligible', '')}",
                    f"rejection_reason={row.get('rejection_reason', '')}",
                    f"score={row.get('title_match_score', '0.000')}",
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled Mastercard browser discovery smoke tests without writing recent items.")
    parser.add_argument("--repeat", type=int, default=2, help="Run count for idempotency check.")
    parser.add_argument("--wait-seconds", type=float, default=4.0, help="Seconds to wait after browser navigation.")
    args = parser.parse_args()
    repeat = max(1, args.repeat)
    runs = []
    engine = ""
    for _ in range(repeat):
        resolution, inspection, engine = run_once(args.wait_seconds)
        runs.append((resolution, inspection))
    final_resolution, final_inspection = runs[-1]
    write_csv(RESOLUTION_PATH, final_resolution, RESOLUTION_COLUMNS)
    write_csv(INSPECTION_PATH, final_inspection, INSPECTION_COLUMNS)
    log_path = write_browser_smoke_log(final_resolution)
    report_path = DATA_DIR / f"mastercard_browser_refinement_report_{now_stamp()}.md"
    first_resolution, first_inspection = runs[0]
    write_report(report_path, first_resolution, first_inspection, final_resolution, final_inspection, engine)
    print("Mastercard browser smoke test complete")
    print(f"browser_engine={engine}")
    print(f"runs={repeat}")
    print(f"seed_resolution_rows={len(final_resolution)}")
    print(f"candidate_inspection_rows={len(final_inspection)}")
    print(f"true_recent_item_candidates={sum(1 for row in final_inspection if row.get('recent_item_eligible') == 'True')}")
    print(f"claude_eligible={sum(1 for row in final_inspection if row.get('claude_eligible') == 'True')}")
    print(f"resolution_csv={RESOLUTION_PATH.relative_to(ROOT_DIR)}")
    print(f"inspection_csv={INSPECTION_PATH.relative_to(ROOT_DIR)}")
    print(f"report={report_path.relative_to(ROOT_DIR)}")
    print(f"dry_run_log={log_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
