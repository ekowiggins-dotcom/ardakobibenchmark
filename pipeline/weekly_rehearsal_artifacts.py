from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from utils.rehearsal_ops import (
    DATA_DIR,
    TRACKED_FILES,
    before_after,
    clean,
    create_rehearsal_snapshot,
    file_metadata,
    ids_added_since_snapshot,
    load_snapshot_manifest,
    now_iso,
    read_csv,
    validate_registry,
    write_csv,
)


CANDIDATE_COLUMNS = [
    "institution_name",
    "source_id",
    "source_name",
    "item_title",
    "item_url",
    "publication_date",
    "recency_basis_date",
    "recency_basis_type",
    "date_confidence",
    "source_role",
    "customer_segment",
    "content_role",
    "relevance_evidence",
    "duplicate_status",
    "revision_status",
    "eligible_for_claude",
    "proposed_destination",
    "rejection_reason",
    "notes",
]

ROUTING_COLUMNS = [
    "recent_item_id",
    "institution_name",
    "content_role",
    "relevance_status",
    "intended_destination",
    "actual_destination",
    "destination_count",
    "valid_single_lane",
    "error_reason",
]

PUBLISH_COLUMNS = [
    "recent_item_id",
    "institution_name",
    "title",
    "publication_date",
    "strategic_theme",
    "product_area",
    "impact_on_us",
    "importance_level",
    "recommended_action",
    "destination",
    "approval_status",
    "publish_ready",
    "publish_block_reason",
]

SOURCE_HEALTH_COLUMNS = [
    "institution",
    "source_id",
    "source_name",
    "monitoring_mode",
    "collector_capability",
    "attempted",
    "skipped",
    "success",
    "latest_item_date",
    "current_candidates",
    "unchanged",
    "error",
    "health_status",
    "action_required",
]


def action_snapshot(args: argparse.Namespace) -> None:
    manifest = create_rehearsal_snapshot(args.run_id)
    registry_issues = validate_registry()
    path = DATA_DIR / f"weekly_rehearsal_registry_validation_{args.run_id}.csv"
    write_csv(path, registry_issues)
    print("Rehearsal snapshot created")
    print(f"run_id: {args.run_id}")
    print(f"snapshot_path: {manifest['snapshot_path']}")
    print(f"registry_issues: {len(registry_issues)}")
    print(f"registry_validation: {path.relative_to(ROOT_DIR)}")


def snapshot_time(snapshot: dict[str, object]) -> pd.Timestamp:
    return pd.to_datetime(snapshot.get("created_at", ""), utc=True, errors="coerce")


def rows_after_snapshot(df: pd.DataFrame, time_column: str, snapshot: dict[str, object]) -> pd.DataFrame:
    if df.empty or time_column not in df.columns:
        return df.iloc[0:0].copy()
    cutoff = snapshot_time(snapshot)
    dates = pd.to_datetime(df[time_column], utc=True, errors="coerce")
    return df[dates >= cutoff].copy()


def candidate_inspection(snapshot: dict[str, object]) -> pd.DataFrame:
    audit = read_csv(DATA_DIR / "recent_item_extraction_audit.csv")
    audit = rows_after_snapshot(audit, "checked_at", snapshot)
    if audit.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    registry = read_csv(DATA_DIR / "source_registry.csv")
    source_lookup = registry.set_index("source_id").to_dict("index") if not registry.empty and "source_id" in registry.columns else {}
    rows = []
    for _, row in audit.iterrows():
        source = source_lookup.get(clean(row.get("source_id")), {})
        saved = clean(row.get("saved_to_recent_items")).casefold() == "true"
        is_recent = clean(row.get("is_recent")).casefold() == "true"
        actual = clean(row.get("is_actual_development")).casefold() == "true"
        item_quality = clean(row.get("item_quality"))
        eligible = saved and is_recent and actual and item_quality in {"Good", "Medium"} and not clean(row.get("duplicate_of_recent_item_id"))
        content_role = clean(row.get("content_role"))
        proposed_destination = "No destination due rejection"
        if eligible:
            proposed_destination = "Claude Eligibility Gate"
        elif content_role in {"Benchmark Fact", "Benchmark Bilgisi"}:
            proposed_destination = "Benchmark"
        elif content_role in {"Bağlamsal Veri", "Tarihsel Bağlam"}:
            proposed_destination = "Bağlamsal Veri"
        elif clean(row.get("rejected_reason")):
            proposed_destination = "No destination due rejection"
        rows.append(
            {
                "institution_name": clean(row.get("institution_name")),
                "source_id": clean(row.get("source_id")),
                "source_name": clean(row.get("source_name")),
                "item_title": clean(row.get("candidate_title")),
                "item_url": clean(row.get("candidate_url")),
                "publication_date": clean(row.get("publication_date")),
                "recency_basis_date": clean(row.get("recency_basis_date")),
                "recency_basis_type": clean(row.get("recency_basis_type")),
                "date_confidence": clean(row.get("date_confidence")),
                "source_role": clean(source.get("extraction_mode")),
                "customer_segment": clean(source.get("customer_segment")),
                "content_role": content_role,
                "relevance_evidence": clean(row.get("actual_development_reason") or row.get("content_role_reason")),
                "duplicate_status": "duplicate" if clean(row.get("duplicate_of_recent_item_id")) else "unique_or_not_saved",
                "revision_status": "material_revision" if clean(row.get("development_candidate_type")) == "Revision" else "",
                "eligible_for_claude": str(eligible),
                "proposed_destination": proposed_destination,
                "rejection_reason": clean(row.get("rejected_reason")),
                "notes": clean(row.get("recency_reason")),
            }
        )
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)


def destination_maps() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    review = read_csv(DATA_DIR / "recent_item_review_queue.csv")
    awareness = read_csv(DATA_DIR / "management_awareness_queue.csv")
    archive = read_csv(DATA_DIR / "recent_item_archive.csv")
    return (
        {clean(row.get("recent_item_id")): clean(row.get("review_status")) for _, row in review.iterrows()} if not review.empty else {},
        {clean(row.get("recent_item_id")): clean(row.get("review_status")) for _, row in awareness.iterrows()} if not awareness.empty else {},
        {clean(row.get("recent_item_id")): clean(row.get("triage_status")) for _, row in archive.iterrows()} if not archive.empty else {},
    )


def intended_destination(row: pd.Series) -> str:
    role = clean(row.get("content_role"))
    relevance = clean(row.get("relevance_status"))
    action = clean(row.get("recommended_action"))
    impact = clean(row.get("impact_on_us"))
    importance = clean(row.get("importance_level"))
    if role in {"Benchmark Fact", "Benchmark Bilgisi"}:
        return "Benchmark"
    if role in {"Bağlamsal Veri", "Tarihsel Bağlam"}:
        return "Bağlamsal Veri"
    if role == "Yönetici Bilgilendirme" or action == "Yönetici Bilgilendirme Notuna Ekle":
        return "Yönetici Bilgilendirme"
    if relevance == "İlgisiz" or impact == "Düşük" and importance == "Düşük":
        return "Düşük Öncelik / Arşiv"
    return "Analist Onay Kuyruğu"


def routing_reconciliation(snapshot: dict[str, object]) -> pd.DataFrame:
    summaries = read_csv(DATA_DIR / "recent_item_summaries.csv")
    new_summary_ids = ids_added_since_snapshot(snapshot, "recent_item_summaries.csv")
    if new_summary_ids:
        summaries = summaries[summaries["summary_id"].astype(str).isin(new_summary_ids)].copy()
    else:
        summaries = rows_after_snapshot(summaries, "created_at", snapshot)
    if summaries.empty:
        return pd.DataFrame(columns=ROUTING_COLUMNS)
    review_map, awareness_map, archive_map = destination_maps()
    rows = []
    for _, row in summaries.iterrows():
        item_id = clean(row.get("recent_item_id"))
        destinations = []
        if item_id in review_map:
            destinations.append("Analist Onay Kuyruğu")
        if item_id in awareness_map:
            destinations.append("Yönetici Bilgilendirme")
        if item_id in archive_map:
            destinations.append("Düşük Öncelik / Arşiv")
        intended = intended_destination(row)
        errors = []
        if len(destinations) != 1 and intended not in {"Benchmark", "Bağlamsal Veri", "No destination due rejection"}:
            errors.append("destination_count_not_one")
        if "Yönetici Bilgilendirme" in destinations and clean(row.get("relevance_status")) == "İlgisiz":
            errors.append("awareness_item_irrelevant")
        if intended == "Benchmark" and "Analist Onay Kuyruğu" in destinations:
            errors.append("benchmark_in_review")
        rows.append(
            {
                "recent_item_id": item_id,
                "institution_name": clean(row.get("institution_name")),
                "content_role": clean(row.get("content_role")),
                "relevance_status": clean(row.get("relevance_status")),
                "intended_destination": intended,
                "actual_destination": "; ".join(destinations) or "No destination due rejection",
                "destination_count": str(len(destinations)),
                "valid_single_lane": str(len(errors) == 0),
                "error_reason": "; ".join(errors),
            }
        )
    return pd.DataFrame(rows, columns=ROUTING_COLUMNS)


def publish_preview(snapshot: dict[str, object]) -> pd.DataFrame:
    summaries = read_csv(DATA_DIR / "recent_item_summaries.csv")
    if summaries.empty:
        return pd.DataFrame(columns=PUBLISH_COLUMNS)
    new_summary_ids = ids_added_since_snapshot(snapshot, "recent_item_summaries.csv")
    if new_summary_ids:
        summaries = summaries[summaries["summary_id"].astype(str).isin(new_summary_ids)].copy()
    else:
        summaries = rows_after_snapshot(summaries, "created_at", snapshot)
    review = read_csv(DATA_DIR / "recent_item_review_queue.csv")
    review_by_item = {clean(row.get("recent_item_id")): row.to_dict() for _, row in review.iterrows()} if not review.empty else {}
    rows = []
    for _, row in summaries.iterrows():
        item_id = clean(row.get("recent_item_id"))
        review_row = review_by_item.get(item_id, {})
        approval = clean(review_row.get("review_status")) or clean(row.get("review_status")) or "Bekliyor"
        destination = intended_destination(row)
        publish_ready = approval == "Onaylandı" and destination == "Analist Onay Kuyruğu"
        rows.append(
            {
                "recent_item_id": item_id,
                "institution_name": clean(row.get("institution_name")),
                "title": clean(row.get("item_title")),
                "publication_date": clean(row.get("item_date")),
                "strategic_theme": clean(row.get("strategic_theme")),
                "product_area": clean(row.get("product_area")),
                "impact_on_us": clean(row.get("impact_on_us")),
                "importance_level": clean(row.get("importance_level")),
                "recommended_action": clean(row.get("recommended_action")),
                "destination": destination,
                "approval_status": approval,
                "publish_ready": str(publish_ready),
                "publish_block_reason": "" if publish_ready else "Analyst approval required or non-publish destination",
            }
        )
    return pd.DataFrame(rows, columns=PUBLISH_COLUMNS)


def source_health() -> pd.DataFrame:
    registry = read_csv(DATA_DIR / "source_registry.csv")
    metadata = read_csv(DATA_DIR / "raw_documents_metadata.csv")
    if registry.empty:
        return pd.DataFrame(columns=SOURCE_HEALTH_COLUMNS)
    latest_by_source = {}
    if not metadata.empty and "source_id" in metadata.columns:
        metadata["_dt"] = pd.to_datetime(metadata.get("fetched_at", ""), utc=True, errors="coerce")
        metadata = metadata.sort_values("_dt")
        latest_by_source = {source_id: group.iloc[-1].to_dict() for source_id, group in metadata.groupby("source_id")}
    rows = []
    for _, row in registry.iterrows():
        active = clean(row.get("active")).casefold() in {"true", "1", "yes", "evet", "aktif"}
        mode = clean(row.get("monitoring_mode"))
        method = clean(row.get("collection_method"))
        latest = latest_by_source.get(clean(row.get("source_id")), {})
        attempted = bool(latest)
        skipped = not active or method in {"manual", "browser_required"} or mode in {"blocked_source_watch", "historical_resolution", "benchmark_monitoring"}
        success = clean(latest.get("status")) == "fetched"
        health = "Sağlıklı" if success and not skipped else "Uyarı"
        action = ""
        if method == "manual":
            health = "Manuel İzleme"
            action = "Manuel kaynak; otomatik fetch yok."
        elif mode == "blocked_source_watch":
            health = "Erişim Engelli"
            action = "Mastercard için manuel resmî kanıt + periyodik recovery."
        elif mode == "historical_resolution":
            health = "Tarihsel Çözümleme"
            action = "Recent discovery dışı; canonical/history resolver."
        elif mode == "benchmark_monitoring":
            health = "Benchmark İzleme"
            action = "Benchmark/context only; recent item üretmez."
        elif latest and clean(latest.get("status")) == "error":
            health = "Hatalı"
            action = clean(latest.get("error_message"))
        rows.append(
            {
                "institution": clean(row.get("institution_name")),
                "source_id": clean(row.get("source_id")),
                "source_name": clean(row.get("source_name")),
                "monitoring_mode": mode,
                "collector_capability": clean(row.get("collector_capability") or method),
                "attempted": str(attempted and not skipped),
                "skipped": str(skipped),
                "success": str(success),
                "latest_item_date": clean(latest.get("fetched_at")),
                "current_candidates": "",
                "unchanged": str(clean(latest.get("change_status")) == "unchanged"),
                "error": clean(latest.get("error_message")),
                "health_status": health,
                "action_required": action,
            }
        )
    return pd.DataFrame(rows, columns=SOURCE_HEALTH_COLUMNS)


def executive_preview(run_id: str, publish: pd.DataFrame, routing: pd.DataFrame) -> str:
    clusters = read_csv(DATA_DIR / "development_clusters.csv")
    lines = [
        "# Bu Hafta Ne Değişti?",
        "",
        "**Rehearsal Preview - Analyst Approval Required**",
        "",
        "## Top Potential Strategic Developments",
    ]
    strategic = publish[publish["destination"].eq("Analist Onay Kuyruğu")].head(5) if not publish.empty else pd.DataFrame()
    if strategic.empty:
        lines.append("- Yeni onay bekleyen stratejik/BD adayı yok.")
    else:
        for _, row in strategic.iterrows():
            lines.append(f"- {row['institution_name']}: {row['title']} ({row['recommended_action']})")
    lines.extend(["", "## Top Management-Awareness Signals"])
    awareness = publish[publish["destination"].eq("Yönetici Bilgilendirme")].head(5) if not publish.empty else pd.DataFrame()
    if awareness.empty:
        lines.append("- Yeni yönetici bilgilendirme adayı yok.")
    else:
        for _, row in awareness.iterrows():
            lines.append(f"- {row['institution_name']}: {row['title']}")
    lines.extend(["", "## Important Competitor Patterns"])
    if clusters.empty:
        lines.append("- Yeni pattern/küme önizlemesi yok.")
    else:
        for _, row in clusters.head(5).iterrows():
            lines.append(f"- {clean(row.get('cluster_title'))}: {clean(row.get('item_count'))} madde")
    lines.extend(
        [
            "",
            "## Payment-Network / Global Technology Signals",
            "- Mastercard otomatik güncel kaynak erişimi engelli; manuel resmi kanıt ve recovery watch ile izleniyor.",
            "",
            "## Items Awaiting Analyst Approval",
            f"- Publish preview rows: {len(publish)}",
            f"- Routing reconciliation rows: {len(routing)}",
            "",
            "# Bu Hafta Neyi İzlemeliyiz?",
            "",
        ]
    )
    for _, row in strategic.head(5).iterrows():
        lines.extend(
            [
                f"## {row['title']}",
                f"- Ne oldu: {row['institution_name']} için yeni aday gelişme rehearsal sırasında değerlendirildi.",
                f"- Neden önemli: {row['strategic_theme']} / {row['product_area']} alanında Akbank kıyaslaması gerektirebilir.",
                f"- Önerilen aksiyon: {row['recommended_action']}",
                "- Güven: Rehearsal preview; analist onayı gerekli.",
                "",
            ]
        )
    path = DATA_DIR / f"weekly_rehearsal_executive_preview_{run_id}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path.relative_to(ROOT_DIR))


def latest_run_row(run_id: str) -> dict[str, str]:
    runs = read_csv(DATA_DIR / "pipeline_runs.csv")
    if runs.empty:
        return {}
    subset = runs[runs["run_id"].astype(str).eq(run_id)].copy() if "run_id" in runs.columns else pd.DataFrame()
    if subset.empty:
        return {}
    return subset.iloc[-1].to_dict()


def write_final_report(
    run_id: str,
    first_run_id: str,
    second_run_id: str,
    comparison: dict[str, object],
    registry: pd.DataFrame,
    candidates: pd.DataFrame,
    routing: pd.DataFrame,
    publish: pd.DataFrame,
    health: pd.DataFrame,
    compile_result: str,
    test_result: str,
) -> str:
    first = latest_run_row(first_run_id)
    second = latest_run_row(second_run_id)
    critical_defects = []
    if comparison.get("published_rows_changed"):
        critical_defects.append("weekly_developments changed without explicit publish")
    if comparison.get("analyst_decisions_changed"):
        critical_defects.append("analyst decisions changed")
    if not routing.empty and routing["valid_single_lane"].astype(str).ne("True").any():
        critical_defects.append("routing reconciliation errors")
    recommendation = "Ready for normal weekly operation"
    if critical_defects:
        recommendation = "Repeat rehearsal after critical fixes"
    elif len(registry[registry.get("severity", "").astype(str).eq("error")]) > 0:
        recommendation = "Ready after minor fixes"

    def metric(row: dict[str, str], key: str) -> str:
        return clean(row.get(key, "0"))

    lines = [
        "# Weekly Rehearsal Report",
        "",
        f"- run ID: `{run_id}`",
        f"- first run ID: `{first_run_id}`",
        f"- second run ID: `{second_run_id}`",
        f"- source universe: active registry with weekly/static eligibility; blocked/manual sources reported but not fetched",
        f"- sources attempted: {metric(first, 'sources_checked')}",
        f"- sources succeeded: {metric(first, 'sources_succeeded')}",
        f"- sources skipped: {len(health[health['skipped'].astype(str).eq('True')]) if not health.empty else 0}",
        f"- blocked sources: {len(health[health['health_status'].eq('Erişim Engelli')]) if not health.empty else 0}",
        f"- manual sources: {len(health[health['health_status'].eq('Manuel İzleme')]) if not health.empty else 0}",
        f"- source failures: {metric(first, 'sources_failed')}",
        f"- raw documents collected: {metric(first, 'sources_succeeded')}",
        f"- candidates discovered: {metric(first, 'candidate_links_found')}",
        f"- rejected old items: {metric(first, 'old_items_rejected')}",
        f"- rejected undated items: {metric(first, 'undated_items_rejected')}",
        f"- rejected source-page rows: measured in candidate inspection rejection_reason",
        f"- duplicates: {metric(first, 'duplicates_skipped')}",
        f"- material revisions: {len(read_csv(DATA_DIR / 'recent_item_revisions.csv'))}",
        f"- Claude-eligible candidates: {len(candidates[candidates['eligible_for_claude'].astype(str).eq('True')]) if not candidates.empty else 0}",
        f"- Claude calls: {metric(first, 'estimated_llm_calls')}",
        f"- summaries created: {metric(first, 'summaries_created')}",
        f"- JSON failures: {metric(first, 'json_parse_failures')}",
        f"- language rewrites: {metric(first, 'llm_rewrite_count')}",
        f"- review additions: {metric(first, 'review_queue_additions')}",
        f"- awareness additions: {metric(first, 'management_awareness_additions')}",
        f"- archive additions: {metric(first, 'archive_additions')}",
        f"- benchmark revisions: not changed by rehearsal publisher",
        f"- cluster preview: {metric(first, 'clusters_created')} clusters, {metric(first, 'cluster_queue_additions')} queue additions",
        f"- publish-preview count: {len(publish)}",
        f"- actual published rows changed: {comparison.get('published_rows_changed')}",
        f"- analyst decisions changed: {comparison.get('analyst_decisions_changed')}",
        "- Mastercard operational status: Critical; automated current-source readiness Blocked; handled via manual official evidence and recovery watch; not a failed source.",
        "",
        "## First Run Counts",
        "",
        json.dumps(first, ensure_ascii=False, indent=2),
        "",
        "## Second Run Counts",
        "",
        json.dumps(second, ensure_ascii=False, indent=2),
        "",
        "## Idempotency Result",
        "",
        f"- second run new_items_created: {metric(second, 'new_items_created')}",
        f"- second run summaries_created: {metric(second, 'summaries_created')}",
        f"- second run review_queue_additions: {metric(second, 'review_queue_additions')}",
        f"- second run archive_additions: {metric(second, 'archive_additions')}",
        f"- second run management_awareness_additions: {metric(second, 'management_awareness_additions')}",
        "",
        "## QA",
        "",
        f"- compilation result: {compile_result}",
        f"- test result: {test_result}",
        f"- rollback readiness: manifest created",
        f"- critical defects found: {', '.join(critical_defects) if critical_defects else 'None'}",
        f"- recommended fixes: {'; '.join(critical_defects) if critical_defects else 'None before normal weekly operation'}",
        "",
        f"## Final Decision: {recommendation}",
        "",
        recommendation,
    ]
    path = DATA_DIR / f"weekly_rehearsal_report_{run_id}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return recommendation


def action_finalize(args: argparse.Namespace) -> None:
    snapshot = load_snapshot_manifest(args.run_id)
    comparison = before_after(snapshot)
    registry_issues = validate_registry()
    candidates = candidate_inspection(snapshot)
    routing = routing_reconciliation(snapshot)
    publish = publish_preview(snapshot)
    health = source_health()

    write_csv(DATA_DIR / f"weekly_rehearsal_registry_validation_{args.run_id}.csv", registry_issues)
    write_csv(DATA_DIR / f"weekly_rehearsal_candidate_inspection_{args.run_id}.csv", candidates, CANDIDATE_COLUMNS)
    write_csv(DATA_DIR / f"weekly_rehearsal_routing_reconciliation_{args.run_id}.csv", routing, ROUTING_COLUMNS)
    write_csv(DATA_DIR / f"weekly_rehearsal_publish_preview_{args.run_id}.csv", publish, PUBLISH_COLUMNS)
    write_csv(DATA_DIR / f"weekly_rehearsal_source_health_{args.run_id}.csv", health, SOURCE_HEALTH_COLUMNS)
    exec_preview_path = executive_preview(args.run_id, publish, routing)

    before_after_path = DATA_DIR / f"weekly_rehearsal_before_after_{args.run_id}.json"
    before_after_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    rollback = {
        "run_id": args.run_id,
        "created_at": now_iso(),
        "snapshot_path": snapshot.get("snapshot_path"),
        "files_changed": comparison.get("changed_files", {}),
        "rows_added": {filename: len(values) for filename, values in comparison.get("new_ids", {}).items()},
        "rows_modified": "Use file hashes and snapshot copies for exact rollback diff.",
        "hashes_before": {filename: meta.get("hash", "") for filename, meta in comparison.get("before", {}).items()},
        "hashes_after": {filename: meta.get("hash", "") for filename, meta in comparison.get("after", {}).items()},
        "safe_rollback_instruction": "Restore required files from data/rehearsal_snapshots/<run_id>/ after manually preserving analyst decisions and published items created after the snapshot.",
    }
    rollback_path = DATA_DIR / f"weekly_rehearsal_rollback_manifest_{args.run_id}.json"
    rollback_path.write_text(json.dumps(rollback, ensure_ascii=False, indent=2), encoding="utf-8")

    recommendation = write_final_report(
        args.run_id,
        args.first_run_id,
        args.second_run_id,
        comparison,
        registry_issues,
        candidates,
        routing,
        publish,
        health,
        args.compile_result,
        args.test_result,
    )

    print("Weekly rehearsal artifacts created")
    print(f"run_id: {args.run_id}")
    print(f"candidate_inspection: data/weekly_rehearsal_candidate_inspection_{args.run_id}.csv")
    print(f"routing_reconciliation: data/weekly_rehearsal_routing_reconciliation_{args.run_id}.csv")
    print(f"publish_preview: data/weekly_rehearsal_publish_preview_{args.run_id}.csv")
    print(f"executive_preview: {exec_preview_path}")
    print(f"source_health: data/weekly_rehearsal_source_health_{args.run_id}.csv")
    print(f"before_after: {before_after_path.relative_to(ROOT_DIR)}")
    print(f"rollback_manifest: {rollback_path.relative_to(ROOT_DIR)}")
    print(f"final_report: data/weekly_rehearsal_report_{args.run_id}.md")
    print(f"recommendation: {recommendation}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create weekly rehearsal snapshots and artifacts.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--run-id", required=True)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--run-id", required=True)
    finalize.add_argument("--first-run-id", required=True)
    finalize.add_argument("--second-run-id", required=True)
    finalize.add_argument("--compile-result", default="not run")
    finalize.add_argument("--test-result", default="not run")
    args = parser.parse_args()
    if args.action == "snapshot":
        action_snapshot(args)
    elif args.action == "finalize":
        action_finalize(args)


if __name__ == "__main__":
    main()
