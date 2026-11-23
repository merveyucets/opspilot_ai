"""OpsPilot FastAPI köprüsü + web paneli (127.0.0.1:8000).

Ders kodu `7. Gün Kodlar Tekrar/api_kopru.py`'den geliştirildi: lifespan içinde SqliteSaver ile graf,
interrupt'ta bekleyen thread'i Command(resume=...) ile sürdürme.

Uç noktalar:
  GET  /                 → destek uzmanı paneli (app/web/index.html)
  POST /analyze          → talebi kaydet + agent analizi (çalışan kararını bekler)
  POST /approve          → çalışan kararı: tek kullanımlık onay token'ı burada (insan eylemiyle) üretilir
  GET  /tickets, /tickets/{talep_no}, /demo-talepler, /ek-turleri, /health

Çalıştırma (MCP sunucusu açıkken):
  .\\.venv\\Scripts\\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from config import CHECKPOINT_PATH, DATA_DIR, INGEST_API_KEY
from app import kurallar as K
from app import veritabani as V
from app.agent.graf import build_graph, config, get_prompt
from app.mcp_istemcisi import call

WEB = Path(__file__).resolve().parent / "web" / "index.html"


class TalepIn(BaseModel):
    mesaj: str = Field(min_length=1, max_length=4000)
    musteri_id: str = ""
    siparis_no: str = ""
    kanal: str = "PANEL"
    ekler: list[str] = Field(default_factory=list, max_length=10)   # ek TÜRLERİ (kurallar.EK_TURLERI)
    operation_key: str | None = None


class KararIn(BaseModel):
    talep_no: str
    karar: str = Field(pattern="^(ONAYLA|DUZENLE_ONAYLA|ESKALE_ET|REDDET)$")
    calisan: str = "demo_uzman"
    rol: str = Field(default="DESTEK_UZMANI", pattern="^(DESTEK_UZMANI|TAKIM_LIDERI|OPERASYON_MUDURU)$")
    yanit_metni: str | None = None
    gerekce: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    V.init_db()
    with SqliteSaver.from_conn_string(str(CHECKPOINT_PATH)) as saver:
        app.state.graph = build_graph(saver)
        yield


app = FastAPI(title="OpsPilot AI API", lifespan=lifespan)


def thread_of(talep_no: str) -> str:
    return f"thr-{talep_no}"


@app.get("/", response_class=HTMLResponse)
def panel():
    return WEB.read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "service": "OpsPilot AI"}


@app.post("/analyze")
def analyze(t: TalepIn, x_api_key: str | None = Header(default=None)):
    """Talebi kaydeder ve agent'ı interrupt noktasına kadar çalıştırır (CPU'da ~1-2 dk)."""
    if INGEST_API_KEY and t.kanal == "N8N" and x_api_key != INGEST_API_KEY:
        raise HTTPException(401, "Geçersiz API anahtarı")
    talep = call("talep_kaydet", {"mesaj": t.mesaj, "musteri_id": t.musteri_id, "siparis_no": t.siparis_no,
                                  "kanal": t.kanal, "operation_key": t.operation_key or uuid.uuid4().hex})
    cfg = config(thread_of(talep["talep_no"]))
    st = app.state.graph.get_state(cfg)
    if st and st.next:   # aynı talep zaten analiz edildi ve karar bekliyor (idempotent)
        return {"talep_no": talep["talep_no"], "durum": "ONAY_BEKLIYOR", "analiz": st.tasks[0].interrupts[0].value["analiz"]}
    out = app.state.graph.invoke({"thread_id": thread_of(talep["talep_no"]), "talep_no": talep["talep_no"],
                                  "mesaj": t.mesaj, "musteri_id": t.musteri_id, "siparis_no": t.siparis_no,
                                  "kanal": t.kanal, "ekler": K.ekleri_dogrula(t.ekler)}, cfg)
    prompt = get_prompt(out)
    if not prompt:
        raise HTTPException(500, "Agent beklenmedik şekilde interrupt olmadan bitti")
    return {"talep_no": talep["talep_no"], "durum": "ONAY_BEKLIYOR", "analiz": prompt["analiz"]}


@app.post("/approve")
def approve(k: KararIn):
    """Çalışan kararı. Token yalnızca burada üretilir ve agent'a resume ile verilir (altın kural 2)."""
    cfg = config(thread_of(k.talep_no))
    st = app.state.graph.get_state(cfg)
    if not (st and st.next and st.next[0] == "calisan_karari"):
        raise HTTPException(409, "Bu talep karar beklemiyor")
    gerekli = st.values["guvenlik"]["gerekli_onay"]
    sira = ["DESTEK_UZMANI", "TAKIM_LIDERI", "OPERASYON_MUDURU"]
    if k.karar in ("ONAYLA", "DUZENLE_ONAYLA") and sira.index(k.rol) < sira.index(gerekli):
        raise HTTPException(403, f"Yetersiz yetki: {k.rol} bu işlemi onaylayamaz (gerekli: {gerekli}). Eskale edebilirsiniz.")
    token = V.onay_token_uret(k.talep_no, k.calisan, k.rol)
    out = app.state.graph.invoke(Command(resume={"karar": k.karar, "onay_token": token, "yanit_metni": k.yanit_metni,
                                                 "gerekce": k.gerekce}), cfg)
    sonuc = out.get("sonuc", {})
    if not sonuc.get("kaydedildi"):
        raise HTTPException(403, sonuc.get("hata", "Karar kaydedilemedi"))
    return sonuc


@app.get("/tickets")
def tickets():
    return V.talep_listele()


@app.get("/tickets/{talep_no}")
def ticket(talep_no: str):
    r = V.talep_getir(talep_no)
    if not r["bulundu"]:
        raise HTTPException(404, "Talep bulunamadı")
    st = app.state.graph.get_state(config(thread_of(talep_no)))
    r["karar_bekliyor"] = bool(st and st.next and st.next[0] == "calisan_karari")
    return r


@app.get("/demo-talepler")
def demo_talepler():
    veri = json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))
    return [{"id": t["id"], "set": t["set"], "mesaj": t["mesaj"], "musteri_id": t["musteri_id"],
             "siparis_no": t["siparis_no"] or "", "kanal": t["kanal"], "ekler": t["ekler"]} for t in veri["talepler"]]


@app.get("/ek-turleri")
def ek_turleri():
    return K.EK_TURLERI
