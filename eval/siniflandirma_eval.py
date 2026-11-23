"""Faz 3 — Talep sınıflandırma model karşılaştırması.

30 test talebini (data/ornek_talepler.json, T01-T30) aday modellerle sınıflandırır (app/llm/siniflandir.py).
Yalnızca KATEGORİ doğruluğu ölçülür; öneri (oneri) sipariş verisi ve politika gerektirdiği için Faz 5'te
uçtan uca değerlendirilir (karar günlüğü).

Ölçülenler (model başına):
- Şema geçerliliği: çıktı JSON mu, tüm alanlar izin verilen değerlerde mi
- Kategori doğruluğu (birebir eşleşme)
- Ortalama / en uzun süre (CPU, model ısıtıldıktan sonra), üretilen token
- Düşünme (think) açıkken: düşünme metni uzunluğu ve token bütçesine takılan (done_reason=length) yanıt sayısı

Kullanım:
  python eval/siniflandirma_eval.py --all
  python eval/siniflandirma_eval.py --model qwen2.5:1.5b --limit 5
  python eval/siniflandirma_eval.py --model qwen3:8b --think
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR, CLASSIFY_OPTIONS, CLASSIFY_THINK_OPTIONS, LLM_ADAYLARI  # noqa: E402
from app.llm.siniflandir import siniflandir, TANIM_SURUMU  # noqa: E402
from eval.metrikler import oran  # noqa: E402

RAPORLAR_DIR = Path(__file__).resolve().parent / "raporlar"


def aday_adi(model: str, think: bool | None) -> str:
    return model if think is None else f"{model} (think={'açık' if think else 'kapalı'})"


def test_talepleri(limit: int | None = None, set_adi: str = "test") -> list[dict]:
    """set_adi: 'test' (T01-T30) veya 'demo' (D01-D06; tanım iyileştirmesinde görülmemiş kontrol seti)."""
    veri = json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))
    talepler = [t for t in veri["talepler"] if t["set"] == set_adi]
    return talepler[:limit] if limit else talepler


def modeli_olc(model: str, think: bool | None, limit: int | None = None, set_adi: str = "test") -> dict:
    """Bir aday modeli test talepleri üzerinde ölçer."""
    secenek = CLASSIFY_THINK_OPTIONS if think else CLASSIFY_OPTIONS
    ad = aday_adi(model, think)
    print(f"\n=== {ad} | options={secenek} ===")
    siniflandir("Isınma mesajı: siparişim nerede?", model, think, secenek)   # modeli belleğe yükle

    detay = []
    for t in test_talepleri(limit, set_adi):
        try:
            sonuc, yanit, hata = siniflandir(t["mesaj"], model, think, secenek)
        except Exception as e:     # zaman aşımı / bağlantı
            sonuc, yanit, hata = None, None, f"çağrı hatası: {e}"
        bek = t["beklenen"]["kategori"]
        d = {
            "id": t["id"], "beklenen": bek,
            "tahmin": sonuc["kategori"] if sonuc else None,
            "sema_gecerli": sonuc is not None,
            "dogru": bool(sonuc) and sonuc["kategori"] == bek,
            "sure_sn": yanit.sure_sn if yanit else None,
            "token": yanit.uretilen_token if yanit else None,
            "bitis": yanit.bitis_nedeni if yanit else None,
            "dusunme_karakter": len(yanit.dusunme) if yanit else 0,
            "hata": hata,
        }
        detay.append(d)
        print(f"{d['id']}: {'✓' if d['dogru'] else '✗'} beklenen={bek:<13} tahmin={str(d['tahmin']):<13} "
              f"{d['sure_sn']} sn {d['bitis']} {('HATA: ' + hata) if hata else ''}")

    n = len(detay)
    sureler = [d["sure_sn"] for d in detay if d["sure_sn"] is not None]
    dusunmeli = [d["dusunme_karakter"] for d in detay if d["dusunme_karakter"]]
    return {
        "aday": ad, "set": set_adi, "model": model, "tanim_surumu": TANIM_SURUMU, "think": think, "options": secenek,
        "tarih": datetime.now().isoformat(timespec="seconds"),
        "talep_sayisi": n,
        "sema_gecerlilik": oran(sum(d["sema_gecerli"] for d in detay), n),
        "kategori_dogrulugu": oran(sum(d["dogru"] for d in detay), n),
        "ortalama_sure_sn": round(sum(sureler) / len(sureler), 2) if sureler else None,
        "en_uzun_sure_sn": max(sureler) if sureler else None,
        "token_sinirina_takilan": sum(1 for d in detay if d["bitis"] == "length"),
        "dusunme_olan_yanit": len(dusunmeli),
        "ortalama_dusunme_karakter": round(sum(dusunmeli) / len(dusunmeli)) if dusunmeli else 0,
        "yanlislar": [{"id": d["id"], "beklenen": d["beklenen"], "tahmin": d["tahmin"], "hata": d["hata"]}
                      for d in detay if not d["dogru"]],
        "detay": detay,
    }


def rapor_yaz(sonuclar: list[dict], dosya_adi: str = "siniflandirma_karsilastirma") -> None:
    adlar = [s["aday"] for s in sonuclar]

    def satir(baslik, f):
        return f"| {baslik} | " + " | ".join(f(s) for s in sonuclar) + " |\n"

    md = f"""# Faz 3: Talep Sınıflandırma — Model Karşılaştırması

**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
**Set:** `data/ornek_talepler.json` — {sonuclar[0]['set']} ({sonuclar[0]['talep_sayisi']} talep). Görev: yalnızca kategori (8 sınıf) + aciliyet/duygu/özet alanlarıyla şemalı JSON.
**Yöntem:** Ollama `/api/chat`, `format` = JSON şeması, temperature 0, seed 42. Her model ilk ölçümden önce ısıtıldı. Donanım: CPU.
Öneri (oneri) bu ölçümde yoktur; sipariş ve politika bilgisi gerektirdiği için Faz 5'te ölçülür.
**Kategori tanımları sürümü:** {TANIM_SURUMU} (`app/llm/siniflandir.py`). v1 sonuçları: `siniflandirma_karsilastirma_v1.md`.

| Metrik | {' | '.join(adlar)} |
|---|{'---|' * len(adlar)}
"""
    md += satir("Şema geçerliliği", lambda s: s["sema_gecerlilik"])
    md += satir("Kategori doğruluğu", lambda s: s["kategori_dogrulugu"])
    md += satir("Ortalama süre", lambda s: f"{s['ortalama_sure_sn']} sn")
    md += satir("En uzun süre", lambda s: f"{s['en_uzun_sure_sn']} sn")
    md += satir("num_predict", lambda s: str(s["options"]["num_predict"]))
    md += satir("Token sınırına takılan", lambda s: f"{s['token_sinirina_takilan']}/{s['talep_sayisi']}")
    md += satir("Düşünme metni olan yanıt", lambda s: f"{s['dusunme_olan_yanit']}/{s['talep_sayisi']}")
    md += satir("Ort. düşünme metni (karakter)", lambda s: str(s["ortalama_dusunme_karakter"]))

    md += "\n## Yanlış sınıflandırılan talepler\n\n"
    for s in sonuclar:
        yanlis = ", ".join(f"{y['id']} ({y['beklenen']}→{y['tahmin']})" for y in s["yanlislar"]) or "yok"
        md += f"**{s['aday']}:** {yanlis}\n\n"
    md += "## Yorum\n\nBu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.\n"

    RAPORLAR_DIR.mkdir(parents=True, exist_ok=True)
    (RAPORLAR_DIR / f"{dosya_adi}.md").write_text(md, encoding="utf-8")
    (RAPORLAR_DIR / f"{dosya_adi}.json").write_text(
        json.dumps(sonuclar, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRapor: {RAPORLAR_DIR / (dosya_adi + '.md')}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Talep sınıflandırma model karşılaştırması")
    p.add_argument("--model", default="qwen2.5:1.5b")
    p.add_argument("--think", choices=["acik", "kapali"], default=None,
                   help="Düşünme modu (qwen3). Verilmezse parametre gönderilmez; qwen3 varsayılanı açıktır.")
    p.add_argument("--all", action="store_true", help="config.LLM_ADAYLARI'nın hepsini ölç")
    p.add_argument("--limit", type=int, default=None, help="İlk N talep (hızlı deneme)")
    p.add_argument("--set", choices=["test", "demo"], default="test", help="Talep seti")
    p.add_argument("--rapor", default="siniflandirma_karsilastirma", help="eval/raporlar/ altındaki rapor adı")
    a = p.parse_args()
    if a.all:
        adaylar = LLM_ADAYLARI
    else:
        adaylar = [(a.model, {"acik": True, "kapali": False, None: None}[a.think])]
    rapor_yaz([modeli_olc(m, t, a.limit, a.set) for m, t in adaylar], a.rapor)
