# Batch B Source Validation Report

- generated_at: 2026-06-26T06:08:20.211473+00:00
- candidates_tested: 36
- activate_weekly_development: 4
- activate_benchmark_fact: 16
- manual_or_browser: 1
- ignored: 15

## Şekerbank

- activate_weekly_development | Valid weekly source | Şekerbank Basın Odası | HTTP 200 | useful=6 dated=1 sme=5 ops=0 retail=0.00 nav=0.49 | https://www.sekerbank.com.tr/hakkimizda/basin-odasi | Dated item surface plus SME/commercial evidence detected; page_date_count=0.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank Esnaf KOBİ | HTTP 200 | useful=2 dated=0 sme=2 ops=0 retail=0.00 nav=0.73 | https://www.sekerbank.com.tr/esnaf-kobi | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank KOBİ | HTTP 200 | useful=0 dated=0 sme=0 ops=0 retail=0.00 nav=0.73 | https://www.sekerbank.com.tr/esnaf-kobi/kobi | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no dated links | Şekerbank Esnaf KOBİ Kampanyalar | HTTP 200 | useful=2 dated=0 sme=2 ops=0 retail=0.00 nav=0.73 | https://www.sekerbank.com.tr/esnaf-kobi/kampanyalar | SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- ignore | Static/no dated links | Şekerbank KOBİ Kampanyaları | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.74 | https://www.sekerbank.com.tr/esnaf-kobi/kampanyalar/kobi-kampanyalari | SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank Üye İşyeri POS | HTTP 200 | useful=8 dated=0 sme=7 ops=0 retail=0.00 nav=0.70 | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no dated links | Şekerbank POS Kampanyaları | HTTP 200 | useful=5 dated=0 sme=5 ops=0 retail=0.00 nav=0.72 | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari | SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank ÖKC Yazar Kasa POS | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.73 | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/okc-yazar-kasa-pos | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank NarPOS | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.74 | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/narpos | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Şekerbank e-Fatura Finansmanı | HTTP 200 | useful=0 dated=0 sme=0 ops=0 retail=0.00 nav=0.74 | https://www.sekerbank.com.tr/esnaf-kobi/esnafkobi-kredileri/kobi-kredileri/e-fatura-finansmani | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no useful SME content | Şekerbank Sektörel Destek ve İş Birlikleri | HTTP 200 | useful=2 dated=0 sme=2 ops=0 retail=0.00 nav=0.73 | https://www.sekerbank.com.tr/esnaf-kobi/sektorel-destek-ve-is-birlikleri | No sufficient local SME/commercial product evidence after navigation removal.
- ignore | Validated for structural testing | Şekerbank Yeni Müşterilere Özel POS Kampanyası | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.73 | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari/yeni-musterilere-ozel-pos-kampanyasi | Parser test item; source değil.
- ignore | Validated for structural testing | Şekerbank Eczacı POS Kampanyası | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.73 | https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari/eczaci-musterilerimize-ozel-pos-kampanyasi | Parser test item; source değil.

## Fibabanka

- manual | Manual source - no item-level URLs | Fibabanka Duyuru ve Haberler 2026 | HTTP 200 | useful=23 dated=15 sme=0 ops=7 retail=0.04 nav=0.42 | https://www.fibabanka.com.tr/hakkimizda/duyuru-ve-haberler/2026 | Accordion-style page; no item-level URLs in static HTML.
- ignore | Invalid | Fibabanka Basın Bültenleri 2026 | HTTP 404 | useful=0 dated=0 sme=0 ops=0 retail=0.00 nav=0.00 | https://www.fibabanka.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri/2026 | HTTP 404.
- ignore | Validated for structural testing | Fibabanka Basın Bültenleri 2025 | HTTP 200 | useful=13 dated=13 sme=0 ops=0 retail=0.00 nav=0.43 | https://www.fibabanka.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri/2025 | Fallback archive; 2026 structure test edilir.
- activate_weekly_development | Valid weekly source | Fibabanka Güncel Özel Kampanyalar | HTTP 200 | useful=9 dated=1 sme=3 ops=0 retail=0.35 nav=0.41 | https://www.fibabanka.com.tr/kampanyalar/guncel-ozel-kampanyalar | Dated item surface plus SME/commercial evidence detected; page_date_count=4.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka KOBİ Kredileri | HTTP 200 | useful=2 dated=0 sme=1 ops=0 retail=0.00 nav=0.46 | https://www.fibabanka.com.tr/kucuk-isletme-ve-tarim/kobi-kredileri | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka İşletme ve Tarım Kredi Başvuru | HTTP 200 | useful=3 dated=0 sme=3 ops=0 retail=0.00 nav=0.45 | https://www.fibabanka.com.tr/kucuk-isletme-ve-tarim/isletme-ve-tarim-kredi-basvuru-formu | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka Ticari Müşteri Olmak İstiyorum | HTTP 200 | useful=0 dated=0 sme=0 ops=0 retail=0.00 nav=0.47 | https://www.fibabanka.com.tr/ticari-musteri-olmak-istiyorum | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Fibabanka Nakit Yönetim Ürünleri | HTTP 200 | useful=8 dated=0 sme=8 ops=0 retail=0.00 nav=0.47 | https://www.fibabanka.com.tr/ticari-kurumsal/nakit-yonetim-urunleri | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Static/no useful SME content | Fibabanka Tüzel Müşteri Ücretleri | HTTP 200 | useful=0 dated=0 sme=0 ops=0 retail=0.00 nav=0.00 | https://www.fibabanka.com.tr/tuzel-musteriler-bankacilik-islemleri | No sufficient local SME/commercial product evidence after navigation removal.

## Anadolubank

- activate_weekly_development | Valid weekly source | Anadolubank Basın Bültenleri ve Röportajlar | HTTP 200 | useful=51 dated=44 sme=5 ops=0 retail=0.12 nav=0.16 | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar | Dated item surface plus SME/commercial evidence detected; page_date_count=12.
- ignore | Invalid weekly source | Anadolubank Basın Bültenleri 2026 | HTTP 200 | useful=4 dated=4 sme=0 ops=0 retail=0.00 nav=0.18 | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2026 | No dated item-level SME/commercial feed detected after navigation removal.
- ignore | Validated for structural testing | Anadolubank Sizin İçin Kampanya Yüzeyi | HTTP 200 | useful=2 dated=0 sme=2 ops=0 retail=0.18 nav=0.11 | https://www.anadolubank.com.tr/sizin-icin | Retail/lifestyle noise riski yüksek.
- activate_benchmark_fact | Valid benchmark-only source | Anadolubank Açık Bankacılık Çözümleri | HTTP 200 | useful=2 dated=0 sme=2 ops=0 retail=0.00 nav=0.18 | https://www.anadolubank.com.tr/isiniz-icin/nakit-yonetimi/acik-bankacilik-cozumlerimiz | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Anadolubank Doğrudan Borçlandırma Sistemi | HTTP 200 | useful=2 dated=0 sme=2 ops=0 retail=0.00 nav=0.17 | https://www.anadolubank.com.tr/isiniz-icin/nakit-yonetimi/dogrudan-borclandirma-sistemi | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Anadolubank Nakit Yönetimi | HTTP 200 | useful=1 dated=0 sme=1 ops=1 retail=0.12 nav=0.18 | https://www.anadolubank.com.tr/sizin-icin/nakit-yonetimi | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Validated for structural testing | Anadolubank 7/24 Ticareti Destekleyen Hizmet | HTTP 200 | useful=0 dated=0 sme=0 ops=0 retail=0.00 nav=0.16 | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2023/anadolubanktan-7-24-ticareti-destekleyen-hizmet | Historical parser test item.
- ignore | Validated for structural testing | Anadolubank POS Artık Cebinde | HTTP 200 | useful=0 dated=0 sme=0 ops=0 retail=0.00 nav=0.16 | https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2022/anadolubank-pos-artik-cebinde | Historical parser test item.

## Odeabank

- activate_weekly_development | Valid weekly source | Odeabank Basın Bültenleri | HTTP 200 | useful=147 dated=75 sme=54 ops=0 retail=0.12 nav=0.27 | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri | Dated item surface plus SME/commercial evidence detected; page_date_count=26.
- ignore | Static/no dated links | Odeabank Kampanyalar | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.94 | https://www.odeabank.com.tr/kampanyalar | SME/commercial evidence exists, but no reliable publication/start-date feed was detected.
- activate_benchmark_fact | Valid benchmark-only source | Odeabank Ticari | HTTP 200 | useful=19 dated=0 sme=19 ops=0 retail=0.00 nav=0.80 | https://www.odeabank.com.tr/ticari | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Odeabank Nakit Yönetimi | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.96 | https://www.odeabank.com.tr/ticari/nakit-yonetimi | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- activate_benchmark_fact | Valid benchmark-only source | Odeabank Dış Ticaret ve Nakit Yönetimi Uzman Hattı | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.96 | https://www.odeabank.com.tr/ticari/dis-ticaret-ve-finansman/dis-ticaret-ve-nakit-yonetimi-uzman-hatti | Evergreen SME/commercial product content; weekly item requires explicit dated material change.
- ignore | Validated for structural testing | Odeabank Ticari Bankacılık Projesi Ödülü | HTTP 200 | useful=1 dated=0 sme=1 ops=0 retail=0.00 nav=0.96 | https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/odeabankin-ticari-bankacilik-projesine-qorustan-1incilik-odulu | Management-awareness parser test item; source değil.
