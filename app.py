import streamlit as st

from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(
    page_title="Akbank KOBİ Rekabet Radarı",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="auto",
)

apply_akbank_theme()

with st.sidebar:
    st.header("MVP Komutları")
    st.code(
        """python3 pipeline/run_bank_recent_flow.py --institution "Garanti BBVA"
python3 pipeline/run_bank_recent_flow.py --institution "İş Bankası"
python3 pipeline/run_bank_recent_flow.py --institution "Yapı Kredi"
python3 pipeline/run_bank_recent_flow.py --institution "QNB Finansbank"
python3 pipeline/publish_recent_items_to_weekly_developments.py""",
        language="bash",
    )

render_page_header(
    "Akbank KOBİ Rekabet Gelişmeleri Radarı",
    "Analist onayından geçmiş haftalık rekabet gelişmeleri ve yönetici notları.",
)

st.info(
    "Bu MVP güncel gelişmeler ve rekabet istihbaratı akışına odaklanır. "
    "Sabit benchmark modülleri V2 kapsamındadır."
)

c1, c2, c3 = st.columns(3)
c1.metric("Odak", "Güncel gelişmeler")
c2.metric("LLM katmanı", "Claude özetleme")
c3.metric("İnsan kontrolü", "Analist onayı")

st.subheader("MVP Akışı")
st.write(
    "`source_registry.csv` kaynaklarından sayfalar taranır, değişiklikler tespit edilir, tekil gelişmeler çıkarılır, "
    "Claude tarafından stratejik önemleri özetlenir ve düşük değerli PR içerikleri ana kuyruktan ayrıştırılır. "
    "Analist onayı alan maddeler yayınlama scriptiyle yönetici radarına taşınır."
)

st.subheader("Görünür Modüller")
st.write(
    "Sol menüden Yönetici Radarı, Tüm Gelişmeler, Analist Onay Kuyruğu, "
    "Elenen düşük öncelik ve Kaynak Sağlığı sayfalarına geçebilirsiniz."
)
