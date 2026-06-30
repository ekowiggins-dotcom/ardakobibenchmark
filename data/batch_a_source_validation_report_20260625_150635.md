# Batch A Source Validation Report

- generated_at: 2026-06-25T12:06:35.565126+00:00
- candidates_tested: 34
- activate_weekly_development: 6
- activate_benchmark_fact: 23
- ignored/manual/browser: -30

## Alternatif Bank

- activate_weekly_development | Valid weekly source | Alternatif Bank Basın Odası | HTTP 200 | useful=20 dated=0 kobi=20 noise=0.00 | https://www.alternatifbank.com.tr/hakkimizda/basin-odasi | Dated source surface detected; page_date_count=1, dated_link_count=0.
- activate_weekly_development | Valid weekly source | Alternatif Bank Basın Bültenleri ve Duyurular | HTTP 200 | useful=30 dated=10 kobi=21 noise=0.00 | https://www.alternatifbank.com.tr/hakkimizda/basin-odasi/basin-bultenleri-ve-duyurular | Dated source surface detected; page_date_count=22, dated_link_count=10.
- activate_weekly_development | Valid weekly source | Alternatif Bank Kampanyalar | HTTP 200 | useful=20 dated=0 kobi=20 noise=0.00 | https://www.alternatifbank.com.tr/kampanyalar | Dated source surface detected; page_date_count=1, dated_link_count=0.
- activate_benchmark_fact | Valid benchmark-only source | Alternatif Bank Tahsilat Çözümleri | HTTP 200 | useful=44 dated=0 kobi=44 noise=0.00 | https://www.alternatifbank.com.tr/kurumsal/nakit-yonetimi/tahsilat-cozumleri | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | Alternatif Bank POS ve Üye İşyeri Hizmetleri | HTTP 200 | useful=38 dated=0 kobi=38 noise=0.00 | https://www.alternatifbank.com.tr/kurumsal/nakit-yonetimi/pos-ve-uye-isyeri-hizmetleri | Evergreen SME/commercial product content; no reliable dated detail feed required.
- ignore | Validated for structural testing | Alternatif Bank Yazarkasa POS | HTTP 200 | useful=37 dated=0 kobi=37 noise=0.00 | https://www.alternatifbank.com.tr/kurumsal/nakit-yonetimi/pos-ve-uye-isyeri-hizmetleri/pos-urunleri/yazarkasa-pos | Structural product example only.
- ignore | Validated for structural testing | Alternatif Bank Otomotiv Kampanyası | HTTP 200 | useful=20 dated=0 kobi=20 noise=0.00 | https://www.alternatifbank.com.tr/kampanyalar/alternatif-bank-otomotiv-kampanyasi | Parser test example only.

## DenizBank

- activate_weekly_development | Valid weekly source | DenizBank Medya Merkezi / Basında DenizBank | HTTP 200 | useful=14 dated=0 kobi=13 noise=0.44 | https://www.denizbank.com/hakkimizda/medya-merkezi/basinda-denizbank | Dated source surface detected; page_date_count=30, dated_link_count=0.
- activate_benchmark_fact | Valid benchmark-only source | DenizBank İşim İçin | HTTP 200 | useful=123 dated=3 kobi=110 noise=0.11 | https://www.denizbank.com/isim-icin | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | DenizBank KOBİ Kredileri | HTTP 200 | useful=53 dated=2 kobi=52 noise=0.38 | https://www.denizbank.com/krediler/kobi-bankaciligi | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | DenizBank POS Ürünleri | HTTP 200 | useful=134 dated=0 kobi=124 noise=0.11 | https://www.denizbank.com/isim-icin/kobi-bankaciligi/uye-isyeri-ve-pos-islemleri/pos-urunleri | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | DenizBank Üye İşyeri Hizmetleri | HTTP 200 | useful=119 dated=0 kobi=109 noise=0.12 | https://www.denizbank.com/isim-icin/kobi-bankaciligi/uye-isyeri-ve-pos-islemleri/uye-isyeri-hizmetleri | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | DenizBank Hesap Hareketi Entegrasyonu | HTTP 200 | useful=111 dated=0 kobi=101 noise=0.12 | https://www.denizbank.com/isim-icin/kobi-bankaciligi/nakit-yonetimi-ve-dis-ticaret/nakit-yonetimi/hesap-hareketi-entegrasyonu | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | DenizBank Doğrudan Borçlandırma Sistemi | HTTP 200 | useful=118 dated=0 kobi=108 noise=0.12 | https://www.denizbank.com/isim-icin/kobi-bankaciligi/nakit-yonetimi-ve-dis-ticaret/nakit-yonetimi/dogrudan-borclandirma-sistemi | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | DenizBank Güvenli Araç Alım Satım Sistemi | HTTP 200 | useful=120 dated=0 kobi=110 noise=0.12 | https://www.denizbank.com/isim-icin/kobi-bankaciligi/nakit-yonetimi-ve-dis-ticaret/nakit-yonetimi/guvenli-arac-alim-satim-sistemi | Evergreen SME/commercial product content; no reliable dated detail feed required.

## ING

- activate_benchmark_fact | Valid benchmark-only source | ING İşiniz İçin | HTTP 200 | useful=16 dated=1 kobi=12 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_weekly_development | Valid weekly source | ING Basın Bültenleri 2026 | HTTP 200 | useful=48 dated=44 kobi=6 noise=0.05 | https://www.ing.com.tr/tr/ing/basin-odasi/basin-bultenleri/2026 | Dated source surface detected; page_date_count=61, dated_link_count=44.
- ignore | Validated for structural testing | ING Basın Bültenleri 2025 | HTTP 200 | useful=31 dated=27 kobi=4 noise=0.05 | https://www.ing.com.tr/tr/ing/basin-odasi/basin-bultenleri/2025 | Archive fallback only; not active while 2026 works.
- ignore | Validated for structural testing | ING Basın Bültenleri 2024 | HTTP 200 | useful=32 dated=26 kobi=6 noise=0.07 | https://www.ing.com.tr/tr/ing/basin-odasi/basin-bultenleri/2024 | Archive fallback only; not active while 2026 works.
- activate_benchmark_fact | Valid benchmark-only source | ING Üye İşyeri | HTTP 200 | useful=19 dated=1 kobi=17 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | ING Üye İşyeri Hizmetleri | HTTP 200 | useful=17 dated=1 kobi=15 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/uye-is-yeri-hizmetleri | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | ING POS Ürünleri | HTTP 200 | useful=14 dated=1 kobi=12 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/pos-urunleri | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | ING Cebimde POS | HTTP 200 | useful=17 dated=1 kobi=15 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/ing-cebimde-pos | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | ING POS Ekstra | HTTP 200 | useful=16 dated=1 kobi=14 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/pos-ekstra | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | ING KOBİ Nakit POS | HTTP 200 | useful=25 dated=1 kobi=23 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/kobi-nakit-pos | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | ING Sağlık POS | HTTP 200 | useful=14 dated=1 kobi=12 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/saglik-pos | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | ING Karekod Ödeme | HTTP 200 | useful=11 dated=1 kobi=9 noise=0.03 | https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/karekod-odeme | Evergreen SME/commercial product content; no reliable dated detail feed required.

## TEB

- activate_weekly_development | Valid weekly source | TEB Basın Açıklamaları | HTTP 200 | useful=37 dated=22 kobi=15 noise=0.03 | https://www.teb.com.tr/teb-hakkinda/basin-aciklamalari/ | Dated source surface detected; page_date_count=21, dated_link_count=22.
- ignore | Invalid | TEB KOBİ'yim | HTTP 200 | useful=0 dated=0 kobi=0 noise=0.00 | https://www.teb.com.tr/kobiyim/ | Redirected to not-found page: https://www.teb.com.tr/FileNotFound.aspx
- activate_benchmark_fact | Valid benchmark-only source | TEB Tahsilat Çözümleri | HTTP 200 | useful=103 dated=0 kobi=101 noise=0.00 | https://www.teb.com.tr/kobiyim/tahsilat-cozumleri/ | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | TEB CEPTETEB Kurumsal Şube | HTTP 200 | useful=87 dated=0 kobi=85 noise=0.00 | https://www.teb.com.tr/kobiyim/cepteteb-kurumsal-sube/ | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | TEB Bonus Business Card | HTTP 200 | useful=105 dated=2 kobi=101 noise=0.00 | https://www.teb.com.tr/kobiyim/teb-bonus-business-card/ | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | TEB OSB Ürün | HTTP 200 | useful=87 dated=0 kobi=83 noise=0.00 | https://www.teb.com.tr/kobiyim/osb-urun/ | Evergreen SME/commercial product content; no reliable dated detail feed required.
- activate_benchmark_fact | Valid benchmark-only source | TEB Kamu Finansmanı | HTTP 200 | useful=98 dated=0 kobi=96 noise=0.00 | https://www.teb.com.tr/kobiyim/kamu-finansmani/ | Evergreen SME/commercial product content; no reliable dated detail feed required.
