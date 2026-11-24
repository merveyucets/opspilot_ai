"""Faz 9 — Talep mesajlarıyla politika araması: tek sorgu vs çoklu sorgu (sorgu yeniden yazma + RRF).

Neden: Faz 3 arama ölçümü (rag_izgara.md) düzgün yazılmış sorularla yapıldı. Karar değerlendirmesinde agent'ın
müşteri mesajını olduğu gibi sorgu yapması, beklenen maddelerin hepsini yalnızca 7/30 talepte LLM'e getirdi.

Beklenen maddeler: talebin `beklenen.dayanak` listesi (ana madde düzeyi). POL-ESK-007 Madde 2 (tutara göre onay
yetkisi) hariç tutulur: onay rolünü kod hesaplar ve LLM'e "onay yetkisini sen belirleme" denir.

Varyantlar:
  mesaj_top3  — bugünkü agent: maskelenmiş müşteri mesajı tek sorgu, ilk 3 madde
  mesaj_top5  — aynı sorgu, ilk 5 (yalnızca N'yi artırmanın etkisini ayırmak için)
  rrf_top3/5        — mesaj + sınıflandırıcının yazdığı arama soruları, RRF (ortak çıkan madde öne geçer)
  donusumlu_top3/5  — aynı sorgular, dönüşümlü (her sorgunun 1. sonucu, sonra 2. sonuçları...)
Seçim kuralı (ölçümden ÖNCE belirlendi): "beklenen maddelerin hepsi bulundu" sayısı en yüksek varyant;
eşitlikte madde duyarlılığı (recall) yüksek olan; yine eşitse N'si küçük olan (LLM'e daha kısa bağlam = daha hızlı).

Sınıflandırıcı çıktıları önbelleğe yazılır; --yeniden ile LLM tekrar çağrılır.
Kullanım: python eval/arama_talep_eval.py [--set test|demo] [--yeniden]
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR, CLASSIFIER_MODEL, CLASSIFIER_THINK, CLASSIFY_OPTIONS, EMBED_MODEL  # noqa: E402
from app.agent.graf import maskele  # noqa: E402
from app.llm.siniflandir import siniflandir  # noqa: E402
from app.rag.search import ara, coklu_ara, isit  # noqa: E402
from eval.metrikler import ana_madde, oran  # noqa: E402

RAPORLAR = Path(__file__).resolve().parent / "raporlar"
HARIC = {("POL-ESK-007", 2)}
# (ad, birleştirme yöntemi veya None = yalnızca mesaj, N)
VARYANTLAR = [("mesaj_top3", None, 3), ("mesaj_top5", None, 5), ("rrf_top3", "rrf", 3), ("rrf_top5", "rrf", 5),
              ("donusumlu_top3", "donusumlu", 3), ("donusumlu_top5", "donusumlu", 5)]


def siniflandirmalar(talepler: list[dict], dosya: Path, yeniden: bool) -> dict:
    onbellek = json.loads(dosya.read_text(encoding="utf-8")) if dosya.exists() and not yeniden else {}
    for i, t in enumerate(talepler, 1):
        if t["id"] in onbellek:
            continue
        sonuc, yanit, hata = siniflandir(maskele(t["mesaj"]), CLASSIFIER_MODEL, CLASSIFIER_THINK, CLASSIFY_OPTIONS)
        onbellek[t["id"]] = {"sonuc": sonuc, "hata": hata, "sure_sn": yanit.sure_sn, "bitis": yanit.bitis_nedeni}
        print(f"[{i}/{len(talepler)}] {t['id']} {yanit.sure_sn} sn {'HATA ' + hata if hata else sonuc['arama_sorulari']}", flush=True)
        dosya.write_text(json.dumps(onbellek, ensure_ascii=False, indent=2), encoding="utf-8")
    return onbellek


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--set", default="test", choices=["test", "demo"])
    p.add_argument("--yeniden", action="store_true")
    a = p.parse_args()
    talepler = [t for t in json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))["talepler"]
                if t["set"] == a.set]
    sin = siniflandirmalar(talepler, RAPORLAR / f"arama_talep_{a.set}_siniflandirma.json", a.yeniden)
    isit()

    satirlar, ozet = [], {v[0]: {"hepsi": 0, "biri": 0, "bulunan": 0, "beklenen": 0, "gizli": 0, "sure": 0.0} for v in VARYANTLAR}
    n = 0
    for t in talepler:
        bek = {ana_madde(d) for d in t["beklenen"]["dayanak"]} - HARIC
        s = sin[t["id"]]["sonuc"] or {}
        sorular = s.get("arama_sorulari", [])
        mesaj = maskele(t["mesaj"])
        satir = {"id": t["id"], "beklenen": sorted(f"{k} Md.{m}" for k, m in bek), "sorular": sorular,
                 "kategori_beklenen": t["beklenen"]["kategori"], "kategori": s.get("kategori")}
        if not bek:
            satirlar.append(satir)
            continue
        n += 1
        for ad, yontem, top_n in VARYANTLAR:
            t0 = time.perf_counter()
            sonuc = coklu_ara([mesaj] + sorular, erisim_modu="musteri", top_n=top_n, yontem=yontem)[0] if yontem \
                else ara(mesaj, erisim_modu="musteri", top_n=top_n)[0]
            o = ozet[ad]
            o["sure"] += time.perf_counter() - t0
            bulunan = {(x.kod, x.madde_no) for x in sonuc}
            kesisim = bek & bulunan
            o["hepsi"] += bek <= bulunan
            o["biri"] += bool(kesisim)
            o["bulunan"] += len(kesisim)
            o["beklenen"] += len(bek)
            o["gizli"] += sum(1 for x in sonuc if x.kod.startswith("GZL"))
            satir[ad] = {"bulunan": [f"{x.kod} Md.{x.madde_no}" for x in sonuc], "kesisim": f"{len(kesisim)}/{len(bek)}"}
        satirlar.append(satir)

    secim = max(VARYANTLAR, key=lambda v: (ozet[v[0]]["hepsi"], ozet[v[0]]["bulunan"], -v[2]))[0]
    kat_dogru = sum(1 for r in satirlar if r["kategori"] == r["kategori_beklenen"])
    hatali = sum(1 for v in sin.values() if v["hata"])
    sureler = [v["sure_sn"] for v in sin.values()]

    md = f"""# Faz 9: Talep mesajlarıyla politika araması — tek sorgu vs çoklu sorgu

**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
**Set:** `data/ornek_talepler.json` — {a.set} ({len(talepler)} talep; beklenen maddesi olan {n}). Arama: {EMBED_MODEL}, müşteri modu.
**Arama soruları:** sınıflandırıcı ({CLASSIFIER_MODEL}, düşünme kapalı) aynı çağrıda 2-3 soru yazar; mesaj + sorular RRF ile birleştirilir.
**Beklenen maddeler:** `beklenen.dayanak` (ana madde). POL-ESK-007 Madde 2 hariç (onay yetkisini kod hesaplar).
**Seçim kuralı (ölçümden önce):** "hepsi bulundu" en yüksek → eşitlikte madde duyarlılığı → eşitlikte küçük N.

| Varyant | Beklenen maddelerin hepsi bulundu | En az biri bulundu | Madde duyarlılığı | Gizli doküman | Arama süresi (ort.) |
|---|---|---|---|---|---|
"""
    for ad, _, _ in VARYANTLAR:
        o = ozet[ad]
        md += (f"| {'**' + ad + '** (seçilen)' if ad == secim else ad} | {oran(o['hepsi'], n)} | {oran(o['biri'], n)} | "
               f"{oran(o['bulunan'], o['beklenen'])} | {o['gizli']} | {round(o['sure'] / max(n, 1), 2)} sn |\n")
    md += f"""
**Sınıflandırıcı (arama soruları eklendikten sonra):** kategori doğruluğu {oran(kat_dogru, len(talepler))} (ham LLM, tarih kuralı öncesi) ·
şema hatası {hatali}/{len(talepler)} · süre ort. {round(sum(sureler) / len(sureler), 1)} sn / en uzun {max(sureler)} sn.
Karşılaştırma: arama soruları eklenmeden önce v2 tanımlarıyla test setinde 26/30 (`siniflandirma_v2.md`).

## Talep bazında

| ID | Beklenen | mesaj_top3 | rrf_top3 | donusumlu_top3 | donusumlu_top5 | Arama soruları |
|---|---|---|---|---|---|---|
"""
    for r in satirlar:
        if "mesaj_top3" not in r:
            md += f"| {r['id']} | — (yalnızca onay yetkisi) | | | | | {' · '.join(r['sorular'])} |\n"
            continue
        md += (f"| {r['id']} | {', '.join(r['beklenen'])} | {r['mesaj_top3']['kesisim']} | {r['rrf_top3']['kesisim']} | "
               f"{r['donusumlu_top3']['kesisim']} | {r['donusumlu_top5']['kesisim']} | {' · '.join(r['sorular'])} |\n")
    md += "\n## Yorum\n\nBu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.\n"
    (RAPORLAR / f"arama_talep_{a.set}.md").write_text(md, encoding="utf-8")
    (RAPORLAR / f"arama_talep_{a.set}.json").write_text(json.dumps({"ozet": ozet, "secim": secim, "satirlar": satirlar},
                                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
