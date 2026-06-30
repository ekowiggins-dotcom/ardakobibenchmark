import pandas as pd
import streamlit as st

from utils.data_loader import load_all_data, with_institution_names
from utils.translations import format_turkish_date, tr_columns, tr_label


st.set_page_config(page_title="Haftalık Gelişmeler Radarı", layout="wide")

data = load_all_data()
institutions = data["institutions"]
registry = data["source_registry"]
weekly = with_institution_names(data["weekly_developments"], institutions)
queue = data["review_queue"].copy()
extractions = data["llm_extractions"].copy()

st.title("Haftalık Gelişmeler Radarı")
st.caption("Akbank KOBİ strateji ve BD ekipleri için onaylı haftalık rekabet gelişmeleri.")

source_lookup = registry[
    ["source_id", "tier", "source_type", "source_name", "url", "reliability_level"]
].rename(columns={"url": "source_url"})

approved = weekly.merge(source_lookup, on="source_id", how="left")
approved["date"] = pd.to_datetime(approved["date"], errors="coerce")
approved["review_status"] = "Approved"
approved["confidence_level"] = approved["tags"].fillna("").str.extract(r"confidence:([^;]+)")[0].fillna("High")
approved["source_lane"] = "Onaylı gelişmeler"
approved["tier"] = approved["tier"].fillna("Mock/Eski")
approved["source_type"] = approved["source_type"].fillna("Eski kaynak")
approved["source_name"] = approved["source_name"].fillna(approved["source_id"])
approved["source_url"] = approved["source_url"].fillna("")
approved["reliability_level"] = approved["reliability_level"].fillna("Medium")

if not queue.empty and not extractions.empty:
    pending = queue.merge(
        extractions,
        on=["extraction_id", "document_id", "source_id"],
        how="left",
        suffixes=("_review", ""),
    )
    pending = pending.merge(source_lookup, on="source_id", how="left")
    pending = pending[pending["review_status_review"].fillna("Pending").eq("Pending")].copy()
    pending["date"] = pd.to_datetime(pending["created_at"], errors="coerce")
    pending["analyst_note"] = pending["review_notes"].fillna("")
    pending["source_lane"] = "Onay bekleyen maddeler"
    pending["tags"] = ""
else:
    pending = pd.DataFrame()

common_columns = [
    "date",
    "institution_id",
    "institution_name",
    "institution_type",
    "headline",
    "strategic_theme",
    "product_area",
    "development_type",
    "summary",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "source_id",
    "analyst_note",
    "tier",
    "source_type",
    "source_name",
    "source_url",
    "reliability_level",
    "confidence_level",
    "review_status",
    "source_lane",
]
for col in common_columns:
    if col not in approved.columns:
        approved[col] = ""
    if not pending.empty and col not in pending.columns:
        pending[col] = ""

combined = approved[common_columns]
if not pending.empty:
    combined = pd.concat([combined, pending[common_columns]], ignore_index=True)
combined = combined[combined["date"].notna()].copy()

if combined.empty:
    st.warning("Henüz radar maddesi bulunmuyor.")
    st.stop()

impact_rank = {"Yüksek": 3, "High": 3, "Orta": 2, "Medium": 2, "Düşük": 1, "Low": 1}
importance_rank = {"Kritik": 4, "Critical": 4, "Yüksek": 3, "High": 3, "Orta": 2, "Medium": 2, "Düşük": 1, "Low": 1}
action_rank = {
    "Yönetime Eskale Et": 4,
    "Escalate to Leadership": 4,
    "Yanıt Geliştir": 3,
    "Respond": 3,
    "Uyarlama Fırsatını Değerlendir": 3,
    "Copy / Adapt": 3,
    "İş Birliği Fırsatını İncele": 2,
    "Explore Partnership": 2,
    "BD Konuşma Notlarına Ekle": 2,
    "Add to BD Talking Points": 2,
    "İzle": 1,
    "Monitor": 1,
}
combined["briefing_score"] = (
    combined["impact_on_us"].map(impact_rank).fillna(0) * 3
    + combined["importance_level"].map(importance_rank).fillna(0) * 2
    + combined["recommended_action"].map(action_rank).fillna(0)
)

min_date = combined["date"].min().date()
max_date = combined["date"].max().date()
default_start = (pd.Timestamp(max_date) - pd.Timedelta(days=6)).date()

with st.sidebar:
    st.header("Radar Filtreleri")
    show_pending = st.checkbox("Onay bekleyen maddeleri de göster", value=False)
    selected_range = st.date_input("Tarih Aralığı", value=(default_start, max_date), min_value=min_date, max_value=max_date)
    selected_institutions = st.multiselect("Kurum", sorted(combined["institution_name"].dropna().unique()), default=sorted(combined["institution_name"].dropna().unique()))
    selected_types = st.multiselect("Kurum Tipi", sorted(combined["institution_type"].dropna().unique()), default=sorted(combined["institution_type"].dropna().unique()))
    selected_tiers = st.multiselect("Kaynak Seviyesi", sorted(combined["tier"].dropna().unique()), default=sorted(combined["tier"].dropna().unique()))
    selected_source_types = st.multiselect("Kaynak Tipi", sorted(combined["source_type"].dropna().unique()), default=sorted(combined["source_type"].dropna().unique()))
    selected_themes = st.multiselect("Stratejik Tema", sorted(combined["strategic_theme"].dropna().unique()), default=sorted(combined["strategic_theme"].dropna().unique()))
    selected_impacts = st.multiselect("Etki Seviyesi", sorted(combined["impact_on_us"].dropna().unique()), default=sorted(combined["impact_on_us"].dropna().unique()))
    selected_confidence = st.multiselect("Güven Seviyesi", sorted(combined["confidence_level"].dropna().unique()), default=sorted(combined["confidence_level"].dropna().unique()))
    selected_actions = st.multiselect("Önerilen Aksiyon", sorted(combined["recommended_action"].dropna().unique()), default=sorted(combined["recommended_action"].dropna().unique()))

if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date, end_date = default_start, max_date

lanes = ["Onaylı gelişmeler"]
if show_pending:
    lanes.append("Onay bekleyen maddeler")

filtered = combined[
    (combined["date"].dt.date >= start_date)
    & (combined["date"].dt.date <= end_date)
    & combined["institution_name"].isin(selected_institutions)
    & combined["institution_type"].isin(selected_types)
    & combined["tier"].isin(selected_tiers)
    & combined["source_type"].isin(selected_source_types)
    & combined["strategic_theme"].isin(selected_themes)
    & combined["impact_on_us"].isin(selected_impacts)
    & combined["confidence_level"].isin(selected_confidence)
    & combined["recommended_action"].isin(selected_actions)
    & combined["source_lane"].isin(lanes)
].copy()

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen madde yok.")
    st.stop()

approved_filtered = filtered[filtered["source_lane"].eq("Onaylı gelişmeler")]
pending_filtered = filtered[filtered["source_lane"].eq("Onay bekleyen maddeler")]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Radardaki madde", len(filtered))
k2.metric("Yüksek etki", filtered["impact_on_us"].apply(lambda x: tr_label("impact_on_us", x)).eq("Yüksek").sum())
k3.metric("En aktif kurum", filtered["institution_name"].mode().iloc[0])
k4.metric("En sık tema", tr_label("strategic_theme", filtered["strategic_theme"].mode().iloc[0]))

st.subheader("Bu Haftanın Öne Çıkan Gelişmeleri")
table = filtered.sort_values(["date", "briefing_score"], ascending=[False, False])[
    ["date", "source_lane", "institution_name", "tier", "source_type", "headline", "strategic_theme", "impact_on_us", "confidence_level", "recommended_action"]
].copy()
table["date"] = table["date"].apply(format_turkish_date)
table["strategic_theme"] = table["strategic_theme"].apply(lambda x: tr_label("strategic_theme", x))
table["impact_on_us"] = table["impact_on_us"].apply(lambda x: tr_label("impact_on_us", x))
table["confidence_level"] = table["confidence_level"].apply(lambda x: tr_label("confidence_level", x))
table["recommended_action"] = table["recommended_action"].apply(lambda x: tr_label("recommended_action", x))
st.dataframe(
    tr_columns(
        table,
        {
            "date": "Tarih",
            "source_lane": "Durum",
            "institution_name": "Kurum",
            "tier": "Kaynak seviyesi",
            "source_type": "Kaynak tipi",
            "headline": "Başlık",
            "strategic_theme": "Stratejik tema",
            "impact_on_us": "Etki",
            "confidence_level": "Güven",
            "recommended_action": "Önerilen aksiyon",
        },
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Onay Bekleyen Yeni Maddeler")
if pending_filtered.empty:
    st.success("Seçili filtrelerde onay bekleyen madde yok.")
else:
    st.dataframe(pending_filtered[["institution_name", "headline", "strategic_theme", "impact_on_us", "confidence_level", "recommended_action"]], use_container_width=True, hide_index=True)

st.subheader("Yönetime Sunulacak İlk 5 Gelişme")
top_five = approved_filtered.sort_values(["briefing_score", "date"], ascending=[False, False]).head(5)
if top_five.empty:
    st.info("Onaylı gelişme bulunmadığı için yönetim özeti üretilemiyor.")
else:
    for _, row in top_five.iterrows():
        st.markdown(f"**{row['institution_name']} - {row['headline']}**")
        st.write(row["strategic_relevance"])

st.subheader("BD Konuşma Notları")
if top_five.empty:
    st.info("BD konuşma notları için önce gelişmelerin onaylanması gerekir.")
else:
    for _, row in top_five.iterrows():
        action = tr_label("recommended_action", row["recommended_action"])
        st.write(f"- {row['institution_name']} gelişmesi için önerilen aksiyon: {action}. BD görüşmelerinde {row['product_area']} ihtiyacını sorun.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Tema Bazlı Gelişmeler")
    theme_counts = filtered.assign(Tema=filtered["strategic_theme"].apply(lambda x: tr_label("strategic_theme", x))).groupby("Tema", as_index=False).size()
    st.dataframe(theme_counts.rename(columns={"size": "Madde sayısı"}), hide_index=True, use_container_width=True)
with col2:
    st.subheader("Kurum Bazlı Gelişmeler")
    inst_counts = filtered.groupby("institution_name", as_index=False).size().rename(columns={"institution_name": "Kurum", "size": "Madde sayısı"})
    st.dataframe(inst_counts, hide_index=True, use_container_width=True)

st.subheader("Geçen Haftadan Bu Haftaya Ne Değişti?")
st.info("V2 otomasyon alanı: önceki hafta ile bu haftanın onaylı gelişmeleri karşılaştırılarak yeni tema, tekrar eden kurum aktivitesi ve yönetim özeti fark analizi üretilecek.")
