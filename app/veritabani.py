"""SQLite iş verileri; MCP araçlarının çağırdığı veri erişim katmanı.

Ders kodu `7. Gün Kodlar Tekrar/veritabani.py`'den geliştirildi: connect() bağlam yöneticisi, operation_key ile
idempotency, workflow_events ve mcp_calls izleme tabloları. OpsPilot eklemeleri:
- Sipariş/müşteri seed'i (data/siparisler_seed.json; *_gun_once → bugünün tarihine göre gerçek tarih)
- Karar kaydı yalnızca tek kullanımlık onay token'ı ile (altın kural 2)
"""
from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, DATA_DIR  # noqa: E402

GECERLI_KARARLAR = {"ONAYLA", "DUZENLE_ONAYLA", "ESKALE_ET", "REDDET"}
ROLLER = {"DESTEK_UZMANI", "TAKIM_LIDERI", "OPERASYON_MUDURU"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> str:
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS musteriler(
          musteri_id TEXT PRIMARY KEY, ad_soyad TEXT NOT NULL, eposta TEXT, son_30_gun_sikayet INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS siparisler(
          siparis_no TEXT PRIMARY KEY, musteri_id TEXT NOT NULL REFERENCES musteriler(musteri_id),
          durum TEXT NOT NULL, siparis_tarihi TEXT, kargo_tarihi TEXT, teslim_tarihi TEXT,
          odeme_yontemi TEXT, taksit_sayisi INTEGER, kargo_ucreti REAL, kampanya_json TEXT,
          degisim_sayisi INTEGER, telafi_kuponu_tl REAL, kalemler_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS talepler(
          talep_no TEXT UNIQUE, id INTEGER PRIMARY KEY AUTOINCREMENT, operation_key TEXT NOT NULL UNIQUE,
          musteri_id TEXT, siparis_no TEXT, kanal TEXT, mesaj TEXT NOT NULL, durum TEXT NOT NULL,
          analiz_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS onay_tokenlari(
          token TEXT PRIMARY KEY, talep_no TEXT NOT NULL REFERENCES talepler(talep_no),
          calisan TEXT NOT NULL, rol TEXT NOT NULL, kullanildi INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS kararlar(
          id INTEGER PRIMARY KEY AUTOINCREMENT, talep_no TEXT NOT NULL REFERENCES talepler(talep_no),
          karar TEXT NOT NULL, calisan TEXT NOT NULL, rol TEXT NOT NULL, gerekli_onay TEXT,
          ai_onerisi TEXT, ai_taslak TEXT, gonderilen_yanit TEXT, duzenlendi INTEGER NOT NULL,
          eskalasyon_birimi TEXT, gerekce TEXT, dayanak TEXT, operation_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workflow_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT NOT NULL, talep_no TEXT, node_name TEXT NOT NULL,
          event_type TEXT NOT NULL, details_json TEXT NOT NULL, operation_key TEXT UNIQUE, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mcp_calls(
          id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL UNIQUE, tool_name TEXT NOT NULL,
          arguments_json TEXT NOT NULL, response_json TEXT, success INTEGER NOT NULL, duration_ms INTEGER NOT NULL,
          error_message TEXT, created_at TEXT NOT NULL);
        """)
    return str(DB_PATH)


def seed(bugun: date | None = None) -> dict:
    """Müşteri ve sipariş verisini yeniden yükler; gün farkları bugüne göre gerçek tarihe çevrilir."""
    bugun = bugun or date.today()
    veri = json.loads((DATA_DIR / "siparisler_seed.json").read_text(encoding="utf-8"))

    def tarih(gun):
        return None if gun is None else (bugun - timedelta(days=gun)).isoformat()

    init_db()
    with connect() as c:
        c.execute("DELETE FROM siparisler")
        c.execute("DELETE FROM musteriler")
        for m in veri["musteriler"]:
            c.execute("INSERT INTO musteriler VALUES(?,?,?,?)",
                      (m["musteri_id"], m["ad_soyad"], m["eposta"], m["son_30_gun_sikayet"]))
        for s in veri["siparisler"]:
            c.execute("INSERT INTO siparisler VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                s["siparis_no"], s["musteri_id"], s["durum"], tarih(s["siparis_gun_once"]),
                tarih(s["kargo_gun_once"]), tarih(s["teslim_gun_once"]), s["odeme_yontemi"], s["taksit_sayisi"],
                s["kargo_ucreti"], json.dumps(s["kampanya"], ensure_ascii=False), s["degisim_sayisi"],
                s["telafi_kuponu_tl"], json.dumps(s["kalemler"], ensure_ascii=False)))
    return {"musteri": len(veri["musteriler"]), "siparis": len(veri["siparisler"]), "bugun": bugun.isoformat()}


def siparis_getir(siparis_no: str) -> dict:
    """Sipariş + müşteri (kişisel veriden yalnızca ad ve şikâyet sayısı döner)."""
    with connect() as c:
        s = c.execute("SELECT * FROM siparisler WHERE siparis_no=?", (siparis_no,)).fetchone()
        if not s:
            return {"bulundu": False, "siparis_no": siparis_no}
        m = c.execute("SELECT musteri_id, ad_soyad, son_30_gun_sikayet FROM musteriler WHERE musteri_id=?",
                      (s["musteri_id"],)).fetchone()
        siparis = dict(s)
        siparis["kampanya"] = json.loads(siparis.pop("kampanya_json") or "null")
        siparis["kalemler"] = json.loads(siparis.pop("kalemler_json"))
        return {"bulundu": True, "siparis": siparis, "musteri": dict(m)}


def musteri_getir(musteri_id: str) -> dict | None:
    with connect() as c:
        m = c.execute("SELECT musteri_id, ad_soyad, son_30_gun_sikayet FROM musteriler WHERE musteri_id=?",
                      (musteri_id,)).fetchone()
        return dict(m) if m else None


def talep_kaydet(mesaj: str, musteri_id: str | None, siparis_no: str | None, kanal: str, operation_key: str) -> dict:
    """Gelen talebi YENI durumunda kaydeder (karar değildir); aynı operation_key ikinci kez kayıt açmaz."""
    if not mesaj.strip() or len(mesaj) > 4000:
        raise ValueError("Mesaj boş olamaz ve 4000 karakteri aşamaz")
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        var = c.execute("SELECT talep_no, durum FROM talepler WHERE operation_key=?", (operation_key,)).fetchone()
        if var:
            return {"talep_no": var["talep_no"], "durum": var["durum"], "idempotent": True}
        t = now()
        cur = c.execute("INSERT INTO talepler(operation_key,musteri_id,siparis_no,kanal,mesaj,durum,created_at,updated_at)"
                        " VALUES(?,?,?,?,?,?,?,?)", (operation_key, musteri_id, siparis_no, kanal, mesaj, "YENI", t, t))
        talep_no = f"TLP-{1000 + cur.lastrowid}"
        c.execute("UPDATE talepler SET talep_no=? WHERE id=?", (talep_no, cur.lastrowid))
        return {"talep_no": talep_no, "durum": "YENI", "idempotent": False}


def analiz_kaydet(talep_no: str, analiz: dict) -> dict:
    """Agent analizini (öneri + taslak) saklar. Talep durumunu DEĞİŞTİRMEZ: durum yalnızca çalışan kararıyla
    değişir (altın kural 2). Panel, analizi olup kararı olmayan talebi 'onay bekliyor' gösterir."""
    with connect() as c:
        c.execute("UPDATE talepler SET analiz_json=?, updated_at=? WHERE talep_no=?",
                  (json.dumps(analiz, ensure_ascii=False, default=str), now(), talep_no))
    return {"talep_no": talep_no, "kaydedildi": True}


def onay_token_uret(talep_no: str, calisan: str, rol: str) -> str:
    """Çalışan panelde karar verdiğinde tek kullanımlık token üretilir (agent üretmez)."""
    if rol not in ROLLER:
        raise ValueError("Geçersiz rol")
    token = secrets.token_urlsafe(16)
    with connect() as c:
        c.execute("INSERT INTO onay_tokenlari VALUES(?,?,?,?,0,?)", (token, talep_no, calisan, rol, now()))
    return token


def karar_kaydet(talep_no: str, karar: str, onay_token: str, gerekli_onay: str, ai_onerisi: str, ai_taslak: str,
                 gonderilen_yanit: str, eskalasyon_birimi: str | None, gerekce: str, dayanak: str,
                 operation_key: str) -> dict:
    """Karar kaydı (altın kural 2): geçerli ve kullanılmamış token, yeterli rol; token tek seferde tüketilir."""
    if karar not in GECERLI_KARARLAR:
        raise ValueError(f"Geçersiz karar: {karar}")
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        var = c.execute("SELECT id FROM kararlar WHERE operation_key=?", (operation_key,)).fetchone()
        if var:
            return {"kaydedildi": True, "idempotent": True}
        tk = c.execute("SELECT * FROM onay_tokenlari WHERE token=? AND talep_no=?", (onay_token, talep_no)).fetchone()
        if not tk or tk["kullanildi"]:
            raise PermissionError("Onay token'ı geçersiz veya daha önce kullanılmış")
        sira = ["DESTEK_UZMANI", "TAKIM_LIDERI", "OPERASYON_MUDURU"]
        if karar in ("ONAYLA", "DUZENLE_ONAYLA") and sira.index(tk["rol"]) < sira.index(gerekli_onay):
            raise PermissionError(f"Yetersiz yetki: {tk['rol']} bu işlemi onaylayamaz (gerekli: {gerekli_onay})")
        c.execute("UPDATE onay_tokenlari SET kullanildi=1 WHERE token=?", (onay_token,))
        durum = {"ONAYLA": "KAPANDI", "DUZENLE_ONAYLA": "KAPANDI", "ESKALE_ET": "ESKALE_EDILDI", "REDDET": "TASLAK_REDDEDILDI"}[karar]
        c.execute("INSERT INTO kararlar(talep_no,karar,calisan,rol,gerekli_onay,ai_onerisi,ai_taslak,gonderilen_yanit,"
                  "duzenlendi,eskalasyon_birimi,gerekce,dayanak,operation_key,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (talep_no, karar, tk["calisan"], tk["rol"], gerekli_onay, ai_onerisi, ai_taslak,
                   gonderilen_yanit if karar in ("ONAYLA", "DUZENLE_ONAYLA") else None,
                   int((gonderilen_yanit or "") != (ai_taslak or "")), eskalasyon_birimi, gerekce, dayanak,
                   operation_key, now()))
        c.execute("UPDATE talepler SET durum=?, updated_at=? WHERE talep_no=?", (durum, now(), talep_no))
        return {"kaydedildi": True, "idempotent": False, "talep_no": talep_no, "durum": durum}


def talep_getir(talep_no: str) -> dict:
    with connect() as c:
        t = c.execute("SELECT * FROM talepler WHERE talep_no=?", (talep_no,)).fetchone()
        if not t:
            return {"bulundu": False}
        kararlar = [dict(r) for r in c.execute("SELECT * FROM kararlar WHERE talep_no=? ORDER BY id", (talep_no,))]
        olaylar = [dict(r) for r in c.execute(
            "SELECT node_name, event_type, details_json, created_at FROM workflow_events WHERE talep_no=? ORDER BY id", (talep_no,))]
        d = dict(t)
        d["analiz"] = json.loads(d.pop("analiz_json") or "null")
        return {"bulundu": True, "talep": d, "kararlar": kararlar, "olaylar": olaylar}


def talep_listele(limit: int = 50) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT talep_no, musteri_id, siparis_no, kanal, substr(mesaj,1,120) AS mesaj, durum, created_at "
            "FROM talepler ORDER BY id DESC LIMIT ?", (limit,))]


def workflow_event(thread_id, talep_no, node_name, event_type, details, operation_key) -> dict:
    with connect() as c:
        c.execute("INSERT OR IGNORE INTO workflow_events(thread_id,talep_no,node_name,event_type,details_json,operation_key,created_at)"
                  " VALUES(?,?,?,?,?,?,?)", (thread_id, talep_no, node_name, event_type,
                                             json.dumps(details, ensure_ascii=False, default=str), operation_key, now()))
    return {"saved": True, "node": node_name}


def log_tool_call(call_id, tool_name, arguments, result, success, duration_ms, error_message=None):
    with connect() as c:
        c.execute("INSERT INTO mcp_calls(call_id,tool_name,arguments_json,response_json,success,duration_ms,error_message,created_at)"
                  " VALUES(?,?,?,?,?,?,?,?)", (call_id, tool_name, json.dumps(arguments, ensure_ascii=False, default=str),
                                               json.dumps(result, ensure_ascii=False, default=str) if result is not None else None,
                                               int(bool(success)), duration_ms, error_message, now()))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", action="store_true", help="Müşteri/sipariş verisini bugüne göre yeniden yükle")
    a = p.parse_args()
    print("SQLite:", init_db())
    if a.seed:
        print("Seed:", seed())
