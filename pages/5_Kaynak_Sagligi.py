from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.recent_mvp import (
    METADATA_COLUMNS,
    RECENT_ITEM_COLUMNS,
    SOURCE_COLUMNS,
    is_active,
    parse_date_series,
    read_csv_safe,
)
from utils.institution_aliases import institution_group
from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(page_title="Kaynak Sağlığı", layout="wide")
apply_akbank_theme()

render_page_header(
    "Kaynak Sağlığı",
    "Kaynak tarama durumu, hata sinyalleri ve gelişme üretimi.",
)

registry = read_csv_safe("source_registry.csv", SOURCE_COLUMNS)
metadata = read_csv_safe("raw_documents_metadata.csv", METADATA_COLUMNS)
items = read_csv_safe("recent_items.csv", RECENT_ITEM_COLUMNS)

if registry.empty:
    st.info("Kaynak envanteri bulunamadı.")
    st.stop()
    raise SystemExit

registry_view = registry.copy()
registry_view["active_bool"] = registry_view["active"].apply(is_active)
registry_view["mvp_active_bool"] = registry_view.get("mvp_active", "").apply(is_active)
registry_view["institution_group"] = registry_view["institution_name"].apply(institution_group)

if not metadata.empty:
    metadata_view = metadata.copy()
    metadata_view["fetched_dt"] = parse_date_series(metadata_view["fetched_at"])
    latest = metadata_view.sort_values("fetched_dt").groupby("source_id", as_index=False).tail(1)
    docs_count = metadata_view.groupby("source_id").size().rename("documents_collected").reset_index()
    success = metadata_view[metadata_view["status"].astype(str).eq("fetched")]
    last_success = success.groupby("source_id")["fetched_dt"].max().rename("last_success_at").reset_index()
    health = registry_view.merge(
        latest[["source_id", "fetched_dt", "status_code", "status", "error_message"]],
        on="source_id",
        how="left",
    ).merge(docs_count, on="source_id", how="left").merge(last_success, on="source_id", how="left")
else:
    health = registry_view.copy()
    health["fetched_dt"] = pd.NaT
    health["status_code"] = ""
    health["status"] = ""
    health["error_message"] = ""
    health["documents_collected"] = 0
    health["last_success_at"] = pd.NaT

if not items.empty:
    recent_counts = items.groupby("source_id").size().rename("recent_items_created").reset_index()
    items["detected_dt"] = parse_date_series(items["detected_at"])
    recent_7d_sources = set(items[items["detected_dt"] >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=7))]["source_id"])
else:
    recent_counts = pd.DataFrame(columns=["source_id", "recent_items_created"])
    recent_7d_sources = set()

health = health.merge(recent_counts, on="source_id", how="left")
health["documents_collected"] = health["documents_collected"].fillna(0).astype(int)
health["recent_items_created"] = health["recent_items_created"].fillna(0).astype(int)
health["last_checked_at"] = health["fetched_dt"]
health["son_7_gun_gelisme"] = health["source_id"].isin(recent_7d_sources)
health["active_label"] = health["active_bool"].map({True: "Aktif", False: "Pasif"})

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Aktif kaynak", int(health["active_bool"].sum()))
k2.metric("Son taranan kaynak", int(health["last_checked_at"].notna().sum()))
k3.metric("Başarılı tarama", int(health["status"].astype(str).eq("fetched").sum()))
k4.metric("Hata alan kaynak", int(health["status"].astype(str).eq("error").sum()))
k5.metric("MVP aktif kaynak", int(health["mvp_active_bool"].sum()))
k6.metric("Kurum sayısı", health["institution_name"].nunique())

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
coverage_matrix = pd.DataFrame(columns=matrix_columns)
if (Path(__file__).resolve().parents[1] / "data" / "private_bank_coverage_matrix.csv").exists():
    coverage_matrix = read_csv_safe("private_bank_coverage_matrix.csv", matrix_columns)
if not coverage_matrix.empty:
    st.subheader("Özel Banka Kapsama Matrisi")
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
    validation_statuses = sorted(health.get("source_validation_status", pd.Series(dtype=str)).dropna().astype(str).unique())
    status_codes = sorted(health["status_code"].dropna().astype(str).unique())
    active_labels = sorted(health["active_label"].dropna().astype(str).unique())

    selected_groups = st.multiselect("Kurum grubu", institution_groups, default=institution_groups)
    selected_institutions = st.multiselect("Kurum", institutions, default=institutions)
    selected_source_types = st.multiselect("Kaynak tipi", source_types, default=source_types)
    selected_modes = st.multiselect("extraction_mode", modes, default=modes)
    selected_validation_statuses = st.multiselect("Doğrulama durumu", validation_statuses, default=validation_statuses)
    selected_status_codes = st.multiselect("status_code", status_codes, default=status_codes)
    selected_active = st.multiselect("Aktif/Pasif", active_labels, default=active_labels)

filtered = health[
    health["institution_group"].isin(selected_groups)
    & health["institution_name"].isin(selected_institutions)
    & health["source_type"].isin(selected_source_types)
    & health["extraction_mode"].isin(selected_modes)
    & health["source_validation_status"].isin(selected_validation_statuses)
    & health["status_code"].astype(str).isin(selected_status_codes)
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
        "source_validation_status",
        "collector_capability",
        "mvp_active",
        "extraction_mode",
        "url",
        "last_checked_at",
        "status_code",
        "last_success_at",
        "documents_collected",
        "recent_items_created",
        "active_label",
        "status",
        "error_message",
    ]
].copy()
table["last_checked_at"] = table["last_checked_at"].astype(str).replace("NaT", "")
table["last_success_at"] = table["last_success_at"].astype(str).replace("NaT", "")
st.dataframe(
    table.rename(
        columns={
            "source_id": "Kaynak ID",
            "institution_name": "Kurum",
            "source_name": "Kaynak adı",
            "source_type": "Kaynak tipi",
            "coverage_priority": "Kapsama önceliği",
            "sme_relevance": "KOBİ ilgisi",
            "source_validation_status": "Doğrulama",
            "collector_capability": "Collector",
            "mvp_active": "MVP aktif",
            "extraction_mode": "Çıkarım modu",
            "url": "URL",
            "last_checked_at": "Son kontrol",
            "status_code": "HTTP",
            "last_success_at": "Son başarılı",
            "documents_collected": "Toplanan doküman",
            "recent_items_created": "Gelişme sayısı",
            "active_label": "Durum",
            "status": "Tarama durumu",
            "error_message": "Hata",
        }
    ),
    use_container_width=True,
    hide_index=True,
)
