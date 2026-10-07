# Weekly Operations Report

## Run Summary

- run ID: `daily_tr_37607581470`
- started: 2026-10-07T10:28:28.808021+00:00
- completed: 2026-10-07T10:31:48.778191+00:00
- duration: 199.97s
- institutions checked: Garanti BBVA, İş Bankası, Yapı Kredi, QNB, DenizBank, TEB, ING, Enpara, Alternatif Bank, Şekerbank, Fibabanka, Anadolubank, Odeabank, Türk Ticaret Bankası, BKM, TROY, TCMB, BDDK, Türkiye Bankalar Birligi, TODEB, Rekabet Kurumu, Webrazzi, FinTech Istanbul
- effective extraction start date: 2026-08-23
- final status: Kısmi Başarılı
- backup: `data/run_backups/daily_tr_37607581470`
- snapshot: `data/snapshots/2026-10-07/daily_tr_37607581470`

## New This Run

- new developments: 1
- new Claude summaries: 10
- new strategic/BD queue items: 0
- new management-awareness items: 0
- new archived items: 1
- new clusters: 12
- revised existing items: 0

## Source Health

- Garanti BBVA | Garanti BBVA Kurumsal communication / press releases | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- İş Bankası | İş Bankası Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Yapı Kredi | Yapı Kredi KOBİ Kampanyaları | Hatalı | HTTP - | error | aday 0 | hata: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- Yapı Kredi | Yapı Kredi Basın Bültenleri | Hatalı | HTTP - | error | aday 0 | hata: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- BKM | BKM Ödeme Çözümleri / TechPOS | Uyarı | HTTP 200.0 | changed | aday 0
- BKM | BKM TROY | Uyarı | HTTP 200.0 | changed | aday 0
- Rekabet Kurumu | Rekabet Kurumu Güncel | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Rekabet Kurumu | Rekabet Kurumu Mastercard and Visa investigation | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- TCMB | TCMB Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- BDDK | BDDK Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Türkiye Bankalar Birligi | Türkiye Bankalar Birligi Duyurular | Sağlıklı | HTTP 200.0 | changed | aday 34
- TODEB | TODEB Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Webrazzi | Webrazzi Fintech | Sağlıklı | HTTP 200.0 | changed | aday 4
- FinTech Istanbul | FinTech Istanbul | Sağlıklı | HTTP 200.0 | changed | aday 3
- QNB | QNB Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB Card KOBİ Ticari Kredi Kartı Kampanyaları | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ POS Çözümleri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB POS | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB Yazar Kasa POS | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Kredileri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Rahat | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- QNB | QNB KOBİ Ticari Kredi Kartları | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- ING | ING Basın Bültenleri 2026 | Sağlıklı | HTTP 200.0 | changed | aday 4
- Odeabank | Odeabank Basın Bültenleri | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Enpara | Enpara Şirketim Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Alternatif Bank | Alternatif Bank Basın Bültenleri ve Duyurular | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Şekerbank | Şekerbank Basın Odası | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Fibabanka | Fibabanka Güncel Özel Kampanyalar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Anadolubank | Anadolubank Basın Bültenleri ve Röportajlar | Sağlıklı | HTTP 200.0 | unchanged | aday ölçülmedi
- Türk Ticaret Bankası | Türk Ticaret Bankası Haberler | Hatalı | HTTP 512.0 | error | aday 0 | hata: 512 Server Error: Unknown Code for url: https://www.turkticaretbankasi.com.tr/icerikler/haberler

## Rejections

- duplicates: 7
- old items: 21
- undated items: 11
- campaign-end-date-only items: 0
- non-developments: 0
- static/noise pages: 0

## LLM Usage

- provider: anthropic
- model: llm-error-dry-run
- API key found: True
- eligible items: 10
- calls made: 10
- parse failures: 0
- rewrite calls: 0
- input character estimate: 31112
- output character estimate: 14000

## Analyst Workload

- items newly entering review: 0
- management-awareness items: 0
- revised items needing review: 0
- clusters needing review: 1
- expected analyst workload count: 1

## Alerts

- Aday link hacmi önceki başarılı koşuların 3 katından fazla.
- Arşiv oranı %90 üzerinde; kaynak gürültüsü artmış olabilir.
- LLM çağrı hacmi önceki başarılı koşuların 3 katından fazla.

## Operational Notes

- Ek operasyon notu yok.

## Recommended Next Action

1 yeni madde analist incelemesi bekliyor. Başarısız kaynaklar kaynak sağlığı ekranından kontrol edilmeli.
