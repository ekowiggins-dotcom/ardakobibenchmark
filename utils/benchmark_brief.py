from __future__ import annotations

import csv
from pathlib import Path


TOPICS = {
    "AI / SaaS": ["Ürün / çözüm", "Kullanım amacı", "Hedef müşteri", "İş ortağı", "Fiyat", "Ücretsiz süre", "Uygunluk koşulları"],
    "POS": ["POS türü", "Kart türü", "Peşin komisyon oranı", "Ciro sınırı", "Kampanya süresi", "Uygunluk koşulları"],
    "Kredi kartları": ["Kart / ürün", "Yıllık ücret", "Ödül / avantaj", "Kampanya süresi", "Uygunluk koşulları"],
    "Para transferleri": ["Transfer türü", "Kanal", "İşlem tutarı aralığı", "Komisyon oranı", "Asgari ücret", "Azami ücret", "Ücretsiz haklar"],
    "KOBİ paketleri": ["Paket adı", "Paket ücreti", "Dahil işlemler", "İşlem limitleri", "Geçerlilik süresi", "Uygunluk koşulları"],
    "Yeni müşteri teklifleri": ["Teklif", "Maddi fayda", "Vade / süre", "Dijital müşteri olma şartı", "Uygunluk koşulları", "Son başvuru tarihi"],
    "Özel araştırma": [],
}


def bank_catalog(root: Path) -> dict[str, dict[str, list[str]]]:
    catalog = {"Türkiye": {"Tier 1": [], "Tier 2": []}, "Global": {"Mevcut global kapsam": []}}
    with (root / "data" / "bank_ai_initiatives.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            tier = row["institution_tier"]
            market, group = ("Global", "Mevcut global kapsam") if tier == "Global" else ("Türkiye", tier)
            if group not in catalog[market]:
                continue
            name = row["institution_name"]
            if name not in catalog[market][group]:
                catalog[market][group].append(name)
    return catalog


def build_prompt(brief: dict) -> str:
    return (
        f"Araştırma konusu: {brief['topic']}\n"
        f"Pazar: {brief['market']}\n"
        f"Banka grubu: {brief['group']}\n"
        f"Karşılaştırılacak kurumlar: {', '.join(brief['banks'])}\n"
        f"Müşteri segmenti: {brief['segment']}\n"
        f"Zaman kapsamı: {brief['period']}\n\n"
        f"Matris sütunları: Kurum, {', '.join(brief['criteria'])}, Kaynak, Kontrol tarihi.\n\n"
        f"Kaynak yaklaşımı: {brief['source_policy']}\n"
        "Her bulguyu kaynak bağlantısı ve destekleyici metinle doğrula. "
        "Fiyat, para birimi, dönem, kanal ve uygunluk koşullarını açıkça belirt. "
        "Standart tarifeleri ve kampanyaları birbirinden ayır. "
        "Farklı koşullardaki teklifleri doğrudan eşdeğer gibi sunma. "
        "Kaynaklarda bulunamayan bilgi için 'Doğrulanamadı' yaz; değer tahmin etme. "
        "Sonucu Türkçe bir karşılaştırma matrisi olarak hazırla.\n\n"
        f"Kapsam dışı: {brief['exclusions'] or 'Belirtilmedi'}\n"
        f"Ek talimatlar: {brief['instructions'] or 'Yok'}"
    )
