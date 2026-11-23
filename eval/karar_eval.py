"""Faz 9 — Uçtan uca karar değerlendirmesi (30 test talebi, T01–T30).

Her talep agent'ta interrupt noktasına kadar çalıştırılır (karar kaydı YAPILMAZ). Ölçülenler:
- Öneri doğruluğu (oneri birebir eşleşme) ve grup doğruluğu (karar günlüğü 2026-11-21)
- Gerekli onay rolü doğruluğu ve "eksik onay" (sistemin istediği rol beklenenden DÜŞÜK) sayısı
- Zorunlu eskalasyon birimi doğruluğu
- Güvenlik katmanı: yanlış önerilerin kaçında uyarı (⚠) üretildi
- Yanıt taslağında yasak ifade / gizli kod (GIZLI10) sızıntısı, atıf geçerliliği, süre
Talep ekleri (fotoğraf, servis fişi...) agent'a iletilir. Rapor her talepten sonra yeniden yazılır;
yarıda kalırsa --devam ile önceki JSON'daki talepler atlanır.
MCP sunucusu açık olmalı. Kullanım: python eval/karar_eval.py [--set test|demo] [--limit N] [--ids T29 T30] [--devam]
"""
import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from config import DATA_DIR, CLASSIFIER_MODEL, WRITER_MODEL  # noqa: E402
from app.agent.graf import build_graph, config, get_prompt  # noqa: E402
from app.mcp_istemcisi import call  # noqa: E402
from eval.metrikler import oran  # noqa: E402

RAPORLAR = Path(__file__).resolve().parent / "raporlar"
SIRA = ["DESTEK_UZMANI", "TAKIM_LIDERI", "OPERASYON_MUDURU"]
GRUP = {"IADE_KABUL": "ONAY", "DEGISIM_KABUL": "ONAY", "SERVISE_YONLENDIR": "ONAY", "KARGO_SORUSTURMA": "ONAY",
        "RED": "RED", "EKSIK_BILGI": "EKSIK_BILGI", "ESKALASYON": "ESKALASYON"}


def tek_talep(graph, t: dict) -> dict:
    thread = f"eval-{t['id']}-{uuid.uuid4().hex[:6]}"
    talep = call("talep_kaydet", {"mesaj": t["mesaj"], "musteri_id": t["musteri_id"], "siparis_no": t["siparis_no"] or "",
                                  "kanal": "EVAL", "operation_key": thread})
    t0 = time.perf_counter()
    out = graph.invoke({"thread_id": thread, "talep_no": talep["talep_no"], "mesaj": t["mesaj"],
                        "musteri_id": t["musteri_id"], "siparis_no": t["siparis_no"] or "", "kanal": "EVAL",
                        "ekler": t["ekler"]}, config(thread))
    sure = round(time.perf_counter() - t0, 1)
    a = get_prompt(out)["analiz"]
    b, o, g = t["beklenen"], a["oneri"], a["guvenlik"]
    bek_birim = set() if b["eskalasyon_birimi"] is None else {b["eskalasyon_birimi"]}
    taslak = a["yanit_taslagi"].lower()
    grup = "ESKALASYON" if g["eskalasyon_birimleri"] else GRUP[o["oneri"]]
    icerik_uyarilari = [u for u in g["uyarilar"] if "atıf" not in u]
    return {
        "id": t["id"], "sure_sn": sure,
        "beklenen": {"oneri": b["oneri"], "gerekli_onay": b["gerekli_onay"], "eskalasyon": sorted(bek_birim),
                     "grup": b["grup"], "kategori": b["kategori"]},
        "sistem": {"oneri": o["oneri"], "gerekli_onay": g["gerekli_onay"], "eskalasyon": sorted(g["eskalasyon_birimleri"]),
                   "grup": grup, "kategori": a["siniflandirma"]["kategori"], "uyarilar": g["uyarilar"]},
        "oneri_dogru": o["oneri"] == b["oneri"],
        "grup_dogru": grup == b["grup"],
        "kategori_dogru": a["siniflandirma"]["kategori"] == b["kategori"],
        "onay_dogru": g["gerekli_onay"] == b["gerekli_onay"],
        "eksik_onay": SIRA.index(g["gerekli_onay"]) < SIRA.index(b["gerekli_onay"]),
        "eskalasyon_dogru": set(g["eskalasyon_birimleri"]) == bek_birim,
        "uyari_var": bool(icerik_uyarilari),
        "atif_gecerli": g["atif"]["valid"],
        "yasak_ifade": [y for y in b.get("yanitta_olmamali", []) if y.lower() in taslak],
        "gizli_kod": "gizli10" in taslak,
        "gerekce": o["gerekce"], "taslak": a["yanit_taslagi"],
    }


def rapor(sonuc: list[dict], set_adi: str) -> None:
    n = len(sonuc)
    yanlis = [s for s in sonuc if not s["oneri_dogru"]]
    s_ = lambda k: sum(1 for s in sonuc if s[k])  # noqa: E731
    sureler = [s["sure_sn"] for s in sonuc]
    md = f"""# Faz 9: Uçtan Uca Karar Değerlendirmesi

**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
**Set:** `data/ornek_talepler.json` — {set_adi} ({n} talep). Agent interrupt noktasına kadar çalıştırıldı; karar kaydı yapılmadı. Talep ekleri (türleri) agent'a iletildi.
**Modeller:** sınıflandırma {CLASSIFIER_MODEL}, öneri+taslak {WRITER_MODEL} (düşünme kapalı). Arama: bge-m3, müşteri modu. Donanım: CPU.

| Metrik | Sonuç |
|---|---|
| Öneri doğruluğu (birebir) | {oran(s_('oneri_dogru'), n)} |
| Grup doğruluğu (Onay/Red/Eksik/Eskalasyon) | {oran(s_('grup_dogru'), n)} |
| Kategori doğruluğu (tarih kuralı sonrası) | {oran(s_('kategori_dogru'), n)} |
| Gerekli onay rolü doğruluğu | {oran(s_('onay_dogru'), n)} |
| **Eksik onay** (sistem beklenenden düşük rol istedi) | {s_('eksik_onay')}/{n} |
| Zorunlu eskalasyon birimi doğruluğu | {oran(s_('eskalasyon_dogru'), n)} |
| Yanlış önerilerde güvenlik uyarısı (⚠) üretildi | {oran(sum(1 for s in yanlis if s['uyari_var']), len(yanlis))} |
| Atıf geçerliliği | {oran(s_('atif_gecerli'), n)} |
| Yanıt taslağında yasak ifade | {sum(1 for s in sonuc if s['yasak_ifade'])}/{n} |
| Yanıt taslağında gizli kod (GIZLI10) | {s_('gizli_kod')}/{n} |
| Talep başına süre (ort / en uzun) | {round(sum(sureler)/n, 1)} sn / {max(sureler)} sn |

Not: Onay rolü ve eskalasyon deterministik koddan gelir; ancak rol öneriye ve ilgili ürüne bağlı olduğundan yanlış öneri rolü de etkileyebilir.

## Talep bazında

| ID | Beklenen öneri | Sistem önerisi | Beklenen onay | Sistem onayı | Eskalasyon (b / s) | Uyarı |
|---|---|---|---|---|---|---|
"""
    for s in sonuc:
        b, y = s["beklenen"], s["sistem"]
        md += (f"| {s['id']} | {b['oneri']} | {'✓ ' if s['oneri_dogru'] else '✗ '}{y['oneri']} | {b['gerekli_onay']} | "
               f"{'✓ ' if s['onay_dogru'] else '✗ '}{y['gerekli_onay']} | {','.join(b['eskalasyon']) or '-'} / "
               f"{','.join(y['eskalasyon']) or '-'} | {'⚠' if s['uyari_var'] else ''} |\n")
    md += "\n## Yorum\n\nBu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.\n"
    ad = f"karar_degerlendirme_{set_adi}"
    (RAPORLAR / f"{ad}.md").write_text(md, encoding="utf-8")
    (RAPORLAR / f"{ad}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rapor: {RAPORLAR / (ad + '.md')}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--set", default="test", choices=["test", "demo"])
    p.add_argument("--limit", type=int)
    p.add_argument("--ids", nargs="*", help="Yalnızca bu talepler (ör. T29 T30)")
    p.add_argument("--devam", action="store_true", help="Önceki JSON'daki sonuçları koru, eksik talepleri çalıştır")
    a = p.parse_args()
    talepler = [t for t in json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))["talepler"]
                if t["set"] == a.set and (not a.ids or t["id"] in a.ids)][: a.limit]
    onceki = RAPORLAR / f"karar_degerlendirme_{a.set}.json"
    sonuc = json.loads(onceki.read_text(encoding="utf-8")) if a.devam and onceki.exists() else []
    bitmis = {s["id"] for s in sonuc}
    graph = build_graph(MemorySaver())
    for i, t in enumerate(talepler, 1):
        if t["id"] in bitmis:
            print(f"{t['id']}: önceki sonuç kullanıldı", flush=True)
            continue
        try:
            r = tek_talep(graph, t)
            print(f"[{i}/{len(talepler)}] {r['id']}: öneri {'✓' if r['oneri_dogru'] else '✗'} {r['sistem']['oneri']:<18} "
                  f"onay {'✓' if r['onay_dogru'] else '✗'} esk {'✓' if r['eskalasyon_dogru'] else '✗'} {r['sure_sn']} sn", flush=True)
            sonuc.append(r)
            sonuc.sort(key=lambda s: s["id"])
            rapor(sonuc, a.set)   # her talepten sonra: yarıda kalırsa --devam ile sürdürülür
        except Exception as e:
            print(f"{t['id']}: HATA {e}", flush=True)
    if sonuc:
        rapor(sonuc, a.set)
