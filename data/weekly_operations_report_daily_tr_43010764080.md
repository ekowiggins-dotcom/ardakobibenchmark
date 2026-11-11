# Weekly Operations Report

## Run Summary

- run ID: `daily_tr_43010764080`
- started: 2026-11-11T11:18:23.450578+00:00
- completed: 2026-11-11T11:26:07.677809+00:00
- duration: 464.23s
- institutions checked: Garanti BBVA, İş Bankası, Yapı Kredi, QNB, DenizBank, TEB, ING, Enpara, Alternatif Bank, Şekerbank, Fibabanka, Anadolubank, Odeabank, Türk Ticaret Bankası, BKM, TROY, TCMB, BDDK, Türkiye Bankalar Birligi, TODEB, Rekabet Kurumu, Webrazzi, FinTech Istanbul
- effective extraction start date: 2026-09-27
- final status: Kısmi Başarılı
- backup: `data/run_backups/daily_tr_43010764080`
- snapshot: `data/snapshots/2026-11-11/daily_tr_43010764080`

## New This Run

- new developments: 0
- new Claude summaries: 10
- new strategic/BD queue items: 0
- new management-awareness items: 0
- new archived items: 4
- new clusters: 5
- revised existing items: 0

## Source Health

- Garanti BBVA | Garanti BBVA Kurumsal communication / press releases | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- İş Bankası | İş Bankası Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Yapı Kredi | Yapı Kredi KOBİ Kampanyaları | Hatalı | HTTP - | error | aday 0 | hata: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- Yapı Kredi | Yapı Kredi Basın Bültenleri | Hatalı | HTTP - | error | aday 0 | hata: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- BKM | BKM Ödeme Çözümleri / TechPOS | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- BKM | BKM TROY | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Rekabet Kurumu | Rekabet Kurumu Güncel | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Rekabet Kurumu | Rekabet Kurumu Mastercard and Visa investigation | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- TCMB | TCMB Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- BDDK | BDDK Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Türkiye Bankalar Birligi | Türkiye Bankalar Birligi Duyurular | Sağlıklı | HTTP 200.0 | changed | aday 28
- TODEB | TODEB Duyurular | Uyarı | HTTP - | error | aday 0 | hata: HTTPSConnectionPool(host='www.todeb.org.tr', port=443): Max retries exceeded with url: / (Caused by ConnectTimeoutError(<HTTPSConnection(host='www.todeb.org.tr', port=443) at 0x7699da9fa1d0>, 'Connection to www.todeb.org.tr timed out. (connect timeout=20)'))
- Webrazzi | Webrazzi Fintech | Sağlıklı | HTTP 200.0 | changed | aday 4
- FinTech Istanbul | FinTech Istanbul | Sağlıklı | HTTP 200.0 | changed | aday 3
- QNB | QNB Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB Card KOBİ Ticari Kredi Kartı Kampanyaları | Sağlıklı | HTTP 200.0 | changed | aday 11
- QNB | QNB KOBİ POS Çözümleri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB POS | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB Yazar Kasa POS | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Kredileri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Rahat | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Ticari Kredi Kartları | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- ING | ING Basın Bültenleri 2026 | Sağlıklı | HTTP 200.0 | changed | aday 7
- Odeabank | Odeabank Basın Bültenleri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Enpara | Enpara Şirketim Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Alternatif Bank | Alternatif Bank Basın Bültenleri ve Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Şekerbank | Şekerbank Basın Odası | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Fibabanka | Fibabanka Güncel Özel Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Anadolubank | Anadolubank Basın Bültenleri ve Röportajlar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Türk Ticaret Bankası | Türk Ticaret Bankası Haberler | Hatalı | HTTP 512.0 | error | aday 0 | hata: 512 Server Error: Unknown Code for url: https://www.turkticaretbankasi.com.tr/icerikler/haberler

## Rejections

- duplicates: 5
- old items: 19
- undated items: 12
- campaign-end-date-only items: 8
- non-developments: 0
- static/noise pages: 0

## LLM Usage

- provider: anthropic
- model: claude-haiku-4-5-20251001
- API key found: True
- eligible items: 10
- calls made: 11
- parse failures: 0
- rewrite calls: 1
- input character estimate: 132161
- output character estimate: 14000

## Analyst Workload

- items newly entering review: 0
- management-awareness items: 0
- revised items needing review: 0
- clusters needing review: 3
- expected analyst workload count: 3

## Alerts

- Aday link hacmi önceki başarılı koşuların 3 katından fazla.
- Arşiv oranı %90 üzerinde; kaynak gürültüsü artmış olabilir.
- LLM çağrı hacmi önceki başarılı koşuların 3 katından fazla.

## Operational Notes

- Ek operasyon notu yok.

## Recommended Next Action

3 yeni madde analist incelemesi bekliyor. Başarısız kaynaklar kaynak sağlığı ekranından kontrol edilmeli.
