from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
REPORT_PREFIX = "production_rehearsal_report"
LANGUAGE_REPORT_PREFIX = "language_quality_report"
sys.path.insert(0, str(ROOT_DIR))

DEFAULT_INSTITUTIONS = ["Garanti BBVA", "İş Bankası", "Yapı Kredi", "QNB Finansbank"]
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
}
ENGLISH_CONTROLLED_VALUES = {
    "High",
    "Medium",
    "Low",
    "Monitor",
    "Respond",
    "Copy / Adapt",
    "Ignore",
    "Escalate to Leadership",
    "Add to BD Talking Points",
    "Campaign",
    "Product Launch",
    "Partnership",
    "Market Signal",
    "Payments & POS",
    "SME Lending",
    "Cash Management",
}

VISIBLE_LANGUAGE_FIELDS = [
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "awareness_reason",
    "triage_reason",
    "cluster_title",
    "cluster_summary",
    "cluster_core_assessment",
    "why_it_matters",
    "management_takeaway",
]
BANNED_LANGUAGE_PHRASES = [
    "gereklidir",
    "edilmelidir",
    "değerlendirilmelidir",
    "bulunmamaktadır",
    "sunmaktadır",
    "göstermektedir",
    "hedeflemektedir",
    "teşkil etmektedir",
    "önem arz etmektedir",
    "doğrudan rakip bir hamle",
    "değer yaratma potansiyeli",
    "açısından",
    "kapsamında",
    "müştdilde",
]
FORMAL_SUFFIX_RE = re.compile(r"\b\w+(?:maktadır|mektedir)\b", re.IGNORECASE)
OBLIGATION_RE = re.compile(r"\b(?:gereklidir|edilmelidir|değerlendirilmelidir)\b", re.IGNORECASE)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_institutions(value: str | None) -> list[str]:
    if not value:
        return DEFAULT_INSTITUTIONS
    return [item.strip() for item in value.split(",") if item.strip()]


def run_step(args: list[str], capture: bool = True) -> str:
    logging.info("Running: %s", " ".join(args))
    result = subprocess.run([sys.executable, *args], cwd=ROOT_DIR, text=True, capture_output=capture, check=True)
    output = (result.stdout or "") + (result.stderr or "")
    if output:
        print(output, end="")
    return output


def read_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()


def metric_from_log(text: str, label: str) -> int:
    matches = re.findall(rf"{re.escape(label)}:\s*(\d+)", text)
    return int(matches[-1]) if matches else 0


def institution_sources(registry: pd.DataFrame, institution: str) -> pd.DataFrame:
    if registry.empty:
        return pd.DataFrame()
    token = institution.strip().casefold()
    scoped = registry[
        registry["institution_name"].astype(str).str.casefold().eq(token)
        | registry["institution_id"].astype(str).str.casefold().eq(token)
    ].copy()
    return scoped[
        scoped["extraction_mode"].astype(str).isin(["weekly_development", "both"])
        & scoped["source_type"].astype(str).isin(WEEKLY_SOURCE_TYPES)
    ].copy()


def institution_rows(df: pd.DataFrame, institution: str) -> pd.DataFrame:
    if df.empty or "institution_name" not in df.columns:
        return pd.DataFrame()
    return df[df["institution_name"].astype(str).str.casefold().eq(institution.casefold())].copy()


def truthy(value) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "evet"}


def duplicate_canonical_count(items: pd.DataFrame) -> int:
    if items.empty or "canonical_item_url" not in items.columns:
        return 0
    scoped = items[items["canonical_item_url"].fillna("").astype(str).str.strip().ne("")]
    return int(scoped.duplicated(["institution_name", "canonical_item_url"]).sum())


def english_controlled_count(summaries: pd.DataFrame, clusters: pd.DataFrame) -> int:
    columns = ["strategic_theme", "product_area", "development_type", "impact_on_us", "recommended_action", "importance_level", "confidence_level"]
    total = 0
    for df in [summaries, clusters]:
        if df.empty:
            continue
        for column in columns:
            if column in df.columns:
                total += int(df[column].fillna("").astype(str).isin(ENGLISH_CONTROLLED_VALUES).sum())
    return total


def campaign_end_only_count(items: pd.DataFrame) -> int:
    if items.empty:
        return 0
    for column in ["campaign_end_date", "publication_date", "announcement_date", "campaign_start_date"]:
        if column not in items.columns:
            items[column] = ""
    return int(
        (
            items["campaign_end_date"].fillna("").astype(str).str.strip().ne("")
            & items["publication_date"].fillna("").astype(str).str.strip().eq("")
            & items["announcement_date"].fillna("").astype(str).str.strip().eq("")
            & items["campaign_start_date"].fillna("").astype(str).str.strip().eq("")
        ).sum()
    )


def first_titles(df: pd.DataFrame, title_col: str = "item_title", n: int = 10) -> list[str]:
    if df.empty or title_col not in df.columns:
        return []
    return [str(value) for value in df[title_col].dropna().astype(str).head(n)]


def list_block(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def latest_metadata_by_source(metadata: pd.DataFrame) -> pd.DataFrame:
    if metadata.empty or "source_id" not in metadata.columns:
        return pd.DataFrame()
    scoped = metadata.copy()
    if "fetched_at" in scoped.columns:
        scoped["_fetched_at_sort"] = pd.to_datetime(scoped["fetched_at"], errors="coerce")
        scoped = scoped.sort_values("_fetched_at_sort", ascending=False)
    return scoped.drop_duplicates("source_id", keep="first")


def source_status_block(registry: pd.DataFrame, metadata: pd.DataFrame, institution: str) -> list[str]:
    sources = institution_sources(registry, institution)
    if sources.empty:
        return ["- valid sources: 0", "- failed sources: 0", "- source status detail:", "- none"]
    latest = latest_metadata_by_source(metadata)
    merged = sources.merge(
        latest[["source_id", "status", "status_code", "error_message"]] if not latest.empty else pd.DataFrame(columns=["source_id", "status", "status_code", "error_message"]),
        on="source_id",
        how="left",
    )
    status = merged["status"].fillna("").astype(str)
    valid = int(status.eq("fetched").sum())
    failed = int(status.eq("error").sum())
    missing = int(status.eq("").sum())
    lines = [
        f"- valid sources: {valid}",
        f"- failed sources: {failed}",
        f"- missing collection rows: {missing}",
        "- source status detail:",
    ]
    for _, row in merged.iterrows():
        detail = f"{row.get('source_id', '')} | {row.get('source_name', '')} | {row.get('status', '') or 'missing'} | {row.get('status_code', '')}"
        error = str(row.get("error_message", "") or "").strip()
        if error and error.lower() != "nan":
            detail += f" | {error[:120]}"
        lines.append(f"- {detail}")
    return lines


def rejection_reason_block(audit: pd.DataFrame, institution: str) -> list[str]:
    if audit.empty or "institution_name" not in audit.columns:
        return ["- rejected candidates by reason:", "- none"]
    scoped = institution_rows(audit, institution)
    if scoped.empty or "rejected_reason" not in scoped.columns:
        return ["- rejected candidates by reason:", "- none"]
    reasons = scoped["rejected_reason"].fillna("").astype(str).str.strip()
    reasons = reasons[reasons.ne("")]
    if reasons.empty:
        return ["- rejected candidates by reason:", "- none"]
    lines = ["- rejected candidates by reason:"]
    for reason, count in reasons.value_counts().head(10).items():
        lines.append(f"- {reason}: {count}")
    return lines


def visible_text(row: pd.Series) -> str:
    return "\n".join(str(row.get(column, "") or "") for column in VISIBLE_LANGUAGE_FIELDS)


def language_scan_frames() -> list[tuple[str, pd.DataFrame]]:
    return [
        ("recent_item_summaries.csv", read_csv("recent_item_summaries.csv")),
        ("recent_item_review_queue.csv", read_csv("recent_item_review_queue.csv")),
        ("management_awareness_queue.csv", read_csv("management_awareness_queue.csv")),
        ("recent_item_archive.csv", read_csv("recent_item_archive.csv")),
        ("development_clusters.csv", read_csv("development_clusters.csv")),
        ("development_cluster_review_queue.csv", read_csv("development_cluster_review_queue.csv")),
    ]


def build_language_quality_report(report_path: Path) -> None:
    from utils.language_lint import lint_llm_language

    rows_scanned = 0
    needs_review = 0
    needs_rewrite = 0
    formal_suffix_count = 0
    obligation_count = 0
    phrase_counts = {phrase: 0 for phrase in BANNED_LANGUAGE_PHRASES}
    worst_rows: list[dict[str, object]] = []

    for filename, df in language_scan_frames():
        if df.empty:
            continue
        for _, row in df.iterrows():
            text = visible_text(row)
            if not text.strip():
                continue
            rows_scanned += 1
            lint = lint_llm_language(row)
            needs_review += int(bool(lint.get("needs_language_review", False)))
            needs_rewrite += int(bool(lint.get("needs_rewrite", False)))
            formal_suffix_count += len(FORMAL_SUFFIX_RE.findall(text))
            obligation_count += len(OBLIGATION_RE.findall(text))
            lowered = text.casefold()
            for phrase in BANNED_LANGUAGE_PHRASES:
                phrase_counts[phrase] += lowered.count(phrase.casefold())
            score = int(lint.get("language_lint_score", 0))
            if score > 0:
                worst_rows.append(
                    {
                        "score": score,
                        "filename": filename,
                        "title": str(row.get("item_title", row.get("cluster_title", "")) or "")[:160],
                        "warnings": lint.get("language_lint_warnings", []),
                    }
                )

    worst_rows = sorted(worst_rows, key=lambda item: int(item["score"]), reverse=True)[:10]
    remaining = {phrase: count for phrase, count in phrase_counts.items() if count}
    lines = [
        "# Language Quality Report",
        "",
        f"- Created at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Rows scanned: {rows_scanned}",
        f"- Rows needing language review: {needs_review}",
        f"- Rows needing rewrite: {needs_rewrite}",
        f"- Remaining banned phrases total: {sum(remaining.values())}",
        f"- Remaining -maktadır/-mektedir count: {formal_suffix_count}",
        f"- Remaining gereklidir / edilmelidir / değerlendirilmelidir count: {obligation_count}",
        "",
        "## Remaining Banned Phrases",
    ]
    if remaining:
        lines.extend(f"- {phrase}: {count}" for phrase, count in sorted(remaining.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Worst 10 Rows"])
    if worst_rows:
        for item in worst_rows:
            warnings = item.get("warnings", [])
            warning_text = "; ".join(str(warning) for warning in warnings) if isinstance(warnings, list) else str(warnings)
            lines.extend(
                [
                    f"### {item['filename']} | score {item['score']}",
                    f"- title: {item['title']}",
                    f"- warnings: {warning_text}",
                    "",
                ]
            )
    else:
        lines.append("- none")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_report(
    report_path: Path,
    institutions: list[str],
    start_date: str,
    archive_folder: str,
    per_inst: dict[str, dict[str, object]],
) -> None:
    items = read_csv("recent_items.csv")
    summaries = read_csv("recent_item_summaries.csv")
    queue = read_csv("recent_item_review_queue.csv")
    awareness = read_csv("management_awareness_queue.csv")
    archive = read_csv("recent_item_archive.csv")
    audit = read_csv("recent_item_extraction_audit.csv")
    clusters = read_csv("development_clusters.csv")
    cluster_queue = read_csv("development_cluster_review_queue.csv")
    registry = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig") if REGISTRY_PATH.exists() else pd.DataFrame()
    metadata = read_csv("raw_documents_metadata.csv")

    duplicate_recent_item_id = int(items["recent_item_id"].duplicated().sum()) if not items.empty and "recent_item_id" in items.columns else 0
    duplicate_url = duplicate_canonical_count(items)
    url_equals_source = int((items.get("item_url", pd.Series(dtype=str)).astype(str) == items.get("source_url", pd.Series(dtype=str)).astype(str)).sum()) if not items.empty else 0
    fallback_count = int(items.get("extraction_method", pd.Series(dtype=str)).astype(str).eq("fallback_source_page").sum()) if not items.empty else 0
    recency_dates = pd.to_datetime(items.get("recency_basis_date", pd.Series(dtype=str)), errors="coerce") if not items.empty else pd.Series(dtype="datetime64[ns]")
    cutoff = pd.to_datetime(start_date)
    before_cutoff = int((recency_dates < cutoff).sum()) if not items.empty else 0
    missing_recency = int(items.get("recency_basis_date", pd.Series(dtype=str)).fillna("").astype(str).str.strip().eq("").sum()) if not items.empty else 0
    undated_active = missing_recency
    end_only = campaign_end_only_count(items)
    english_values = english_controlled_count(summaries, clusters)
    missing_core = int(summaries.get("core_assessment", pd.Series(dtype=str)).fillna("").astype(str).str.strip().eq("").sum()) if not summaries.empty else 0
    json_failures = int(summaries.get("error_message", pd.Series(dtype=str)).fillna("").astype(str).str.contains("JSON parse", na=False).sum()) if not summaries.empty else 0
    cluster_json_failures = int(clusters.get("error_message", pd.Series(dtype=str)).fillna("").astype(str).str.contains("JSON parse", na=False).sum()) if not clusters.empty else 0
    suppressed_items = int(summaries.get("suppress_individual_review", pd.Series(dtype=str)).fillna("").astype(str).str.casefold().isin(["true", "1", "yes", "evet"]).sum()) if not summaries.empty else 0
    manual_end_date_passes = int(
        (
            summaries.get("campaign_end_date", pd.Series(dtype=str)).fillna("").astype(str).str.strip().ne("")
            & summaries.get("publication_date", pd.Series(dtype=str)).fillna("").astype(str).str.strip().eq("")
            & summaries.get("announcement_date", pd.Series(dtype=str)).fillna("").astype(str).str.strip().eq("")
            & summaries.get("campaign_start_date", pd.Series(dtype=str)).fillna("").astype(str).str.strip().eq("")
        ).sum()
    ) if not summaries.empty else 0

    duplicate_audit = audit[audit.get("rejected_reason", pd.Series(dtype=str)).fillna("").astype(str).str.contains("duplicate", case=False, na=False)].copy() if not audit.empty else pd.DataFrame()
    old_undated_audit = audit[
        audit.get("rejected_reason", pd.Series(dtype=str)).fillna("").astype(str).str.contains("Tarih yok|eski|kampanya bitiş tarihi", case=False, na=False)
    ].copy() if not audit.empty else pd.DataFrame()

    lines = [
        "# Production Rehearsal Report",
        "",
        f"- Created at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Start date cutoff: {start_date}",
        f"- Institutions: {', '.join(institutions)}",
        f"- Archive folder: `{archive_folder}`",
        "",
        "## Per Institution",
    ]
    for institution in institutions:
        data = per_inst.get(institution, {})
        lines.extend(
            [
                f"### {institution}",
                f"- sources considered: {data.get('sources_considered', 0)}",
                "- source URLs:",
                list_block(data.get("source_urls", [])),  # type: ignore[arg-type]
                f"- total links found: {data.get('total_links_found', 0)}",
                f"- candidate links found: {data.get('candidate_links_found', 0)}",
                f"- detail pages fetched: {data.get('detail_pages_fetched', 0)}",
                f"- rejected old items: {data.get('rejected_old_items', 0)}",
                f"- rejected undated items: {data.get('rejected_undated_items', 0)}",
                f"- rejected only campaign_end_date items: {data.get('rejected_only_campaign_end_date_items', 0)}",
                f"- rejected non-developments: {data.get('rejected_non_developments', 0)}",
                f"- duplicates rejected: {data.get('duplicates_rejected', 0)}",
                f"- saved recent developments: {data.get('saved_recent_developments', 0)}",
                f"- Claude summaries created: {data.get('claude_summaries_created', 0)}",
                f"- JSON parse failures: {data.get('json_parse_failures', 0)}",
                f"- review queue items: {len(institution_rows(queue, institution))}",
                f"- management awareness items: {len(institution_rows(awareness, institution))}",
                f"- archive items: {len(institution_rows(archive, institution))}",
                f"- clusters created: {len(institution_rows(clusters, institution))}",
                f"- cluster review queue items: {len(institution_rows(cluster_queue, institution))}",
                "",
            ]
        )
        if institution == "QNB Finansbank":
            lines.extend(["#### QNB Source Diagnostics", *source_status_block(registry, metadata, institution), ""])
            lines.extend(["#### QNB Candidate Rejection Diagnostics", *rejection_reason_block(audit, institution), ""])

    lines.extend(
        [
            "## Global Checks",
            f"- duplicate recent_item_id count: {duplicate_recent_item_id}",
            f"- duplicate canonical_item_url count: {duplicate_url}",
            f"- item_url == source_url count: {url_equals_source}",
            f"- fallback_source_page count: {fallback_count}",
            f"- items before {start_date} count: {before_cutoff}",
            f"- undated active items count: {undated_active}",
            f"- campaign_end_date-only active items count: {end_only}",
            f"- passed only by campaign_end_date count: {manual_end_date_passes}",
            f"- suppressed individual review items count: {suppressed_items}",
            f"- English controlled values count: {english_values}",
            f"- missing core_assessment count: {missing_core}",
            f"- missing recency_basis_date count: {missing_recency}",
            f"- summary JSON parse failures: {json_failures}",
            f"- cluster JSON parse failures: {cluster_json_failures}",
            "",
            "## Totals",
            f"- active recent items: {len(items)}",
            f"- summaries: {len(summaries)}",
            f"- individual review queue items: {len(queue)}",
            f"- management awareness queue items: {len(awareness)}",
            f"- archived low-priority items: {len(archive)}",
            f"- clusters: {len(clusters)}",
            f"- cluster review queue items: {len(cluster_queue)}",
            "",
            "## First 10 Saved Developments By Institution",
        ]
    )
    for institution in institutions:
        lines.append(f"### {institution}")
        scoped = institution_rows(items, institution)
        lines.append(list_block(first_titles(scoped, "item_title", 10)))
        lines.append("")

    lines.extend(
        [
            "## First 10 Rejected Duplicates",
            list_block(first_titles(duplicate_audit, "candidate_title", 10)),
            "",
            "## First 10 Rejected Old / Undated / End-Date-Only Items",
            list_block(first_titles(old_undated_audit, "candidate_title", 10)),
            "",
            "## Success Criteria",
            f"- duplicate recent_item_id count = 0: {'PASS' if duplicate_recent_item_id == 0 else 'FAIL'}",
            f"- duplicate canonical_item_url count = 0: {'PASS' if duplicate_url == 0 else 'FAIL'}",
            f"- item_url == source_url count = 0: {'PASS' if url_equals_source == 0 else 'FAIL'}",
            f"- fallback_source_page count = 0: {'PASS' if fallback_count == 0 else 'FAIL'}",
            f"- active items before cutoff = 0: {'PASS' if before_cutoff == 0 else 'FAIL'}",
            f"- undated active items = 0: {'PASS' if undated_active == 0 else 'FAIL'}",
            f"- campaign_end_date-only active items = 0: {'PASS' if end_only == 0 else 'FAIL'}",
            f"- JSON parse failures = 0: {'PASS' if json_failures == 0 and cluster_json_failures == 0 else 'FAIL'}",
            f"- no English controlled values: {'PASS' if english_values == 0 else 'FAIL'}",
            f"- every summary has core_assessment: {'PASS' if missing_core == 0 else 'FAIL'}",
            f"- every active item has recency_basis_date: {'PASS' if missing_recency == 0 else 'FAIL'}",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fresh four-bank recent-development MVP rehearsal.")
    parser.add_argument("--start-date", default="2026-05-01")
    parser.add_argument("--institutions", default=",".join(DEFAULT_INSTITUTIONS))
    parser.add_argument("--include-raw-files", action="store_true")
    parser.add_argument("--allow-end-date-recency", action="store_true")
    parser.add_argument("--publish-approved", action="store_true")
    args = parser.parse_args()

    institutions = parse_institutions(args.institutions)
    reset_args = [
        "pipeline/reset_recent_developments_mvp.py",
        "--institutions",
        ",".join(institutions),
        "--include-weekly-developments",
    ]
    if args.include_raw_files:
        reset_args.append("--include-raw-files")
    reset_output = run_step(reset_args)
    archive_match = re.search(r"Reset archive folder:\s*(data/archive/reset_\d{8}_\d{6})", reset_output)
    archive_folder = archive_match.group(1) if archive_match else "unknown"

    registry = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig") if REGISTRY_PATH.exists() else pd.DataFrame()
    per_inst: dict[str, dict[str, object]] = {}

    for institution in institutions:
        sources = institution_sources(registry, institution)
        per_inst[institution] = {
            "sources_considered": len(sources),
            "source_urls": sources.get("url", pd.Series(dtype=str)).dropna().astype(str).tolist(),
        }
        run_step(["pipeline/collect_static_pages.py", "--institution", institution])

    run_step(["pipeline/detect_changes.py"])

    for institution in institutions:
        extract_args = [
            "pipeline/extract_recent_items.py",
            "--institution",
            institution,
            "--fetch-detail-pages",
            "--start-date",
            args.start_date,
            "--debug-candidates",
            "--limit",
            "50",
        ]
        if args.allow_end_date_recency:
            extract_args.append("--allow-end-date-recency")
        extract_output = run_step(extract_args)
        summarize_args = [
            "pipeline/summarize_recent_items.py",
            "--institution",
            institution,
            "--start-date",
            args.start_date,
            "--limit",
            "50",
        ]
        if args.allow_end_date_recency:
            summarize_args.append("--allow-end-date-recency")
        summarize_output = run_step(summarize_args)
        per_inst[institution].update(
            {
                "total_links_found": metric_from_log(extract_output, "Total links found"),
                "candidate_links_found": metric_from_log(extract_output, "Candidate links found"),
                "detail_pages_fetched": metric_from_log(extract_output, "Detail pages fetched"),
                "rejected_old_items": metric_from_log(extract_output, "Rejected old items"),
                "rejected_undated_items": metric_from_log(extract_output, "Rejected undated items"),
                "rejected_only_campaign_end_date_items": metric_from_log(extract_output, "Rejected because only campaign_end_date existed"),
                "rejected_non_developments": metric_from_log(extract_output, "Rejected non-developments"),
                "duplicates_rejected": metric_from_log(extract_output, "Duplicates skipped"),
                "saved_recent_developments": metric_from_log(extract_output, "Saved recent developments"),
                "claude_summaries_created": metric_from_log(summarize_output, "Summaries created"),
                "json_parse_failures": metric_from_log(summarize_output, "JSON parse failures"),
            }
        )

    run_step(["pipeline/retriage_recent_item_summaries.py"])
    run_step(["pipeline/cluster_recent_developments.py"])
    run_step(["pipeline/summarize_development_clusters.py"])
    run_step(["pipeline/update_cluster_review_queue.py"])
    run_step(["pipeline/update_recent_item_review_queue.py"])
    if args.publish_approved:
        run_step(["pipeline/publish_recent_items_to_weekly_developments.py"])
        run_step(["pipeline/publish_approved_clusters_to_weekly_developments.py"])
        run_step(["pipeline/publish_management_awareness_to_weekly_developments.py"])

    report_path = DATA_DIR / f"{REPORT_PREFIX}_{timestamp()}.md"
    build_report(report_path, institutions, args.start_date, archive_folder, per_inst)
    language_report_path = DATA_DIR / f"{LANGUAGE_REPORT_PREFIX}_{timestamp()}.md"
    build_language_quality_report(language_report_path)
    print(f"\nProduction rehearsal report: {report_path.relative_to(ROOT_DIR)}\n")
    print(f"Language quality report: {language_report_path.relative_to(ROOT_DIR)}\n")


if __name__ == "__main__":
    main()
