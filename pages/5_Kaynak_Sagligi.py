from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
sys.path.insert(0, str(ROOT))

from utils.institution_aliases import institution_group
from utils.recent_mvp import (
    ARCHIVE_COLUMNS,
    AUDIT_COLUMNS,
    MANAGEMENT_AWARENESS_COLUMNS,
    METADATA_COLUMNS,
    QUEUE_COLUMNS,
    RECENT_ITEM_COLUMNS,
    SOURCE_COLUMNS,
    SUMMARY_COLUMNS,
    is_active,
    parse_date_series,
    read_csv_safe,
)
from utils.source_health import ERROR, HEALTHY, MANUAL, STALE, WARNING, classify_source_health
from utils.ui_theme import apply_akbank_theme, render_page_header


PIPELINE_RUN_COLUMNS = [
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


st.set_page_config(page_title="Kaynak Sağlığı", layout="wide")
apply_akbank_theme()

st.markdown(
    """
    <style>
    .source-health-card {
        background: var(--ak-surface);
        border: 1px solid var(--ak-border);
        border-radius: 14px;
        box-shadow: var(--ak-shadow-soft);
        padding: 1rem 1.1rem;
        min-height: 112px;
    }
    .source-health-label {
        color: var(--ak-muted);
        font-size: 0.68rem;
        font-weight: 850;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }
    .source-health-value {
        color: var(--ak-text);
        font-size: 2rem;
        font-weight: 850;
        line-height: 1.1;
        margin-top: 0.45rem;
    }
    .source-health-note {
        color: var(--ak-secondary);
        font-size: 0.82rem;
        line-height: 1.35;
        margin-top: 0.45rem;
    }
    .source-health-panel {
        background: var(--ak-surface);
        border: 1px solid var(--ak-border);
        border-radius: 14px;
        box-shadow: var(--ak-shadow-soft);
        padding: 1.15rem 1.25rem;
        margin: 0.5rem 0 1rem;
    }
    .source-health-panel h3 {
        margin: 0 0 0.35rem;
        font-size: 1.05rem;
    }
    .source-health-panel p {
        color: var(--ak-secondary);
        margin: 0;
        line-height: 1.5;
    }
    .status-chip {
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--ak-border);
        border-radius: 999px;
        padding: 0.2rem 0.55rem;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        white-space: nowrap;
    }
    .status-chip.ok { color: #166534; background: #F0FDF4; border-color: #BBF7D0; }
    .status-chip.warn { color: #92400E; background: #FFFBEB; border-color: #FDE68A; }
    .status-chip.error { color: var(--ak-red-dark); background: var(--ak-chip-bg); border-color: var(--ak-chip-border); }
    .status-chip.manual { color: var(--ak-secondary); background: var(--ak-soft); border-color: var(--ak-border); }
    </style>
    """,
    unsafe_allow_html=True,
)


def read_optional_csv(filename: str, columns: list[str]) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df.reindex(columns=columns)


def as_int(value: object) -> int:
    try:
        return int(float(str(value or "0").strip() or 0))
    except Exception:
        return 0


def metric_card(label: str, value: object, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="source-health-card">
          <div class="source-health-label">{label}</div>
          <div class="source-health-value">{value}</div>
          <div class="source-health-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_class(status: str) -> str:
    if status == HEALTHY:
        return "ok"
    if status in {WARNING, STALE}:
        return "warn"
    if status == ERROR:
        return "error"
    return "manual"


def status_chip(status: str) -> str:
    return f'<span class="status-chip {status_class(status)}">{status}</span>'


def latest_run(runs: pd.DataFrame) -> pd.Series | None:
    if runs.empty:
        return None
    view = runs.copy()
    view["_started"] = parse_date_series(view["started_at"])
    view = view.sort_values("_started", ascending=False)
    return view.iloc[0] if not view.empty else None


render_page_header(
    "Kaynak Sağlığı",
    "Günlük tarama, aday çıkarımı, Claude özeti ve analist kuyruğu için operasyon kontrol paneli.",
)

registry = read_csv_safe("source_registry.csv", SOURCE_COLUMNS)
metadata = read_csv_safe("raw_documents_metadata.csv", METADATA_COLUMNS)
items = read_csv_safe("recent_items.csv", RECENT_ITEM_COLUMNS)
summaries = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
queue = read_csv_safe("recent_item_review_queue.csv", QUEUE_COLUMNS)
archive = read_csv_safe("recent_item_archive.csv", ARCHIVE_COLUMNS)
awareness = read_csv_safe("management_awareness_queue.csv", MANAGEMENT_AWARENESS_COLUMNS)
audit = read_optional_csv("recent_item_extraction_audit.csv", AUDIT_COLUMNS)
runs = read_optional_csv("pipeline_runs.csv", PIPELINE_RUN_COLUMNS)

if registry.empty:
    st.info("Kaynak envanteri bulunamadı.")
    st.stop()
    raise SystemExit

registry_view = registry.copy()
registry_view["active_bool"] = registry_view["active"].apply(is_active)
registry_view["mvp_active_bool"] = registry_view.get("mvp_active", "").apply(is_active)
registry_view["weekly_enabled_bool"] = registry_view.get("weekly_collection_enabled", "").apply(is_active)
registry_view["institution_group"] = registry_view["institution_name"].apply(institution_group)

if not metadata.empty:
    metadata_view = metadata.copy()
    metadata_view["fetched_dt"] = parse_date_series(metadata_view["fetched_at"])
    latest = metadata_view.sort_values("fetched_dt").groupby("source_id", as_index=False).tail(1)
    docs_count = metadata_view.groupby("source_id").size().rename("documents_collected").reset_index()
    success = metadata_view[metadata_view["status"].astype(str).eq("fetched")]
    last_success = success.groupby("source_id")["fetched_dt"].max().rename("latest_success_at").reset_index()
    changed = metadata_view[metadata_view["change_status"].astype(str).isin(["changed", "new_source"])]
    last_changed = changed.groupby("source_id")["fetched_dt"].max().rename("last_changed_at").reset_index()
    health = (
        registry_view.merge(
            latest[["source_id", "fetched_dt", "status_code", "status", "error_message", "change_status", "cleaned_text_path"]],
            on="source_id",
            how="left",
        )
        .merge(docs_count, on="source_id", how="left")
        .merge(last_success, on="source_id", how="left")
        .merge(last_changed, on="source_id", how="left")
    )
else:
    health = registry_view.copy()
    health["fetched_dt"] = pd.NaT
    health["status_code"] = ""
    health["status"] = ""
    health["error_message"] = ""
    health["change_status"] = ""
    health["cleaned_text_path"] = ""
    health["documents_collected"] = 0
    health["latest_success_at"] = pd.NaT
    health["last_changed_at"] = pd.NaT

if not items.empty:
    recent_counts = items.groupby("source_id").size().rename("recent_items_created").reset_index()
    items["detected_dt"] = parse_date_series(items["detected_at"])
    seven_days_ago = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=7)
    recent_7d_sources = set(items[items["detected_dt"] >= seven_days_ago]["source_id"])
else:
    recent_counts = pd.DataFrame(columns=["source_id", "recent_items_created"])
    recent_7d_sources = set()

if not audit.empty:
    audit["checked_dt"] = parse_date_series(audit["checked_at"])
    audit_recent = audit[audit["checked_dt"] >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=7))]
    candidate_counts = audit_recent.groupby("source_id").size().rename("candidate_item_count_7d").reset_index()
    saved_counts = (
        audit_recent[audit_recent["saved_to_recent_items"].astype(str).str.casefold().isin(["true", "1", "yes"])]
        .groupby("source_id")
        .size()
        .rename("saved_item_count_7d")
        .reset_index()
    )
else:
    candidate_counts = pd.DataFrame(columns=["source_id", "candidate_item_count_7d"])
    saved_counts = pd.DataFrame(columns=["source_id", "saved_item_count_7d"])

health = health.merge(recent_counts, on="source_id", how="left")
health = health.merge(candidate_counts, on="source_id", how="left")
health = health.merge(saved_counts, on="source_id", how="left")
for column in ["documents_collected", "recent_items_created", "candidate_item_count_7d", "saved_item_count_7d"]:
    health[column] = health[column].fillna(0).astype(int)
health["last_checked_at"] = health["fetched_dt"]
health["son_7_gun_gelisme"] = health["source_id"].isin(recent_7d_sources)
health["active_label"] = health["active_bool"].map({True: "Aktif", False: "Pasif"})

classified = []
for _, row in health.iterrows():
    result = classify_source_health(
        latest_status=row.get("status", ""),
        status_code=row.get("status_code", ""),
        content_length=100 if str(row.get("cleaned_text_path", "")).strip() else 0,
        candidate_item_count=row.get("candidate_item_count_7d", 0),
        last_success_at=str(row.get("latest_success_at", row.get("last_success_at", ""))).replace("NaT", ""),
        last_changed_at=str(row.get("last_changed_at", "")).replace("NaT", ""),
        collection_method=row.get("collection_method", ""),
        extraction_mode=row.get("extraction_mode", ""),
    )
    classified.append((result.status, result.reason))
health["health_status"] = [item[0] for item in classified]
health["health_reason"] = [item[1] for item in classified]

latest = latest_run(runs)
open_queue = queue[queue.get("review_status", pd.Series(dtype=str)).fillna("").astype(str).isin(["", "Beklemede", "Ek Araştırma Gerekli"])]
open_awareness = awareness[awareness.get("review_status", pd.Series(dtype=str)).fillna("").astype(str).isin(["", "Beklemede", "Ek Araştırma Gerekli"])]
summary_errors = summaries[summaries.get("error_message", pd.Series(dtype=str)).astype(str).str.strip().ne("")]
run_status = "Kayıt yok" if latest is None else str(latest.get("final_status", "") or "Tamamlandı")
run_note = "pipeline_runs.csv bulunamadı" if latest is None else f"{str(latest.get('started_at', ''))[:16]} · {as_int(latest.get('duration_seconds'))} sn"

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Son koşu", run_status, run_note)
with c2:
    sources_checked = 0 if latest is None else as_int(latest.get("sources_checked"))
    sources_failed = 0 if latest is None else as_int(latest.get("sources_failed"))
    metric_card("Kaynak kontrolü", sources_checked, f"{sources_failed} hata · {int(health['mvp_active_bool'].sum())} MVP aktif")
with c3:
    candidates = 0 if latest is None else as_int(latest.get("candidate_links_found"))
    new_items = 0 if latest is None else as_int(latest.get("new_items_created"))
    metric_card("Aday hunisi", candidates, f"{new_items} yeni gelişme")
with c4:
    queue_additions = 0 if latest is None else as_int(latest.get("review_queue_additions"))
    archive_additions = 0 if latest is None else as_int(latest.get("archive_additions"))
    metric_card("Analist işi", len(open_queue) + len(open_awareness), f"{queue_additions} yeni kuyruk · {archive_additions} arşiv")

if latest is not None:
    st.markdown(
        f"""
        <div class="source-health-panel">
          <h3>Bugünkü Operasyon Özeti</h3>
          <p>
            Son koşuda <strong>{sources_checked}</strong> kaynak kontrol edildi,
            <strong>{candidates}</strong> aday link bulundu,
            <strong>{new_items}</strong> yeni gelişme çıkarıldı,
            <strong>{as_int(latest.get('summaries_created'))}</strong> Claude özeti üretildi.
            JSON parse hatası: <strong>{as_int(latest.get('json_parse_failures'))}</strong>.
            {str(latest.get('error_summary', '') or '')}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

health_counts = health["health_status"].value_counts()
h1, h2, h3, h4, h5 = st.columns(5)
h1.metric("Sağlıklı", int(health_counts.get(HEALTHY, 0)))
h2.metric("Uyarı", int(health_counts.get(WARNING, 0)))
h3.metric("Hatalı", int(health_counts.get(ERROR, 0)))
h4.metric("Manuel", int(health_counts.get(MANUAL, 0)))
h5.metric("Stale", int(health_counts.get(STALE, 0)))

problem_statuses = {WARNING, ERROR, STALE}
problem_sources = health[
    health["active_bool"]
    & (
        health["health_status"].isin(problem_statuses)
        | health["source_validation_status"].astype(str).str.contains("needs|blocked|unknown|pending", case=False, na=False)
    )
].copy()
problem_sources = problem_sources.sort_values(["health_status", "coverage_priority", "institution_name"], ascending=[True, True, True])

st.subheader("Aksiyon Gerektiren Kaynaklar")
if problem_sources.empty:
    st.success("Aktif kaynaklarda kritik sağlık problemi görünmüyor.")
else:
    problem_table = problem_sources[
        [
            "source_id",
            "institution_name",
            "source_name",
            "health_status",
            "health_reason",
            "source_validation_status",
            "collector_capability",
            "last_checked_at",
            "status_code",
            "candidate_item_count_7d",
            "saved_item_count_7d",
            "url",
        ]
    ].copy()
    problem_table["last_checked_at"] = problem_table["last_checked_at"].astype(str).replace("NaT", "")
    st.dataframe(
        problem_table.rename(
            columns={
                "source_id": "Kaynak ID",
                "institution_name": "Kurum",
                "source_name": "Kaynak",
                "health_status": "Sağlık",
                "health_reason": "Neden",
                "source_validation_status": "Doğrulama",
                "collector_capability": "Collector",
                "last_checked_at": "Son kontrol",
                "status_code": "HTTP",
                "candidate_item_count_7d": "7g aday",
                "saved_item_count_7d": "7g kayıt",
                "url": "URL",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Son Pipeline Koşuları")
if runs.empty:
    st.info("Henüz pipeline koşu kaydı yok.")
else:
    run_table = runs.copy()
    run_table["_started"] = parse_date_series(run_table["started_at"])
    run_table = run_table.sort_values("_started", ascending=False).head(8)
    run_table = run_table[
        [
            "run_id",
            "started_at",
            "duration_seconds",
            "sources_checked",
            "sources_failed",
            "candidate_links_found",
            "new_items_created",
            "summaries_created",
            "review_queue_additions",
            "archive_additions",
            "json_parse_failures",
            "final_status",
            "report_path",
        ]
    ]
    st.dataframe(
        run_table.rename(
            columns={
                "run_id": "Run ID",
                "started_at": "Başlangıç",
                "duration_seconds": "Süre sn",
                "sources_checked": "Kaynak",
                "sources_failed": "Hata",
                "candidate_links_found": "Aday",
                "new_items_created": "Yeni gelişme",
                "summaries_created": "Claude özeti",
                "review_queue_additions": "Kuyruk",
                "archive_additions": "Arşiv",
                "json_parse_failures": "JSON hata",
                "final_status": "Durum",
                "report_path": "Rapor",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

if not summary_errors.empty:
    st.subheader("Claude / Özetleme Hataları")
    st.dataframe(
        summary_errors[
            [
                "summary_id",
                "institution_name",
                "item_title",
                "created_at",
                "error_message",
            ]
        ].tail(20).rename(
            columns={
                "summary_id": "Özet ID",
                "institution_name": "Kurum",
                "item_title": "Başlık",
                "created_at": "Tarih",
                "error_message": "Hata",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

matrix_columns = [
    "institution_name",
    "institution_id",
    "institution_group",
    "coverage_priority",
    "coverage_scope",
    "sme_relevance",
    "sources_total",
    "valid_weekly_sources",
    "valid_benchmark_sources",
    "browser_required_sources",
    "manual_sources",
    "mvp_active_sources",
    "coverage_status",
    "worked_source_pages",
    "needs_refinement",
]
coverage_matrix = read_optional_csv("private_bank_coverage_matrix.csv", matrix_columns)
if not coverage_matrix.empty:
    with st.expander("Özel banka kapsama matrisi", expanded=False):
        st.dataframe(
            coverage_matrix.rename(
                columns={
                    "institution_name": "Kurum",
                    "institution_group": "Kurum grubu",
                    "coverage_priority": "Öncelik",
                    "sme_relevance": "KOBİ ilgisi",
                    "valid_weekly_sources": "Geçerli haftalık kaynak",
                    "valid_benchmark_sources": "Benchmark kaynak",
                    "browser_required_sources": "Browser gerekli",
                    "manual_sources": "Manuel",
                    "mvp_active_sources": "MVP aktif",
                    "coverage_status": "Kapsama durumu",
                    "worked_source_pages": "Çalışan kaynaklar",
                    "needs_refinement": "İyileştirme gerekenler",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

with st.sidebar:
    st.header("Kaynak Filtreleri")
    institution_groups = sorted(health["institution_group"].dropna().astype(str).unique())
    institutions = sorted(health["institution_name"].dropna().astype(str).unique())
    source_types = sorted(health["source_type"].dropna().astype(str).unique())
    modes = sorted(health["extraction_mode"].dropna().astype(str).unique())
    health_statuses = sorted(health["health_status"].dropna().astype(str).unique())
    validation_statuses = sorted(health.get("source_validation_status", pd.Series(dtype=str)).dropna().astype(str).unique())
    active_labels = sorted(health["active_label"].dropna().astype(str).unique())

    selected_groups = st.multiselect("Kurum grubu", institution_groups, default=institution_groups)
    selected_institutions = st.multiselect("Kurum", institutions, default=institutions)
    selected_source_types = st.multiselect("Kaynak tipi", source_types, default=source_types)
    selected_modes = st.multiselect("extraction_mode", modes, default=modes)
    selected_health = st.multiselect("Sağlık", health_statuses, default=health_statuses)
    selected_validation_statuses = st.multiselect("Doğrulama durumu", validation_statuses, default=validation_statuses)
    selected_active = st.multiselect("Aktif/Pasif", active_labels, default=active_labels)

filtered = health[
    health["institution_group"].isin(selected_groups)
    & health["institution_name"].isin(selected_institutions)
    & health["source_type"].isin(selected_source_types)
    & health["extraction_mode"].isin(selected_modes)
    & health["health_status"].isin(selected_health)
    & health["source_validation_status"].isin(selected_validation_statuses)
    & health["active_label"].isin(selected_active)
].copy()

st.subheader("Kurum Bazında Kaynak Sayısı")
st.bar_chart(filtered["institution_name"].value_counts())

st.subheader("Kaynak Sağlığı Tablosu")
table = filtered[
    [
        "source_id",
        "institution_name",
        "source_name",
        "source_type",
        "coverage_priority",
        "sme_relevance",
        "health_status",
        "health_reason",
        "source_validation_status",
        "collector_capability",
        "mvp_active",
        "weekly_collection_enabled",
        "extraction_mode",
        "url",
        "last_checked_at",
        "status_code",
        "change_status",
        "latest_success_at",
        "documents_collected",
        "candidate_item_count_7d",
        "saved_item_count_7d",
        "recent_items_created",
        "active_label",
        "status",
        "error_message",
    ]
].copy()
table["last_checked_at"] = table["last_checked_at"].astype(str).replace("NaT", "")
table["latest_success_at"] = table["latest_success_at"].astype(str).replace("NaT", "")
st.dataframe(
    table.rename(
        columns={
            "source_id": "Kaynak ID",
            "institution_name": "Kurum",
            "source_name": "Kaynak adı",
            "source_type": "Kaynak tipi",
            "coverage_priority": "Kapsama önceliği",
            "sme_relevance": "KOBİ ilgisi",
            "health_status": "Sağlık",
            "health_reason": "Sağlık nedeni",
            "source_validation_status": "Doğrulama",
            "collector_capability": "Collector",
            "mvp_active": "MVP aktif",
            "weekly_collection_enabled": "Haftalık açık",
            "extraction_mode": "Çıkarım modu",
            "url": "URL",
            "last_checked_at": "Son kontrol",
            "status_code": "HTTP",
            "change_status": "Değişim",
            "latest_success_at": "Son başarılı",
            "documents_collected": "Toplanan doküman",
            "candidate_item_count_7d": "7g aday",
            "saved_item_count_7d": "7g kayıt",
            "recent_items_created": "Toplam gelişme",
            "active_label": "Durum",
            "status": "Tarama durumu",
            "error_message": "Hata",
        }
    ),
    use_container_width=True,
    hide_index=True,
)
