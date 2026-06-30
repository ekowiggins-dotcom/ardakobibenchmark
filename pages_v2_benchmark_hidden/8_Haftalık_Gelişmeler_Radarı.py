import pandas as pd
import streamlit as st

from utils.data_loader import load_all_data
from utils.translations import format_turkish_date, tr_columns, tr_label


st.set_page_config(page_title="Haftalık Gelişmeler Radarı", layout="wide")

data = load_all_data()
institutions = data["institutions"]
registry = data["source_registry"]
weekly = data["weekly_developments"].copy()

st.title("Haftalık Gelişmeler Radarı")
st.caption("Akbank KOBİ strateji ve BD ekipleri için analist onayından geçmiş haftalık rekabet gelişmeleri.")
st.info("Bu radar yalnızca analist onayından geçen gelişmeleri gösterir.")

if weekly.empty:
    st.warning("Henüz yayınlanmış haftalık gelişme yok.")
    st.stop()

institution_cols = ["institution_id", "institution_name", "institution_type", "country", "region"]
institution_lookup = institutions[institution_cols].copy()
weekly = weekly.merge(institution_lookup, on="institution_id", how="left", suffixes=("", "_master"))
for column in ["institution_name", "institution_type", "country", "region"]:
    master_col = f"{column}_master"
    if column not in weekly.columns:
        weekly[column] = ""
    if master_col in weekly.columns:
        weekly[column] = weekly[column].fillna(weekly[master_col])
        weekly = weekly.drop(columns=[master_col])

source_lookup = registry[
    ["source_id", "tier", "source_type", "source_name", "url", "reliability_level"]
].rename(columns={"url": "source_url_registry"})
weekly = weekly.merge(source_lookup, on="source_id", how="left")
for column in ["summary_id", "recent_item_id", "source_url", "item_url", "institution_name"]:
    if column not in weekly.columns:
        weekly[column] = ""
weekly["source_url"] = weekly["source_url"].fillna("")
weekly["source_url"] = weekly["source_url"].where(weekly["source_url"].astype(str).str.len() > 0, weekly["source_url_registry"].fillna(""))
weekly["item_url"] = weekly["item_url"].fillna("")
weekly["date"] = pd.to_datetime(weekly["date"], errors="coerce")
weekly = weekly[weekly["date"].notna()].copy()

if weekly.empty:
    st.warning("Tarih bilgisi okunabilen yayınlanmış gelişme yok.")
    st.stop()

for column in [
    "tier",
    "source_type",
    "source_name",
    "reliability_level",
    "strategic_theme",
    "product_area",
    "development_type",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "core_assessment",
    "analyst_note",
    "tags",
]:
    if column not in weekly.columns:
        weekly[column] = ""
    weekly[column] = weekly[column].fillna("")

importance_rank = {"Kritik": 4, "Critical": 4, "Yüksek": 3, "Orta": 2, "Düşük": 1}
impact_rank = {"Yüksek": 3, "Orta": 2, "Düşük": 1}
action_rank = {
    "Yönetime Eskale Et": 4,
    "Yönetici Bilgilendirme Notuna Ekle": 3,
    "Yanıt Geliştir": 3,
    "Uyarlama Fırsatını Değerlendir": 3,
    "İş Birliği Fırsatını İncele": 2,
    "BD Konuşma Notlarına Ekle": 2,
    "İzle": 1,
    "Önceliklendirme": 0,
}
weekly["briefing_score"] = (
    weekly["importance_level"].map(importance_rank).fillna(0) * 3
    + weekly["impact_on_us"].map(impact_rank).fillna(0) * 2
    + weekly["recommended_action"].map(action_rank).fillna(0)
)

min_date = weekly["date"].min().date()
max_date = weekly["date"].max().date()
default_start = (pd.Timestamp(max_date) - pd.Timedelta(days=6)).date()

with st.sidebar:
    st.header("Radar Filtreleri")
    selected_range = st.date_input("Tarih Aralığı", value=(default_start, max_date), min_value=min_date, max_value=max_date)
    selected_institutions = st.multiselect("Kurum", sorted(weekly["institution_name"].dropna().unique()), default=sorted(weekly["institution_name"].dropna().unique()))
    selected_types = st.multiselect("Kurum Tipi", sorted(weekly["institution_type"].dropna().unique()), default=sorted(weekly["institution_type"].dropna().unique()))
    selected_tiers = st.multiselect("Kaynak Seviyesi", sorted(weekly["tier"].dropna().unique()), default=sorted(weekly["tier"].dropna().unique()))
    selected_source_types = st.multiselect("Kaynak Tipi", sorted(weekly["source_type"].dropna().unique()), default=sorted(weekly["source_type"].dropna().unique()))
    selected_themes = st.multiselect("Stratejik Tema", sorted(weekly["strategic_theme"].dropna().unique()), default=sorted(weekly["strategic_theme"].dropna().unique()))
    selected_product_areas = st.multiselect("Ürün Alanı", sorted(weekly["product_area"].dropna().unique()), default=sorted(weekly["product_area"].dropna().unique()))
    selected_impacts = st.multiselect("Etki Seviyesi", sorted(weekly["impact_on_us"].dropna().unique()), default=sorted(weekly["impact_on_us"].dropna().unique()))
    selected_importance = st.multiselect("Önem Seviyesi", sorted(weekly["importance_level"].dropna().unique()), default=sorted(weekly["importance_level"].dropna().unique()))
    selected_actions = st.multiselect("Önerilen Aksiyon", sorted(weekly["recommended_action"].dropna().unique()), default=sorted(weekly["recommended_action"].dropna().unique()))

if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date, end_date = default_start, max_date

filtered = weekly[
    (weekly["date"].dt.date >= start_date)
    & (weekly["date"].dt.date <= end_date)
    & weekly["institution_name"].isin(selected_institutions)
    & weekly["institution_type"].isin(selected_types)
    & weekly["tier"].isin(selected_tiers)
    & weekly["source_type"].isin(selected_source_types)
    & weekly["strategic_theme"].isin(selected_themes)
    & weekly["product_area"].isin(selected_product_areas)
    & weekly["impact_on_us"].isin(selected_impacts)
    & weekly["importance_level"].isin(selected_importance)
    & weekly["recommended_action"].isin(selected_actions)
].copy()

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen onaylı gelişme yok.")
    st.stop()

filtered = filtered.sort_values(["briefing_score", "date"], ascending=[False, False])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Onaylı gelişme", len(filtered))
k2.metric("Yüksek etki", filtered["impact_on_us"].eq("Yüksek").sum())
k3.metric("En aktif kurum", filtered["institution_name"].mode().iloc[0])
k4.metric("En sık tema", tr_label("strategic_theme", filtered["strategic_theme"].mode().iloc[0]))

st.subheader("Yönetime Sunulacak İlk 5 Gelişme")
top_five = filtered.head(5)
for _, row in top_five.iterrows():
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"**{row['institution_name']} - {row['headline']}**")
        if str(row.get("core_assessment", "") or "").strip():
            c1.write(f"**Kısa değerlendirme:** {row['core_assessment']}")
        c1.write(row["summary"])
        c1.caption(row["strategic_relevance"])
        c2.metric("Etki", tr_label("impact_on_us", row["impact_on_us"]))
        c2.metric("Aksiyon", tr_label("recommended_action", row["recommended_action"]))
        if str(row.get("item_url", "") or "").startswith("http"):
            c2.link_button("Gelişmeyi Aç", row["item_url"])
        elif str(row.get("source_url", "") or "").startswith("http"):
            c2.link_button("Kaynağı Aç", row["source_url"])

st.subheader("Bu Haftanın Onaylı Gelişmeleri")
table = filtered[
    [
        "date",
        "institution_name",
        "headline",
        "strategic_theme",
        "product_area",
        "impact_on_us",
        "recommended_action",
        "importance_level",
        "source_name",
    ]
].copy()
table["date"] = table["date"].apply(format_turkish_date)
st.dataframe(
    tr_columns(
        table,
        {
            "date": "Tarih",
            "institution_name": "Kurum",
            "headline": "Başlık",
            "strategic_theme": "Stratejik tema",
            "product_area": "Ürün alanı",
            "impact_on_us": "Etki",
            "recommended_action": "Önerilen aksiyon",
            "importance_level": "Önem",
            "source_name": "Kaynak",
        },
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("BD Konuşma Notları")
for _, row in top_five.iterrows():
    action = tr_label("recommended_action", row["recommended_action"])
    st.write(f"- **{row['institution_name']}**: {row['product_area']} alanında {action}. {row['analyst_note']}")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Kurum Bazlı Gelişmeler")
    inst_counts = filtered.groupby("institution_name", as_index=False).size().rename(
        columns={"institution_name": "Kurum", "size": "Madde sayısı"}
    )
    st.dataframe(inst_counts.sort_values("Madde sayısı", ascending=False), hide_index=True, use_container_width=True)
with col2:
    st.subheader("Tema Bazlı Gelişmeler")
    theme_counts = filtered.groupby("strategic_theme", as_index=False).size().rename(
        columns={"strategic_theme": "Tema", "size": "Madde sayısı"}
    )
    theme_counts["Tema"] = theme_counts["Tema"].apply(lambda x: tr_label("strategic_theme", x))
    st.dataframe(theme_counts.sort_values("Madde sayısı", ascending=False), hide_index=True, use_container_width=True)

st.subheader("Gelişme Detayları ve Kaynaklar")
for _, row in filtered.iterrows():
    with st.expander(f"{format_turkish_date(row['date'])} | {row['institution_name']} | {row['headline']}"):
        st.write(row["summary"])
        if str(row.get("core_assessment", "") or "").strip():
            st.write(f"**Kısa değerlendirme:** {row['core_assessment']}")
        st.write(f"**Stratejik önem:** {row['strategic_relevance']}")
        st.write(f"**Analist notu:** {row['analyst_note']}")
        links = st.columns(2)
        if str(row.get("item_url", "") or "").startswith("http"):
            links[0].link_button("Gelişmeyi Aç", row["item_url"])
        if str(row.get("source_url", "") or "").startswith("http"):
            links[1].link_button("Kaynağı Aç", row["source_url"])
