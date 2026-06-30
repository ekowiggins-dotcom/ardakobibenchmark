# Final Weekly Production Readiness Report

- run ID: `final_readiness_20260629T133423`
- controlled Claude run: `final_readiness_20260629T133423_first_clean`
- post-fix idempotency run: `final_readiness_20260629T133423_idempotency_clean`
- cutoff: `2026-05-01`

## Hardening

- Archive ID stabilization: fixed. Existing archive rows preserve historical `archive_id`; new archive rows use deterministic `recent_item_id`-based IDs.
- Archive timestamp preservation: fixed for existing rows; no existing `archived_at` changed in the post-fix idempotency run.
- No-op file-write suppression: staging writes now compare normalized CSV content and skip unchanged writes.
- Anomaly logic correction: clean unchanged-source runs are `Başarılı — Değişiklik Yok` and do not emit zero-candidate alerts.
- Pipeline-state correction: no-op run stores successful status and blank error.
- Source-health attempted correction: final artifact uses current-run source IDs and timestamps; attempted count reconciles to pipeline `sources_checked`.
- İş Bankası detail-fetch reduction: REG-006 adapter rejects product/navigation roots before detail fetch and preserves valid announcement paths.

## Controlled Claude Test

- candidates inspected: 3
- candidates eligible: 3
- Claude calls: 3
- summaries created: 3
- JSON failures: 0
- rewrites: 0
- review additions: 1
- awareness additions: 1
- archive/context additions: 2 archive rows total, including 1 newly summarized low-priority card item and 1 existing archived awareness reconciliation
- publish additions: 0

- Garanti BBVA | Global Finance Türkiye’nin En İyi Nakit Yönetimi Bankası Ödülü → Yönetici Bilgilendirme (RI-4bd38c2acf44)
- Garanti BBVA | TÜRKONFED ve Garanti BBVA’dan Ankara’da İkiz Dönüşüm Buluşması → Analist Onay Kuyruğu (RI-486659a98116)
- Garanti BBVA | Miles&Smiles Garanti BBVA Diamond Limited Edition Kredi Kartı → Düşük Öncelik / Arşiv (RI-402f008bdb89)

## Source Health

- attempted this run: 18
- fetched this run: 18
- source failures: 0
- Mastercard: blocked official-source watch/manual evidence mode; not counted as failed weekly static collection.

## Idempotency

- second-run status: Başarılı — Değişiklik Yok
- second-run Claude calls: 0
- duplicate summaries: 0
- duplicate queue rows: 0
- archive replacements: 0
- archive timestamp changes: 0
- substantive file hash changes after post-fix idempotency run: 0
- analyst decisions changed: False
- weekly developments changed: False

## QA

- compilation result: passed
- test result: `74 passed in 0.70s`
- rollback readiness: `data/final_readiness_rollback_manifest_final_readiness_20260629T133423.json`
- defects remaining: None

## Artifacts

- `data/final_readiness_before_after_final_readiness_20260629T133423.json`
- `data/final_readiness_rollback_manifest_final_readiness_20260629T133423.json`
- `data/final_readiness_source_health_final_readiness_20260629T133423.csv`
- `data/final_readiness_pre_llm_inspection_final_readiness_20260629T133423.csv`
- `data/final_readiness_routing_reconciliation_final_readiness_20260629T133423.csv`
- `data/final_readiness_publish_preview_final_readiness_20260629T133423.csv`

FINAL DECISION

Ready for normal weekly operation
