# Weekly Operations Report

## Run Summary

- run ID: `daily_tr_37193874121`
- started: 2026-10-04T09:59:30.472141+00:00
- completed: 2026-10-04T10:05:21.727383+00:00
- duration: 351.26s
- institutions checked: Garanti BBVA, İş Bankası, Yapı Kredi, QNB, DenizBank, TEB, ING, Enpara, Alternatif Bank, Şekerbank, Fibabanka, Anadolubank, Odeabank, Türk Ticaret Bankası, BKM, TROY, TCMB, BDDK, Türkiye Bankalar Birligi, TODEB, Rekabet Kurumu, Webrazzi, FinTech Istanbul
- effective extraction start date: 2026-08-20
- final status: Kısmi Başarılı
- backup: `data/run_backups/daily_tr_37193874121`
- snapshot: `data/snapshots/2026-10-04/daily_tr_37193874121`

## New This Run

- new developments: 0
- new Claude summaries: 8
- new strategic/BD queue items: 0
- new management-awareness items: 0
- new archived items: 0
- new clusters: 12
- revised existing items: 0

## Source Health

- Garanti BBVA | Garanti BBVA Kurumsal communication / press releases | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- İş Bankası | İş Bankası Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Yapı Kredi | Yapı Kredi KOBİ Kampanyaları | Hatalı | HTTP - | error | aday 0 | hata: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- Yapı Kredi | Yapı Kredi Basın Bültenleri | Hatalı | HTTP - | error | aday 0 | hata: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- BKM | BKM Ödeme Çözümleri / TechPOS | Uyarı | HTTP 200.0 | changed | aday 0
- BKM | BKM TROY | Uyarı | HTTP 200.0 | changed | aday 0
- Rekabet Kurumu | Rekabet Kurumu Güncel | Uyarı | HTTP - | error | aday 0 | hata: HTTPSConnectionPool(host='www.rekabet.gov.tr', port=443): Max retries exceeded with url: /tr/Guncel (Caused by ConnectTimeoutError(<HTTPSConnection(host='www.rekabet.gov.tr', port=443) at 0x7f6a476ada10>, 'Connection to www.rekabet.gov.tr timed out. (connect timeout=20)'))
- Rekabet Kurumu | Rekabet Kurumu Mastercard and Visa investigation | Uyarı | HTTP - | error | aday 0 | hata: HTTPSConnectionPool(host='www.rekabet.gov.tr', port=443): Max retries exceeded with url: /en/Guncel/investigation-launched-on-mastercard-and-visa-b69b1d5fb063f01193e90050568585c9 (Caused by ConnectTimeoutError(<HTTPSConnection(host='www.rekabet.gov.tr', port=443) at 0x7f385856a210>, 'Connection to www.rekabet.gov.tr timed out. (connect timeout=20)'))
- TCMB | TCMB Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- BDDK | BDDK Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Türkiye Bankalar Birligi | Türkiye Bankalar Birligi Duyurular | Sağlıklı | HTTP 200.0 | changed | aday 32
- TODEB | TODEB Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Webrazzi | Webrazzi Fintech | Sağlıklı | HTTP 200.0 | changed | aday 4
- FinTech Istanbul | FinTech Istanbul | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB Card KOBİ Ticari Kredi Kartı Kampanyaları | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ POS Çözümleri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB POS | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB Yazar Kasa POS | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Kredileri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Rahat | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Ticari Kredi Kartları | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- ING | ING Basın Bültenleri 2026 | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Odeabank | Odeabank Basın Bültenleri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Enpara | Enpara Şirketim Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Alternatif Bank | Alternatif Bank Basın Bültenleri ve Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Şekerbank | Şekerbank Basın Odası | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Fibabanka | Fibabanka Güncel Özel Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Anadolubank | Anadolubank Basın Bültenleri ve Röportajlar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Türk Ticaret Bankası | Türk Ticaret Bankası Haberler | Hatalı | HTTP 512.0 | error | aday 0 | hata: 512 Server Error: Unknown Code for url: https://www.turkticaretbankasi.com.tr/icerikler/haberler

## Rejections

- duplicates: 6
- old items: 21
- undated items: 8
- campaign-end-date-only items: 0
- non-developments: 0
- static/noise pages: 0

## LLM Usage

- provider: anthropic
- model: llm-error-dry-run
- API key found: True
- eligible items: 8
- calls made: 8
- parse failures: 0
- rewrite calls: 0
- input character estimate: 28798
- output character estimate: 11200

## Analyst Workload

- items newly entering review: 0
- management-awareness items: 0
- revised items needing review: 0
- clusters needing review: 1
- expected analyst workload count: 1

## Alerts

- Aday link hacmi önceki başarılı koşuların 3 katından fazla.
- LLM çağrı hacmi önceki başarılı koşuların 3 katından fazla.

## Operational Notes

- Ek operasyon notu yok.

## Recommended Next Action

1 yeni madde analist incelemesi bekliyor. Başarısız kaynaklar kaynak sağlığı ekranından kontrol edilmeli.
