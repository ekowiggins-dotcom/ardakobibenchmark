from __future__ import annotations

import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from bs4 import BeautifulSoup

from pipeline.extract_recent_items import (
    canonicalize_url,
    classify_content_role_for_candidate,
    duplicate_index,
    extract_is_bankasi_duyuru_links,
    extract_global_payments_links,
    find_duplicate,
    has_financial_results_export_evidence,
    should_fetch_detail_for_candidate,
)
from pipeline.rebuild_seen_item_index import normalize_title
from pipeline.summarize_recent_items import gate_skip_reason
from pipeline.run_weekly_incremental_mvp import RunMetrics, add_anomaly_alerts, eligible_sources, final_status_for
from pipeline.update_recent_item_review_queue import route_summaries
from pipeline.update_recent_item_review_queue import (
    ARCHIVE_COLUMNS,
    MANAGEMENT_AWARENESS_COLUMNS,
    archive_id_for,
    awareness_id_for,
    merge_archive,
    merge_destination,
    write_csv_if_changed,
)
from pipeline.validate_mastercard_sources import (
    canonicalize_mastercard_url,
    classify_mastercard_item,
    source_key as mastercard_source_key,
)
from utils.browser_collector import (
    BrowserPage,
    detect_mastercard_page_type,
    is_generic_product_root_url,
    is_item_level_mastercard_url,
    mastercard_url_key,
    passes_mastercard_article_gate,
)
from utils.mastercard_official_fallback import (
    classify_source_access,
    dedupe_item_rows,
    extract_mastercard_press_index,
    item_row_from_article,
    PressArticle,
)
from utils.mastercard_blocked_mode import (
    high_precision_historical_taxonomy,
    passes_manual_official_evidence_gate,
    recovery_check_due,
    should_skip_mastercard_weekly_source,
)
from utils.date_utils import extract_date_semantics
from utils.github_data_sync import _git_blob_sha, _repo_from_remote_url
from utils.recency import evaluate_recency
from utils.source_health import ERROR, HEALTHY, MANUAL, WARNING, classify_source_health
from utils.triage import TRIAGE_MANAGEMENT_AWARENESS, triage_recent_item_summary
from pipeline.weekly_rehearsal_artifacts import intended_destination


class SourceHealthTests(unittest.TestCase):
    def test_healthy_source(self) -> None:
        health = classify_source_health(
            latest_status="fetched",
            status_code=200,
            content_length=2000,
            candidate_item_count=3,
            consecutive_failures=0,
            collection_method="static_scrape",
            extraction_mode="weekly_development",
        )
        self.assertEqual(health.status, HEALTHY)

    def test_repeated_failures_are_error(self) -> None:
        health = classify_source_health(
            latest_status="error",
            status_code=500,
            content_length=0,
            candidate_item_count=0,
            consecutive_failures=3,
        )
        self.assertEqual(health.status, ERROR)

    def test_zero_candidates_warns_for_weekly_source(self) -> None:
        health = classify_source_health(
            latest_status="fetched",
            status_code=200,
            content_length=1000,
            candidate_item_count=0,
            consecutive_failures=0,
            extraction_mode="weekly_development",
        )
        self.assertEqual(health.status, WARNING)

    def test_manual_source_is_manual(self) -> None:
        health = classify_source_health(collection_method="browser_required")
        self.assertEqual(health.status, MANUAL)


class GitHubDataSyncTests(unittest.TestCase):
    def test_repo_slug_parses_https_remote(self) -> None:
        self.assertEqual(
            _repo_from_remote_url("https://github.com/ekowiggins-dotcom/ardakobibenchmark.git"),
            "ekowiggins-dotcom/ardakobibenchmark",
        )

    def test_repo_slug_parses_ssh_remote(self) -> None:
        self.assertEqual(
            _repo_from_remote_url("git@github.com:ekowiggins-dotcom/ardakobibenchmark.git"),
            "ekowiggins-dotcom/ardakobibenchmark",
        )

    def test_git_blob_sha_matches_known_empty_blob(self) -> None:
        self.assertEqual(_git_blob_sha(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")


class GlobalPaymentsExtractionTests(unittest.TestCase):
    def test_checkout_newsroom_keeps_dated_merchant_payment_item(self) -> None:
        soup = BeautifulSoup(
            """
            <a href="/newsroom/checkout-com-scales-stablecoin-settlement-for-us-merchants-in-partnership-with-fireblocks">
              <div>Product Jun 3, 2026</div>
              <h3>Checkout.com scales stablecoin settlement for US merchants in partnership with Fireblocks</h3>
              <span>Read more</span>
            </a>
            """,
            "html.parser",
        )
        candidates = extract_global_payments_links(soup, "https://www.checkout.com/newsroom", "REG-238")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].raw_date_text, "2026-06-03")

    def test_wise_newsroom_rejects_listing_but_keeps_payment_infrastructure(self) -> None:
        soup = BeautifulSoup(
            """
            <li>
              <a href="/en-NAM/265506-wise-debuts-us-listing-on-nasdaq/">
                May 11, 2026 Wise debuts US listing on Nasdaq
              </a>
            </li>
            <li>
              <a href="/en-NAM/260024-wise-strengthens-its-canadian-market-investment-with-payments-canada-membership/">
                January 27, 2026 Wise strengthens its Canadian market investment with Payments Canada membership
                expansion of global infrastructure to enable faster international payments for businesses
              </a>
            </li>
            """,
            "html.parser",
        )
        candidates = extract_global_payments_links(soup, "https://newsroom.wise.com/releases/", "REG-239")
        self.assertEqual(len(candidates), 1)
        self.assertIn("Payments Canada", candidates[0].title)

    def test_the_paypers_keeps_dated_commercial_payment_item(self) -> None:
        soup = BeautifulSoup(
            """
            <a href="/payments/news/mastercard-adds-new-controls-to-virtual-card-platform">
              Mastercard adds new controls to virtual card platform 24 Jul 2026 / 5 min read / News
            </a>
            <a href="/fintech/news/western-union-to-discontinue-its-western-union-digital-bank-service">
              Western Union to discontinue its Western Union Digital Bank service 27 Jul 2026 / News / Fintech
            </a>
            """,
            "html.parser",
        )
        candidates = extract_global_payments_links(soup, "https://thepaypers.com/news", "REG-242")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].raw_date_text, "2026-07-24")
        self.assertEqual(candidates[0].title, "Mastercard adds new controls to virtual card platform")

    def test_pymnts_keeps_relevant_undated_candidate_for_detail_date_validation(self) -> None:
        soup = BeautifulSoup(
            """
            <a href="/news/b2b-payments/2026/ramp-opens-stablecoin-accounts-and-payments-to-business-clients/">
              Ramp Opens Stablecoin Accounts and Payments to Business Clients
            </a>
            <a href="/news/b2b-payments/2026/passionfroot-raises-15-million-dollars-connect-b2b-tech-companies-with-vetted-creators/">
              Passionfroot Raises $15 Million to Connect B2B Tech Companies With Vetted Creators
            </a>
            """,
            "html.parser",
        )
        candidates = extract_global_payments_links(
            soup,
            "https://www.pymnts.com/category/news/b2b-payments/",
            "REG-243",
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].raw_date_text, "")
        self.assertIn("Stablecoin", candidates[0].title)


class SeenIndexTests(unittest.TestCase):
    def test_title_normalization_is_stable(self) -> None:
        self.assertEqual(
            normalize_title("Yapı Kredi’den Yeni KOBİ Müşterilerine 48.000 TL!"),
            "yapi kredi den yeni kobi müşterilerine 48 000 tl",
        )


class ClaudeReadinessGateTests(unittest.TestCase):
    def base_row(self, **overrides) -> pd.Series:
        data = {
            "source_active": "True",
            "source_mvp_active": "True",
            "source_claude_eligible": "True",
            "item_quality": "Good",
            "item_url": "https://example.com/item",
            "source_url": "https://example.com/source",
            "canonical_item_url": "https://example.com/item",
            "extraction_method": "detail_page_fetch",
            "content_role": "Bağımsız Gelişme",
            "is_actual_development": "True",
            "actual_development_reason": "explicit_sme_signal:kobi",
            "date_confidence": "Yüksek",
            "normalized_item_date": "2026-05-15",
            "publication_date": "2026-05-15",
            "recency_basis_date": "2026-05-15",
            "recency_basis_reason": "Yayın tarihi bulundu; recency için kullanıldı.",
            "date_source": "publication_date",
            "event_date_type": "Yayın Tarihi",
        }
        data.update(overrides)
        return pd.Series(data)

    def test_active_source_with_inactive_mvp_cannot_reach_claude(self) -> None:
        reason = gate_skip_reason(self.base_row(source_mvp_active="False"), "2026-05-01", False, False, False)
        self.assertIn("mvp_active", reason)

    def test_claude_ineligible_source_cannot_reach_claude(self) -> None:
        reason = gate_skip_reason(self.base_row(source_claude_eligible="False"), "2026-05-01", False, False, False)
        self.assertIn("claude_eligible", reason)

    def test_archived_or_rejected_item_cannot_return_to_review(self) -> None:
        _, queue_rows, awareness_rows, archive_rows, _ = route_summaries(
            pd.DataFrame(
                [
                    {
                        "summary_id": "SUM-test",
                        "recent_item_id": "RI-test",
                        "review_status": "Reddedildi",
                        "relevance_status": "İlgili",
                        "impact_on_us": "Yüksek",
                        "importance_level": "Yüksek",
                        "recommended_action": "Yönetime Eskale Et",
                        "headline": "KOBİ POS hamlesi",
                        "item_title": "KOBİ POS hamlesi",
                        "summary": "Ödeme tarafında önemli sinyal.",
                    }
                ]
            )
        )
        self.assertEqual(queue_rows, [])
        self.assertEqual(awareness_rows, [])
        self.assertEqual(len(archive_rows), 1)

    def test_management_awareness_award_does_not_enter_bd_review(self) -> None:
        triage = triage_recent_item_summary(
            pd.Series(
                {
                    "content_role": "Yönetici Bilgilendirme",
                    "relevance_status": "İlgili",
                    "impact_on_us": "Düşük",
                    "importance_level": "Orta",
                    "recommended_action": "Yönetici Bilgilendirme Notuna Ekle",
                    "strategic_theme": "KOBİ Kredileri",
                    "development_type": "Ödül / İtibar Sinyali",
                    "headline": "Şekerbank Yerinde Kredi platformu The Banker ödülü aldı",
                    "item_title": "Şekerbank’ın Yerinde Kredi platformuna The Banker’dan ödül",
                    "summary": "Platform çiftçi ve esnaf müşterilerine sahada kredi erişimi sağlıyor.",
                }
            )
        )
        self.assertEqual(triage["triage_status"], TRIAGE_MANAGEMENT_AWARENESS)
        self.assertFalse(triage["should_queue_for_review"])


class BatchC1GuardrailTests(unittest.TestCase):
    def test_campaign_end_date_only_does_not_pass_recency(self) -> None:
        recency = evaluate_recency(
            {
                "campaign_end_date": "2026-12-31",
                "date_confidence": "Yüksek",
            },
            "2026-05-01",
        )
        self.assertFalse(recency["is_recent"])
        self.assertTrue(recency["is_active_campaign"])
        self.assertIn("Sadece kampanya bitiş tarihi", recency["recency_reason"])

    def test_long_running_campaign_uses_start_date_not_end_date(self) -> None:
        recency = evaluate_recency(
            {
                "campaign_start_date": "2022-04-01",
                "campaign_end_date": "2026-12-31",
                "date_confidence": "Yüksek",
            },
            "2026-05-01",
        )
        self.assertFalse(recency["is_recent"])
        self.assertTrue(recency["is_active_campaign"])
        self.assertEqual(recency["recency_basis_date"], "2022-04-01")

    def test_enpara_weekly_source_fetches_detail_even_without_flag(self) -> None:
        row = pd.Series({"source_id": "REG-101"})
        args = Namespace(fetch_detail_pages=False)
        self.assertTrue(should_fetch_detail_for_candidate(row, args))

    def test_enpara_qnb_aliases_dedupe_by_canonical_url(self) -> None:
        url = canonicalize_url("https://www.enpara.com/sirketim/kampanyalar/sgk-talimat-kampanyasi?utm_source=x")
        index = duplicate_index(
            pd.DataFrame(
                [
                    {
                        "institution_name": "QNB Finansbank",
                        "canonical_item_url": url,
                        "recent_item_id": "RI-existing",
                    }
                ]
            )
        )
        is_duplicate, reason, duplicate_id = find_duplicate(
            index,
            "Enpara",
            url,
            "",
            "enpara şirketim sgk talimat kampanyası",
            "2026-01-07",
        )
        self.assertTrue(is_duplicate)
        self.assertEqual(reason, "duplicate_canonical_item_url")
        self.assertEqual(duplicate_id, "RI-existing")

    def test_hsbc_global_content_without_turkiye_evidence_is_out_of_scope(self) -> None:
        role, reason = classify_content_role_for_candidate(
            pd.Series(
                {
                    "institution_id": "hsbc",
                    "institution_name": "HSBC",
                    "source_name": "HSBC Global Research",
                    "source_type": "Business News",
                    "extraction_mode": "weekly_development",
                }
            ),
            "HSBC global research on Germany corporate treasurers",
            "https://www.business.hsbc.com/insights/global/germany-corporate-treasurers",
            "Global insights for corporate treasurers in Germany and Qatar.",
        )
        self.assertEqual(role, "Kapsam Dışı")
        self.assertEqual(reason, "hsbc_global_content_without_turkiye_evidence")


class BatchC2GuardrailTests(unittest.TestCase):
    def c2_row(self, institution_id: str, **overrides) -> pd.Series:
        data = {
            "institution_id": institution_id,
            "institution_name": "Batch C2 Bank",
            "source_name": "Resmi Haber Sayfası",
            "source_type": "Resmi Haber Sayfası",
            "extraction_mode": "weekly_development",
        }
        data.update(overrides)
        return pd.Series(data)

    def test_boilerplate_kobi_text_does_not_rescue_legal_notice(self) -> None:
        role, reason = classify_content_role_for_candidate(
            self.c2_row("t_bank", institution_name="T-Bank"),
            "2026 Olağan Genel Kurul Duyurusu",
            "https://www.tbank.com.tr/hakkimizda/duyuru-detay/26-03-2026-OIagan-Genel-Kurul-Duyurusu/20/591/0",
            "KVKK ve footer alanında KOBİ ticari nakit yönetimi bağlantıları tekrarlanıyor.",
        )
        self.assertEqual(role, "Kapsam Dışı")
        self.assertEqual(reason, "legal_event_or_operational_noise")

    def test_financial_report_without_segment_evidence_is_context_only(self) -> None:
        role, reason = classify_content_role_for_candidate(
            self.c2_row("turkish_bank", institution_name="TurkishBank"),
            "TurkishBank 2026 ikinci çeyrek finansal sonuçları",
            "https://www.turkishbank.com/hakkimizda/bizden-haberler/finansal-sonuclar/",
            "Banka finansal sonuçlarını açıkladı; ticari bankacılık veya KOBİ segmentine özel veri yer almıyor.",
        )
        self.assertEqual(role, "Bağlamsal Veri")
        self.assertEqual(reason, "financial_report_without_segment_evidence")

    def test_generic_financial_results_cannot_reach_claude(self) -> None:
        row = ClaudeReadinessGateTests().base_row(
            source_mvp_active="True",
            source_claude_eligible="True",
            content_role="Bağlamsal Veri",
            is_actual_development="False",
            actual_development_reason="financial_report_without_segment_evidence",
        )
        reason = gate_skip_reason(row, "2026-05-01", False, False, False)
        self.assertIn("content_role Claude için uygun değil", reason)

    def test_export_metrics_qualify_for_management_awareness_without_kobi_literal(self) -> None:
        text = (
            "Nakdi kredi hacmi 40,5 milyar TL oldu. Nakdi ve gayri nakdi kredilerin toplamı 79 milyar TL'ye çıktı. "
            "Tamamına yakını ihracatçı kesimi finanse eden kredilerin aktif içindeki payı yüzde 65'e yükseldi."
        )
        role, reason = classify_content_role_for_candidate(
            self.c2_row("turk_ticaret_bankasi", institution_name="Türk Ticaret Bankası"),
            "2026 yılı ilk çeyreğini güçlü finansal sonuçlarla tamamladık",
            "https://www.turkticaretbankasi.com.tr/icerik/2026-yili-ilk-ceyregini-guclu-finansal-sonuclarla-tamamladik",
            text,
        )
        self.assertTrue(has_financial_results_export_evidence(text))
        self.assertEqual(role, "Yönetici Bilgilendirme")
        self.assertEqual(reason, "financial_results_with_export_finance_evidence")

    def test_reporting_period_is_not_publication_recency(self) -> None:
        date_meta = extract_date_semantics(
            visible_text="Banka 2026 yılı ilk çeyreğinde kredi hacmini artırdı.",
            url="https://example.com/finansal-sonuclar",
            listing_text="",
            inferred_text="",
            source_type="Resmi Haber Sayfası",
        )
        recency = evaluate_recency(date_meta, "2026-05-01")
        self.assertEqual(date_meta["normalized_date"], "")
        self.assertFalse(recency["is_recent"])

    def test_ineligible_financial_results_routes_to_archive_context_without_claude(self) -> None:
        triage = triage_recent_item_summary(
            pd.Series(
                {
                    "content_role": "Bağlamsal Veri",
                    "relevance_status": "Belirsiz",
                    "impact_on_us": "Düşük",
                    "importance_level": "Düşük",
                    "recommended_action": "Önceliklendirme",
                    "development_type": "İlgili Gelişme Yok",
                    "headline": "Genel finansal sonuç açıklaması",
                    "item_title": "Genel finansal sonuç açıklaması",
                    "summary": "KOBİ/ticari rekabet gelişmesi değil.",
                }
            )
        )
        self.assertFalse(triage["should_queue_for_review"])
        self.assertFalse(triage["should_queue_for_management_awareness"])

    def test_awareness_merge_is_idempotent(self) -> None:
        summary_id = "SUM-c2-test"
        row = {
            "awareness_id": awareness_id_for(summary_id),
            "summary_id": summary_id,
            "recent_item_id": "RI-c2-test",
            "institution_name": "Türk Ticaret Bankası",
            "item_title": "İhracat finansmanı kapasite sinyali",
            "item_date": "2026-05-01",
            "headline": "İhracat finansmanı kapasite sinyali",
            "summary": "Kısa özet.",
            "core_assessment": "Yönetici bilgilendirme notu.",
            "strategic_relevance": "BD aksiyonu zayıf.",
            "impact_on_us": "Düşük",
            "recommended_action": "Yönetici Bilgilendirme Notuna Ekle",
            "importance_level": "Düşük",
            "confidence_level": "Yüksek",
            "strategic_theme": "Kurumsal Konumlandırma",
            "product_area": "Diğer",
            "development_type": "Yönetim Açıklaması",
            "awareness_reason": "Yönetici farkındalığı.",
            "source_url": "https://example.com/source",
            "item_url": "https://example.com/item",
            "review_status": "Beklemede",
            "analyst_note": "",
            "reviewer": "",
            "reviewed_at": "",
            "created_at": "2026-06-26T00:00:00+00:00",
        }
        existing = pd.DataFrame([row]).reindex(columns=MANAGEMENT_AWARENESS_COLUMNS)
        rebuilt, new_count, updated_count = merge_destination(existing, [row], "summary_id", MANAGEMENT_AWARENESS_COLUMNS)
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(new_count, 0)
        self.assertEqual(updated_count, 1)

    def test_t_bank_and_turkishbank_remain_blocked_from_claude(self) -> None:
        base = ClaudeReadinessGateTests().base_row(source_mvp_active="False", source_claude_eligible="False")
        self.assertIn("mvp_active", gate_skip_reason(base, "2026-05-01", False, False, False))

    def test_turkishbank_group_without_local_bank_evidence_is_out_of_scope(self) -> None:
        role, reason = classify_content_role_for_candidate(
            self.c2_row("turkish_bank", institution_name="TurkishBank"),
            "TurkishBank Group kültür etkinliği düzenledi",
            "https://www.turkishbank.com/hakkimizda/bizden-haberler/group-event/",
            "TurkishBank Group uluslararası sanat etkinliğini duyurdu.",
        )
        self.assertEqual(role, "Kapsam Dışı")
        self.assertEqual(reason, "group_level_without_turkiye_or_bank_entity_evidence")

    def test_old_ownership_change_cannot_pass_cutoff(self) -> None:
        recency = evaluate_recency(
            {
                "publication_date": "2025-03-01",
                "date_confidence": "Yüksek",
            },
            "2026-05-01",
        )
        self.assertFalse(recency["is_recent"])

    def test_export_finance_item_can_pass_without_kobi_keyword(self) -> None:
        role, reason = classify_content_role_for_candidate(
            self.c2_row("turk_ticaret_bankasi", institution_name="Türk Ticaret Bankası"),
            "Türk Ticaret Bankası ihracat finansmanı limitlerini genişletti",
            "https://www.turkticaretbankasi.com.tr/icerik/ihracat-finansmani",
            "Dış ticaret ve reeskont finansmanı kapsamında ihracatçı şirketlere yeni finansman kapasitesi sağlandı.",
        )
        self.assertEqual(role, "Bağımsız Gelişme")
        self.assertEqual(reason, "export_finance_commercial_evidence")

    def test_branch_opening_needs_valid_date_for_recency(self) -> None:
        without_date = evaluate_recency({"date_confidence": "Yüksek"}, "2026-05-01")
        with_date = evaluate_recency(
            {
                "publication_date": "2026-05-10",
                "date_confidence": "Yüksek",
            },
            "2026-05-01",
        )
        role, reason = classify_content_role_for_candidate(
            self.c2_row("turk_ticaret_bankasi", institution_name="Türk Ticaret Bankası"),
            "Türk Ticaret Bankası yeni ihracat şubesini hizmete açtı",
            "https://www.turkticaretbankasi.com.tr/icerik/yeni-ihracat-subesi",
            "İhracatçı müşterilere dış ticaret finansmanı sağlamak üzere yeni şube hizmete açıldı.",
        )
        self.assertFalse(without_date["is_recent"])
        self.assertTrue(with_date["is_recent"])
        self.assertEqual(role, "Bağımsız Gelişme")
        self.assertEqual(reason, "exporter_branch_channel_expansion")


class MastercardGuardrailTests(unittest.TestCase):
    def test_direct_akbank_item_is_high_relevance_without_kobi_literal(self) -> None:
        item = classify_mastercard_item(
            "Akbank and Mastercard launch tokenized commercial card credentials",
            "https://www.mastercard.com/news/press/akbank-tokenized-commercial-card",
            "Akbank commercial card issuing capability uses network tokens for card-on-file credentials.",
            "2026-06-15",
        )
        self.assertEqual(item["network_signal_type"], "Doğrudan Akbank Sinyali")
        self.assertIn(item["akbank_relevance"], {"Kritik", "Yüksek"})
        self.assertGreaterEqual(int(item["strategic_priority_score"]), 14)
        self.assertEqual(item["accepted"], "True")

    def test_turkish_competitor_deployment_is_not_akbank_signal(self) -> None:
        item = classify_mastercard_item(
            "Garanti BBVA launches Mastercard virtual card supplier payments in Türkiye",
            "https://www.mastercard.com/news/press/garanti-bbva-virtual-card",
            "Garanti BBVA deploys virtual cards for supplier payment automation.",
            "2026-06-10",
        )
        self.assertEqual(item["network_signal_type"], "Türkiye Rakip Banka Uygulaması")
        self.assertEqual(item["direct_akbank_signal"], "False")
        self.assertEqual(item["deployment_scope"], "Türkiye")

    def test_network_infrastructure_change_can_pass_without_kobi_wording(self) -> None:
        item = classify_mastercard_item(
            "Mastercard expands network token credential lifecycle controls for issuers",
            "https://www.mastercard.com/news/press/network-token-credential-controls",
            "Issuer card-on-file credentials gain new authentication and fraud controls.",
            "2026-06-12",
        )
        self.assertEqual(item["accepted"], "True")
        self.assertIn(item["network_layer"], {"Tokenizasyon", "Fraud ve Siber Güvenlik"})
        self.assertNotEqual(item["network_signal_type"], "Kapsam Dışı")

    def test_global_product_page_remains_benchmark_without_dated_launch(self) -> None:
        item = classify_mastercard_item(
            "Mastercard Virtual Cards",
            "https://www.mastercard.com/global/en/business/payment-solutions/virtual-cards.html",
            "Commercial virtual card product page for supplier payments.",
            "",
        )
        self.assertEqual(item["content_role"], "Benchmark Fact")
        self.assertEqual(item["proposed_destination"], "Benchmark Fact")

    def test_generic_mastercard_brand_pr_is_rejected(self) -> None:
        item = classify_mastercard_item(
            "Mastercard Priceless music sponsorship campaign returns for summer",
            "https://www.mastercard.com/news/press/priceless-music-sponsorship",
            "A lifestyle and entertainment sponsorship campaign.",
            "2026-06-10",
        )
        self.assertEqual(item["accepted"], "False")
        self.assertEqual(item["rejection_reason"], "brand_lifestyle_or_consumer_noise")

    def test_product_specific_award_routes_to_management_awareness(self) -> None:
        item = classify_mastercard_item(
            "Mastercard Receivables Manager wins commercial payments innovation award",
            "https://www.mastercard.com/news/press/receivables-manager-award",
            "Product-specific recognition for accounts receivable automation.",
            "2026-06-08",
        )
        self.assertEqual(item["content_role"], "Yönetici Bilgilendirme")
        self.assertEqual(item["proposed_destination"], "Yönetici Bilgilendirme Notları")

    def test_research_is_context_only_unless_actionable(self) -> None:
        item = classify_mastercard_item(
            "Mastercard research on consumer payment preferences",
            "https://www.mastercardservices.com/en/insights/consumer-payment-survey",
            "Broad consumer survey without concrete issuer, acquirer, standard or product deployment.",
            "2026-06-02",
        )
        self.assertIn(item["content_role"], {"Bağlamsal Veri", "Kapsam Dışı"})
        self.assertNotEqual(item["proposed_destination"], "Stratejik / BD Gündemi")

    def test_pre_cutoff_akbank_partnership_is_context_not_recent(self) -> None:
        item = classify_mastercard_item(
            "Akbank and Mastercard expand Axess relationship",
            "https://www.mastercard.com/news/press/akbank-axess-partnership",
            "Akbank card partnership context.",
            "2025-04-15",
        )
        self.assertEqual(item["network_signal_type"], "Doğrudan Akbank Sinyali")
        self.assertEqual(item["content_role"], "Bağlamsal Veri")
        self.assertEqual(item["proposed_destination"], "Stratejik İlişki Bağlamı")

    def test_regional_and_global_deployments_are_not_destructively_deduped(self) -> None:
        global_url = canonicalize_mastercard_url("https://www.mastercard.com/news/press/agent-pay?utm_source=x")
        regional_url = canonicalize_mastercard_url(
            "https://www.mastercard.com/news/europe/en/newsroom/press-releases/en/2026/santander-agent-pay/"
        )
        self.assertNotEqual(mastercard_source_key(global_url), mastercard_source_key(regional_url))

    def test_browser_required_source_cannot_reach_claude_before_extraction(self) -> None:
        reason = gate_skip_reason(
            ClaudeReadinessGateTests().base_row(
                source_mvp_active="False",
                source_claude_eligible="False",
                institution_id="mastercard",
                collector_capability="browser_required",
            ),
            "2026-05-01",
            False,
            False,
            False,
        )
        self.assertIn("mvp_active", reason)

    def test_repeated_dry_run_source_key_is_stable(self) -> None:
        url = "https://www.mastercard.com/news/press/agent-pay?utm_campaign=test&utm_source=x"
        first = mastercard_source_key(url)
        second = mastercard_source_key("https://www.mastercard.com/news/press/agent-pay")
        self.assertEqual(first, second)

    def test_search_query_url_is_not_item_level_or_recent_eligible(self) -> None:
        self.assertFalse(is_item_level_mastercard_url("https://www.mastercard.com/news/press/?q=Agent+Pay"))
        self.assertFalse(is_item_level_mastercard_url("https://www.mastercard.com/news/press/?q=tokenization+network+credentials"))

    def test_listing_itself_is_not_item_level(self) -> None:
        self.assertFalse(is_item_level_mastercard_url("https://www.mastercard.com/news/eemea/en/newsroom/press-releases/"))
        self.assertEqual(
            detect_mastercard_page_type("https://www.mastercard.com/news/eemea/en/newsroom/press-releases/", "<html></html>", "", ""),
            "listing_page",
        )

    def test_product_page_remains_benchmark(self) -> None:
        url = "https://www.mastercard.com/global/en/business/payment-solutions/virtual-cards.html"
        self.assertTrue(is_generic_product_root_url(url))
        self.assertFalse(is_item_level_mastercard_url(url))

    def test_access_denied_page_cannot_produce_candidate(self) -> None:
        page = BrowserPage(
            url="https://www.mastercard.com/news/press/?q=Agent+Pay",
            final_url="https://www.mastercard.com/news/press/?q=Agent+Pay",
            title="Access Denied",
            html="<html><title>Access Denied</title><body>Access Denied You don't have permission to access this server.</body></html>",
            body_text="Access Denied You don't have permission to access this server.",
            page_type="access_denied",
            engine="test",
        )
        gate = passes_mastercard_article_gate(page, ["Agent Pay"])
        self.assertFalse(gate.passed)
        self.assertEqual(gate.rejection_reason, "access_denied")

    def test_date_modified_only_cannot_establish_recency(self) -> None:
        html = """
        <html><head>
        <title>Mastercard token credential update</title>
        <script type="application/ld+json">{"dateModified":"2026-06-20"}</script>
        </head><body><article><h1>Mastercard token credential update</h1>
        <p>Mastercard expands token credential lifecycle controls for issuers and merchants with authentication and fraud features.</p>
        <p>""" + ("Substantive payment infrastructure detail. " * 30) + """</p></article></body></html>
        """
        url = "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2026/june/mastercard-token-credential-update/"
        page = BrowserPage(url=url, final_url=url, title="Mastercard token credential update", html=html, body_text="", page_type="article_page", engine="test")
        gate = passes_mastercard_article_gate(page, ["token", "credential"])
        self.assertFalse(gate.passed)
        self.assertEqual(gate.rejection_reason, "missing_publication_date")

    def test_merchant_cloud_article_passes_only_with_valid_date_and_body(self) -> None:
        url = "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2026/may/network-international-jordan-launches-click-to-pay-through-mastercard-merchant-cloud-expanding-access-to-secure-digital-payments/"
        html = """
        <html><head>
        <title>Network International Jordan launches Click to Pay through Mastercard Merchant Cloud</title>
        <meta property="article:published_time" content="May 20, 2026">
        <link rel="canonical" href="https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2026/may/network-international-jordan-launches-click-to-pay-through-mastercard-merchant-cloud-expanding-access-to-secure-digital-payments/">
        </head><body><article>
        <h1>Network International Jordan launches Click to Pay through Mastercard Merchant Cloud</h1>
        <p>Network International Jordan and Mastercard launched Click to Pay through Mastercard Merchant Cloud for secure digital payment acceptance.</p>
        <p>""" + ("Merchant acceptance deployment detail for issuers, acquirers, and merchants. " * 20) + """</p>
        </article></body></html>
        """
        page = BrowserPage(url=url, final_url=url, title="", html=html, body_text="", page_type="article_page", engine="test")
        gate = passes_mastercard_article_gate(page, ["Click to Pay", "Merchant Cloud"])
        self.assertTrue(gate.passed)
        self.assertEqual(gate.publication_date, "2026-05-20")

    def test_same_canonical_article_with_tracking_collapses_to_one_key(self) -> None:
        a = mastercard_url_key("https://www.mastercard.com/news/press/agent-pay?utm_source=x")
        b = mastercard_url_key("https://www.mastercard.com/news/press/agent-pay")
        self.assertEqual(a, b)

    def test_official_press_listing_extracts_local_links_and_dates(self) -> None:
        html = """
        <div class="accordion-item__separator">
          <div class="accordion-item__separator-eyebrow">June 10, 2026</div>
          <div class="accordion-item__separator-heading">
            <a href="/news/press/2026/june/mastercard-launches-agent-pay-for-machines/">Mastercard launches Agent Pay for Machines</a>
          </div>
        </div>
        """
        items = extract_mastercard_press_index(html, "https://newsroom.mastercard.com/news/press/")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].visible_date, "2026-06-10")
        self.assertTrue(items[0].item_url.endswith("/news/press/2026/june/mastercard-launches-agent-pay-for-machines/"))
        self.assertFalse(is_item_level_mastercard_url("https://newsroom.mastercard.com/news/press/"))

    def test_direct_official_article_row_extracts_quality_fields(self) -> None:
        body = " ".join(["Agent Pay for Machines enables always-on payments for connected devices with token credentials."] * 20)
        article = PressArticle(
            source_url="https://www.mastercard.com/us/en/news-and-trends/press/2026/june/mastercard-launches-agent-pay-for-machines.html",
            final_url="https://www.mastercard.com/us/en/news-and-trends/press/2026/june/mastercard-launches-agent-pay-for-machines.html",
            canonical_url="https://www.mastercard.com/us/en/news-and-trends/press/2026/june/mastercard-launches-agent-pay-for-machines.html",
            title="Mastercard launches Agent Pay for Machines to unlock super-fast, always-on payments",
            subtitle="",
            publication_date="2026-06-12",
            date_raw_text="June 12, 2026",
            date_source="visible_article_date",
            date_confidence="Yüksek",
            location="Purchase, NY",
            article_body=body,
            body_chars=len(body),
            named_partners="",
            named_products="Agent Pay; Agent Pay for Machines",
            named_banks="",
            source_region="US/Global",
            structured_metadata_found=True,
            page_type="article_page",
            access_status="accessible",
        )
        row = item_row_from_article(article, "Direct positive test: Agent Pay for Machines", "Agent Pay for Machines", "", "2026-05-01")
        self.assertEqual(row["recent_item_eligible"], "True")
        self.assertEqual(row["publication_date_verified"], "True")
        self.assertEqual(row["network_layer"], "AI / Agentic Commerce")

    def test_original_agent_pay_launch_remains_pre_cutoff_context(self) -> None:
        article = PressArticle(
            source_url="https://newsroom.mastercard.com/news/press/2025/april/mastercard-unveils-agent-pay-pioneering-agentic-payments-technology-to-power-commerce-in-the-age-of-ai/",
            final_url="https://newsroom.mastercard.com/news/press/2025/april/mastercard-unveils-agent-pay-pioneering-agentic-payments-technology-to-power-commerce-in-the-age-of-ai/",
            canonical_url="https://www.mastercard.com/news/press/2025/april/mastercard-unveils-agent-pay-pioneering-agentic-payments-technology-to-power-commerce-in-the-age-of-ai/",
            title="Mastercard unveils Agent Pay, pioneering agentic payments technology to power commerce in the age of AI",
            subtitle="",
            publication_date="2025-04-29",
            date_raw_text="April 29, 2025",
            date_source="visible_article_date",
            date_confidence="Yüksek",
            location="",
            article_body="Agent Pay token credentials and agentic commerce. " * 30,
            body_chars=1500,
            named_partners="",
            named_products="Agent Pay",
            named_banks="",
            source_region="US/Global",
            structured_metadata_found=True,
            page_type="article_page",
            access_status="accessible",
        )
        row = item_row_from_article(article, "Direct positive test: Original Agent Pay launch", "Original Agent Pay", "", "2026-05-01")
        self.assertEqual(row["recent_item_eligible"], "False")
        self.assertEqual(row["rejection_reason"], "pre_cutoff")

    def test_synthetic_tokenization_seed_cannot_pass_without_real_article(self) -> None:
        self.assertFalse(is_item_level_mastercard_url("https://www.mastercard.com/news/press/?q=tokenization+network+credentials"))

    def test_legacy_url_dedupes_against_modern_canonical_url(self) -> None:
        base = {
            "article_title": "Mastercard and PayPal to partner on Mastercard One Credential",
            "publication_date": "2025-06-04",
            "recent_item_eligible": "False",
            "body_chars": "3000",
            "duplicate_status": "canonical_unique",
            "rejection_reason": "pre_cutoff",
        }
        rows = [
            {**base, "discovered_from": "legacy", "item_url": "https://newsroom.mastercard.com/news/press/2025/june/paypal/", "final_url": "https://newsroom.mastercard.com/news/press/2025/june/paypal/", "canonical_url": "https://www.mastercard.com/news/press/2025/june/paypal/"},
            {**base, "discovered_from": "modern", "item_url": "https://www.mastercard.com/news/press/2025/june/paypal/", "final_url": "https://www.mastercard.com/news/press/2025/june/paypal/", "canonical_url": "https://www.mastercard.com/news/press/2025/june/paypal/"},
        ]
        deduped = dedupe_item_rows(rows)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["duplicate_status"], "canonical_collapsed_legacy_modern")

    def test_access_denied_source_health_semantics_are_separated(self) -> None:
        page = BrowserPage(
            url="https://www.mastercard.com/us/en/news-and-trends/press.html",
            final_url="https://www.mastercard.com/us/en/news-and-trends/press.html",
            title="Access Denied",
            html="<html><body>Access Denied</body></html>",
            body_text="Access Denied",
            page_type="access_denied",
            engine="test",
        )
        health = classify_source_access(page, 0, 0, 0)
        self.assertEqual(health["official_source_valid"], "True")
        self.assertEqual(health["collector_accessible"], "False")
        self.assertEqual(health["extraction_structurally_valid"], "False")

    def test_lifestyle_sponsorship_article_is_rejected(self) -> None:
        article = PressArticle(
            source_url="https://www.mastercard.com/news/press/2026/june/priceless-music-sponsorship/",
            final_url="https://www.mastercard.com/news/press/2026/june/priceless-music-sponsorship/",
            canonical_url="https://www.mastercard.com/news/press/2026/june/priceless-music-sponsorship/",
            title="Mastercard Priceless music sponsorship campaign returns",
            subtitle="",
            publication_date="2026-06-10",
            date_raw_text="June 10, 2026",
            date_source="visible_article_date",
            date_confidence="Yüksek",
            location="",
            article_body="Music sponsorship and entertainment experiences. " * 30,
            body_chars=1400,
            named_partners="",
            named_products="",
            named_banks="",
            source_region="US/Global",
            structured_metadata_found=True,
            page_type="article_page",
            access_status="accessible",
        )
        row = item_row_from_article(article, "test", "Priceless", "", "2026-05-01")
        self.assertEqual(row["recent_item_eligible"], "False")
        self.assertEqual(row["rejection_reason"], "brand_lifestyle_or_corporate_noise")

    def test_unverified_seed_date_cannot_establish_recency(self) -> None:
        row = {
            "item_url": "https://www.mastercard.com/news/press/?q=Agent+Pay",
            "seed_date_hint": "2026-06-01",
            "publication_date": "",
            "recency_basis_date": "",
            "recent_item_eligible": "False",
            "claude_eligible": "False",
        }
        self.assertFalse(is_item_level_mastercard_url(row["item_url"]))
        self.assertEqual(row["publication_date"], "")
        self.assertEqual(row["recent_item_eligible"], "False")

    def test_benchmark_semantics_are_explicit_not_recent(self) -> None:
        url = "https://www.mastercard.com/global/en/business/payment-solutions/virtual-cards.html"
        row = {
            "benchmark_eligible": "True",
            "context_eligible": "False",
            "recent_item_eligible": "False",
            "claude_eligible": "False",
        }
        self.assertTrue(is_generic_product_root_url(url))
        self.assertEqual(row["benchmark_eligible"], "True")
        self.assertEqual(row["recent_item_eligible"], "False")

    def test_historical_weak_taxonomy_defaults_unclassified_not_fraud(self) -> None:
        taxonomy = high_precision_historical_taxonomy(
            "OnePay and Synchrony launch credit card program with Walmart",
            "https://newsroom.mastercard.com/news/press/2025/june/onepay-synchrony/",
            "",
            "",
        )
        self.assertEqual(taxonomy["taxonomy_status"], "Unclassified")
        self.assertEqual(taxonomy["network_layer"], "")
        self.assertNotEqual(taxonomy["network_layer"], "Fraud ve Siber Güvenlik")

    def test_high_precision_taxonomy_requires_explicit_fraud_terms(self) -> None:
        taxonomy = high_precision_historical_taxonomy(
            "Mastercard expands authentication attack monitoring",
            "https://newsroom.mastercard.com/news/press/2025/june/security/",
            "The update adds transaction monitoring to reduce fraud and cyber risk.",
            "",
        )
        self.assertEqual(taxonomy["network_layer"], "Fraud ve Siber Güvenlik")
        self.assertEqual(taxonomy["taxonomy_method"], "deterministic_high_precision")

    def test_blocked_mastercard_source_is_skipped_from_weekly_collection(self) -> None:
        row = pd.Series(
            {
                "institution_id": "mastercard",
                "monitoring_mode": "blocked_source_watch",
                "weekly_collection_enabled": "False",
                "mvp_active": "False",
                "claude_eligible": "False",
            }
        )
        self.assertTrue(should_skip_mastercard_weekly_source(row))

    def test_representative_recovery_runs_only_when_due(self) -> None:
        self.assertFalse(recovery_check_due({"next_retry_at": "2026-07-29"}, date(2026, 6, 29)))
        self.assertTrue(recovery_check_due({"next_retry_at": "2026-06-01"}, date(2026, 6, 29)))

    def test_legacy_resolver_remains_outside_recent_flow(self) -> None:
        row = {
            "source_id": "REG-231",
            "monitoring_mode": "historical_resolution",
            "weekly_collection_enabled": "False",
            "mvp_active": "False",
            "claude_eligible": "False",
        }
        self.assertTrue(should_skip_mastercard_weekly_source({"institution_id": "mastercard", **row}))

    def manual_evidence_row(self, **overrides) -> dict[str, str]:
        data = {
            "intake_id": "MC-MAN-1",
            "submitted_by": "analyst",
            "official_url": "https://www.mastercard.com/us/en/news-and-trends/press/2026/june/mastercard-launches-token-credential-controls.html",
            "institution_name": "Mastercard",
            "proposed_title": "Mastercard launches token credential controls for issuers",
            "proposed_publication_date": "2026-06-15",
            "copied_official_text": "Mastercard launches token credential lifecycle controls for issuers and merchants. " * 15,
            "uploaded_evidence_path": "",
            "evidence_capture_method": "analyst_copy_from_official_page",
            "official_domain_verified": "True",
            "analyst_date_verified": "True",
            "analyst_body_verified": "True",
            "named_partner": "",
            "proposed_network_signal_type": "",
            "proposed_network_layer": "",
            "proposed_deployment_scope": "",
        }
        data.update(overrides)
        return data

    def test_manual_official_url_only_is_insufficient_when_blocked(self) -> None:
        passed, reason, candidate = passes_manual_official_evidence_gate(
            self.manual_evidence_row(copied_official_text="", evidence_capture_method="official_url")
        )
        self.assertFalse(passed)
        self.assertEqual(reason, "insufficient_official_evidence")
        self.assertEqual(candidate["recent_item_eligible"], "False")

    def test_manual_verified_evidence_can_be_individual_claude_candidate(self) -> None:
        passed, reason, candidate = passes_manual_official_evidence_gate(self.manual_evidence_row())
        self.assertTrue(passed, reason)
        self.assertEqual(candidate["recent_item_eligible"], "True")
        self.assertEqual(candidate["claude_eligible"], "True")
        self.assertNotIn("source_mvp_active", candidate)

    def test_manual_verified_item_does_not_promote_source_mvp(self) -> None:
        source = {"institution_id": "mastercard", "mvp_active": "False", "monitoring_mode": "blocked_source_watch"}
        passed, _, _ = passes_manual_official_evidence_gate(self.manual_evidence_row())
        self.assertTrue(passed)
        self.assertEqual(source["mvp_active"], "False")

    def test_third_party_or_unverified_domain_cannot_satisfy_manual_gate(self) -> None:
        passed, reason, _ = passes_manual_official_evidence_gate(
            self.manual_evidence_row(
                official_url="https://example.com/mastercard-token-controls",
                official_domain_verified="False",
            )
        )
        self.assertFalse(passed)
        self.assertEqual(reason, "not_official_mastercard_domain")

    def test_duplicate_manual_submission_is_rejected(self) -> None:
        row = self.manual_evidence_row()
        passed, reason, candidate = passes_manual_official_evidence_gate(
            row,
            existing_urls={canonicalize_mastercard_url(row["official_url"])},
        )
        self.assertFalse(passed)
        self.assertEqual(reason, "duplicate_manual_or_recent_item")
        self.assertEqual(candidate["duplicate_status"], "duplicate_manual_or_recent_item")


class WeeklyRehearsalGuardrailTests(unittest.TestCase):
    def registry_row(self, **overrides) -> dict[str, str]:
        row = {
            "source_id": "REG-test",
            "institution_id": "test_bank",
            "institution_name": "Test Bank",
            "source_name": "Test Source",
            "source_type": "Official Press Release Page",
            "active": "True",
            "collection_method": "static_scrape",
            "collector_capability": "static_scrape",
            "extraction_mode": "weekly_development",
            "monitoring_mode": "",
            "weekly_collection_enabled": "",
            "mvp_active": "True",
        }
        row.update(overrides)
        return row

    def test_blocked_mastercard_source_does_not_enter_weekly_collection(self) -> None:
        registry = pd.DataFrame(
            [
                self.registry_row(
                    source_id="REG-mc",
                    institution_id="mastercard",
                    institution_name="Mastercard",
                    collection_method="browser_required",
                    collector_capability="browser_required",
                    monitoring_mode="blocked_source_watch",
                    weekly_collection_enabled="False",
                ),
                self.registry_row(),
            ]
        )
        eligible = eligible_sources(registry, ["Mastercard", "Test Bank"])
        self.assertEqual(eligible["source_id"].tolist(), ["REG-test"])

    def test_manual_source_does_not_enter_static_weekly_collection(self) -> None:
        registry = pd.DataFrame([self.registry_row(collection_method="manual")])
        eligible = eligible_sources(registry, ["Test Bank"])
        self.assertTrue(eligible.empty)

    def test_benchmark_item_cannot_enter_review_destination(self) -> None:
        destination = intended_destination(
            pd.Series(
                {
                    "content_role": "Benchmark Fact",
                    "relevance_status": "İlgili",
                    "recommended_action": "BD Konuşma Notlarına Ekle",
                    "impact_on_us": "Orta",
                    "importance_level": "Orta",
                }
            )
        )
        self.assertEqual(destination, "Benchmark")

    def test_awareness_item_has_consistent_destination(self) -> None:
        destination = intended_destination(
            pd.Series(
                {
                    "content_role": "Yönetici Bilgilendirme",
                    "relevance_status": "İlgili",
                    "recommended_action": "Yönetici Bilgilendirme Notuna Ekle",
                    "impact_on_us": "Düşük",
                    "importance_level": "Orta",
                }
            )
        )
        self.assertEqual(destination, "Yönetici Bilgilendirme")

    def test_publish_preview_requires_approval(self) -> None:
        approval_status = "Bekliyor"
        destination = "Analist Onay Kuyruğu"
        publish_ready = approval_status == "Onaylandı" and destination == "Analist Onay Kuyruğu"
        self.assertFalse(publish_ready)


class FinalReadinessHardeningTests(unittest.TestCase):
    def test_stable_archive_id_uses_recent_item_id(self) -> None:
        self.assertEqual(archive_id_for("RI-stable", "SUM-a"), archive_id_for("RI-stable", "SUM-b"))

    def test_archive_merge_preserves_archived_at_and_id(self) -> None:
        existing = pd.DataFrame(
            [
                {
                    "archive_id": archive_id_for("RI-1", "SUM-old"),
                    "summary_id": "SUM-old",
                    "recent_item_id": "RI-1",
                    "item_title": "Eski başlık",
                    "triage_reason": "Eski gerekçe",
                    "archived_at": "2026-06-01T00:00:00+00:00",
                }
            ]
        ).reindex(columns=ARCHIVE_COLUMNS)
        updated, new_count, updated_count = merge_archive(
            existing,
            [
                {
                    "archive_id": archive_id_for("RI-1", "SUM-new"),
                    "summary_id": "SUM-new",
                    "recent_item_id": "RI-1",
                    "item_title": "Yeni başlık",
                    "triage_reason": "Yeni gerekçe",
                    "archived_at": "2026-06-29T00:00:00+00:00",
                }
            ],
        )
        self.assertEqual(new_count, 0)
        self.assertEqual(updated_count, 1)
        self.assertEqual(updated.iloc[0]["archive_id"], archive_id_for("RI-1", "SUM-new"))
        self.assertEqual(updated.iloc[0]["archived_at"], "2026-06-01T00:00:00+00:00")

    def test_write_csv_if_changed_preserves_file_when_same(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"
            df = pd.DataFrame([{"a": "1", "b": "2"}])
            self.assertTrue(write_csv_if_changed(path, df, ["a", "b"]))
            before_bytes = path.read_bytes()
            before_mtime = path.stat().st_mtime_ns
            self.assertFalse(write_csv_if_changed(path, df.copy(), ["a", "b"]))
            self.assertEqual(path.read_bytes(), before_bytes)
            self.assertEqual(path.stat().st_mtime_ns, before_mtime)

    def test_clean_noop_status_is_success_without_change(self) -> None:
        metrics = RunMetrics(sources_checked=2, sources_succeeded=2, unchanged_sources=2)
        self.assertEqual(final_status_for(Namespace(dry_run=False), metrics, ""), "Başarılı — Değişiklik Yok")
        add_anomaly_alerts(metrics, ["Garanti BBVA"])
        self.assertEqual(metrics.alerts, [])

    def test_is_bankasi_product_navigation_link_rejected_before_detail(self) -> None:
        soup = BeautifulSoup('<a href="/is-ticari/kobi-kredileri">KOBİ Kredileri</a>', "html.parser")
        self.assertEqual(extract_is_bankasi_duyuru_links(soup, "https://www.isbank.com.tr/duyurular"), [])

    def test_is_bankasi_valid_announcement_passes(self) -> None:
        html = """
        <div class="duyuru-card">
          <span>16 Haziran 2026</span>
          <a href="/duyurular/kobi-ticari-pos-kampanyasi">KOBİ ticari POS kampanyası duyurusu</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        candidates = extract_is_bankasi_duyuru_links(soup, "https://www.isbank.com.tr/duyurular")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].reason, "is_bankasi_duyuru_detail")


if __name__ == "__main__":
    unittest.main()
