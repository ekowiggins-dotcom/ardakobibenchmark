# Weekly Rehearsal Report

- run ID: `weekly_rehearsal_20260629T082655`
- first run ID: `weekly_rehearsal_20260629T082655_first`
- second run ID: `weekly_rehearsal_20260629T082655_second`
- source universe: active registry with weekly/static eligibility; blocked/manual sources reported but not fetched
- sources attempted: 18.0
- sources succeeded: 18.0
- sources skipped: 70
- blocked sources: 16
- manual sources: 34
- source failures: 0.0
- raw documents collected: 18.0
- candidates discovered: 91.0
- rejected old items: 2.0
- rejected undated items: 21.0
- rejected source-page rows: measured in candidate inspection rejection_reason
- duplicates: 18.0
- material revisions: 0
- Claude-eligible candidates: 3
- Claude calls: 0.0
- summaries created: 0.0
- JSON failures: 0.0
- language rewrites: 0.0
- review additions: 0.0
- awareness additions: 0.0
- archive additions: 0.0
- benchmark revisions: not changed by rehearsal publisher
- cluster preview: 4.0 clusters, 0.0 queue additions
- publish-preview count: 0
- actual published rows changed: False
- analyst decisions changed: False
- Mastercard operational status: Critical; automated current-source readiness Blocked; handled via manual official evidence and recovery watch; not a failed source.

## First Run Counts

{
  "run_id": "weekly_rehearsal_20260629T082655_first",
  "run_type": "weekly_rehearsal",
  "started_at": "2026-06-29T08:27:19.559094+00:00",
  "completed_at": "2026-06-29T08:30:05.661545+00:00",
  "duration_seconds": "166.1",
  "institutions_requested": "Adyen,Alternatif Bank,Anadolu Ajansı,Anadolubank,BDDK,BKM,Bloomberg HT,Burgan Bank,Dünya Gazetesi,Enpara,Fibabanka,FinTech Istanbul,Garanti BBVA,ING,KAP,Kuveyt Türk,Mastercard,Odeabank,Param,QNB Finansbank,Rekabet Kurumu,Stripe,TCMB,TODEB,Türk Ticaret Bankası,Türkiye Bankalar Birligi,VakifBank,Visa,Webrazzi,Yapı Kredi,iyzico,İş Bankası,Şekerbank",
  "sources_requested": "18.0",
  "sources_checked": "18.0",
  "sources_succeeded": "18.0",
  "sources_failed": "0.0",
  "unchanged_sources": "14.0",
  "changed_sources": "4.0",
  "candidate_links_found": "91.0",
  "detail_pages_fetched": "55.0",
  "new_items_created": "3.0",
  "duplicates_skipped": "18.0",
  "old_items_rejected": "2.0",
  "undated_items_rejected": "21.0",
  "end_date_only_items_rejected": "6.0",
  "non_developments_rejected": "0.0",
  "summaries_created": "0.0",
  "summaries_skipped_existing": "0.0",
  "json_parse_failures": "0.0",
  "llm_rewrite_count": "0.0",
  "review_queue_additions": "0.0",
  "management_awareness_additions": "0.0",
  "archive_additions": "0.0",
  "clusters_created": "4.0",
  "cluster_queue_additions": "0.0",
  "estimated_input_characters": "0.0",
  "estimated_output_characters": "0.0",
  "estimated_llm_calls": "0.0",
  "final_status": "Kısmi Başarılı",
  "error_summary": "Aday link hacmi önceki başarılı koşuların 3 katından fazla.",
  "report_path": "data/weekly_operations_report_weekly_rehearsal_20260629T082655_first.md"
}

## Second Run Counts

{
  "run_id": "weekly_rehearsal_20260629T082655_second",
  "run_type": "weekly_rehearsal",
  "started_at": "2026-06-29T08:30:27.621789+00:00",
  "completed_at": "2026-06-29T08:31:10.255811+00:00",
  "duration_seconds": "42.63",
  "institutions_requested": "Adyen,Alternatif Bank,Anadolu Ajansı,Anadolubank,BDDK,BKM,Bloomberg HT,Burgan Bank,Dünya Gazetesi,Enpara,Fibabanka,FinTech Istanbul,Garanti BBVA,ING,KAP,Kuveyt Türk,Mastercard,Odeabank,Param,QNB Finansbank,Rekabet Kurumu,Stripe,TCMB,TODEB,Türk Ticaret Bankası,Türkiye Bankalar Birligi,VakifBank,Visa,Webrazzi,Yapı Kredi,iyzico,İş Bankası,Şekerbank",
  "sources_requested": "18",
  "sources_checked": "18",
  "sources_succeeded": "18",
  "sources_failed": "0",
  "unchanged_sources": "18",
  "changed_sources": "0",
  "candidate_links_found": "0",
  "detail_pages_fetched": "0",
  "new_items_created": "0",
  "duplicates_skipped": "0",
  "old_items_rejected": "0",
  "undated_items_rejected": "0",
  "end_date_only_items_rejected": "0",
  "non_developments_rejected": "0",
  "summaries_created": "0",
  "summaries_skipped_existing": "0",
  "json_parse_failures": "0",
  "llm_rewrite_count": "0",
  "review_queue_additions": "0",
  "management_awareness_additions": "0",
  "archive_additions": "0",
  "clusters_created": "0",
  "cluster_queue_additions": "0",
  "estimated_input_characters": "0",
  "estimated_output_characters": "0",
  "estimated_llm_calls": "0",
  "final_status": "Kısmi Başarılı",
  "error_summary": "Aday link sayısı önceki başarılı koşulara göre beklenmedik biçimde sıfır.",
  "report_path": "data/weekly_operations_report_weekly_rehearsal_20260629T082655_second.md"
}

## Idempotency Result

- second run new_items_created: 0
- second run summaries_created: 0
- second run review_queue_additions: 0
- second run archive_additions: 0
- second run management_awareness_additions: 0

## QA

- compilation result: passed
- test result: 68 passed
- rollback readiness: manifest created
- critical defects found: None
- recommended fixes: None before normal weekly operation

## Final Decision: Ready for normal weekly operation

Ready for normal weekly operation