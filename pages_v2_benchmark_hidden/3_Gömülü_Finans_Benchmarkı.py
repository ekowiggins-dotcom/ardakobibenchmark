import streamlit as st

from utils.charts import horizontal_rank
from utils.data_loader import load_all_data, with_institution_names
from utils.scoring import dimension_ranking


st.set_page_config(page_title="Gömülü Finans Benchmark’ı", layout="wide")

data = load_all_data()
institutions = data["institutions"]
scores = data["scores"]
embedded = with_institution_names(data["embedded"], institutions)

st.title("Gömülü Finans Benchmark’ı")
st.caption("Platformlar, API’ler, POS ve iş ortağı kanallarında iş akışına gömülü KOBİ finans sinyalleri.")

contexts = sorted(embedded["embedded_context"].dropna().unique())
selected_contexts = st.sidebar.multiselect("Gömülü finans bağlamı", contexts, default=contexts)
embedded_filtered = embedded[embedded["embedded_context"].isin(selected_contexts)]

ranking = dimension_ranking(scores, institutions, "Embedded Finance Maturity")
if not embedded_filtered.empty:
    ranking = ranking[ranking["institution_id"].isin(embedded_filtered["institution_id"].unique())]

global_refs = ranking[ranking["region"].eq("Global") | ~ranking["country"].isin(["Turkey", "Türkiye"])].head(5)
turkish_refs = ranking[ranking["country"].isin(["Turkey", "Türkiye"])].head(5)

c1, c2, c3 = st.columns(3)
c1.metric("En yüksek olgunluk", ranking.iloc[0]["institution_name"], f"{ranking.iloc[0]['score_1_to_5']:.1f}/5")
c2.metric("Kapsanan bağlamlar", embedded_filtered["embedded_context"].nunique())
c3.metric("İleri örnekler", embedded_filtered["maturity_level"].isin(["İleri", "Advanced"]).sum())

st.plotly_chart(
    horizontal_rank(
        ranking,
        "institution_name",
        "score_1_to_5",
        "Gömülü Finans Olgunluk Sıralaması",
    ),
    use_container_width=True,
)

left, right = st.columns(2)
with left:
    st.subheader("En Güçlü Global Örnekler")
    st.dataframe(
        global_refs[["institution_name", "institution_type", "score_1_to_5", "analyst_notes"]],
        use_container_width=True,
        hide_index=True,
    )

with right:
    st.subheader("Öne Çıkan Türkiye Referansları")
    st.dataframe(
        turkish_refs[["institution_name", "institution_type", "score_1_to_5", "analyst_notes"]],
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Gömülü Finans Özellik Kanıtları")
st.dataframe(
    embedded_filtered[
        [
            "institution_name",
            "embedded_context",
            "feature_name",
            "partner_or_channel",
            "target_segment",
            "maturity_level",
            "strategic_relevance",
            "description",
        ]
    ].sort_values(["maturity_level", "strategic_relevance"], ascending=[True, False]),
    use_container_width=True,
    hide_index=True,
)

st.info(
    "En güçlü global örnekler finansı doğrudan üye işyeri iş akışlarına gömüyor. Türkiye’deki kurumlar "
    "POS, muhasebe, e-ticaret ve pazaryeri ilişkilerini yalnızca ürün ortaklığı değil, dağıtım kanalı "
    "olarak ele aldığında daha aksiyon alınabilir görünüyor."
)
