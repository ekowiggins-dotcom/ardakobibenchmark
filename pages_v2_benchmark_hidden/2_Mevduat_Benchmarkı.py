import streamlit as st

from utils.charts import horizontal_rank
from utils.data_loader import load_all_data, with_institution_names
from utils.scoring import dimension_ranking


st.set_page_config(page_title="Mevduat Benchmark’ı", layout="wide")

data = load_all_data()
institutions = data["institutions"]
scores = data["scores"]
deposits = with_institution_names(data["deposits"], institutions)

st.title("KOBİ Mevduat Benchmark’ı")
st.caption("KOBİ mevduat önerisi, operasyonel bakiyeler ve kampanya tetikleyicileri için odaklı benchmark.")

ranking = dimension_ranking(scores, institutions, "SME Deposit Proposition")
types = sorted(ranking["institution_type"].unique())
selected_types = st.sidebar.multiselect("Kurum tipi", types, default=types)
ranking = ranking[ranking["institution_type"].isin(selected_types)]
deposits = deposits[deposits["institution_type"].isin(selected_types)]

top = ranking.head(5)
c1, c2, c3 = st.columns(3)
c1.metric("En güçlü öneri", top.iloc[0]["institution_name"], f"{top.iloc[0]['score_1_to_5']:.1f}/5")
c2.metric("Mevduat ilgisi yüksek ürünler", deposits["deposit_relevance"].eq("Yüksek").sum())
c3.metric("Ürün verisi olan kurumlar", deposits["institution_id"].nunique())

st.plotly_chart(
    horizontal_rank(
        ranking,
        "institution_name",
        "score_1_to_5",
        "KOBİ Mevduat Önerisi Sıralaması",
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

st.subheader("En Güçlü Mevduat Kazanım Sinyalleri")
st.write(
    ", ".join(top["institution_name"].tolist())
    + " en güçlü örnek mevduat kazanım sinyallerini gösteriyor. Ortak örüntü geniş KOBİ erişimi, "
    "üye işyeri tahsilat görünürlüğü ve günlük nakit akışından vadesiz ya da vadeli bakiyelere "
    "inandırıcı geçiş yoludur."
)

st.subheader("Bizim İçin Fırsat")
st.info(
    "Pazarda daha net bir KOBİ operasyonel bakiye önerisi için alan var: şeffaf vade/faiz mesajları, "
    "POS tahsilat bakiyesi tetikleyicileri ve segmente özel nakit döngüsü yönlendirmeleri mevduat "
    "kazanımını daha proaktif ve daha az şube odaklı hale getirebilir."
)
