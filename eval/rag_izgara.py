"""Faz 3 ayar ızgarası: embedding modeli × parçalama × rerank ağırlığı.

Ders kodu `benim_rag/rerank_karsilastirma.py` (Chroma / lexical ağırlık deneyi) ve `d6_04_eval.py`'den
geliştirildi; metrikler eval/metrikler.py, tek ayar ölçümü eval/rag_eval.modeli_degerlendir.

- Parçalama: 900 (uzun maddeler bölünür) ve 1600 (her madde tek parça; en uzun madde + başlık < 1600)
- Semantik ağırlık: 1.0 (rerank yok), 0.8, 0.6 (ders: lexical_weight=0.4), 0.4
- Seçim kuralı (ölçümden önce belirlendi): en yüksek madde Hit@3 → eşitse madde Top1 → eşitse daha hızlı

Kullanım: python eval/rag_izgara.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import EMBED_MODEL_ADAYLARI  # noqa: E402
from eval.rag_eval import modeli_degerlendir, RAPORLAR_DIR  # noqa: E402

PARCA_BOYUTLARI = [900, 1600]
AGIRLIKLAR = [1.0, 0.8, 0.6, 0.4]


def _sayi(oran_metni: str) -> int:
    """'27/34 (%79.4)' → 27"""
    return int(oran_metni.split("/")[0])


def calistir() -> list[dict]:
    satirlar = []
    for model in EMBED_MODEL_ADAYLARI:
        for cs in PARCA_BOYUTLARI:
            for w in AGIRLIKLAR:
                r = modeli_degerlendir(model, semantik_agirlik=w, chunk_size=cs, sessiz=True)
                satir = {
                    "model": model, "chunk_size": cs, "parca_sayisi": r["ayarlar"]["parca_sayisi"],
                    "semantik_agirlik": w,
                    "dokuman_hit_3": r["dokuman_hit_3"], "madde_hit_3": r["madde_hit_3"],
                    "top1_madde": r["top1_madde"],
                    "capraz_madde_hit": r["tur_kirilim"].get("CAPRAZ", {}).get("madde_hit", "-"),
                    "gunluk_dil_madde_hit": r["tur_kirilim"].get("GUNLUK_DIL", {}).get("madde_hit", "-"),
                    "gizli_sizinti": r["gizli_sizinti"],
                    "esik": r["esik_analizi"],
                    "ortalama_arama_ms": r["ortalama_arama_ms"],
                    "kacan": [k["id"] for k in r["kacan_maddeler"]],
                }
                satirlar.append(satir)
                print(f"{model:22} chunk={cs:<5} w={w:<4} madde={satir['madde_hit_3']:<15} "
                      f"top1={satir['top1_madde']:<15} çapraz={satir['capraz_madde_hit']:<12} {satir['ortalama_arama_ms']} ms")
    return satirlar


def sirala(satirlar: list[dict]) -> list[dict]:
    """Seçim kuralına göre sıralar."""
    return sorted(satirlar, key=lambda s: (-_sayi(s["madde_hit_3"]), -_sayi(s["top1_madde"]), s["ortalama_arama_ms"]))


def rapor_yaz(satirlar: list[dict]) -> None:
    sirali = sirala(satirlar)
    md = f"""# Faz 3: RAG Ayar Izgarası

**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
**Test seti:** `data/rag_sorular.json` (34 cevaplı + 6 cevapsız soru). Metrik tanımları: `eval/metrikler.py`.
**Sabit ayarlar:** k=8 aday, top 3 tekil madde. Arama süreleri model ısıtıldıktan sonra, CPU.
**Seçim kuralı (ölçümden önce belirlendi):** en yüksek madde Hit@3 → eşitse madde Top1 → eşitse daha kısa süre.

| # | Model | Parçalama | Semantik ağırlık | Doküman Hit@3 | Madde Hit@3 | Madde Top1 | Çapraz madde | Günlük dil madde | Sızıntı | Ort. ms |
|---|---|---|---|---|---|---|---|---|---|---|
"""
    for i, s in enumerate(sirali, 1):
        parcalama = f"{s['chunk_size']} ({s['parca_sayisi']} parça)"
        md += (f"| {i} | {s['model']} | {parcalama} | {s['semantik_agirlik']} | {s['dokuman_hit_3']} | "
               f"{s['madde_hit_3']} | {s['top1_madde']} | {s['capraz_madde_hit']} | {s['gunluk_dil_madde_hit']} | "
               f"{s['gizli_sizinti']} | {s['ortalama_arama_ms']} |\n")
    en_iyi = sirali[0]
    md += f"""
**Kurala göre seçilen ayar:** {en_iyi['model']}, parçalama {en_iyi['chunk_size']}, semantik ağırlık {en_iyi['semantik_agirlik']}.
Bu ayarda madde isabeti olmayan sorular: {', '.join(en_iyi['kacan']) or 'yok'}.
Bu ayarda "kaynak yok" eşik analizi: en iyi eşik {en_iyi['esik']['esik']}, yanlış alarm {en_iyi['esik']['yanlis_alarm']}/34, kaçan {en_iyi['esik']['kacan']}/6.

## Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
"""
    RAPORLAR_DIR.mkdir(parents=True, exist_ok=True)
    (RAPORLAR_DIR / "rag_izgara.md").write_text(md, encoding="utf-8")
    (RAPORLAR_DIR / "rag_izgara.json").write_text(json.dumps(sirali, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRapor: {RAPORLAR_DIR / 'rag_izgara.md'}")


if __name__ == "__main__":
    rapor_yaz(calistir())
