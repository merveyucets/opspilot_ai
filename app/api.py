"""OpsPilot FastAPI köprüsü + web paneli (127.0.0.1:8000).

Ders kodu `7. Gün Kodlar Tekrar/api_kopru.py`'den geliştirildi: lifespan içinde SqliteSaver ile graf,
interrupt'ta bekleyen thread'i Command(resume=...) ile sürdürme.

Faz 9 eklemeleri (panel):
- Analiz arka planda tek işçili kuyrukta çalışır (CPU'da modeller paylaşılır); panel ilerlemeyi agent'ın
  workflow_events kayıtlarından okur. `bekle=true` (varsayılan) eski eşzamanlı davranıştır (n8n akışı bunu kullanır).
- Müşteri uç noktaları (/musteri/...) yalnızca app/panel.musteri_gorunumu biçimini döndürür: yapay zekâ önerisi,
  gerekçe, uyarı ve onaylanmamış taslak müşteriye gitmez (altın kural 2 ve 4).

Uç noktalar:
  GET  /  (yeni panel) · /eski (önceki panel) · /health · /sistem
  POST /analyze                    → talebi kaydet + agent analizi (bekle=false: kuyruğa al, hemen dön)
  POST /tickets/{no}/yeniden-analiz → yarıda kalan / hatalı analizi yeniden kuyruğa al
  POST /approve                    → çalışan kararı: tek kullanımlık onay token'ı burada (insan eylemiyle) üretilir
  GET  /tickets, /tickets/{no}, /istatistik, /politika/{kod}/{madde}, /demo-talepler, /ek-turleri
  GET  /musteri/liste, /musteri/{id}/siparisler, /musteri/{id}/talepler · POST /musteri/{id}/talep

Çalıştırma (MCP sunucusu açıkken):
  .\\.venv\\Scripts\\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib import request

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from config import CHECKPOINT_PATH, DATA_DIR, INGEST_API_KEY, MCP_URL, OLLAMA_URL, CLASSIFIER_MODEL, WRITER_MODEL, EMBED_MODEL
from app import kurallar as K
from app import panel as P
from app import veritabani as V
from app.agent.graf import build_graph, config, get_prompt, maskele
from app.mcp_istemcisi import call
from app.politika_metni import madde_getir

WEB = Path(__file__).resolve().parent / "web"
ROLLER = ["DESTEK_UZMANI", "TAKIM_LIDERI", "OPERASYON_MUDURU"]


class TalepIn(BaseModel):
    mesaj: str = Field(min_length=1, max_length=4000)
    musteri_id: str = ""
    siparis_no: str = ""
    kanal: str = "PANEL"
    ekler: list[str] = Field(default_factory=list, max_length=10)   # ek TÜRLERİ (kurallar.EK_TURLERI)
    operation_key: str | None = None
    bekle: bool = True   # False: analiz arka planda kuyruğa alınır, yanıt hemen döner (panel)


class MusteriTalepIn(BaseModel):
    mesaj: str = Field(min_length=10, max_length=4000)
    siparis_no: str = ""
    ekler: list[str] = Field(default_factory=list, max_length=10)


class KararIn(BaseModel):
    talep_no: str
    karar: str = Field(pattern="^(ONAYLA|DUZENLE_ONAYLA|ESKALE_ET|REDDET)$")
    calisan: str = "demo_uzman"
    rol: str = Field(default="DESTEK_UZMANI", pattern="^(DESTEK_UZMANI|TAKIM_LIDERI|OPERASYON_MUDURU)$")
    yanit_metni: str | None = Field(default=None, max_length=4000)
    gerekce: str = Field(default="", max_length=1000)
    eskalasyon_birimi: str = Field(default="", max_length=60)


# --- Analiz kuyruğu: tek işçi (CPU'da iki analiz aynı modeli paylaşıp birbirini yavaşlatmasın) ---
class Kuyruk:
    def __init__(self):
        self.havuz = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analiz")
        self.kilit = threading.Lock()
        self.bekleyen: list[str] = []   # sırayla: çalışan + bekleyenler
        self.calisan: str | None = None
        self.hatalar: dict[str, str] = {}

    def ekle(self, talep_no: str, is_):
        with self.kilit:
            if talep_no in self.bekleyen:
                return
            self.bekleyen.append(talep_no)
            self.hatalar.pop(talep_no, None)
        self.havuz.submit(self._calistir, talep_no, is_)

    def _calistir(self, talep_no: str, is_):
        with self.kilit:
            self.calisan = talep_no
        try:
            is_()
        except Exception as e:   # panelde "yeniden dene" gösterilir
            with self.kilit:
                self.hatalar[talep_no] = f"{type(e).__name__}: {e}"[:300]
        finally:
            with self.kilit:
                self.calisan = None
                if talep_no in self.bekleyen:
                    self.bekleyen.remove(talep_no)

    def durum(self):
        with self.kilit:
            return list(self.bekleyen), self.calisan, dict(self.hatalar)


@asynccontextmanager
async def lifespan(app: FastAPI):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    V.init_db()
    app.state.kuyruk = Kuyruk()
    with SqliteSaver.from_conn_string(str(CHECKPOINT_PATH)) as saver:
        app.state.graph = build_graph(saver)
        yield
    app.state.kuyruk.havuz.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="OpsPilot AI API", lifespan=lifespan)


def thread_of(talep_no: str) -> str:
    return f"thr-{talep_no}"


def _analiz_et(talep_no: str, girdi: dict) -> dict | None:
    """Agent'ı interrupt noktasına kadar çalıştırır. Yarıda kalmış bir thread varsa kaldığı yerden sürdürür."""
    g = app.state.graph
    cfg = config(thread_of(talep_no))
    st = g.get_state(cfg)
    if st and st.next and st.next[0] == "calisan_karari":
        return st.tasks[0].interrupts[0].value
    out = g.invoke(None if (st and st.values and st.next) else girdi, cfg)
    prompt = get_prompt(out)
    if not prompt:
        raise RuntimeError("Agent interrupt olmadan bitti")
    return prompt


def _girdi(talep_no: str, t: dict, ekler: list[str]) -> dict:
    return {"thread_id": thread_of(talep_no), "talep_no": talep_no, "mesaj": t["mesaj"],
            "musteri_id": t.get("musteri_id") or "", "siparis_no": t.get("siparis_no") or "",
            "kanal": t.get("kanal") or "PANEL", "ekler": K.ekleri_dogrula(ekler)}


def _talep_al(mesaj: str, musteri_id: str, siparis_no: str, kanal: str, ekler: list[str], operation_key: str | None) -> str:
    talep = call("talep_kaydet", {"mesaj": mesaj, "musteri_id": musteri_id, "siparis_no": siparis_no, "kanal": kanal,
                                  "operation_key": operation_key or uuid.uuid4().hex})
    if not talep.get("idempotent"):
        V.talep_ekleri_kaydet(talep["talep_no"], K.ekleri_dogrula(ekler))
    return talep["talep_no"]


# ---------------- Sayfalar ve sistem ----------------
@app.get("/", response_class=HTMLResponse)
def panel():
    return (WEB / "index.html").read_text(encoding="utf-8")


@app.get("/eski", response_class=HTMLResponse)
def eski_panel():
    return (WEB / "eski.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "service": "OpsPilot AI"}


def _http_ok(url: str) -> tuple[bool, dict | None]:
    try:
        with request.urlopen(url, timeout=1.5) as r:
            return True, json.loads(r.read() or b"null")
    except Exception as e:   # MCP GET isteğine 406 döner: sunucu ayakta demektir
        return getattr(e, "code", None) is not None, None


@app.get("/sistem")
def sistem():
    """Üst çubuktaki durum noktaları: Ollama, yüklü modeller, MCP sunucusu."""
    ollama, ps = _http_ok(f"{OLLAMA_URL}/api/ps")
    mcp, _ = _http_ok(MCP_URL)
    yuklu = [m["name"] for m in (ps or {}).get("models", [])]
    kuyruk, calisan, _ = app.state.kuyruk.durum()
    return {"ollama": ollama, "mcp": mcp, "yuklu_modeller": yuklu,
            "modeller": {"siniflandirma": CLASSIFIER_MODEL, "yazim": WRITER_MODEL, "arama": EMBED_MODEL},
            "model_sicak": any(m.startswith(WRITER_MODEL) for m in yuklu), "kuyruk": len(kuyruk), "calisan": calisan}


# ---------------- Analiz ve karar ----------------
@app.post("/analyze")
def analyze(t: TalepIn, x_api_key: str | None = Header(default=None)):
    """Talebi kaydeder ve agent'ı interrupt noktasına kadar çalıştırır (CPU'da birkaç dakika).
    bekle=false: analiz kuyruğa alınır, yanıt hemen döner; panel ilerlemeyi /tickets/{no} ile izler."""
    if INGEST_API_KEY and t.kanal == "N8N" and x_api_key != INGEST_API_KEY:
        raise HTTPException(401, "Geçersiz API anahtarı")
    talep_no = _talep_al(t.mesaj, t.musteri_id, t.siparis_no, t.kanal, t.ekler, t.operation_key)
    girdi = _girdi(talep_no, t.model_dump(), t.ekler)
    if not t.bekle:
        app.state.kuyruk.ekle(talep_no, lambda: _analiz_et(talep_no, girdi))
        return {"talep_no": talep_no, "durum": "ANALIZ_KUYRUKTA"}
    prompt = _analiz_et(talep_no, girdi)
    return {"talep_no": talep_no, "durum": "ONAY_BEKLIYOR", "analiz": prompt["analiz"]}


@app.post("/tickets/{talep_no}/yeniden-analiz")
def yeniden_analiz(talep_no: str):
    r = V.talep_getir(talep_no)
    if not r["bulundu"]:
        raise HTTPException(404, "Talep bulunamadı")
    if r["talep"]["durum"] in P.KARAR_DURUMLARI:
        raise HTTPException(409, "Bu talep için karar verilmiş")
    girdi = _girdi(talep_no, r["talep"], r["talep"]["ekler"])
    app.state.kuyruk.ekle(talep_no, lambda: _analiz_et(talep_no, girdi))
    return {"talep_no": talep_no, "durum": "ANALIZ_KUYRUKTA"}


@app.post("/approve")
def approve(k: KararIn):
    """Çalışan kararı. Token yalnızca burada üretilir ve agent'a resume ile verilir (altın kural 2)."""
    cfg = config(thread_of(k.talep_no))
    st = app.state.graph.get_state(cfg)
    if not (st and st.next and st.next[0] == "calisan_karari"):
        raise HTTPException(409, "Bu talep karar beklemiyor")
    gerekli = st.values["guvenlik"]["gerekli_onay"]
    if k.karar in ("ONAYLA", "DUZENLE_ONAYLA") and ROLLER.index(k.rol) < ROLLER.index(gerekli):
        raise HTTPException(403, f"Yetersiz yetki: {k.rol} bu işlemi onaylayamaz (gerekli: {gerekli}). Eskale edebilirsiniz.")
    if k.karar in ("ONAYLA", "DUZENLE_ONAYLA") and not (k.yanit_metni or st.values.get("yanit_taslagi") or "").strip():
        raise HTTPException(422, "Müşteriye gönderilecek yanıt boş olamaz")
    token = V.onay_token_uret(k.talep_no, k.calisan, k.rol)
    out = app.state.graph.invoke(Command(resume={"karar": k.karar, "onay_token": token, "yanit_metni": k.yanit_metni,
                                                 "gerekce": k.gerekce, "eskalasyon_birimi": k.eskalasyon_birimi}), cfg)
    sonuc = out.get("sonuc", {})
    if not sonuc.get("kaydedildi"):
        raise HTTPException(403, sonuc.get("hata", "Karar kaydedilemedi"))
    return sonuc


# ---------------- Temsilci ekranı ----------------
def _tamamlanan(olaylar: list[dict]) -> set[str]:
    return {o["node_name"] for o in olaylar}


@app.get("/tickets")
def tickets():
    kuyruk, calisan, hatalar = app.state.kuyruk.durum()
    liste = V.panel_listesi()
    g = app.state.graph
    for t in liste:
        # Analizi olup kararı olmayan talep gerçekten çalışan kararını mı bekliyor? (eski/yarım kalmış oturumlar ayrılır)
        st = g.get_state(config(thread_of(t["talep_no"]))) if t["analiz_var"] and not t["karar"] else None
        t["karar_bekliyor"] = bool(st and st.next and st.next[0] == "calisan_karari")
        t["ekler"] = json.loads(t.pop("ekler_json") or "[]")
        t["eskalasyon"] = json.loads(t["eskalasyon"] or "[]")
        t["injection"] = bool(t["injection"])
        tamam = {a for a, _ in P.ANALIZ_ADIMLARI[: t["adim"]]}   # liste için yaklaşık; ayrıntıda gerçek adlar kullanılır
        t["analiz_durumu"] = P.analiz_durumu(t["talep_no"], bool(t["analiz_var"]), tamam, kuyruk, calisan, hatalar)
    return liste


@app.get("/tickets/{talep_no}")
def ticket(talep_no: str):
    r = V.talep_getir(talep_no)
    if not r["bulundu"]:
        raise HTTPException(404, "Talep bulunamadı")
    t = r["talep"]
    st = app.state.graph.get_state(config(thread_of(talep_no)))
    r["karar_bekliyor"] = bool(st and st.next and st.next[0] == "calisan_karari")
    kuyruk, calisan, hatalar = app.state.kuyruk.durum()
    r["analiz_durumu"] = P.analiz_durumu(talep_no, t["analiz"] is not None, _tamamlanan(r["olaylar"]), kuyruk, calisan, hatalar)
    r["adimlar"] = [{"ad": a, "etiket": e} for a, e in P.ANALIZ_ADIMLARI]
    sp = V.siparis_getir(t["siparis_no"]) if t.get("siparis_no") else {"bulundu": False}
    r["siparis"] = sp.get("siparis") if sp.get("bulundu") else None
    r["musteri"] = sp.get("musteri") if sp.get("bulundu") else (V.musteri_getir(t["musteri_id"]) if t.get("musteri_id") else None)
    r["zaman_cizelgesi"] = K.zaman_cizelgesi(r["siparis"], date.today())
    # Temsilci de kişisel veriyi maskeli görür (POL-ILT-008 Madde 6); talimat iddiası içeren cümleler işaretlenir
    maskeli = maskele(t["mesaj"])
    r["mesaj_parcalari"] = K.mesaj_isaretle(maskeli)
    r["mesaj_maskelendi"] = maskeli != t["mesaj"]
    t["mesaj"] = maskeli
    for o in r["olaylar"]:
        o.pop("details_json", None)
    return r


@app.get("/istatistik")
def istatistik():
    return V.istatistik()


@app.get("/politika/{kod}/{madde_no}")
def politika(kod: str, madde_no: int):
    m = madde_getir(kod, madde_no)
    if not m:
        raise HTTPException(404, "Madde bulunamadı")
    return m


@app.get("/demo-talepler")
def demo_talepler():
    veri = json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))
    return [{"id": t["id"], "set": t["set"], "mesaj": t["mesaj"], "musteri_id": t["musteri_id"],
             "siparis_no": t["siparis_no"] or "", "kanal": t["kanal"], "ekler": t["ekler"]} for t in veri["talepler"]]


@app.get("/ek-turleri")
def ek_turleri():
    return K.EK_TURLERI


# ---------------- Müşteri ekranı (yalnızca müşteriye ait, güvenli alanlar) ----------------
def _musteri_var(musteri_id: str) -> dict:
    m = V.musteri_getir(musteri_id)
    if not m:
        raise HTTPException(404, "Müşteri bulunamadı")
    return m


@app.get("/musteri/liste")
def musteri_liste():
    return V.musteri_listesi()


@app.get("/musteri/{musteri_id}/siparisler")
def musteri_siparisler(musteri_id: str):
    _musteri_var(musteri_id)
    return V.musteri_siparisleri(musteri_id)


@app.get("/musteri/{musteri_id}/talepler")
def musteri_talepler(musteri_id: str):
    _musteri_var(musteri_id)
    return [dict(P.musteri_gorunumu(t), mesaj=maskele(t["mesaj"])) for t in V.musteri_talepleri(musteri_id)]


@app.post("/musteri/{musteri_id}/talep")
def musteri_talep(musteri_id: str, t: MusteriTalepIn):
    _musteri_var(musteri_id)
    if t.siparis_no and t.siparis_no not in {s["siparis_no"] for s in V.musteri_siparisleri(musteri_id)}:
        raise HTTPException(400, "Bu sipariş size ait değil")
    talep_no = _talep_al(t.mesaj, musteri_id, t.siparis_no, "WEB_FORM", t.ekler, None)
    girdi = _girdi(talep_no, {"mesaj": t.mesaj, "musteri_id": musteri_id, "siparis_no": t.siparis_no,
                              "kanal": "WEB_FORM"}, t.ekler)
    app.state.kuyruk.ekle(talep_no, lambda: _analiz_et(talep_no, girdi))
    return {"talep_no": talep_no, "asama": "ALINDI"}
