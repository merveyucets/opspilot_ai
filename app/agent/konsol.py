"""Konsoldan uçtan uca agent: talep → analiz → [çalışan kararı] → kayıt.

Ders kodu `7. Gün Kodlar Tekrar/04_konsol_agent.py`'den geliştirildi (SqliteSaver, Command(resume=...)).
Onay token'ı insan tarafında (bu konsol / panel) üretilir; agent token üretemez.

Önce MCP sunucusu açık olmalı:  .\\.venv\\Scripts\\python.exe -m app.mcp_sunucusu
Örnek:  .\\.venv\\Scripts\\python.exe -m app.agent.konsol --talep D01
        .\\.venv\\Scripts\\python.exe -m app.agent.konsol --talep D03 --karar REDDET --rol DESTEK_UZMANI
"""
from __future__ import annotations

import argparse
import json
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from config import CHECKPOINT_PATH, DATA_DIR
from app import veritabani as V
from app.agent.graf import build_graph, config, get_prompt
from app.mcp_istemcisi import call


def ornek_talep(talep_id: str) -> dict:
    veri = json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))
    return next(t for t in veri["talepler"] if t["id"] == talep_id)


def analizi_yaz(a: dict) -> None:
    s, o, g = a["siniflandirma"], a["oneri"], a["guvenlik"]
    print("\n" + "=" * 70)
    print(f"KATEGORİ : {s['kategori']} ({s['kaynak']}) | aciliyet {s['aciliyet']} | duygu {s['duygu']}")
    print(f"ÖNERİ    : {o['oneri']}  |  GEREKLİ ONAY: {g['gerekli_onay']}  |  işlem tutarı: {g['islem_tutari']}")
    print(f"ESKALASYON: {', '.join(g['eskalasyon_birimleri']) or '-'}")
    print(f"GEREKÇE  : {o['gerekce']}")
    print(f"DAYANAK  : {'; '.join(g['dayanak']) or '-'}")
    for u in g["uyarilar"]:
        print(f"⚠ {u}")
    print(f"\nYANIT TASLAĞI:\n{a['yanit_taslagi']}")
    print("=" * 70)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--talep", help="data/ornek_talepler.json kimliği (ör. D01)")
    p.add_argument("--mesaj")
    p.add_argument("--siparis", default="")
    p.add_argument("--musteri", default="")
    p.add_argument("--karar", choices=["ONAYLA", "DUZENLE_ONAYLA", "ESKALE_ET", "REDDET"], help="Etkileşimsiz karar")
    p.add_argument("--rol", default="DESTEK_UZMANI", choices=["DESTEK_UZMANI", "TAKIM_LIDERI", "OPERASYON_MUDURU"])
    p.add_argument("--calisan", default="demo_uzman")
    a = p.parse_args()

    if a.talep:
        t = ornek_talep(a.talep)
        mesaj, siparis, musteri, kanal = t["mesaj"], t["siparis_no"] or "", t["musteri_id"], t["kanal"]
    else:
        mesaj, siparis, musteri, kanal = a.mesaj, a.siparis, a.musteri, "KONSOL"
    thread = uuid.uuid4().hex[:10]
    talep = call("talep_kaydet", {"mesaj": mesaj, "musteri_id": musteri, "siparis_no": siparis, "kanal": kanal,
                                  "operation_key": f"konsol:{thread}"})
    print(f"Talep: {talep['talep_no']} | thread: {thread}\nMESAJ: {mesaj}")

    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(CHECKPOINT_PATH)) as saver:
        graph = build_graph(saver)
        cfg = config(thread)
        out = graph.invoke({"thread_id": thread, "talep_no": talep["talep_no"], "mesaj": mesaj,
                            "musteri_id": musteri, "siparis_no": siparis, "kanal": kanal}, cfg)
        prompt = get_prompt(out)
        if not prompt:
            print("Beklenmeyen: interrupt oluşmadı", out.get("sonuc"))
            return
        analizi_yaz(prompt["analiz"])

        karar = a.karar or input("\nKARAR [ONAYLA / DUZENLE_ONAYLA / ESKALE_ET / REDDET] > ").strip().upper()
        rol = a.rol if a.karar else (input(f"ROL [{a.rol}] > ").strip().upper() or a.rol)
        yanit = None
        if karar == "DUZENLE_ONAYLA" and not a.karar:
            yanit = input("Düzenlenmiş yanıt > ").strip()
        token = V.onay_token_uret(talep["talep_no"], a.calisan, rol)   # insan eylemi → token
        out = graph.invoke(Command(resume={"karar": karar, "onay_token": token, "yanit_metni": yanit,
                                           "gerekce": "konsol kararı"}), cfg)
        print("\nSONUÇ:", out.get("sonuc"))


if __name__ == "__main__":
    main()
