# Batch A Claude Pilot QA Report

Generated: 2026-06-25T15:31:53

Scope: Alternatif Bank and ING only. DenizBank and TEB were not sent to Claude. No auto-approval and no auto-publishing.

## Pre-LLM Candidate Inspection

| recent_item_id | institution | source_id | title | date | basis | date_source | confidence | quality | chars | duplicate | existing summary | gate |
|---|---|---|---|---|---|---|---|---:|---:|---|---|---|
| RI-f6167c763174 | Alternatif Bank | REG-118 | Alternatif Bank’a Kurumsal, Ticari Bankacılık ve Dış Ticarette 3 Uluslararası Ödül! | 05 Mayıs 2026 | 2026-05-05 | announcement_date | Yüksek | Good | 3751 | none | none before Claude | PASS |
| RI-b461fe1c2787 | ING | REG-083 | ING’den KOBİ’lere masrafsız bankacılık desteği | 3 Haziran 2026 | 2026-06-03 | announcement_date | Yüksek | Good | 5510 | none | none before Claude | PASS |
| RI-11a75c9dc055 | ING | REG-083 | ING’nin araştırmasına göre masrafsız bankacılık temel beklenti haline geldi | 20 Mayıs 2026 | 2026-05-20 | announcement_date | Yüksek | Good | 7108 | none | none before Claude | PASS |

Rejected before Claude: none. All three candidates had item-level URLs, dates on/after 2026-05-01, non-end-date recency, Good quality, and no existing summary/queue/archive/published presence.

## Claude Run

- Claude-eligible items: 3
- Final summaries stored: 3
- JSON parse failures: 0
- Language rewrite count: 0
- Note: initial Alternatif and ING summarizers were started in parallel and exposed a CSV write race. Alternatif was rerun sequentially; final stored output is exactly one summary per pilot item. Future runs were verified idempotent.

## Turkish Output QA

### Alternatif Bank — Alternatif Bank’a Kurumsal, Ticari Bankacılık ve Dış Ticarette 3 Uluslararası Ödül!

- Ne oldu? Alternatif Bank, Stevie Awards'ta VOV Tüzel Hesap ürünü için Bronz Ödül, Global Brands Magazine'den Ticaret Finansmanı Mükemmellik Ödülü ve IFC'den Sürdürülebilir Dış Ticaret Üstün Başarı Ödülü aldı. Ödüller, bankanın kurumsal ve dış ticaret alanındaki konumlandırmasını güçlendirmeyi amaçlayan PR faaliyeti.
- Neden önemli? Bu içerik Alternatif Bank'ın kurumsal itibarını destekliyor, ancak KOBİ mevduat, kredi, POS, nakit yönetimi veya dijital edinim tarafında pratik bir sonuç üretmiyor. Ödüller geçmiş performansa yönelik ve yeni ürün/hizmet lansmanı içermiyor.
- Çekirdek değerlendirme: Düşük değerli PR; KOBİ tarafında aksiyon gerektirmiyor.
- Etki: Düşük
- Önem: Düşük
- Aksiyon: Önceliklendirme
- Güven: Yüksek
- Triage destination: management_awareness
- QA verdict: İyi (Düşük değerli PR doğru ayrıştırıldı; yeni ürün/hizmet iddiası kurulmadı)
- Flags: none
- Extracted facts: ["Alternatif Bank, 2026 Middle East & North Africa Stevie Awards'ta VOV Tüzel Hesap için Bronz Stevie Ödülü kazandı.", "Global Brands Magazine tarafından Ticaret Finansmanı ve İhracat Çözümlerinde Mükemmellik Ödülü verildi.", "International Finance Corporation (IFC) tarafından Küresel Ticaret Partnerleri Toplantısı'nda Üstün Başarı Ödülü aldı.", "CEO Ozan Kırmızı, müşteri ihtiyacını merkeze alan danışman bankacılık anlayışını vurguladı.", "Ödüller, kurumsal ve ticari bankacılık ile dış ticaret alanındaki konumlandırmayı desteklemek için kullanılıyor."]
- Open questions: ["Bu ödüller Alternatif Bank'ın KOBİ müşteri kazanımında veya ürün satışında pratik bir etkiye sahip mi?", "VOV Tüzel Hesap ürünü KOBİ segmentine yönelik mi, yoksa daha büyük kurumsal müşterilere mi hitap ediyor?"]

### ING — ING’den KOBİ’lere masrafsız bankacılık desteği

- Ne oldu? ING Türkiye, KOBİ müşterilerine 7/24 ücretsiz para transferleri (EFT, havale, FAST), masrafsız ticari kredi kartı ve POS cihazı başvurusunda nakit iade (5.000 TL'ye kadar) sunuyor. Kampanya, dijital kanallar üzerinden hızlı müşteri onboarding'i de içeriyor.
- Neden önemli? Akbank için asıl soru, ücretsiz işlem paketlerinin yeni KOBİ müşteri kazanımında gerçek etkisinin ne olduğu. ING, ticari kart aktivasyonu ve POS cihaz kazanımını nakit iade ile destekliyor; bu, KOBİ edinim maliyetini düşürme taktiği.
- Çekirdek değerlendirme: Yeni KOBİ müşteri edinimi için net fiyat avantajı kampanyası; ödemeler ve POS tarafında izlenmeli.
- Etki: Orta
- Önem: Orta
- Aksiyon: BD Konuşma Notlarına Ekle
- Güven: Yüksek
- Triage destination: review
- QA verdict: İyi (KOBİ/masrafsız işlem sinyali doğru orta etkiyle ele alındı)
- Flags: none
- Extracted facts: ["EFT, havale ve FAST işlemleri 7/24 ücretsiz", "ING Bonus Business ticari kredi kartı yıllık aidatı yok", "Yeni POS cihazı başvurusunda 750.000 TL ciroya kadar 5.000 TL nakit iade", "İki ve üzeri otomatik ödeme talimatında 2.500 TL nakit iade", "Dijital kanallar üzerinden şubesiz müşteri onboarding", "Kampanya tarihi: 3 Haziran 2026"]
- Open questions: ["Bu kampanya ne kadar sürecek? (Bitiş tarihi belirtilmemiş)", "Nakit iade mekanizması gerçek müşteri kazanımında ne kadar etkili?", "ING'nin KOBİ mevduat hedefleri neler? (Kampanya sadece işlem ücreti ve POS'a odaklanıyor)"]

### ING — ING’nin araştırmasına göre masrafsız bankacılık temel beklenti haline geldi

- Ne oldu? ING Türkiye, ING Mobil üzerinden EFT/havale/FAST işlemlerini ve kredi kartı aidatlarını kaldırdı. Hamle, araştırmasına göre masrafsız bankacılığın müşteriler için temel beklenti haline geldiğini gösteriyor.
- Neden önemli? Akbank için asıl soru, ücretsiz işlem paketlerinin yeni KOBİ müşteri kazanımında ne kadar etkili olduğu. ING'nin araştırması (müşterilerin %64'ü masraflar nedeniyle banka değiştirmeye istekli) fiyat hassasiyetini gösteriyor; bu, ticari müşteri edinim konuşmalarında Akbank'ın da benzer paket sunup sunmadığını sorgulatıyor.
- Çekirdek değerlendirme: Yeni KOBİ müşteri kazanımını fiyat avantajı üzerinden destekleme kampanyası; ticari müşteri edinim taktikleri tarafında izlenmeli.
- Etki: Orta
- Önem: Orta
- Aksiyon: BD Konuşma Notlarına Ekle
- Güven: Yüksek
- Triage destination: review
- QA verdict: İyi (KOBİ/masrafsız işlem sinyali doğru orta etkiyle ele alındı)
- Flags: none
- Extracted facts: ["ING Mobil üzerinden yurt içi para transferi (EFT/havale/FAST) ücretsiz hale getirildi.", "ING Dijital Kredi Kartı ve ING Light Kredi Kartı aidat muafiyeti sağlanıyor.", "ING Bonus Kredi Kartı aylık 5.000 TL harcamayla ücretsiz kullanılabiliyor.", "ING araştırmasına göre katılımcıların %63'ü son bir ayda banka/işlem ücreti ödedi.", "Katılımcıların %64'ü masraflar nedeniyle banka değiştirmeye istekli.", "Katılımcıların neredeyse yarısı masraflar nedeniyle bankasını değiştirdi.", "Araştırma 24-26 Mart 2026'de 300 dijital bankacılık müşterisiyle yapıldı."]
- Open questions: ["Akbank'ın yeni KOBİ müşteri edinim paketinde benzer ücretsiz işlem avantajları var mı?", "Bu kampanyanın ING'nin yeni KOBİ müşteri kazanımında gerçek etkisi ne oldu (3-6 ay sonra)?", "Akbank KOBİ müşterilerinin ücret hassasiyeti ING'nin araştırması kadar yüksek mi?"]

## Triage

| item | destination | triage_status | triage_reason | analyst review required |
|---|---|---|---|---|
| Alternatif Bank’a Kurumsal, Ticari Bankacılık ve Dış Ticarette 3 Uluslararası Ödül! | management_awareness | Beklemede | Majör ödül, ranking veya itibar sinyali yönetici farkındalığı gerektiriyor. | Evet |
| ING’den KOBİ’lere masrafsız bankacılık desteği | review | Beklemede | Review queue: orta etki / BD konuşma notu | Evet |
| ING’nin araştırmasına göre masrafsız bankacılık temel beklenti haline geldi | review | Beklemede | Review queue: orta etki / BD konuşma notu | Evet |

- Review queue additions: 2 (both ING items)
- Management-awareness additions: 1 (Alternatif Bank award/PR signal)
- Archive additions: 0
- Weekly developments additions: 0

## Cluster Check

- Alternatif Bank’a Kurumsal, Ticari Bankacılık ve Dış Ticarette 3 Uluslararası Ödül!: matched existing cluster = no; new cluster created = no; suppression applied = no. Reason: Alternatif award item is a single weak PR/awareness item; no cluster created or matched.
- ING’den KOBİ’lere masrafsız bankacılık desteği: matched existing cluster = no; new cluster created = no; suppression applied = no. Reason: No existing cluster matches ING masrafsız işlem/POS acquisition signal closely enough; İş Bankası ticari kart cluster is not the same pattern.
- ING’nin araştırmasına göre masrafsız bankacılık temel beklenti haline geldi: matched existing cluster = no; new cluster created = no; suppression applied = no. Reason: No existing cluster matches ING masrafsız işlem/POS acquisition signal closely enough; İş Bankası ticari kart cluster is not the same pattern.

## Immediate Idempotency Rerun

- New recent items: 0 across rerun source extractions; duplicate candidates detected: 3
- New summaries: 0
- JSON parse failures on rerun: 0
- Language rewrite attempts on rerun: 0
- New review queue rows: 0
- New archive rows: 0
- New management-awareness rows: 0
- Duplicate Claude calls on rerun: 0 (summarizer found 0 candidates)
- Analyst decisions changed: 0; protected reviewer/status fields are preserved by the triage merge.

Stable-file check after triage merge fix:

| file | rows before | rows after | byte-stable |
|---|---:|---:|---|
| data/recent_item_review_queue.csv | 13 | 13 | True |
| data/management_awareness_queue.csv | 2 | 2 | True |
| data/recent_item_archive.csv | 12 | 12 | True |
| data/recent_item_summaries.csv | 32 | 32 | True |

## Coverage Status

- Alternatif Bank: MVP active | weekly=1 | benchmark=2 | refinement=Kampanya ve üst basın odası sayfaları manuel; aktif weekly kaynak REG-118 ile sınırlı.
- ING: MVP active | weekly=1 | benchmark=9 | refinement=POS ürün sayfaları benchmark_fact; haftalık akış yalnızca REG-083 2026 basın bültenleri.
- DenizBank: Kaynak Geliştirme Gerekli | weekly=0 | benchmark=9 | refinement=Resmi medya sayfası static extraction ile temiz dated item üretmedi; browser/manual kaynak geliştirme gerekli.
- TEB: Kaynak Geliştirme Gerekli | weekly=0 | benchmark=7 | refinement=Basın/KOBİ sayfaları temiz dated item üretmedi; KOBİ root FileNotFound yönleniyor; browser/manual kaynak geliştirme gerekli.

## Acceptance

Batch A passes: at least one eligible item was summarized, final stored pilot summaries = 3, JSON parse failures = 0, controlled values are Turkish, no static product page was mislabeled as a weekly development, triage destinations are defensible, immediate rerun produced no new rows, and nothing was published automatically.

Safe to proceed to Batch B: yes, after reviewing this report. Do not start Batch B automatically.
