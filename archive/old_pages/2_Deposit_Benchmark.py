import streamlit as st

from utils.charts import horizontal_rank
from utils.data_loader import load_all_data, with_institution_names
from utils.scoring import dimension_ranking


st.set_page_config(page_title="Mevduat Benchmark’ı", layout="wide")

data = load_all_data()
institutions = data["institutions"]
scores = data["scores"]
deposits = with_institution_names(data["deposits"], institutions)

st.title("SME Mevduat Benchmark’ı")
st.caption("Focused benchmark for SME deposit proposition, operating balances and campaign hooks.")

ranking = dimension_ranking(scores, institutions, "SME Deposit Proposition")
types = sorted(ranking["institution_type"].unique())
selected_types = st.sidebar.multiselect("Kurum tipi", types, default=types)
ranking = ranking[ranking["institution_type"].isin(selected_types)]
deposits = deposits[deposits["institution_type"].isin(selected_types)]

top = ranking.head(5)
c1, c2, c3 = st.columns(3)
c1.metric("Strongest proposition", top.iloc[0]["institution_name"], f"{top.iloc[0]['score_1_to_5']:.1f}/5")
c2.metric("High deposit relevance products", (deposits["deposit_relevance"] == "High").sum())
c3.metric("Kurumlar with product data", deposits["institution_id"].nunique())

st.plotly_chart(
    horizontal_rank(
        ranking,
        "institution_name",
        "score_1_to_5",
        "SME Deposit Proposition Ranking",
    ),
    use_container_width=True,
)

st.subheader("Mevduat Ürün Kanıtları")
st.dataframe(
    deposits[
        [
            "institution_name",
            "product_name",
            "product_type",
            "target_segment",
            "deposit_relevance",
            "digital_availability",
            "pricing_or_rate_notes",
            "campaign_notes",
        ]
    ].sort_values(["deposit_relevance", "institution_name"], ascending=[False, True]),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Strongest Deposit Acquisition Signals")
st.write(
    ", ".join(top["institution_name"].tolist())
    + " show the strongest mock deposit acquisition signals. The common pattern is broad SME reach, "
    "merchant settlement visibility and a credible route from daily cash flow into operating or term balances."
)

st.subheader("Bizim İçin Fırsat")
st.info(
    "The market still leaves room for a clearer SME operating-balance proposition: transparent tenor/rate messaging, "
    "POS settlement balance prompts, and segment-specific cash-cycle nudges could make deposit acquisition feel more "
    "proactive and less branch-led."
)
