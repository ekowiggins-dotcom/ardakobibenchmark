from __future__ import annotations

import re


def _key(value: str) -> str:
    text = str(value or "").casefold()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "İ".casefold(): "i",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


ALIASES: dict[str, tuple[str, str]] = {
    "garanti bbva": ("garanti_bbva", "Garanti BBVA"),
    "garanti": ("garanti_bbva", "Garanti BBVA"),
    "is bankasi": ("is_bankasi", "İş Bankası"),
    "turkiye is bankasi": ("is_bankasi", "İş Bankası"),
    "yapi kredi": ("yapi_kredi", "Yapı Kredi"),
    "qnb finansbank": ("qnb_finansbank", "QNB Finansbank"),
    "qnb bank": ("qnb_finansbank", "QNB Finansbank"),
    "qnb": ("qnb_finansbank", "QNB Finansbank"),
    "alternatif bank": ("alternatif_bank", "Alternatif Bank"),
    "alternatifbank": ("alternatif_bank", "Alternatif Bank"),
    "denizbank": ("denizbank", "DenizBank"),
    "deniz bank": ("denizbank", "DenizBank"),
    "ing": ("ing", "ING"),
    "teb": ("teb", "TEB"),
    "turk ekonomi bankasi": ("teb", "TEB"),
    "sekerbank": ("sekerbank", "Şekerbank"),
    "seker bank": ("sekerbank", "Şekerbank"),
    "fibabanka": ("fibabanka", "Fibabanka"),
    "fiba banka": ("fibabanka", "Fibabanka"),
    "anadolubank": ("anadolubank", "Anadolubank"),
    "anadolu bank": ("anadolubank", "Anadolubank"),
    "odeabank": ("odeabank", "Odeabank"),
    "odea bank": ("odeabank", "Odeabank"),
    "burgan bank": ("burgan_bank", "Burgan Bank"),
    "burgan": ("burgan_bank", "Burgan Bank"),
    "hsbc": ("hsbc", "HSBC"),
    "hsbc bank": ("hsbc", "HSBC"),
    "hsbc turkiye": ("hsbc", "HSBC"),
    "enpara": ("enpara", "Enpara"),
    "enpara com": ("enpara", "Enpara"),
    "enpara com sirketim": ("enpara", "Enpara"),
    "enpara sirketim": ("enpara", "Enpara"),
    "enpara bank": ("enpara", "Enpara"),
    "enpara bank a s": ("enpara", "Enpara"),
    "t bank": ("t_bank", "T-Bank"),
    "tbank": ("t_bank", "T-Bank"),
    "turkland bank": ("t_bank", "T-Bank"),
    "turkland bank a s": ("t_bank", "T-Bank"),
    "turkish bank": ("turkish_bank", "TurkishBank"),
    "turkishbank": ("turkish_bank", "TurkishBank"),
    "turkish bank a s": ("turkish_bank", "TurkishBank"),
    "turk ticaret bankasi": ("turk_ticaret_bankasi", "Türk Ticaret Bankası"),
    "turk ticaret": ("turk_ticaret_bankasi", "Türk Ticaret Bankası"),
    "turk ticaret bankasi a s": ("turk_ticaret_bankasi", "Türk Ticaret Bankası"),
    "colendi bank": ("colendi_bank", "Colendi Bank"),
    "fups bank": ("fups_bank", "FUPS Bank"),
    "icbc turkey": ("icbc_turkey", "ICBC Turkey"),
    "icbc": ("icbc_turkey", "ICBC Turkey"),
    "arap turk bankasi": ("arap_turk_bankasi", "Arap Türk Bankası"),
    "bank of china turkey": ("bank_of_china_turkey", "Bank of China Turkey"),
    "citibank": ("citibank", "Citibank"),
    "deutsche bank": ("deutsche_bank", "Deutsche Bank"),
    "jpmorgan chase bank": ("jpmorgan_chase_bank", "JPMorgan Chase Bank"),
    "jpmorgan": ("jpmorgan_chase_bank", "JPMorgan Chase Bank"),
    "mufg bank turkey": ("mufg_bank_turkey", "MUFG Bank Turkey"),
    "intesa sanpaolo": ("intesa_sanpaolo", "Intesa Sanpaolo"),
    "rabobank": ("rabobank", "Rabobank"),
    "societe generale": ("societe_generale", "Société Générale"),
    "société générale": ("societe_generale", "Société Générale"),
    "bank mellat": ("bank_mellat", "Bank Mellat"),
    "visa": ("visa", "Visa"),
    "mastercard": ("mastercard", "Mastercard"),
    "bkm": ("bkm", "BKM"),
    "troy": ("troy", "TROY"),
}

GROUP_BY_ID = {
    "garanti_bbva": "Büyük Ölçekli Bankalar",
    "is_bankasi": "Büyük Ölçekli Bankalar",
    "yapi_kredi": "Büyük Ölçekli Bankalar",
    "qnb_finansbank": "Büyük Ölçekli Bankalar",
    "denizbank": "Büyük Ölçekli Bankalar",
    "teb": "Orta/Küçük Ölçekli Özel Bankalar",
    "alternatif_bank": "Orta/Küçük Ölçekli Özel Bankalar",
    "ing": "Orta/Küçük Ölçekli Özel Bankalar",
    "sekerbank": "Orta/Küçük Ölçekli Özel Bankalar",
    "fibabanka": "Orta/Küçük Ölçekli Özel Bankalar",
    "anadolubank": "Orta/Küçük Ölçekli Özel Bankalar",
    "odeabank": "Orta/Küçük Ölçekli Özel Bankalar",
    "burgan_bank": "Orta/Küçük Ölçekli Özel Bankalar",
    "hsbc": "Orta/Küçük Ölçekli Özel Bankalar",
    "enpara": "Dijital/Gelişen Oyuncular",
    "colendi_bank": "Dijital/Gelişen Oyuncular",
    "fups_bank": "Dijital/Gelişen Oyuncular",
    "t_bank": "Orta/Küçük Ölçekli Özel Bankalar",
    "turkish_bank": "Orta/Küçük Ölçekli Özel Bankalar",
    "turk_ticaret_bankasi": "Orta/Küçük Ölçekli Özel Bankalar",
    "visa": "Global Ödeme Ağları",
    "mastercard": "Global Ödeme Ağları",
    "bkm": "Sektör / Altyapı",
    "troy": "Sektör / Altyapı",
}


def canonical_institution(value: str) -> tuple[str, str]:
    key = _key(value)
    if key in ALIASES:
        return ALIASES[key]
    compact = key.replace(" ", "")
    if compact in ALIASES:
        return ALIASES[compact]
    fallback_name = str(value or "").strip()
    fallback_id = re.sub(r"[^a-z0-9]+", "_", _key(value)).strip("_")
    return fallback_id, fallback_name


def canonical_institution_id(value: str) -> str:
    return canonical_institution(value)[0]


def canonical_institution_name(value: str) -> str:
    return canonical_institution(value)[1]


def institution_group(value: str) -> str:
    institution_id = canonical_institution_id(value)
    return GROUP_BY_ID.get(institution_id, "Diğer")
