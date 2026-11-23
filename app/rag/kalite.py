"""Model gerektirmeyen sıralama ve atıf yardımcıları.

Ders kodu `rag_kodlar/quality_utils.py`'den geliştirildi:
- `tokens` / `lexical_score`: aynı durak kelime listesi ve kelime örtüşme oranı; OpsPilot için
  sorguda doküman kodu veya "madde N" geçerse bonus eklendi.
- `citations_in_answer` / `validate_citations`: [K#] atıf doğrulaması (d6_03_validate).
"""
import re

STOP = {"ve", "ile", "için", "mi", "mı", "mu", "mü", "bir", "ne", "nerede", "nasıl", "hangi", "kadar", "kaç",
        "ben", "benim", "nedir", "bu", "de", "da", "olan", "olarak", "var", "mıydı", "mıyım", "olur", "yapılır"}


def tokens(text: str) -> set[str]:
    """Küçük harfli, 2 karakterden uzun, durak kelime olmayan kelime kümesi."""
    return {x for x in re.findall(r"[a-z0-9çğıöşü]+", text.lower()) if len(x) > 2 and x not in STOP}


def lexical_score(question: str, content: str, kod: str = "", madde_no: int | None = None) -> float:
    """Sorudaki kelimelerin içerikte geçme oranı (0-1); kod / madde numarası açıkça geçerse +0.3'er bonus."""
    qs = tokens(question)
    oran = len(qs & tokens(content)) / len(qs) if qs else 0.0
    soru = question.lower()
    bonus = 0.0
    if kod and kod.lower() in soru:
        bonus += 0.3
    if madde_no is not None and f"madde {madde_no}" in soru:
        bonus += 0.3
    return min(1.0, oran + bonus)


def citations_in_answer(answer: str) -> set[str]:
    return set(re.findall(r"\[(K\d+)\]", answer))


def validate_citations(answer: str, known_ids) -> dict:
    """Atıf etiketi doğrulaması — olgusal doğruluk garantisi DEĞİLDİR (ders: d6_03_validate)."""
    got = citations_in_answer(answer)
    known = set(known_ids)
    return {"valid": bool(got) and got <= known, "used": sorted(got),
            "invalid": sorted(got - known), "missing": not bool(got)}
