import streamlit as st

from utils.charts import bar_scores, heatmap
from utils.data_loader import load_all_data
from utils.filters import sidebar_filters
from utils.scoring import overall_scores, score_pivot, top_in_dimension, strategic_gap_text


st.set_page_config(page_title="Yönetici Özeti", layout="wide")

data = load_all_data()
institutions = data["institutions"]
scores = data["scores"]

filtered_institutions, filtered_scores, _ = sidebar_filters(
    institutions, scores, key_prefix="overview"
)

st.title("Yönetici Özeti")
st.caption("KOBİ strateji ve iş geliştirme için portföy seviyesinde benchmark görünümü.")

if filtered_institutions.empty or filtered_scores.empty:
    st.warning("Seçili filtrelere uyan kurum bulunamadı.")
    st.stop()

turkish_bank_types = ["Türk Bankası", "Kamu Bankası", "Katılım Bankası", "Turkish Bank", "Public Bank", "Participation Bank"]
payment_fintech_types = ["Ödeme Kuruluşu", "Global Fintek", "Payment Institution", "Global Fintech"]
global_refs = filtered_institutions[filtered_institutions["region"].eq("Global")]

deposit_top = top_in_dimension(filtered_scores, filtered_institutions, "SME Deposit Proposition")
embedded_top = top_in_dimension(filtered_scores, filtered_institutions, "Embedded Finance Maturity")
threat_top = top_in_dimension(filtered_scores, filtered_institutions, "Strategic Threat Level")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Takip edilen kurumlar", len(filtered_institutions))
k2.metric(
    "Türkiye bankaları",
    filtered_institutions["institution_type"].isin(turkish_bank_types).sum(),
)
k3.metric(
    "Ödeme / fintek oyuncuları",
    filtered_institutions["institution_type"].isin(payment_fintech_types).sum(),
)
k4.metric("Global referanslar", len(global_refs))

k5, k6, k7 = st.columns(3)
k5.metric("En yüksek mevduat skoru", deposit_top["institution_name"], f"{deposit_top['score_1_to_5']:.1f}/5")
k6.metric("En yüksek gömülü finans", embedded_top["institution_name"], f"{embedded_top['score_1_to_5']:.1f}/5")
k7.metric("En yüksek stratejik tehdit", threat_top["institution_name"], f"{threat_top['score_1_to_5']:.1f}/5")

overall = overall_scores(filtered_scores, filtered_institutions)
st.plotly_chart(
    bar_scores(
        overall.head(20),
        "institution_name",
        "overall_score",
    "Kurum Bazında Ortalama Benchmark Skoru",
    ),
    use_container_width=True,
)

st.subheader("Kurum x Boyut Isı Haritası")
pivot = score_pivot(filtered_scores)
pivot = pivot.loc[pivot.index.intersection(filtered_institutions["institution_id"])]
pivot.index = pivot.index.map(
    filtered_institutions.set_index("institution_id")["institution_name"].to_dict()
)
st.plotly_chart(heatmap(pivot.round(1), "Benchmark Boyut Skorları"), use_container_width=True)

st.subheader("Yönetici İçgörüsü")
st.write(strategic_gap_text(filtered_scores, filtered_institutions))
st.write(
    "V1 için ana stratejik sinyal, KOBİ mevduatı, üye işyeri edinimi ve iş akışı içine gömülü "
    "dağıtımın birbirine yaklaşmasıdır. Geleneksel bankalar mevduat ve ilişki derinliğinde güçlü "
    "kalırken, global fintek referansları KOBİ bakiyelerinin günlük ticaret ve finans operasyonları "
    "içinden nasıl yakalanabileceğini gösteriyor."
)
