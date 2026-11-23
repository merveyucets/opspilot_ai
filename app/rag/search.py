"""Politika araması: anlamsal arama + erişim filtresi + hibrit rerank.

Ders kodu `d5_05_search.py` (similarity_search + metadata filtresi) ve `d6_01_rerank.py`'den
(k=8 aday → rerank → top 3) geliştirildi. OpsPilot eklemeleri:
- Rerank'te sıra yerine gerçek kosinüs benzerliği kullanılır (benim_rag/rerank_karsilastirma deneyi)
- Müşteri modunda gizli dokümanlar aramaya hiç girmez; bilinmeyen mod hata verir (sessizce filtresiz aramaz)
- Aynı maddenin bölünmüş parçaları sonuçta tek kez yer alır
"""
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import EMBED_MODEL, RETRIEVAL_K, RERANK_TOP_N, SEMANTIK_AGIRLIK, CHUNK_SIZE  # noqa: E402
from app.rag.indexer import get_store  # noqa: E402
from app.rag.kalite import lexical_score  # noqa: E402

ERISIM_MODLARI = ("ic", "musteri")


@dataclass
class AramaSonucu:
    """Tek bir arama sonucu."""
    id: str
    kod: str
    madde_no: int
    madde_baslik: str
    kategori: str
    erisim: str
    kaynak: str           # "POL-IADE-001 Madde 3"
    icerik: str
    skor: float           # Kosinüs uzaklığı (düşük = daha yakın)
    benzerlik: float      # 1 - uzaklık (yüksek = daha yakın)
    hibrit_skor: float    # Rerank skoru (yüksek = daha iyi)


_STORES = {}


def _store(embed_model: str, chunk_size: int = CHUNK_SIZE):
    anahtar = (embed_model, chunk_size)
    if anahtar not in _STORES:
        _STORES[anahtar] = get_store(embed_model, chunk_size)
    return _STORES[anahtar]


def erisim_filtresi(erisim_modu: str) -> dict | None:
    """Erişim moduna göre metadata filtresi; bilinmeyen mod hata verir."""
    if erisim_modu not in ERISIM_MODLARI:
        raise ValueError(f"Geçersiz erişim modu: {erisim_modu!r}. Geçerli: {ERISIM_MODLARI}")
    return {"erisim": "ic"} if erisim_modu == "musteri" else None


def tekillestir(sirali_adaylar: list[AramaSonucu]) -> list[AramaSonucu]:
    """Aynı maddenin (kod + madde_no) yalnızca en üst sıradaki parçasını bırakır."""
    gorulen, sonuc = set(), []
    for a in sirali_adaylar:
        if (a.kod, a.madde_no) not in gorulen:
            gorulen.add((a.kod, a.madde_no))
            sonuc.append(a)
    return sonuc


def isit(embed_model: str = EMBED_MODEL, chunk_size: int = CHUNK_SIZE) -> float:
    """Embedding modelini belleğe yükler; ölçümde ilk sorgunun süresini şişirmesin diye."""
    t0 = time.perf_counter()
    _store(embed_model, chunk_size).similarity_search("ısınma sorgusu", k=1)
    return round(time.perf_counter() - t0, 2)


def ara(
    sorgu: str,
    embed_model: str = EMBED_MODEL,
    erisim_modu: str = "ic",
    k: int = RETRIEVAL_K,
    top_n: int = RERANK_TOP_N,
    rerank: bool = True,
    semantik_agirlik: float = SEMANTIK_AGIRLIK,
    chunk_size: int = CHUNK_SIZE,
) -> tuple[list[AramaSonucu], float]:
    """k aday getirir, hibrit skorla sıralar, maddeleri tekilleştirir ve ilk top_n'i döndürür.

    Hibrit skor = semantik_agirlik * benzerlik + (1 - semantik_agirlik) * kelime örtüşmesi
    Returns: (sonuçlar, geçen_süre_sn)
    """
    filtre = erisim_filtresi(erisim_modu)
    t0 = time.perf_counter()
    ham = _store(embed_model, chunk_size).similarity_search_with_score(query=sorgu, k=k, filter=filtre)

    adaylar = []
    for doc, uzaklik in ham:
        m = doc.metadata
        benzerlik = max(0.0, 1.0 - float(uzaklik))
        kod, madde_no = str(m.get("kod", "")), int(m.get("madde_no", 0))
        lex = lexical_score(sorgu, doc.page_content, kod, madde_no)
        hibrit = semantik_agirlik * benzerlik + (1 - semantik_agirlik) * lex if rerank else benzerlik
        adaylar.append(AramaSonucu(
            id=str(m.get("chunk_id", "")), kod=kod, madde_no=madde_no,
            madde_baslik=str(m.get("madde_baslik", "")), kategori=str(m.get("kategori", "")),
            erisim=str(m.get("erisim", "")), kaynak=str(m.get("kaynak", f"{kod} Madde {madde_no}")),
            icerik=doc.page_content, skor=round(float(uzaklik), 4),
            benzerlik=round(benzerlik, 4), hibrit_skor=round(hibrit, 4),
        ))

    adaylar.sort(key=lambda x: x.hibrit_skor, reverse=True)
    return tekillestir(adaylar)[:top_n], round(time.perf_counter() - t0, 4)


if __name__ == "__main__":
    soru = "Cayma hakkı kaç gün içinde kullanılabilir?"
    print(f"Sorgu: {soru}\nIsınma: {isit()} sn")
    sonuclar, sure = ara(soru)
    for s in sonuclar:
        print(f"  [{s.id}] {s.kaynak} - {s.madde_baslik} (benzerlik={s.benzerlik}, hibrit={s.hibrit_skor})")
    print(f"Süre: {sure} sn")
