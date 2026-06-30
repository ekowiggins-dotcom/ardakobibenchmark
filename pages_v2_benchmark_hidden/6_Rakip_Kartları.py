import streamlit as st

from utils.data_loader import institution_options, load_all_data, with_institution_names


st.set_page_config(page_title="Rakip Kartları", layout="wide")

data = load_all_data()
institutions = data["institutions"]
battlecards = with_institution_names(data["battlecards"], institutions)

st.title("Rakip Kartları")
st.caption("PowerPoint’e aktarılmaya uygun, sade tek sayfalık rakip notları.")

options = institution_options(institutions)
selected_name = st.selectbox("Kurum", list(options.keys()))
selected_id = options[selected_name]
card = battlecards[battlecards["institution_id"] == selected_id].iloc[0]

top_left, top_right = st.columns([2, 1])
with top_left:
    st.header(card["institution_name"])
    st.write(card["strategic_notes"])
with top_right:
    st.metric("Tehdit seviyesi", card["threat_level"])
    st.write(card["institution_type"])
    st.write(card["country"])

st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("Güçlü Yönler")
    st.write(card["key_strengths"])
    st.subheader("Mevduat Açısı")
    st.write(card["deposit_angle"])
    st.subheader("Ödemeler Açısı")
    st.write(card["payments_angle"])

with c2:
    st.subheader("Zayıf Yönler")
    st.write(card["key_weaknesses"])
    st.subheader("Gömülü Finans Açısı")
    st.write(card["embedded_finance_angle"])
    st.subheader("Karşı Konumlandırmamız")
    st.write(card["our_counter_positioning"])

st.subheader("BD Konuşma Notları")
st.write(card["bd_talking_points"])

st.subheader("Açık Sorular")
st.write(card["open_questions"])
