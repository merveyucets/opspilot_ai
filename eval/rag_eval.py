"""RAG Değerlendirme ve Kıyaslama Scripti (Faz 3).

40 soruluk test setiyle (data/rag_sorular.json) embedding modellerini ölçer:
- Doküman ve madde (ana madde) düzeyinde Hit@3, Top1 — payda yalnızca cevaplı sorular
- Soru türlerine göre kırılım
- Gizli doküman sızıntısı (yasak doküman sonuçta görünürse)
- "Kaynak yok" eşik analizi: cevaplı ve cevapsız soruların en iyi benzerlik dağılımı
- Ortalama arama süresi (model ısıtıldıktan sonra)

Metrik tanımları: eval/metrikler.py

Kullanım:
  python eval/rag_eval.py --model embeddinggemma
  python eval/rag_eval.py --all
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (  # noqa: E402
    DATA_DIR, EMBED_MODEL, EMBED_MODEL_ADAYLARI, RETRIEVAL_K, RERANK_TOP_N, SEMANTIK_AGIRLIK, CHUNK_SIZE,
)
from app.rag.indexer import indeksle  # noqa: E402
from app.rag.search import ara, isit  # noqa: E402
from eval.metrikler import soruyu_degerlendir, esik_analizi, oran  # noqa: E402

RAPORLAR_DIR = Path(__file__).resolve().parent / "raporlar"
TURLER = ["DOGRUDAN", "GUNLUK_DIL", "ESKI_KURAL", "CAPRAZ", "CEVAPSIZ", "GIZLI"]


def sorulari_yukle() -> list[dict]:
    with open(DATA_DIR / "rag_sorular.json", encoding="utf-8") as f:
        return json.load(f)["sorular"]


def modeli_degerlendir(
    embed_model: str,
    rerank: bool = True,
    semantik_agirlik: float = SEMANTIK_AGIRLIK,
    k: int = RETRIEVAL_K,
    top_n: int = RERANK_TOP_N,
    chunk_size: int = CHUNK_SIZE,
    sessiz: bool = False,
) -> dict:
    """Tek bir embedding modeli + ayar için 40 soruluk değerlendirmeyi çalıştırır."""
    if not sessiz:
        print(f"\n=== Model: {embed_model} (rerank={rerank}, semantik_agirlik={semantik_agirlik}, chunk={chunk_size}) ===")
    _, parca_sayisi, indeks_sure = indeksle(embed_model, chunk_size=chunk_size)
    isinma_sn = isit(embed_model, chunk_size)

    detaylar, sureler = [], []
    for s in sorulari_yukle():
        sonuclar, sure = ara(
            s["soru"], embed_model=embed_model, erisim_modu=s["erisim"],
            k=k, top_n=top_n, rerank=rerank, semantik_agirlik=semantik_agirlik, chunk_size=chunk_size,
        )
        d = soruyu_degerlendir(s, sonuclar)
        d["sure_ms"] = round(sure * 1000, 1)
        detaylar.append(d)
        sureler.append(d["sure_ms"])

    cevapli = [d for d in detaylar if d["cevapli"]]
    cevapsiz = [d for d in detaylar if not d["cevapli"]]
    yasakli = [s for s in sorulari_yukle() if s.get("yasak_dokumanlar")]
    n = len(cevapli)

    tur_kirilim = {}
    for tur in TURLER:
        grup = [d for d in cevapli if d["tur"] == tur]
        if grup:
            tur_kirilim[tur] = {
                "dokuman_hit": oran(sum(d["dokuman_hit"] for d in grup), len(grup)),
                "madde_hit": oran(sum(d["madde_hit"] for d in grup), len(grup)),
            }

    ozet = {
        "model": embed_model,
        "tarih": datetime.now().isoformat(timespec="seconds"),
        "ayarlar": {"rerank": rerank, "semantik_agirlik": semantik_agirlik, "k": k, "top_n": top_n,
                    "chunk_size": chunk_size, "parca_sayisi": parca_sayisi},
        "cevapli_soru": n,
        "cevapsiz_soru": len(cevapsiz),
        "dokuman_hit_3": oran(sum(d["dokuman_hit"] for d in cevapli), n),
        "madde_hit_3": oran(sum(d["madde_hit"] for d in cevapli), n),
        "top1_dokuman": oran(sum(d["top1_dokuman"] for d in cevapli), n),
        "top1_madde": oran(sum(d["top1_madde"] for d in cevapli), n),
        "gizli_sizinti": f"{sum(d['sizinti'] for d in detaylar)}/{len(yasakli)} soru",
        "esik_analizi": esik_analizi([d["top1_benzerlik"] for d in cevapli],
                                     [d["top1_benzerlik"] for d in cevapsiz]),
        "indeksleme_sn": indeks_sure,
        "isinma_sn": isinma_sn,
        "ortalama_arama_ms": round(sum(sureler) / len(sureler), 1),
        "tur_kirilim": tur_kirilim,
        "kacan_maddeler": [
            {"id": d["id"], "tur": d["tur"], "bulunan": d["kaynaklar"]}
            for d in cevapli if not d["madde_hit"]
        ],
        "soru_detaylari": detaylar,
    }

    if not sessiz:
        print(f"Doküman Hit@3: {ozet['dokuman_hit_3']} | Madde Hit@3: {ozet['madde_hit_3']} | "
              f"Top1 madde: {ozet['top1_madde']} | Sızıntı: {ozet['gizli_sizinti']} | "
              f"Ort. arama: {ozet['ortalama_arama_ms']} ms")
    return ozet


def rapor_yaz(sonuclar: dict[str, dict], dosya_adi: str = "rag_karsilastirma") -> None:
    """Karşılaştırma sonuçlarını Markdown + JSON olarak eval/raporlar/ altına yazar."""
    RAPORLAR_DIR.mkdir(parents=True, exist_ok=True)
    modeller = list(sonuclar)
    ilk = sonuclar[modeller[0]]
    a = ilk["ayarlar"]

    def satir(baslik, f):
        return f"| {baslik} | " + " | ".join(f(sonuclar[m]) for m in modeller) + " |\n"

    md = f"""# Faz 3: Embedding Modelleri Karşılaştırma Raporu

**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
**Test seti:** `data/rag_sorular.json` — 40 soru ({ilk['cevapli_soru']} cevaplı, {ilk['cevapsiz_soru']} cevapsız)
**Ayarlar:** {a['parca_sayisi']} parça (madde bazlı, {a['chunk_size']} karakter üstü bölünür), k={a['k']}, top_n={a['top_n']}, rerank={a['rerank']}, semantik ağırlık={a['semantik_agirlik']}

**Yöntem notları**
- Hit/Top1 paydası yalnızca cevaplı sorulardır. Cevapsız sorular: 4 CEVAPSIZ + müşteri modunda cevabı yalnızca gizli dokümanda olan 2 GIZLI soru.
- Madde eşleşmesi ana madde düzeyindedir (beklenen 5.1 ise Madde 5 parçası isabettir). Aynı maddenin parçaları ilk 3'te tek kez sayılır.
- CAPRAZ sorularda beklenen dokümanların hepsi (madde için her dokümandan bir beklenen madde) ilk 3'te olmalıdır.
- Eşik analizi aynı soru setiyle yapıldığı için iyimserdir; eşik "en iyi sonucun benzerliği < eşik ise kaynak yok" kuralıdır.
- Arama süreleri model ısıtıldıktan sonra ölçülmüştür; sorgu embedding'i dahildir. Donanım: CPU.

## 1. Genel karşılaştırma

| Metrik | {' | '.join(modeller)} |
|---|{'---|' * len(modeller)}
"""
    md += satir("Doküman Hit@3", lambda r: r["dokuman_hit_3"])
    md += satir("Madde Hit@3", lambda r: r["madde_hit_3"])
    md += satir("Top1 doküman", lambda r: r["top1_dokuman"])
    md += satir("Top1 madde", lambda r: r["top1_madde"])
    md += satir("Gizli doküman sızıntısı", lambda r: r["gizli_sizinti"])
    md += satir("Ortalama arama süresi", lambda r: f"{r['ortalama_arama_ms']} ms")
    md += satir("İndeksleme süresi", lambda r: f"{r['indeksleme_sn']} sn" if r["indeksleme_sn"] else "güncel (yeniden yapılmadı)")

    md += f"""
## 2. "Kaynak yok" eşik analizi

| Metrik | {' | '.join(modeller)} |
|---|{'---|' * len(modeller)}
"""
    md += satir("Cevaplı sorularda en düşük top1 benzerlik", lambda r: str(r["esik_analizi"]["cevapli_min"]))
    md += satir("Cevapsız sorularda en yüksek top1 benzerlik", lambda r: str(r["esik_analizi"]["cevapsiz_max"]))
    md += satir("İki grup tam ayrışıyor mu", lambda r: "evet" if r["esik_analizi"]["tam_ayrisiyor"] else "hayır")
    md += satir("En iyi eşik", lambda r: str(r["esik_analizi"]["esik"]))
    md += satir("Yanlış alarm (cevaplı → 'kaynak yok')", lambda r: f"{r['esik_analizi']['yanlis_alarm']}/{r['cevapli_soru']}")
    md += satir("Kaçan (cevapsız → kaynak var)", lambda r: f"{r['esik_analizi']['kacan']}/{r['cevapsiz_soru']}")

    md += f"""
## 3. Soru türüne göre madde Hit@3

| Soru türü | {' | '.join(modeller)} |
|---|{'---|' * len(modeller)}
"""
    for tur in TURLER:
        if tur in ilk["tur_kirilim"]:
            md += satir(tur, lambda r, t=tur: r["tur_kirilim"].get(t, {}).get("madde_hit", "-"))

    md += "\n## 4. Madde isabeti olmayan sorular\n\n"
    for m in modeller:
        md += f"**{m}:** "
        kacan = sonuclar[m]["kacan_maddeler"]
        md += (", ".join(f"{k['id']} ({k['tur']})" for k in kacan) if kacan else "yok") + "\n\n"

    md += "## 5. Yorum\n\nBu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.\n"

    (RAPORLAR_DIR / f"{dosya_adi}.md").write_text(md, encoding="utf-8")
    (RAPORLAR_DIR / f"{dosya_adi}.json").write_text(
        json.dumps(sonuclar, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRapor: {RAPORLAR_DIR / (dosya_adi + '.md')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG değerlendirmesi çalıştırır.")
    parser.add_argument("--model", default=EMBED_MODEL, help="Test edilecek embedding modeli")
    parser.add_argument("--all", action="store_true", help="config.EMBED_MODEL_ADAYLARI'nın hepsini test et")
    parser.add_argument("--no-rerank", action="store_true", help="Rerank kapalı test et")
    args = parser.parse_args()

    modeller = EMBED_MODEL_ADAYLARI if args.all else [args.model]
    rapor_yaz({m: modeli_degerlendir(m, rerank=not args.no_rerank) for m in modeller})
