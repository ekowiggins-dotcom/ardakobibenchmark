from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from utils.benchmark_brief import TOPICS, bank_catalog, build_prompt
from utils import benchmark_jobs as jobs
from utils.llm_client import get_llm_config
from utils.ui_theme import apply_akbank_theme, render_page_header


ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Benchmark Oluştur", layout="wide")
apply_akbank_theme()
for setting in ('BENCHMARK_DATABASE_URL', 'BENCHMARK_WORKER_MODE'):
    if not os.environ.get(setting):
        try:
            value = st.secrets.get(setting, '')
            if value:
                os.environ[setting] = str(value)
        except Exception:
            pass
render_page_header("Benchmark Oluştur", "Kurumları ve kıyas ölçütlerini seç, araştırma metnini hazırla.")
try:
    with jobs.connect():
        pass
except Exception:
    st.error("Araştırma veritabanına bağlanılamadı. Bağlantı ayarlarını kontrol edin.")
    st.stop()

catalog = bank_catalog(ROOT)
st.subheader("1. Araştırma kapsamı")
left, right = st.columns(2)
with left:
    topic = st.selectbox("Benchmark konusu", list(TOPICS), key="brief_topic")
    market = st.selectbox("Pazar", list(catalog), key="brief_market")
with right:
    segment = st.selectbox("Müşteri segmenti", ["KOBİ / ticari", "KOBİ", "Ticari", "Kurumsal", "Bireysel"], key="brief_segment")
    groups = list(catalog[market]) + ["Özel seçim"]
    group = st.selectbox("Banka grubu", groups, key=f"brief_group_{market}")

custom_topic = st.text_input("Araştırma konusu", key="brief_custom_topic") if topic == "Özel araştırma" else topic
options = list(dict.fromkeys(name for names in catalog[market].values() for name in names)) if group == "Özel seçim" else catalog[market][group]
bank_key = f"brief_banks_{market}_{group}"
if bank_key not in st.session_state:
    st.session_state[bank_key] = options.copy()
select_all, clear_all, _ = st.columns([1, 1, 4])
with select_all:
    if st.button("Tümünü seç", key="brief_select_all"):
        st.session_state[bank_key] = options.copy()
with clear_all:
    if st.button("Seçimi temizle", key="brief_clear_all"):
        st.session_state[bank_key] = []
banks = st.multiselect("Bankalar", options, key=bank_key)
extra_banks = st.text_input("Diğer kurumlar (isteğe bağlı)", placeholder="Kurum adlarını virgülle ayır", key="brief_extra_banks") if group == "Özel seçim" else ""
banks = list(dict.fromkeys(banks + [name.strip() for name in extra_banks.split(",") if name.strip()]))

st.subheader("2. Kıyas ölçütleri")
criteria = st.multiselect("Matris sütunları", TOPICS[topic], default=TOPICS[topic], key=f"brief_criteria_{topic}")
extra_criteria = st.text_input("Ek ölçütler (isteğe bağlı)", placeholder="Örneğin: Entegrasyon süresi, destek kanalı", key=f"brief_extra_criteria_{topic}")
criteria = list(dict.fromkeys(criteria + [value.strip() for value in extra_criteria.split(",") if value.strip()]))
left, right = st.columns(2)
with left:
    period = st.selectbox("Zaman kapsamı", ["Güncel ve aktif teklifler", "Son 30 gün", "Son 90 gün", "Son 1 yıl"], key="brief_period")
with right:
    source_policy = st.selectbox("Kaynak tercihi", ["Yalnızca resmî kaynaklar", "Resmî kaynaklar öncelikli; diğer kaynaklar ayrıca işaretlensin"], key="brief_source")
exclusions = st.text_area("Kapsam dışında kalanlar", placeholder="Örneğin: Bireysel teklifler, bakım ücretleri", key="brief_exclusions")
instructions = st.text_area("Ek talimatlar", placeholder="Araştırmada özellikle yanıtlanmasını istediğiniz sorular", key="brief_instructions")
web_discovery = st.checkbox("Alternatif resmî kaynakları web'de ara", value=True, key="brief_web_discovery")
st.caption("Banka başına en fazla 2 web araması. Arama ve AI kullanımı API hesabınıza yansır.")
brief = dict(topic=custom_topic.strip(), market=market, group=group, banks=banks, segment=segment, criteria=criteria, period=period, source_policy=source_policy, exclusions=exclusions.strip(), instructions=instructions.strip(), web_discovery=web_discovery)

if st.button("Araştırma metnini oluştur", type="primary"):
    if not brief["topic"] or not banks or not criteria:
        st.error("Araştırma konusu, en az bir kurum ve en az bir kıyas ölçütü seçin.")
    else:
        st.session_state["brief_generated"] = brief.copy()
        st.session_state["brief_prompt"] = build_prompt(brief)

if "brief_generated" in st.session_state:
    st.divider()
    st.subheader("3. Araştırma metnini gözden geçir")
    stale = brief != st.session_state["brief_generated"]
    if stale:
        st.warning("Seçimler değişti. Taslağı kaydetmeden önce araştırma metnini yeniden oluşturun. Yeniden oluşturma, metindeki düzenlemelerinizin yerini alır.")
    prompt = st.text_area("Düzenlenebilir araştırma metni", height=340, key="brief_prompt")
    st.caption("Kayıtlar ortak veritabanında saklanır." if jobs.database_url() else "Kayıtlar bu sunucuda saklanır. Cloud yeniden kurulumunda korunmaları için ortak veritabanını bağlayın.")
    if st.button("Taslağı kaydet", disabled=stale or not prompt.strip()):
        jobs.create(st.session_state["brief_generated"], prompt.strip())
        st.success("Araştırma taslağı kaydedildi.")


@st.fragment(run_every="5s")
def research_library():
    st.divider()
    st.subheader("Araştırmalar")
    st.caption("Kayıtlı kaynaklar ve seçildiyse web'de bulunan alternatif resmî sayfalar taranır. Sonuçlar analist incelemesi gerektirir.")
    config = get_llm_config()
    try:
        secret_key = str(st.secrets.get("ANTHROPIC_API_KEY", ""))
    except Exception:
        secret_key = ""
    has_key = config.has_api_key or bool(secret_key)
    if jobs.external_worker():
        st.caption("Araştırmalar GitHub Actions kuyruğuna gönderilir. Kuyruk 15 dakikalık aralıklarla kontrol edilir; GitHub yoğunluğuna ve önceki işlere göre bekleme uzayabilir.")
    elif not has_key:
        st.info("Araştırmayı başlatmak için ANTHROPIC_API_KEY tanımlanmalı. Taslak kaydetmeye devam edebilirsiniz.")
    records = jobs.list_jobs()
    if not records:
        st.caption("Henüz kayıtlı araştırma yok.")
    for job in records:
        with st.expander(f"{job['brief']['topic']} · {len(job['brief']['banks'])} kurum · {job['status']} · {job['created_at']}", expanded=job['status'] in ('Sırada', 'Araştırılıyor')):
            st.text(job['prompt'])
            if job['status'] == 'Taslak':
                st.caption(f"En fazla {config.max_items_per_run} banka ve banka başına 8 sayfa incelenir. AI çağrıları API kullanımına yansır.")
                if len(job['brief']['banks']) > config.max_items_per_run:
                    st.warning("Banka sayısı çağrı sınırını aşıyor. Daha az bankayla yeni bir taslak oluşturun.")
                if st.button("Araştırmayı Başlat", key=f"start_{job['id']}", type="primary", disabled=(not has_key and not jobs.external_worker()) or len(job['brief']['banks']) > config.max_items_per_run):
                    jobs.launch(job['id'], secret_key or None)
                    st.rerun(scope="fragment")
            progress = job['progress']
            if job['status'] == 'Sırada':
                st.info("Araştırma sırada. GitHub Actions → Benchmark Research Queue → Run workflow ile kontrolü elle başlatabilirsiniz.")
            if job['status'] == 'Kesildi':
                st.warning("Araştırma servisiyle bağlantı kesildi. Mevcut sonuçlar korundu; yeni sürüm oluşturabilirsiniz.")
            if progress:
                st.write(progress.get('message', ''))
                st.caption(f"{progress.get('completed', 0)} / {progress.get('total', 0)} banka tamamlandı · {progress.get('pages', 0)} sayfa okundu")
                for bank, status in progress.get('banks', {}).items():
                    st.write(f"**{bank}:** {status}")
            if job['status'] in ('Sırada', 'Araştırılıyor'):
                if st.button("Araştırmayı iptal et", key=f"cancel_{job['id']}"):
                    jobs.cancel(job['id'])
                    st.rerun(scope="fragment")
            elif job['status'] != 'Taslak':
                if st.button("Yeni sürüm olarak tekrar hazırla", key=f"retry_{job['id']}"):
                    jobs.create(job['brief'], job['prompt'])
                    st.rerun(scope="fragment")
            if job['result']:
                rows = [{'Kurum': row['bank'], 'Bulgu': row['title'], **{criterion: row['values'].get(criterion, {}).get('value', 'Doğrulanamadı') for criterion in job['brief']['criteria']}} for row in job['result']]
                st.dataframe(rows, hide_index=True, use_container_width=True)
                st.markdown("**Bulguların dayanakları**")
                for row in job['result']:
                    st.write(f"**{row['bank']} · {row['title']}**")
                    for criterion, cell in row['values'].items():
                        st.write(f"{criterion}: {cell['value']}")
                        st.text(cell['quote'])
                        st.link_button("Kaynağı aç", cell['url'])
                    st.caption(f"Kontrol: {row['checked_at']}")
            if progress.get('sources'):
                st.markdown("**Taranan kaynaklar**")
                st.dataframe(progress['sources'], hide_index=True, use_container_width=True)
            for bank, search in progress.get('discovery', {}).items():
                st.markdown(f"**{bank} · Kaynak keşfi**")
                st.caption(f"{len(search['queries'])} arama · {len(search['urls'])} aday bağlantı")
                if search['errors']:
                    st.warning("Web araması tamamlanamadı veya sınıra ulaştı: " + ', '.join(search['errors']))
                for query in search['queries']:
                    st.text(query)
                for url in search['urls']:
                    st.link_button("Aday kaynağı aç", url)
            st.download_button("Araştırmayı indir (JSON)", json.dumps(job, ensure_ascii=False, indent=2), file_name=f"benchmark-{job['id']}.json", mime="application/json", key=f"download_{job['id']}")


research_library()
