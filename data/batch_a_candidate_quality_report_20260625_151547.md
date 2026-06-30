# Batch A Candidate Quality Report

Generated: 2026-06-25T15:15:47

Scope: Alternatif Bank, DenizBank, ING, TEB. No Claude calls, no approvals, no publishing, no reset.
Permanent cutoff used in discovery: 2026-05-01. Dry-run discovery was executed twice per bank; the second run produced the same candidate counts, so discovery is idempotent at URL/candidate level.

## Executive Decision

| Bank | Weekly source status | Genuine recent candidates | Ready for Claude | Decision |
|---|---:|---:|---|---|
| Alternatif Bank | 1 active | 1 | Yes, tiny Claude pilot only. One recent item; let triage decide whether the award item is management-relevant. | Proceed with tiny pilot |
| DenizBank | 0 active | 0 | No. Stop before Claude until a clean official press/news item feed is found or browser collector is introduced. | Stop before Claude |
| ING | 1 active | 2 | Yes, tiny Claude pilot. Two recent PDF candidates with readable titles and dates. | Proceed with tiny pilot |
| TEB | 0 active | 0 | No. Stop before Claude until a reliable current dated press/campaign item source exists. | Stop before Claude |

## Alternatif Bank

- Source candidates tested: 7
- Sources validated: 3 active static sources: 1 weekly_development, 2 benchmark_fact. 2 broad pages downgraded to manual/inactive after item-level dry-run; 2 structural examples ignored.
- Working official sources: Official press detail list REG-118 exposes dated item URLs in raw HTML.
- Rejected/noisy sources: Basın Odası category page and Kampanyalar page: broad/navigation surfaces; no reliable dated item-level weekly extraction.
- Total links found: 130
- Candidate links: 4
- Candidates with valid accepted dates: 1
- Candidates rejected as old: 3
- Candidates rejected as undated: 0
- Candidates rejected as campaign-end-date-only: 0
- Retail-noise candidates: 0 accepted retail-noise candidates; campaign listing held inactive.
- Static product pages: 2
- Genuine KOBİ/commercial development candidates: 1
- Duplicate candidates: 0
- Dry-run idempotency: run 1 created 1; run 2 created 1; candidate links run 1/run 2 = 4/4.

Source role decisions:
- REG-118 Alternatif Bank Basın Bültenleri ve Duyurular: weekly_development, active, static_scrape, mvp_active.
- REG-119 Tahsilat Çözümleri: benchmark_fact, active.
- REG-120 POS ve Üye İşyeri Hizmetleri: benchmark_fact, active.
- REG-078 Basın Odası: manual/inactive after item-level discovery failed.
- REG-079 Kampanyalar: manual/inactive; retail/campaign surface not reliable enough for weekly flow.

Top accepted candidates:
- Alternatif Bank’a Kurumsal, Ticari Bankacılık ve Dış Ticarette 3 Uluslararası Ödül! [2026-05-05] https://www.alternatifbank.com.tr/hakkimizda/basin-odasi/basin-bultenleri-ve-duyurular/alternatif-banka-uc-uluslararasi-odul

Top rejected candidates and reasons:
- Alternatif Bank, Kurumsal ve Ticari Bankacılıkta 2025 Yılını Güçlü Büyümeyle Tamamladı :: Kesim tarihinden eski: 2026-02-26 < 2026-05-01 :: https://www.alternatifbank.com.tr/hakkimizda/basin-odasi/basin-bultenleri-ve-duyurular/alternatif-bank-kurumsal-ve-ticari-bankacilikta-2025-yilini-guclu-buyumeyle-tamamladi
- Alternatif Bank'tan Dış Ticaret Finansmanında Asya Kalkınma Bankası'yla Önemli İş Birliği :: Kesim tarihinden eski: 2026-02-20 < 2026-05-01 :: https://www.alternatifbank.com.tr/hakkimizda/basin-odasi/basin-bultenleri-ve-duyurular/alternatif-bank-dis-ticaret-finansmaninda-asya-kalkinma-bankasiyla-onemli-is-birligi
- Alternatif Bank, Dijital/Mobil Kanallarda Masrafsız Bankacılık Deneyimi Sunmaya Devam Ediyor :: Kesim tarihinden eski: 2026-01-21 < 2026-05-01 :: https://www.alternatifbank.com.tr/hakkimizda/basin-odasi/basin-bultenleri-ve-duyurular/alternatif-bank-masrafsiz-bankacilik-deneyimi

- Recommended source rows to activate: Activate only REG-118 for weekly development; keep REG-119 and REG-120 as benchmark_fact. Do not activate REG-078/REG-079 for weekly flow.
- Bank-specific parser needed: Yes: extract_alternatif_bank_links() was added for the press-card HTML structure.
- Bank-specific filter refinement needed: Keep positive commercial keywords; campaign surface still needs stricter item-level parser before use.
- Ready for Claude: Yes, tiny Claude pilot only. One recent item; let triage decide whether the award item is management-relevant.

## DenizBank

- Source candidates tested: 8
- Sources validated: 7 benchmark_fact sources active; 0 weekly_development sources active after item-level discovery.
- Working official sources: Official KOBİ/POS/cash pages work as benchmark_fact sources.
- Rejected/noisy sources: Media center page was HTML/static but did not yield clean official dated media-release item URLs in static extraction.
- Total links found: 0
- Candidate links: 0
- Candidates with valid accepted dates: 0
- Candidates rejected as old: 0
- Candidates rejected as undated: 0
- Candidates rejected as campaign-end-date-only: 0
- Retail-noise candidates: No active weekly candidates. Deniz Yatırım/daily-market PDF flood was not activated.
- Static product pages: 7
- Genuine KOBİ/commercial development candidates: 0
- Duplicate candidates: 0
- Dry-run idempotency: run 1 created 0; run 2 created 0; candidate links run 1/run 2 = 0/0.

Source role decisions:
- REG-080 Medya Merkezi / Basında DenizBank: manual/inactive after item-level discovery failed.
- REG-121 İşim İçin: benchmark_fact, active.
- REG-122 KOBİ Kredileri: benchmark_fact, active.
- REG-082/REG-123 POS/Üye İşyeri surfaces: benchmark_fact, active.
- REG-124/125/126 cash-management pages: benchmark_fact, active.

Top accepted candidates:
- None.

Top rejected candidates and reasons:
- None from active weekly sources; bank is stopped before Claude because no active weekly source produced item-level candidates.

- Recommended source rows to activate: No weekly source activation yet. Keep product/cash-management pages benchmark_fact only.
- Bank-specific parser needed: No new parser added; static media source did not expose a reliable item-level feed to parse.
- Bank-specific filter refinement needed: Needed before future weekly activation: explicit Deniz Yatırım, BIST, VİOP, market-bulletin exclusion remains mandatory.
- Ready for Claude: No. Stop before Claude until a clean official press/news item feed is found or browser collector is introduced.
- Media release structure: official media page is HTML/static in collection, but item-level media/PDF release links were not cleanly extractable; Deniz Yatırım-style market bulletin noise remains blocked by non-activation.

## ING

- Source candidates tested: 12
- Sources validated: 9 active static sources: 1 weekly_development press-year page and 8 benchmark_fact business/POS pages. 2025/2024 archive pages ignored while 2026 is valid.
- Working official sources: Latest valid press-release year page is 2026; candidate URLs are PDFs linked from official listing.
- Rejected/noisy sources: Older 2026 press PDFs correctly rejected by permanent 2026-05-01 cutoff; POS product pages not treated as recent without announcement/start date.
- Total links found: 116
- Candidate links: 6
- Candidates with valid accepted dates: 2
- Candidates rejected as old: 4
- Candidates rejected as undated: 0
- Candidates rejected as campaign-end-date-only: 0
- Retail-noise candidates: 0 accepted retail-noise candidates. Press PDF cards are dated; generic product pricing pages are benchmark-only.
- Static product pages: 8
- Genuine KOBİ/commercial development candidates: 2
- Duplicate candidates: 0
- Dry-run idempotency: run 1 created 2; run 2 created 2; candidate links run 1/run 2 = 6/6.

Source role decisions:
- REG-083 ING Basın Bültenleri 2026: weekly_development, active, static_scrape, mvp_active.
- REG-084/085 and REG-127-133 business/POS/product pages: benchmark_fact, active.
- 2025/2024 press archive URLs: ignored as structural fallbacks, not active while 2026 works.

Top accepted candidates:
- ING’den KOBİ’lere masrafsız bankacılık desteği [2026-06-03] https://www.ing.com.tr/F/Documents/pdf/Basin_Odasi/2026/INGden_KOBIlere_masrafsiz_bankacilik_destegi.pdf
- ING’nin araştırmasına göre masrafsız bankacılık temel beklenti haline geldi [2026-05-20] https://www.ing.com.tr/F/Documents/pdf/Basin_Odasi/2026/INGnin_arastirmasina_gore_masrafsiz_bankacilik_temel_beklenti_haline_geldi.pdf

Top rejected candidates and reasons:
- Masrafsız bankacılıkta öncü adım: ING’de sonsuza kadar masraf yok :: Kesim tarihinden eski: 2026-03-16 < 2026-05-01 :: https://www.ing.com.tr/F/Documents/pdf/Basin_Odasi/2026/INGde_sonsuza_kadar_masraf_yok.pdf
- Dijital Öğretmenler Projesi yenilendi: Daha geniş etki alanı, güçlü yapı ve zengin içerik :: Kesim tarihinden eski: 2026-02-18 < 2026-05-01 :: https://www.ing.com.tr/F/Documents/pdf/Basin_Odasi/2026/ING_DOP_BB_Subat2025.pdf
- ING Türkiye'den dijital altyapı dönüşümü :: Kesim tarihinden eski: 2026-01-14 < 2026-05-01 :: https://www.ing.com.tr/F/Documents/pdf/Basin_Odasi/2026/ING_Turkiye'den_dijital_altyapi_donusumu.pdf
- ING Leasing’den 500 milyon TL’lik sermaye artışı: Sanayi dönüşümüne güçlü destek :: Kesim tarihinden eski: 2026-01-06 < 2026-05-01 :: https://www.ing.com.tr/F/Documents/INGLeasing_SermayeArtisi_2026.pdf

- Recommended source rows to activate: Activate REG-083 for weekly development; keep POS and business pages benchmark_fact only.
- Bank-specific parser needed: Yes: extract_ing_links() was added for ING PDF press-card listing.
- Bank-specific filter refinement needed: Minor refinement later: research/management-statements should remain eligible but low/medium unless clearly SME/POS/commercial.
- Ready for Claude: Yes, tiny Claude pilot. Two recent PDF candidates with readable titles and dates.
- Latest valid press-release year page: 2026. POS campaign/product pages have poor date quality for recent-development use and remain benchmark_fact.

## TEB

- Source candidates tested: 7
- Sources validated: 6 benchmark_fact sources active; 0 weekly_development sources active after item-level discovery.
- Working official sources: Tahsilat, CEPTETEB Kurumsal Şube, Bonus Business, OSB, Kamu Finansmanı pages work as benchmark_fact sources.
- Rejected/noisy sources: Press page does not produce clean current weekly candidates in static mode; KOBİ root redirects to FileNotFound.aspx.
- Total links found: 0
- Candidate links: 0
- Candidates with valid accepted dates: 0
- Candidates rejected as old: 0
- Candidates rejected as undated: 0
- Candidates rejected as campaign-end-date-only: 0
- Retail-noise candidates: No active weekly candidates. /arama/ and navigation/search noise are excluded by not activating those surfaces.
- Static product pages: 6
- Genuine KOBİ/commercial development candidates: 0
- Duplicate candidates: 0
- Dry-run idempotency: run 1 created 0; run 2 created 0; candidate links run 1/run 2 = 0/0.

Source role decisions:
- REG-086 Basın Açıklamaları: manual/inactive after item-level discovery failed.
- REG-134 KOBİ’yim: manual/inactive; exact URL redirects to FileNotFound.aspx.
- REG-088 and REG-135-139 POS/KOBİ/product pages: benchmark_fact, active.
- REG-087 CEPTETEB İşte Kampanyaları: manual/inactive; disabled by exact-source review.

Top accepted candidates:
- None.

Top rejected candidates and reasons:
- None from active weekly sources; bank is stopped before Claude because no active weekly source produced item-level candidates.

- Recommended source rows to activate: No weekly source activation yet. Keep validated product pages benchmark_fact only.
- Bank-specific parser needed: No. Not added because static sources did not expose a clean weekly item-level structure.
- Bank-specific filter refinement needed: Needed if future source is found: reject /arama/, menu labels, old reports, investor/career/sponsorship noise.
- Ready for Claude: No. Stop before Claude until a reliable current dated press/campaign item source exists.
- Press page exposes page/navigation content but not a clean current dated weekly feed in static mode. KOBİ root exact URL redirects to FileNotFound.aspx. /arama/ noise is not active.

## Files and Audit Trail

- Source validation candidates: data/batch_a_source_validation_candidates.csv
- Latest source validation report: data/batch_a_source_validation_report_20260625_150715.md
- Final dry-run logs: data/batch_a_discovery_logs_final/
- Registry updated: data/source_registry.csv
- Extraction code touched: pipeline/extract_recent_items.py
- Batch A validation helper: pipeline/validate_batch_a_sources.py

## Claude Gate

Claude remains blocked for DenizBank and TEB. Alternatif Bank and ING can proceed only after this report is reviewed; recommended next run would be a small Claude pilot on the accepted candidates, not a broad bank-wide run.
