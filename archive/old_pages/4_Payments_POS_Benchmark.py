import streamlit as st

from utils.charts import horizontal_rank
from utils.data_loader import load_all_data, with_institution_names
from utils.scoring import dimension_ranking


st.set_page_config(page_title="Ödemeler ve POS Benchmark’ı", layout="wide")

data = load_all_data()
institutions = data["institutions"]
scores = data["scores"]
payments = with_institution_names(data["payments"], institutions)

st.title("Ödemeler ve POS Benchmark’ı")
st.caption("Merchant acquiring, POS, SoftPOS, virtual POS, QR and payment-link capabilities.")

product_areas = sorted(payments["product_area"].dropna().unique())
selected_areas = st.sidebar.multiselect("Product area", product_areas, default=product_areas)
payments_filtered = payments[payments["product_area"].isin(selected_areas)]

ranking = dimension_ranking(scores, institutions, "Payments & Merchant Acquiring")
if not payments_filtered.empty:
    ranking = ranking[ranking["institution_id"].isin(payments_filtered["institution_id"].unique())]

c1, c2, c3 = st.columns(3)
c1.metric("Top payments benchmark", ranking.iloc[0]["institution_name"], f"{ranking.iloc[0]['score_1_to_5']:.1f}/5")
c2.metric("Features tracked", len(payments_filtered))
c3.metric("Reconciliation available", (payments_filtered["reconciliation_available"] == "Yes").sum())

st.plotly_chart(
    horizontal_rank(
        ranking,
        "institution_name",
        "score_1_to_5",
        "Payments & Merchant Acquiring Ranking",
    ),
    use_container_width=True,
)

st.subheader("Özellik Kanıtları")
st.dataframe(
    payments_filtered[
        [
            "institution_name",
            "feature_name",
            "product_area",
            "availability",
            "settlement_notes",
            "pricing_notes",
            "merchant_analytics_available",
            "reconciliation_available",
            "description",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

deposit_gateway = payments_filtered[
    payments_filtered["settlement_notes"].str.contains("settlement|payout|relationship", case=False, na=False)
]
st.subheader("KOBİ Mevduata Geçiş Kapısı Olarak Ödemeler")
st.write(
    "Kurumlar with strong acquiring, settlement and reconciliation propositions have the clearest path to "
    "turn merchant payment flow into operating balances. In the mock data, the strongest gateway signals appear around "
    + ", ".join(deposit_gateway["institution_name"].drop_duplicates().head(8).tolist())
    + "."
)
