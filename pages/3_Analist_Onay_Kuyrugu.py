from __future__ import annotations

import pandas as pd
import streamlit as st

from pipeline.publish_approved_clusters_to_weekly_developments import publish_approved_clusters
from pipeline.publish_management_awareness_to_weekly_developments import publish_approved_management_awareness
from pipeline.publish_recent_items_to_weekly_developments import publish_approved_recent_items
from utils.recent_mvp import (
    ARCHIVE_COLUMNS,
    CLUSTER_QUEUE_COLUMNS,
    MANAGEMENT_AWARENESS_COLUMNS,
    QUEUE_COLUMNS,
    SUMMARY_COLUMNS,
    archive_id_for,
    clean_text,
    link_markdown,
    parse_json_list,
    read_csv_safe,
    utc_now,
    write_csv_safe,
)
from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(page_title="Analist Onay Kuyruğu", layout="wide")
apply_akbank_theme()

render_page_header(
    "Analist Onay Kuyruğu",
    "Tekil gelişmeler ve yöneticiye uygun patern/küme gelişmeleri için analist kararı.",
)

publish_message = st.session_state.pop("approval_publish_message", "")
if publish_message:
    st.success(publish_message)

queue = read_csv_safe("recent_item_review_queue.csv", QUEUE_COLUMNS)
summaries = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
archive = read_csv_safe("recent_item_archive.csv", ARCHIVE_COLUMNS)
cluster_queue = read_csv_safe("development_cluster_review_queue.csv", CLUSTER_QUEUE_COLUMNS)
awareness_queue = read_csv_safe("management_awareness_queue.csv", MANAGEMENT_AWARENESS_COLUMNS)

CLOSED_REVIEW_STATUSES = {"Onaylandı", "Reddedildi", "Arşivlendi", "Düşük Öncelik / Arşiv"}
OPEN_REVIEW_STATUSES = {"", "Beklemede", "Ek Araştırma Gerekli"}


def open_review_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty or "review_status" not in df.columns:
        return pd.Series([], dtype=bool)
    statuses = df["review_status"].fillna("").astype(str).str.strip()
    return statuses.isin(OPEN_REVIEW_STATUSES) | ~statuses.isin(CLOSED_REVIEW_STATUSES)


def queue_scope(df: pd.DataFrame, show_closed: bool) -> pd.DataFrame:
    if show_closed or df.empty:
        return df.copy()
    return df[open_review_mask(df)].copy()


def hidden_closed_count(df: pd.DataFrame, scoped: pd.DataFrame, show_closed: bool) -> int:
    if show_closed or df.empty:
        return 0
    return max(0, len(df) - len(scoped))


show_closed_reviews = st.toggle(
    "Kararı verilmiş kayıtları göster",
    value=False,
    help="Kapalıyken Onaylandı, Reddedildi ve Arşivlendi durumları gizlenir; kuyruk sadece açık işleri gösterir.",
)

single_tab, cluster_tab, awareness_tab = st.tabs(["Stratejik / BD Gelişmeleri", "Patern / Küme Gelişmeler", "Yönetici Notları"])


def publish_after_approval(publish_fn, label: str) -> None:
    try:
        published_count = publish_fn()
    except Exception as exc:
        st.session_state["approval_publish_message"] = (
            f"Onay kaydedildi fakat {label} yönetici radarına otomatik eklenemedi: {exc}"
        )
        return
    if published_count:
        st.session_state["approval_publish_message"] = (
            f"Onay kaydedildi; {published_count} yeni {label} Yönetici Özeti'ne eklendi."
        )
    else:
        st.session_state["approval_publish_message"] = (
            f"Onay kaydedildi; bu {label} zaten Yönetici Özeti'nde veya yayınlanacak yeni kayıt yok."
        )


def update_review(row: pd.Series, status: str, reviewer: str, note: str) -> None:
    queue_disk = read_csv_safe("recent_item_review_queue.csv", QUEUE_COLUMNS)
    summaries_disk = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
    mask = queue_disk["review_id"].astype(str).eq(str(row["review_id"]))
    now = utc_now()
    queue_disk.loc[mask, "review_status"] = status
    queue_disk.loc[mask, "reviewer"] = reviewer
    queue_disk.loc[mask, "review_notes"] = note
    queue_disk.loc[mask, "analyst_note"] = note
    queue_disk.loc[mask, "reviewed_at"] = now
    queue_disk.loc[mask, "approved_at"] = now if status == "Onaylandı" else ""
    if not summaries_disk.empty and "review_status" in summaries_disk.columns:
        summaries_disk.loc[summaries_disk["summary_id"].astype(str).eq(str(row["summary_id"])), "review_status"] = status
    write_csv_safe(queue_disk, "recent_item_review_queue.csv", QUEUE_COLUMNS)
    write_csv_safe(summaries_disk, "recent_item_summaries.csv", SUMMARY_COLUMNS)
    if status == "Onaylandı":
        publish_after_approval(publish_approved_recent_items, "tekil gelişme")
    st.success(f"{row['review_id']} için karar kaydedildi: {status}")
    st.rerun()


def archive_from_queue(row: pd.Series, reviewer: str, note: str) -> None:
    queue_disk = read_csv_safe("recent_item_review_queue.csv", QUEUE_COLUMNS)
    archive_disk = read_csv_safe("recent_item_archive.csv", ARCHIVE_COLUMNS)
    summaries_disk = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
    archive_id = archive_id_for(str(row.get("recent_item_id", "")), str(row.get("summary_id", "")))
    if not archive_disk["archive_id"].astype(str).eq(archive_id).any():
        archive_disk = pd.concat(
            [
                archive_disk,
                pd.DataFrame(
                    [
                        {
                            "archive_id": archive_id,
                            "summary_id": row.get("summary_id", ""),
                            "recent_item_id": row.get("recent_item_id", ""),
                            "document_id": row.get("document_id", ""),
                            "source_id": row.get("source_id", ""),
                            "institution_name": row.get("institution_name", ""),
                            "item_title": row.get("item_title", ""),
                            "item_date": row.get("item_date", ""),
                            "headline": row.get("headline", ""),
                            "summary": row.get("summary", ""),
                            "core_assessment": row.get("core_assessment", ""),
                            "strategic_relevance": row.get("strategic_relevance", ""),
                            "impact_on_us": row.get("impact_on_us", ""),
                            "recommended_action": row.get("recommended_action", ""),
                            "importance_level": row.get("importance_level", ""),
                            "confidence_level": row.get("confidence_level", ""),
                            "triage_status": "Düşük Öncelik / Arşiv",
                            "triage_reason": note or "Analist kararıyla düşük öncelik / arşiv.",
                            "archived_at": utc_now(),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    queue_disk = queue_disk[~queue_disk["review_id"].astype(str).eq(str(row["review_id"]))].copy()
    if not summaries_disk.empty and "review_status" in summaries_disk.columns:
        summaries_disk.loc[summaries_disk["summary_id"].astype(str).eq(str(row["summary_id"])), "review_status"] = "Düşük Öncelik / Arşiv"
    write_csv_safe(queue_disk, "recent_item_review_queue.csv", QUEUE_COLUMNS)
    write_csv_safe(archive_disk, "recent_item_archive.csv", ARCHIVE_COLUMNS)
    write_csv_safe(summaries_disk, "recent_item_summaries.csv", SUMMARY_COLUMNS)
    st.success(f"{row['review_id']} arşive taşındı.")
    st.rerun()


def update_cluster_review(row: pd.Series, status: str, reviewer: str, note: str) -> None:
    queue_disk = read_csv_safe("development_cluster_review_queue.csv", CLUSTER_QUEUE_COLUMNS)
    mask = queue_disk["cluster_id"].astype(str).eq(str(row["cluster_id"]))
    queue_disk.loc[mask, "review_status"] = status
    queue_disk.loc[mask, "reviewer"] = reviewer
    queue_disk.loc[mask, "analyst_note"] = note
    queue_disk.loc[mask, "reviewed_at"] = utc_now()
    write_csv_safe(queue_disk, "development_cluster_review_queue.csv", CLUSTER_QUEUE_COLUMNS)
    if status == "Onaylandı":
        publish_after_approval(publish_approved_clusters, "patern/küme gelişmesi")
    st.success(f"{row['cluster_id']} için karar kaydedildi: {status}")
    st.rerun()


def update_awareness_review(row: pd.Series, status: str, reviewer: str, note: str) -> None:
    awareness_disk = read_csv_safe("management_awareness_queue.csv", MANAGEMENT_AWARENESS_COLUMNS)
    summaries_disk = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
    mask = awareness_disk["awareness_id"].astype(str).eq(str(row["awareness_id"]))
    now = utc_now()
    awareness_disk.loc[mask, "review_status"] = status
    awareness_disk.loc[mask, "reviewer"] = reviewer
    awareness_disk.loc[mask, "analyst_note"] = note
    awareness_disk.loc[mask, "reviewed_at"] = now
    if not summaries_disk.empty and "review_status" in summaries_disk.columns:
        summaries_disk.loc[summaries_disk["summary_id"].astype(str).eq(str(row["summary_id"])), "review_status"] = status
    write_csv_safe(awareness_disk, "management_awareness_queue.csv", MANAGEMENT_AWARENESS_COLUMNS)
    write_csv_safe(summaries_disk, "recent_item_summaries.csv", SUMMARY_COLUMNS)
    if status == "Onaylandı":
        publish_after_approval(publish_approved_management_awareness, "yönetici notu")
    st.success(f"{row['awareness_id']} için karar kaydedildi: {status}")
    st.rerun()


def dedupe_for_display(df: pd.DataFrame, subset: list[str]) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df.copy(), 0
    available = [column for column in subset if column in df.columns]
    if not available:
        return df.copy(), 0
    before = len(df)
    out = df.drop_duplicates(subset=available, keep="first").copy()
    return out, before - len(out)


with single_tab:
    scoped_queue = queue_scope(queue, show_closed_reviews)
    hidden_closed = hidden_closed_count(queue, scoped_queue, show_closed_reviews)
    if scoped_queue.empty:
        if queue.empty:
            st.info("Henüz tekil gelişme inceleme kuyruğu yok.")
        else:
            st.success(f"Açık tekil gelişme kalmadı. {hidden_closed} kararı verilmiş kayıt gizlendi.")
    else:
        view = scoped_queue.copy()
        if not summaries.empty:
            extra_cols = [
                "summary_id",
                "product_area",
                "development_type",
                "importance_level",
                "extracted_facts_json",
                "open_questions_json",
                "created_at",
                "error_message",
                "language_lint_score",
                "language_lint_warnings",
                "needs_language_review",
            ]
            available = [column for column in extra_cols if column in summaries.columns]
            summary_lookup = summaries[available].drop_duplicates("summary_id", keep="last") if "summary_id" in available else summaries[available]
            view = view.merge(summary_lookup, on="summary_id", how="left")
        view, hidden_duplicates = dedupe_for_display(view, ["summary_id", "recent_item_id"])
        view["sort_date"] = pd.to_datetime(view["item_date"], errors="coerce", dayfirst=True, utc=True).dt.tz_localize(None)
        view["sort_date"] = view["sort_date"].fillna(pd.Timestamp.utcnow().tz_localize(None))

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Görünen kart", len(view))
        k2.metric("Açık kayıt", int(open_review_mask(queue).sum()) if not queue.empty else 0)
        k3.metric("Gizlenen karar", hidden_closed)
        k4.metric("Ek araştırma", queue["review_status"].eq("Ek Araştırma Gerekli").sum())
        k5.metric("Gizlenen tekrar", hidden_duplicates)
        st.caption(f"Unique summary_id: {view['summary_id'].astype(str).nunique() if 'summary_id' in view.columns else 0}")

        for _, row in view.sort_values(["review_status", "sort_date"], ascending=[True, False]).iterrows():
            with st.container(border=True):
                st.caption(f"{clean_text(row.get('institution_name'))} · {clean_text(row.get('strategic_theme'))} · {clean_text(row.get('item_date'))}")
                st.markdown(f"### {clean_text(row.get('headline'))}")
                warnings = parse_json_list(row.get("language_lint_warnings", ""))
                if warnings:
                    st.warning("Dil kontrolü: " + " | ".join(warnings))
                if clean_text(row.get("core_assessment"), ""):
                    st.write(f"**Kısa yorum:** {clean_text(row.get('core_assessment'))}")
                st.write(f"**Özet:** {clean_text(row.get('summary'))}")
                st.write(f"**Neden önemli?** {clean_text(row.get('strategic_relevance'))}")
                st.write(f"**Ne yapalım?** {clean_text(row.get('recommended_action'))}")
                st.write(f"**Etki:** {clean_text(row.get('impact_on_us'))}")
                facts = parse_json_list(row.get("extracted_facts_json", ""))
                if facts:
                    st.write("**Kaynakta net geçenler**")
                    for fact in facts:
                        st.write(f"- {fact}")
                links = " · ".join(
                    item
                    for item in [
                        link_markdown("Gelişmeyi aç", row.get("item_url", "")),
                        link_markdown("Kaynak", row.get("source_url", "")),
                    ]
                    if item
                )
                if links:
                    st.markdown(links)
                with st.form(f"review_form_{row['review_id']}"):
                    reviewer = st.text_input("Analist", value=clean_text(row.get("reviewer"), ""))
                    existing_note = clean_text(row.get("analyst_note"), "") or clean_text(row.get("review_notes"), "")
                    note = st.text_area("Analist notu", value=existing_note, height=90)
                    b1, b2, b3, b4 = st.columns(4)
                    approve = b1.form_submit_button("Onayla")
                    reject = b2.form_submit_button("Reddet")
                    research = b3.form_submit_button("Ek Araştırma Gerekli")
                    archive_action = b4.form_submit_button("Düşük Öncelik / Arşiv")
                    if approve:
                        update_review(row, "Onaylandı", reviewer, note)
                    if reject:
                        update_review(row, "Reddedildi", reviewer, note)
                    if research:
                        update_review(row, "Ek Araştırma Gerekli", reviewer, note)
                    if archive_action:
                        archive_from_queue(row, reviewer, note)

with cluster_tab:
    scoped_cluster_queue = queue_scope(cluster_queue, show_closed_reviews)
    cluster_hidden_closed = hidden_closed_count(cluster_queue, scoped_cluster_queue, show_closed_reviews)
    if scoped_cluster_queue.empty:
        if cluster_queue.empty:
            st.info("Henüz patern/küme inceleme kuyruğu yok. `cluster_recent_developments.py`, `summarize_development_clusters.py` ve `update_cluster_review_queue.py` çalışınca burada görünür.")
        else:
            st.success(f"Açık patern/küme gelişmesi kalmadı. {cluster_hidden_closed} kararı verilmiş kayıt gizlendi.")
    else:
        cluster_view, cluster_hidden_duplicates = dedupe_for_display(scoped_cluster_queue, ["cluster_id"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Görünen küme", len(cluster_view))
        c2.metric("Açık kayıt", int(open_review_mask(cluster_queue).sum()) if not cluster_queue.empty else 0)
        c3.metric("Gizlenen karar", cluster_hidden_closed)
        c4.metric("Gizlenen tekrar", cluster_hidden_duplicates)

        for _, row in cluster_view.sort_values(["review_status", "created_at"], ascending=[True, False]).iterrows():
            with st.container(border=True):
                st.caption(f"{clean_text(row.get('institution_name'))} · {clean_text(row.get('item_count'))} gelişme · {clean_text(row.get('review_status'))}")
                st.markdown(f"### {clean_text(row.get('cluster_title'))}")
                warnings = parse_json_list(row.get("language_lint_warnings", ""))
                if warnings:
                    st.warning("Dil kontrolü: " + " | ".join(warnings))
                st.write(f"**Kısa yorum:** {clean_text(row.get('cluster_core_assessment'))}")
                st.write(f"**Özet:** {clean_text(row.get('cluster_summary'))}")
                st.write(f"**Neden önemli:** {clean_text(row.get('why_it_matters'))}")
                st.write(f"**Rakip niyeti:** {clean_text(row.get('competitor_intent'))}")
                st.write(f"**Yönetici mesajı:** {clean_text(row.get('management_takeaway'))}")
                st.write(f"**Aksiyon / Etki / Önem:** {clean_text(row.get('recommended_action'))} / {clean_text(row.get('impact_on_us'))} / {clean_text(row.get('importance_level'))}")

                titles = parse_json_list(row.get("item_titles", ""))
                if titles:
                    st.write("**Dahil edilen gelişmeler**")
                    for title in titles:
                        st.write(f"- {title}")
                urls = parse_json_list(row.get("source_urls", ""))
                if urls:
                    st.write("**Kaynak bağlantıları**")
                    for idx, url in enumerate(urls, start=1):
                        link = link_markdown(f"Kaynak {idx}", url)
                        if link:
                            st.markdown(link)

                with st.form(f"cluster_review_form_{row['cluster_id']}"):
                    reviewer = st.text_input("Analist", value=clean_text(row.get("reviewer"), ""), key=f"reviewer_{row['cluster_id']}")
                    note = st.text_area("Analist notu", value=clean_text(row.get("analyst_note"), ""), height=90, key=f"note_{row['cluster_id']}")
                    b1, b2, b3 = st.columns(3)
                    approve = b1.form_submit_button("Onayla")
                    reject = b2.form_submit_button("Reddet")
                    research = b3.form_submit_button("Ek Araştırma Gerekli")
                    if approve:
                        update_cluster_review(row, "Onaylandı", reviewer, note)
                    if reject:
                        update_cluster_review(row, "Reddedildi", reviewer, note)
                    if research:
                        update_cluster_review(row, "Ek Araştırma Gerekli", reviewer, note)

with awareness_tab:
    scoped_awareness_queue = queue_scope(awareness_queue, show_closed_reviews)
    awareness_hidden_closed = hidden_closed_count(awareness_queue, scoped_awareness_queue, show_closed_reviews)
    if scoped_awareness_queue.empty:
        if awareness_queue.empty:
            st.info("Henüz yönetici notu kuyruğu yok.")
        else:
            st.success(f"Açık yönetici notu kalmadı. {awareness_hidden_closed} kararı verilmiş kayıt gizlendi.")
    else:
        awareness_view, awareness_hidden_duplicates = dedupe_for_display(scoped_awareness_queue, ["summary_id", "recent_item_id"])
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Görünen kart", len(awareness_view))
        a2.metric("Açık kayıt", int(open_review_mask(awareness_queue).sum()) if not awareness_queue.empty else 0)
        a3.metric("Gizlenen karar", awareness_hidden_closed)
        a4.metric("Gizlenen tekrar", awareness_hidden_duplicates)

        for _, row in awareness_view.sort_values(["review_status", "created_at"], ascending=[True, False]).iterrows():
            with st.container(border=True):
                st.caption(f"{clean_text(row.get('institution_name'))} · {clean_text(row.get('strategic_theme'))} · {clean_text(row.get('review_status'))}")
                st.markdown(f"### {clean_text(row.get('headline'))}")
                if clean_text(row.get("core_assessment"), ""):
                    st.write(f"**Kısa yorum:** {clean_text(row.get('core_assessment'))}")
                st.write(f"**Özet:** {clean_text(row.get('summary'))}")
                st.write(f"**Neden önemli?** {clean_text(row.get('strategic_relevance'))}")
                st.write(f"**Bilgilendirme nedeni:** {clean_text(row.get('awareness_reason'))}")
                st.write(f"**Aksiyon / Etki / Önem:** {clean_text(row.get('recommended_action'))} / {clean_text(row.get('impact_on_us'))} / {clean_text(row.get('importance_level'))}")
                links = " · ".join(
                    item
                    for item in [
                        link_markdown("Gelişmeyi aç", row.get("item_url", "")),
                        link_markdown("Kaynak", row.get("source_url", "")),
                    ]
                    if item
                )
                if links:
                    st.markdown(links)

                with st.form(f"awareness_review_form_{row['awareness_id']}"):
                    reviewer = st.text_input("Analist", value=clean_text(row.get("reviewer"), ""), key=f"awareness_reviewer_{row['awareness_id']}")
                    note = st.text_area("Analist notu", value=clean_text(row.get("analyst_note"), ""), height=90, key=f"awareness_note_{row['awareness_id']}")
                    b1, b2, b3, b4 = st.columns(4)
                    approve = b1.form_submit_button("Onayla")
                    reject = b2.form_submit_button("Reddet")
                    research = b3.form_submit_button("Ek Araştırma Gerekli")
                    archive_action = b4.form_submit_button("Arşivle")
                    if approve:
                        update_awareness_review(row, "Onaylandı", reviewer, note)
                    if reject:
                        update_awareness_review(row, "Reddedildi", reviewer, note)
                    if research:
                        update_awareness_review(row, "Ek Araştırma Gerekli", reviewer, note)
                    if archive_action:
                        update_awareness_review(row, "Arşivlendi", reviewer, note)
