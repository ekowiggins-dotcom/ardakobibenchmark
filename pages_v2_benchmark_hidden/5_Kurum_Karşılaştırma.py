import streamlit as st

from utils.data_loader import institution_options, load_all_data, with_institution_names
from utils.scoring import score_pivot


st.set_page_config(page_title="Kurum Karşılaştırma", layout="wide")

data = load_all_data()
institutions = data["institutions"]
scores = data["scores"]
deposits = with_institution_names(data["deposits"], institutions)
embedded = with_institution_names(data["embedded"], institutions)
payments = with_institution_names(data["payments"], institutions)
battlecards = with_institution_names(data["battlecards"], institutions)

st.title("Kurum Karşılaştırma")
st.caption("Yan yana stratejik karşılaştırma için 2 ila 5 kurum seçin.")

options = institution_options(institutions)
default_names = ["Garanti BBVA", "Akbank", "Stripe"]
selected_names = st.multiselect(
    "Kurumlar",
    list(options.keys()),
    default=[name for name in default_names if name in options],
    max_selections=5,
)

if len(selected_names) < 2:
    st.warning("Karşılaştırmak için en az iki kurum seçin.")
    st.stop()

selected_ids = [options[name] for name in selected_names]

st.subheader("Benchmark Skorları")
pivot = score_pivot(scores[scores["institution_id"].isin(selected_ids)]).round(1)
pivot.index = pivot.index.map(institutions.set_index("institution_id")["institution_name"].to_dict())
st.dataframe(pivot, use_container_width=True)

st.subheader("Mevduat Karşılaştırması")
st.dataframe(
    deposits[deposits["institution_id"].isin(selected_ids)][
        [
            "institution_name",
            "product_name",
            "product_type",
            "target_segment",
            "deposit_relevance",
            "pricing_or_rate_notes",
            "campaign_notes",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Gömülü Finans Karşılaştırması")
st.dataframe(
    embedded[embedded["institution_id"].isin(selected_ids)][
        [
            "institution_name",
            "embedded_context",
            "feature_name",
            "partner_or_channel",
            "maturity_level",
            "strategic_relevance",
            "description",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Ödeme Özelliği Karşılaştırması")
st.dataframe(
    payments[payments["institution_id"].isin(selected_ids)][
        [
            "institution_name",
            "feature_name",
            "product_area",
            "availability",
            "settlement_notes",
            "reconciliation_available",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Rakip Kartı Özeti")
for _, row in battlecards[battlecards["institution_id"].isin(selected_ids)].iterrows():
    with st.expander(row["institution_name"], expanded=True):
        c1, c2 = st.columns(2)
        c1.write("**Güçlü yönler**")
        c1.write(row["key_strengths"])
        c1.write("**Mevduat açısı**")
        c1.write(row["deposit_angle"])
        c2.write("**Zayıf yönler**")
        c2.write(row["key_weaknesses"])
        c2.write("**Karşı konumlandırma**")
        c2.write(row["our_counter_positioning"])
