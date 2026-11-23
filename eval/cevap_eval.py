"""Faz 3 — Kaynaklı cevap üretimi ve atıf geçerliliği ölçümü.

Ders kodu `d6_03_validate.py` (atıf kontrolü) ve `d6_04_eval.py`'den geliştirildi. 40 RAG sorusu,
seçilen arama ayarlarıyla (config) aranır, aday yazım modelleriyle cevaplanır (app/rag/cevap.py).

Ölçülenler (model başına): doğru davranış (cevaplıda cevap, cevapsızda "prosedür bulunamadı"),
atıf geçerliliği, doğru maddeye atıf, gizli koddan (GIZLI10) sızıntı, üretim süresi.

Kullanım:
  python eval/cevap_eval.py --models qwen2.5:1.5b qwen2.5:latest
  python eval/cevap_eval.py --models qwen2.5:1.5b --limit 5
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import EMBED_MODEL, SEMANTIK_AGIRLIK, CHUNK_SIZE  # noqa: E402
from app.rag.cevap import cevapla, BULUNAMADI  # noqa: E402
from app.rag.search import isit  # noqa: E402
from eval.metrikler import cevap_degerlendir, oran  # noqa: E402
from eval.rag_eval import sorulari_yukle, RAPORLAR_DIR  # noqa: E402


def modeli_olc(model: str, limit: int | None = None) -> dict:
    # qwen3'te düşünme kapalı (sınıflandırma ölçümü: açıkken ~4 kat yavaş); diğer modellere parametre gönderilmez
    think = False if model.startswith("qwen3") else None
    print(f"\n=== Yazım modeli: {model} (think={think}) ===")
    isit()
    cevapla("Isınma: cayma süresi nedir?", model=model, think=think)   # LLM'i belleğe yükle
    detay = []
    for s in sorulari_yukle()[:limit] if limit else sorulari_yukle():
        try:
            r = cevapla(s["soru"], erisim_modu=s["erisim"], model=model, think=think)
            d = cevap_degerlendir(s, r["cevap"], r["provenance"], r["atif"], BULUNAMADI)
            d.update({"cevap": r["cevap"], "kaynaklar": [p["kaynak"] for p in r["provenance"].values()],
                      "uretim_sn": r["uretim_sn"], "hata": ""})
        except Exception as e:
            d = {"id": s["id"], "tur": s["tur"], "cevapli": bool(s["beklenen_dokumanlar"]), "hata": str(e),
                 "dogru_davranis": False, "atif_gecerli": False, "dogru_maddeye_atif": False,
                 "yasak_kod": False, "bulunamadi": False, "uretim_sn": None}
        detay.append(d)
        print(f"{d['id']}: davranış={'✓' if d['dogru_davranis'] else '✗'} atıf={d['atif_gecerli']} "
              f"doğru madde={d['dogru_maddeye_atif']} {d['uretim_sn']} sn {d['hata']}")

    cevapli = [d for d in detay if d["cevapli"]]
    cevapsiz = [d for d in detay if not d["cevapli"]]
    atifli = [d for d in detay if d["atif_gecerli"] is not None]
    sureler = [d["uretim_sn"] for d in detay if d["uretim_sn"]]
    return {
        "model": model, "tarih": datetime.now().isoformat(timespec="seconds"),
        "arama": {"embed_model": EMBED_MODEL, "semantik_agirlik": SEMANTIK_AGIRLIK, "chunk_size": CHUNK_SIZE},
        "cevaplida_cevap_verdi": oran(sum(d["dogru_davranis"] for d in cevapli), len(cevapli)),
        "cevapsizda_bulunamadi_dedi": oran(sum(d["dogru_davranis"] for d in cevapsiz), len(cevapsiz)),
        "atif_gecerliligi": oran(sum(bool(d["atif_gecerli"]) for d in atifli), len(atifli)),
        "dogru_maddeye_atif": oran(sum(bool(d["dogru_maddeye_atif"]) for d in cevapli), len(cevapli)),
        "yasak_kod_sizintisi": f"{sum(d['yasak_kod'] for d in detay)}/{len(detay)}",
        "ortalama_uretim_sn": round(sum(sureler) / len(sureler), 2) if sureler else None,
        "en_uzun_uretim_sn": max(sureler) if sureler else None,
        "detay": detay,
    }


def rapor_yaz(sonuclar: list[dict]) -> None:
    adlar = [s["model"] for s in sonuclar]
    a = sonuclar[0]["arama"]

    def satir(baslik, f):
        return f"| {baslik} | " + " | ".join(f(s) for s in sonuclar) + " |\n"

    md = f"""# Faz 3: Kaynaklı Cevap ve Atıf Geçerliliği

**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
**Test seti:** `data/rag_sorular.json` (34 cevaplı, 6 cevapsız). Arama: {a['embed_model']}, parçalama {a['chunk_size']}, semantik ağırlık {a['semantik_agirlik']}, top 3.
**Yöntem:** `app/rag/cevap.py` (ders: d6_02_answer + d6_03_validate). Atıf geçerliliği olgusal doğruluk garantisi değildir. Donanım: CPU.

| Metrik | {' | '.join(adlar)} |
|---|{'---|' * len(adlar)}
"""
    md += satir("Cevaplı soruda cevap verdi", lambda s: s["cevaplida_cevap_verdi"])
    md += satir("Cevapsız soruda 'prosedür bulunamadı' dedi", lambda s: s["cevapsizda_bulunamadi_dedi"])
    md += satir("Atıf geçerliliği (cevap verilenlerde)", lambda s: s["atif_gecerliligi"])
    md += satir("Doğru maddeye atıf (cevaplı)", lambda s: s["dogru_maddeye_atif"])
    md += satir("GIZLI10 sızıntısı", lambda s: s["yasak_kod_sizintisi"])
    md += satir("Ortalama üretim süresi", lambda s: f"{s['ortalama_uretim_sn']} sn")
    md += satir("En uzun üretim süresi", lambda s: f"{s['en_uzun_uretim_sn']} sn")
    md += "\n## Yorum\n\nBu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.\n"
    (RAPORLAR_DIR / "cevap_karsilastirma.md").write_text(md, encoding="utf-8")
    (RAPORLAR_DIR / "cevap_karsilastirma.json").write_text(json.dumps(sonuclar, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRapor: {RAPORLAR_DIR / 'cevap_karsilastirma.md'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Kaynaklı cevap ve atıf ölçümü")
    p.add_argument("--models", nargs="+", default=["qwen2.5:latest", "qwen3:8b"])
    p.add_argument("--limit", type=int, default=None)
    a = p.parse_args()
    rapor_yaz([modeli_olc(m, a.limit) for m in a.models])
