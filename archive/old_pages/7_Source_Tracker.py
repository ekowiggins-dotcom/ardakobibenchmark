import pandas as pd
import streamlit as st

from utils.data_loader import load_all_data, with_institution_names
from utils.translations import tr_columns, tr_label


st.set_page_config(page_title="Kaynak Takibi", layout="wide")

data = load_all_data()
institutions = data["institutions"]
legacy_sources = with_institution_names(data["sources"], institutions)
registry = data["source_registry"].copy()
metadata = data["raw_documents_metadata"].copy()

st.title("Kaynak Takibi")
st.caption("Kanonik kaynak envanteri, son kontrol durumu ve yarı otomasyon izleme görünümü.")
st.warning(
    "Not: `sources.csv` eski/mock kaynak takip dosyası olabilir. Otomatik izleme için kanonik dosya "
    "`source_registry.csv`’dir."
)

if not metadata.empty:
    metadata = metadata.sort_values("fetched_at")
    latest = metadata.groupby("source_id", as_index=False).tail(1)
else:
    latest = pd.DataFrame(
        columns=[
            "source_id",
            "fetched_at",
            "content_hash",
            "status",
            "change_status",
            "status_code",
            "error_message",
            "document_id",
        ]
    )

for col in ["change_status", "status_code"]:
    if col not in latest.columns:
        latest[col] = ""

registry_view = registry.merge(
    latest[
        [
            "source_id",
            "fetched_at",
            "content_hash",
            "status",
            "change_status",
            "status_code",
            "error_message",
            "document_id",
        ]
    ],
    on="source_id",
    how="left",
)
registry_view["active_label"] = registry_view["active"].astype(str).str.lower().map(
    {"true": "Aktif", "1": "Aktif", "yes": "Aktif", "false": "Pasif"}
).fillna("Pasif")

today = pd.Timestamp.today(tz="UTC")
registry_view["days_since_fetch"] = (
    today - pd.to_datetime(registry_view["fetched_at"], utc=True, errors="coerce")
).dt.days
registry_view["last_fetched"] = pd.to_datetime(
    registry_view["fetched_at"], errors="coerce"
).dt.strftime("%d.%m.%Y %H:%M")
registry_view["last_fetched"] = registry_view["last_fetched"].fillna("Henüz kontrol edilmedi")
registry_view["latest_content_hash"] = registry_view["content_hash"].fillna("").astype(str).str[:12]
registry_view["latest_status"] = registry_view["status"].fillna("not_checked")
registry_view["latest_change_status"] = registry_view["change_status"].fillna("not_checked")
registry_view["has_error"] = registry_view["latest_status"].eq("error") | registry_view[
    "latest_change_status"
].eq("error")

with st.sidebar:
    st.header("Kaynak Filtreleri")
    active_filter = st.multiselect("Aktiflik", ["Aktif", "Pasif"], default=["Aktif", "Pasif"])
    tier_filter = st.multiselect(
        "Kaynak seviyesi",
        sorted(registry_view["tier"].dropna().unique()),
        default=sorted(registry_view["tier"].dropna().unique()),
    )
    source_type_filter = st.multiselect(
        "Kaynak tipi",
        sorted(registry_view["source_type"].dropna().unique()),
        default=sorted(registry_view["source_type"].dropna().unique()),
    )
    mode_filter = st.multiselect(
        "Çıkarım modu",
        sorted(registry_view["extraction_mode"].dropna().unique()),
        default=sorted(registry_view["extraction_mode"].dropna().unique()),
    )
    status_filter = st.multiselect(
        "Son değişim durumu",
        sorted(registry_view["latest_change_status"].dropna().unique()),
        default=sorted(registry_view["latest_change_status"].dropna().unique()),
    )
    institution_filter = st.multiselect(
        "Kurum / kaynak sahibi",
        sorted(registry_view["institution_name"].dropna().unique()),
        default=sorted(registry_view["institution_name"].dropna().unique()),
    )

filtered_registry = registry_view[
    registry_view["active_label"].isin(active_filter)
    & registry_view["tier"].isin(tier_filter)
    & registry_view["source_type"].isin(source_type_filter)
    & registry_view["extraction_mode"].isin(mode_filter)
    & registry_view["latest_change_status"].isin(status_filter)
    & registry_view["institution_name"].isin(institution_filter)
].copy()

errors = filtered_registry[filtered_registry["has_error"]]
not_checked_7 = filtered_registry[
    filtered_registry["active_label"].eq("Aktif")
    & (filtered_registry["days_since_fetch"].isna() | (filtered_registry["days_since_fetch"] > 7))
]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Toplam kaynak", len(filtered_registry))
k2.metric("Aktif kaynak", filtered_registry["active_label"].eq("Aktif").sum())
k3.metric("Static scrape", filtered_registry["collection_method"].eq("static_scrape").sum())
k4.metric("Yeni / değişen", filtered_registry["latest_change_status"].isin(["changed", "new_source"]).sum())
k5.metric("Hata veren", len(errors))

st.subheader("Kaynak Envanteri")
display = filtered_registry[
    [
        "source_id",
        "tier",
        "institution_name",
        "source_name",
        "source_type",
        "collection_method",
        "extraction_mode",
        "reliability_level",
        "strategic_themes",
        "active_label",
        "last_fetched",
        "status_code",
        "latest_status",
        "latest_change_status",
        "latest_content_hash",
        "url",
    ]
]
st.dataframe(
    tr_columns(
        display,
        {
            "source_id": "Kaynak ID",
            "tier": "Seviye",
            "institution_name": "Kurum",
            "source_name": "Kaynak adı",
            "source_type": "Kaynak tipi",
            "collection_method": "Toplama yöntemi",
            "extraction_mode": "Çıkarım modu",
            "reliability_level": "Güvenilirlik",
            "strategic_themes": "Stratejik temalar",
            "active_label": "Aktiflik",
            "last_fetched": "Son kontrol",
            "status_code": "HTTP kodu",
            "latest_status": "Toplama durumu",
            "latest_change_status": "Değişim durumu",
            "latest_content_hash": "İçerik hash",
            "url": "URL",
        },
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Son Kontrol Durumu")
c1, c2 = st.columns(2)
with c1:
    st.write("**Kaynak seviyesi dağılımı**")
    st.dataframe(filtered_registry["tier"].value_counts().rename_axis("Seviye").reset_index(name="Kaynak sayısı"), hide_index=True)
with c2:
    st.write("**Çıkarım modu dağılımı**")
    st.dataframe(filtered_registry["extraction_mode"].value_counts().rename_axis("Çıkarım modu").reset_index(name="Kaynak sayısı"), hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader("Hata Veren Kaynaklar")
    if errors.empty:
        st.success("Seçili filtrelerde hata veren kaynak yok.")
    else:
        st.dataframe(
            tr_columns(
                errors[["source_id", "institution_name", "source_name", "url", "last_fetched", "error_message"]],
                {
                    "source_id": "Kaynak ID",
                    "institution_name": "Kurum",
                    "source_name": "Kaynak adı",
                    "url": "URL",
                    "last_fetched": "Son kontrol",
                    "error_message": "Hata mesajı",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )

with right:
    st.subheader("Son 7 Günde Kontrol Edilmeyen Kaynaklar")
    if not_checked_7.empty:
        st.success("Seçili filtrelerde tüm aktif kaynaklar son 7 gün içinde kontrol edilmiş.")
    else:
        st.dataframe(
            tr_columns(
                not_checked_7[["source_id", "institution_name", "source_name", "tier", "last_fetched", "days_since_fetch"]],
                {
                    "source_id": "Kaynak ID",
                    "institution_name": "Kurum",
                    "source_name": "Kaynak adı",
                    "tier": "Seviye",
                    "last_fetched": "Son kontrol",
                    "days_since_fetch": "Geçen gün",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )

st.subheader("Kurum Bazlı Kaynak Kapsamı")
institution_coverage = (
    filtered_registry.groupby(["institution_name", "tier"], as_index=False)
    .agg(
        source_count=("source_id", "count"),
        active_sources=("active_label", lambda s: (s == "Aktif").sum()),
        high_reliability_sources=("reliability_level", lambda s: (s == "High").sum()),
        changed_or_new=("latest_change_status", lambda s: s.isin(["changed", "new_source"]).sum()),
    )
    .sort_values(["source_count", "active_sources"], ascending=False)
)
st.dataframe(
    tr_columns(
        institution_coverage,
        {
            "institution_name": "Kurum",
            "tier": "Seviye",
            "source_count": "Kaynak sayısı",
            "active_sources": "Aktif kaynak",
            "high_reliability_sources": "Yüksek güvenilirlik",
            "changed_or_new": "Yeni / değişen",
        },
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Tema Bazlı Kaynak Kapsamı")
theme_rows = []
for _, row in filtered_registry.iterrows():
    for theme in str(row["strategic_themes"]).split(";"):
        clean_theme = theme.strip()
        if clean_theme:
            theme_rows.append(
                {
                    "Tema": tr_label("strategic_theme", clean_theme),
                    "source_id": row["source_id"],
                    "active_label": row["active_label"],
                    "latest_change_status": row["latest_change_status"],
                }
            )
theme_df = pd.DataFrame(theme_rows)
if theme_df.empty:
    st.info("Seçili filtrelerde tema kapsamı bulunamadı.")
else:
    theme_coverage = (
        theme_df.groupby("Tema", as_index=False)
        .agg(
            Kaynak_sayısı=("source_id", "count"),
            Aktif_kaynak=("active_label", lambda s: (s == "Aktif").sum()),
            Yeni_değişen=("latest_change_status", lambda s: s.isin(["changed", "new_source"]).sum()),
        )
        .sort_values("Kaynak_sayısı", ascending=False)
    )
    st.dataframe(theme_coverage, use_container_width=True, hide_index=True)

st.subheader("Eski/Mock Kaynak Dosyası Notu")
with st.expander("sources.csv içeriğini göster", expanded=False):
    legacy_sources["source_age_days"] = (
        pd.Timestamp.today().normalize() - legacy_sources["date_accessed"]
    ).dt.days
    st.dataframe(
        tr_columns(
            legacy_sources[
                [
                    "institution_name",
                    "source_type",
                    "source_title",
                    "source_url",
                    "date_accessed",
                    "source_age_days",
                    "reliability_level",
                    "related_dimension",
                    "notes",
                ]
            ],
            {
                "institution_name": "Kurum",
                "source_type": "Kaynak tipi",
                "source_title": "Kaynak başlığı",
                "source_url": "URL",
                "date_accessed": "Erişim tarihi",
                "source_age_days": "Kaynak yaşı",
                "reliability_level": "Güvenilirlik",
                "related_dimension": "İlgili boyut",
                "notes": "Notlar",
            },
        ),
        use_container_width=True,
        hide_index=True,
    )
