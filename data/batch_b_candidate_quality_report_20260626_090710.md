# Batch B Candidate Quality Report

- generated_at: 2026-06-26T06:07:10.854764+00:00
- scope: Şekerbank, Fibabanka, Anadolubank, Odeabank
- cutoff: 2026-05-01
- Claude: not run
- approval/publish: not run

## Registry Summary

- registry_rows_added: 19
- active_weekly_sources: 4
- benchmark_only_sources: 19
- manual_or_disabled_sources: 5
- candidate_validation_csv: data/batch_b_source_validation_candidates.csv
- candidate_inspection_table: data/batch_b_candidate_inspection_table.csv

## Şekerbank

### Sources tested
- activate_weekly_development | Valid weekly source | Şekerbank Basın Odası | https://www.sekerbank.com.tr/hakkimizda/basin-odasi | reason: Dated item surface plus SME/commercial evidence detected; page_date_count=0.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank Esnaf KOBİ | https://www.sekerbank.com.tr/esnaf-kobi | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank KOBİ | https://www.sekerbank.com.tr/esnaf-kobi/kobi | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no dated links | Şekerbank Esnaf KOBİ Kampanyalar | https://www.sekerbank.com.tr/esnaf-kobi/kampanyalar | reason: SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- ignore | Static/no dated links | Şekerbank KOBİ Kampanyaları | https://www.sekerbank.com.tr/esnaf-kobi/kampanyalar/kobi-kampanyalari | reason: SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank Üye İşyeri POS | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no dated links | Şekerbank POS Kampanyaları | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari | reason: SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank ÖKC Yazar Kasa POS | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/okc-yazar-kasa-pos | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank NarPOS | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/narpos | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank e-Fatura Finansmanı | https://www.sekerbank.com.tr/esnaf-kobi/esnafkobi-kredileri/kobi-kredileri/e-fatura-finansmani | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no useful SME content | Şekerbank Sektörel Destek ve İş Birlikleri | https://www.sekerbank.com.tr/esnaf-kobi/sektorel-destek-ve-is-birlikleri | reason: No sufficient local SME/commercial product evidence after navigation removal.
- ignore | Validated for structural testing | Şekerbank Yeni Müşterilere Özel POS Kampanyası | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari/yeni-musterilere-ozel-pos-kampanyasi | reason: Parser test item; source değil.
- ignore | Validated for structural testing | Şekerbank Eczacı POS Kampanyası | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari/eczaci-musterilerimize-ozel-pos-kampanyasi | reason: Parser test item; source değil.

### Source role decisions
- valid_weekly_sources: 1: REG-140 Şekerbank Basın Odası
- benchmark_only_sources: 7: REG-091 Şekerbank Ticari Kartlar, REG-141 Şekerbank Esnaf KOBİ, REG-142 Şekerbank KOBİ, REG-143 Şekerbank Üye İşyeri POS, REG-144 Şekerbank ÖKC Yazar Kasa POS, REG-145 Şekerbank NarPOS, REG-146 Şekerbank e-Fatura Finansmanı
- ignored_manual_disabled_sources: 2: REG-089 Şekerbank Esnaf KOBİ Kampanyalar, REG-090 Şekerbank POS Kampanyaları

### Discovery stats
- total_links_found: 241
- candidates_found: 8
- detail_pages_fetched: 8
- would_create_recent_items: 1
- valid_dates_or_recent_passes: 1
- explicit_sme_relevance_passes: 5
- context_only_items: 0
- management_awareness_candidates: 3
- operational_or_retail_rejected: 0
- date_failures: 7
- duplicate_candidates: 0

### Top accepted candidates
- Şekerbank’ın “Yerinde Kredi” platformuna The Banker’dan ödül | 2026-05-15 | Yönetici Bilgilendirme | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2026/sekerbankin-yerinde-kredi-platformuna-the-bankerdan-odul

### Top rejected candidates
- Şekerbank'a yeni genel müdür yardımcısı | Bağımsız Gelişme | Kesim tarihinden eski: 2026-04-07 < 2026-05-01 | flags: old_before_cutoff | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2026/sekerbanka-yeni-genel-mudur-yardimcisi
- Şekerbank’ın dijital bankacılık uygulamalarına üç uluslararası ödül | Yönetici Bilgilendirme | Kesim tarihinden eski: 2026-04-02 < 2026-05-01 | flags: old_before_cutoff | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2026/sekerbankin-dijital-bankacilik-uygulamalarina-uc-uluslararasi-odul
- Şekerbank’a kalkınma odaklı Avrupa Fonu EFSE’den 50 milyon euroluk yeni kaynak | Bağımsız Gelişme | Kesim tarihinden eski: 2026-03-30 < 2026-05-01 | flags: old_before_cutoff | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2026/sekerbanka-kalkinma-odakli-avrupa-fonu-efseden--50-milyon-euroluk-yeni-kaynak
- Visa’nın kadın girişimcilere yönelik küresel destek programı She is Next, Şekerbank ve GİRVAK iş birliğiyle Anadolu’ya ulaşıyor… | Yönetici Bilgilendirme | Kesim tarihinden eski: 2026-02-24 < 2026-05-01 | flags: old_before_cutoff | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2026/visanin-kadin-girisimcilere-yonelik-kuresel-destek-programi-she-is-next-sekerbank-ve-girvak-is-birligiyle-anadoluya-ulasiyor
- Şekerbank’ın yeni platformu “Yerinde Kredi” ile çiftçilere anında finansman desteği | Bağımsız Gelişme | Kesim tarihinden eski: 2026-02-12 < 2026-05-01 | flags: old_before_cutoff | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2026/sekerbankin-yeni-platformu-yerinde-kredi-ile-ciftcilere-aninda-finansman-destegi
- Şekerbank, CDP’de üç kategoride “A” skoruyla küresel sürdürülebilirlik liderleri arasında | Bağımsız Gelişme | Kesim tarihinden eski: 2025-12-26 < 2026-05-01 | flags: old_before_cutoff | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2025/sekerbank-cdpde-uc-kategoride-a-skoruyla--kuresel-surdurulebilirlik-liderleri-arasinda
- Şekerbank ve EBRD’den kadın KOBİ’lere ve genç girişimcilere finansman desteği | Bağımsız Gelişme | Kesim tarihinden eski: 2025-12-16 < 2026-05-01 | flags: old_before_cutoff | https://www.sekerbank.com.tr/hakkimizda/basin-odasi/basin-bultenlerimiz/2025/sekerbank-ve-ebrdden-kadin-kobilere-ve-genc-girisimcilere-finansman-destegi

### Bank-specific assessment
- press/announcement separation: improved; source-specific adapter reads Next announcementList and filters operational announcements unless local SME evidence exists.
- POS/KOBİ candidate quality: POS/KOBİ campaign listing lacks reliable start/publication dates, so it remains benchmark/manual rather than weekly.
- repeated-widget contamination: controlled by source-specific adapter; product pages are not allowed to emit repeated press-widget candidates.
- activation recommendation: ready for tiny Claude pilot with Şekerbank Basın Odası only.

- bank_specific_adapter_required: yes
- ready_for_tiny_claude_pilot: yes

## Fibabanka

### Sources tested
- activate_weekly_development | Valid weekly source | Fibabanka Duyuru ve Haberler 2026 | https://www.fibabanka.com.tr/hakkimizda/duyuru-ve-haberler/2026 | reason: Dated item surface plus SME/commercial evidence detected; page_date_count=58.
- ignore | Invalid | Fibabanka Basın Bültenleri 2026 | https://www.fibabanka.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri/2026 | reason: HTTP 404.
- ignore | Validated for structural testing | Fibabanka Basın Bültenleri 2025 | https://www.fibabanka.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri/2025 | reason: Fallback archive; 2026 structure test edilir.
- activate_weekly_development | Valid weekly source | Fibabanka Güncel Özel Kampanyalar | https://www.fibabanka.com.tr/kampanyalar/guncel-ozel-kampanyalar | reason: Dated item surface plus SME/commercial evidence detected; page_date_count=4.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka KOBİ Kredileri | https://www.fibabanka.com.tr/kucuk-isletme-ve-tarim/kobi-kredileri | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka İşletme ve Tarım Kredi Başvuru | https://www.fibabanka.com.tr/kucuk-isletme-ve-tarim/isletme-ve-tarim-kredi-basvuru-formu | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka Ticari Müşteri Olmak İstiyorum | https://www.fibabanka.com.tr/ticari-musteri-olmak-istiyorum | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka Nakit Yönetim Ürünleri | https://www.fibabanka.com.tr/ticari-kurumsal/nakit-yonetim-urunleri | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no useful SME content | Fibabanka Tüzel Müşteri Ücretleri | https://www.fibabanka.com.tr/tuzel-musteriler-bankacilik-islemleri | reason: No sufficient local SME/commercial product evidence after navigation removal.

### Source role decisions
- valid_weekly_sources: 1: REG-148 Fibabanka Güncel Özel Kampanyalar
- benchmark_only_sources: 5: REG-093 Fibabanka Business Kredi Kartı, REG-149 Fibabanka KOBİ Kredileri, REG-150 Fibabanka İşletme ve Tarım Kredi Başvuru, REG-151 Fibabanka Ticari Müşteri Olmak İstiyorum, REG-152 Fibabanka Nakit Yönetim Ürünleri
- ignored_manual_disabled_sources: 2: REG-092 Fibabanka Kampanyalar, REG-147 Fibabanka Duyuru ve Haberler 2026

### Discovery stats
- total_links_found: 624
- candidates_found: 1
- detail_pages_fetched: 1
- would_create_recent_items: 0
- valid_dates_or_recent_passes: 0
- explicit_sme_relevance_passes: 1
- context_only_items: 0
- management_awareness_candidates: 0
- operational_or_retail_rejected: 0
- date_failures: 1
- duplicate_candidates: 0

### Top accepted candidates
- None

### Top rejected candidates
- Efsane KOBİ Kredisi – 1.500.000 TL’ye kadar %2,99’dan Başlayan Faiz Oranlarıyla | Bağımsız Gelişme | Sadece kampanya bitiş tarihi bulundu; yeni gelişme kanıtı değil | flags: campaign_end_date_only | https://www.fibabanka.com.tr/kampanyalar/guncel-ozel-kampanyalar/efsane-kredi/efsane-kobi-kredi-kampanyasi

### Bank-specific assessment
- latest valid press/news URL structure: 2026 announcements page exists but lacks item-level URLs in static HTML, so it is manual only.
- campaign candidate quality: exact campaign URL works; Efsane KOBİ is cleanly separated from retail Efsane, but only campaign end-date evidence was found, so it should not enter recent flow yet.
- Efsane retail/KOBİ separation: passed; only `/efsane-kobi-kredi-kampanyasi` remains after adapter filtering.
- activation recommendation: partial coverage; not ready for Claude until a start/publication date source is available or manually confirmed.

- bank_specific_adapter_required: yes
- ready_for_tiny_claude_pilot: no

## Anadolubank

### Sources tested
- activate_weekly_development | Valid weekly source | Anadolubank Basın Bültenleri ve Röportajlar | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar | reason: Dated item surface plus SME/commercial evidence detected; page_date_count=12.
- ignore | Invalid weekly source | Anadolubank Basın Bültenleri 2026 | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2026 | reason: No dated item-level SME/commercial feed detected after navigation removal.
- ignore | Validated for structural testing | Anadolubank Sizin İçin Kampanya Yüzeyi | https://www.anadolubank.com.tr/sizin-icin | reason: Retail/lifestyle noise riski yüksek.
- activate_benchmark_fact | Valid benchmark-only source | Anadolubank Açık Bankacılık Çözümleri | https://www.anadolubank.com.tr/isiniz-icin/nakit-yonetimi/acik-bankacilik-cozumlerimiz | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Anadolubank Doğrudan Borçlandırma Sistemi | https://www.anadolubank.com.tr/isiniz-icin/nakit-yonetimi/dogrudan-borclandirma-sistemi | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Anadolubank Nakit Yönetimi | https://www.anadolubank.com.tr/sizin-icin/nakit-yonetimi | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Validated for structural testing | Anadolubank 7/24 Ticareti Destekleyen Hizmet | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2023/anadolubanktan-7-24-ticareti-destekleyen-hizmet | reason: Historical parser test item.
- ignore | Validated for structural testing | Anadolubank POS Artık Cebinde | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2022/anadolubank-pos-artik-cebinde | reason: Historical parser test item.

### Source role decisions
- valid_weekly_sources: 1: REG-153 Anadolubank Basın Bültenleri ve Röportajlar
- benchmark_only_sources: 4: REG-095 Anadolubank POS, REG-154 Anadolubank Açık Bankacılık Çözümleri, REG-155 Anadolubank Doğrudan Borçlandırma Sistemi, REG-156 Anadolubank Nakit Yönetimi
- ignored_manual_disabled_sources: 1: REG-094 Anadolubank Kampanyalar

### Discovery stats
- total_links_found: 522
- candidates_found: 6
- detail_pages_fetched: 6
- would_create_recent_items: 0
- valid_dates_or_recent_passes: 0
- explicit_sme_relevance_passes: 6
- context_only_items: 0
- management_awareness_candidates: 0
- operational_or_retail_rejected: 0
- date_failures: 6
- duplicate_candidates: 0

### Top accepted candidates
- None

### Top rejected candidates
- Anadolubank ve İGE A.Ş. iş birliği ile ihracata destek | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2023/anadolubank-ve-ige-as-i-birligi-ile-ihracata-destek
- Anadolubank POS artık cebinde! | Anadolubank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2022/anadolubank-pos-artik-cebinde
- Dış Ticarete Navlun Kredisi Desteği | Anadolubank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2021/anadolubanktan-dis-ticarete-navlun-kredisi-destegi
- Dış Ticaretteki Payını Büyütmeye Devam Ediyor | Anadolubank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2021/anadolubank-dis-ticaretteki-payini-buyutmeye-devam-ediyor
- Yeni Nakit Yönetimi Ürünü Müşterilerine Sundu | Anadolubank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2021/anadolubank-yeni-nakit-yoenetimi-ueruenue-tedarikci-finansmann-mueterilerine-sundu
- Genel Müdür Yardımcılığı Görevine Ahmet Yiğit Atandı | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2020/genel-mudur-yardimciligi-gorevine-ahmet-yigit-atandi

### Bank-specific assessment
- current-year archive quality: archive is structurally clean but sparse; 2026 item is corporate financial performance and lacks commercial-detail/date quality for BD flow.
- retail campaign noise ratio: generic campaign surface remains ignored; press archive adapter avoids site-wide KOBİ menu contamination.
- commercial candidate quality: historical commercial links are discoverable but old and/or undated; no current eligible recent item.
- activation recommendation: source development/manual monitoring required before Claude.

- bank_specific_adapter_required: yes
- ready_for_tiny_claude_pilot: no

## Odeabank

### Sources tested
- activate_weekly_development | Valid weekly source | Odeabank Basın Bültenleri | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri | reason: Dated item surface plus SME/commercial evidence detected; page_date_count=26.
- ignore | Static/no dated links | Odeabank Kampanyalar | https://www.odeabank.com.tr/kampanyalar | reason: SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- activate_benchmark_fact | Valid benchmark-only source | Odeabank Ticari | https://www.odeabank.com.tr/ticari | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Odeabank Nakit Yönetimi | https://www.odeabank.com.tr/ticari/nakit-yonetimi | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Odeabank Dış Ticaret ve Nakit Yönetimi Uzman Hattı | https://www.odeabank.com.tr/ticari/dis-ticaret-ve-finansman/dis-ticaret-ve-nakit-yonetimi-uzman-hatti | reason: Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Validated for structural testing | Odeabank Ticari Bankacılık Projesi Ödülü | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/odeabankin-ticari-bankacilik-projesine-qorustan-1incilik-odulu | reason: Management-awareness parser test item; source değil.

### Source role decisions
- valid_weekly_sources: 1: REG-096 Odeabank Basın Bültenleri
- benchmark_only_sources: 3: REG-097 Odeabank Ticari, REG-157 Odeabank Nakit Yönetimi, REG-158 Odeabank Dış Ticaret ve Nakit Yönetimi Uzman Hattı
- ignored_manual_disabled_sources: 0

### Discovery stats
- total_links_found: 388
- candidates_found: 25
- detail_pages_fetched: 25
- would_create_recent_items: 0
- valid_dates_or_recent_passes: 0
- explicit_sme_relevance_passes: 22
- context_only_items: 0
- management_awareness_candidates: 3
- operational_or_retail_rejected: 0
- date_failures: 25
- duplicate_candidates: 0

### Top accepted candidates
- None

### Top rejected candidates
- Odeabank’ın ticari bankacılık projesine Qorus’tan 1’incilik ödülü | Basın Bültenleri | Hakkımızda | Odeabank | Yönetici Bilgilendirme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/odeabankin-ticari-bankacilik-projesine-qorustan-1incilik-odulu
- Sürdürülebilir Kalkınma için Odeabank ve İGE İşbirliği | Odeabank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/surdurulebilir-kalkinma-icin-odeabank-ige-isbirligi
- Odeabank, İzmir Firmaları ile Dış Ticareti Konuştu | Odeabank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/odeabank-izmir-firmalari-ile-dis-ticareti-konustu
- Odeabank, Mersinli İş İnsanları İle Dış Ticareti Konuştu | Odeabank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/odeabank-mersinli-is-insanlari-ile-dis-ticareti-konustu
- Odeabank, Konyalı İş İnsanları İle Bir Araya Geldi | Odeabank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/konya-dis-ticaret-bulusmasi-21-mayis-2021
- Odeabank, Gaziantep’li İş İnsanlarıyla Bir Araya Geldi | Odeabank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/gaziantep-dis-ticaret-bulusmasi
- Odeabank, İskenderunlu İhracatçılarla Dış Ticareti Konuştu | Odeabank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/basin-bultenleriiskenderun-dis-ticaret-bulusmasi
- Odeabank'tan Dış Ticaret ve Nakit Yönetimi Uzman Hattı | Odeabank | Bağımsız Gelişme | Tarih yok; varsayılan kapıdan geçmedi | flags: date_missing | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/basin-bultenleridis-ticaret-ve-nakit-yonetimi-uzman-hatti

### Bank-specific assessment
- commercial press-item quality: commercial/award links are discoverable, including Qorus Commercial Boost/RM Dashboard, but listing/detail pages do not expose reliable publication dates.
- consumer research exclusions: financial literacy/investment/podcast/culture content is filtered or remains rejected before Claude.
- management-awareness candidates: present, but date quality blocks automation.
- activation recommendation: partial coverage; manual/date refinement required before Claude.

- bank_specific_adapter_required: yes
- ready_for_tiny_claude_pilot: no

## Overall QA

- no Claude calls were made
- no approval or publish scripts were run
- item-level URL rule enforced; Fibabanka 2026 accordion source downgraded to manual
- campaign-end-date-only recency rejected
- static product pages retained as benchmark_fact
- operational/retail/context-only gates added for Batch B candidates
- idempotency: second dry-run produced planned dry-run counts only; no recent_items write was performed
- compile: passed
- pytest tests/test_incremental_mvp.py -q: 5 passed