"""OpsPilot MCP HTTP sunucusu (127.0.0.1:8001/mcp).

Ders kodu `7. Gün Kodlar Tekrar/mcp_sunucusu.py`'den geliştirildi: FastMCP streamable HTTP, trace_tool ile her
isteğin/yanıtın konsola ve mcp_calls tablosuna yazılması. OpsPilot araçları: politika_ara (Faz 3 RAG),
siparis_getir, talep_kaydet, analiz_kaydet, karar_kaydet (onay token'ı zorunlu), talep_getir, talep_listele,
olay_kaydet. Onay token'ı üretimi bilerek MCP aracı DEĞİLDİR: agent kendine token üretemez.

Çalıştırma: .\\.venv\\Scripts\\python.exe -m app.mcp_sunucusu
"""
from __future__ import annotations

import functools
import inspect
import json
import time
import uuid
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from config import MCP_HOST, MCP_PORT
from app import veritabani as V
from app.rag.search import ara

mcp = FastMCP("OpsPilot AI", host=MCP_HOST, port=MCP_PORT, stateless_http=True, json_response=True)


def show(etiket, veri):
    print(f"[MCP {datetime.now().strftime('%H:%M:%S')}] {etiket}: "
          + json.dumps(veri, ensure_ascii=False, default=str)[:600], flush=True)


def trace_tool(func):
    """Her aracı sarmalar: argümanlar + yanıt + hata konsola ve mcp_calls tablosuna (ders: trace_tool)."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        call_id = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        argumanlar = dict(inspect.signature(func).bind_partial(*args, **kwargs).arguments)
        show("İSTEK", {"call_id": call_id, "tool": func.__name__, "arguments": argumanlar})
        try:
            sonuc = func(*args, **kwargs)
            ms = round((time.perf_counter() - t0) * 1000)
            show("YANIT", {"call_id": call_id, "duration_ms": ms, "result": sonuc})
            V.log_tool_call(call_id, func.__name__, argumanlar, sonuc, True, ms)
            return sonuc
        except Exception as exc:
            ms = round((time.perf_counter() - t0) * 1000)
            hata = f"{type(exc).__name__}: {exc}"
            show("HATA", {"call_id": call_id, "error": hata})
            V.log_tool_call(call_id, func.__name__, argumanlar, None, False, ms, hata)
            raise
    return wrapper


@mcp.tool()
@trace_tool
def politika_ara(soru: str, erisim_modu: str = "ic") -> dict:
    """Politika maddelerini arar (bge-m3 + Chroma). erisim_modu='musteri' ise gizli dokümanlar aramaya girmez."""
    sonuclar, sure = ara(soru, erisim_modu=erisim_modu)
    return {"sure_sn": sure, "sonuclar": [
        {"kaynak": s.kaynak, "kod": s.kod, "madde_no": s.madde_no, "madde_baslik": s.madde_baslik,
         "erisim": s.erisim, "benzerlik": s.benzerlik, "icerik": s.icerik} for s in sonuclar]}


@mcp.tool()
@trace_tool
def siparis_getir(siparis_no: str) -> dict:
    """Sipariş, kalemler ve müşteri özetini getirir (e-posta gibi kişisel veriler dönmez)."""
    return V.siparis_getir(siparis_no)


@mcp.tool()
@trace_tool
def musteri_getir(musteri_id: str) -> dict:
    """Müşteri adı ve son 30 gündeki şikâyet sayısını getirir."""
    return V.musteri_getir(musteri_id) or {"bulundu": False}


@mcp.tool()
@trace_tool
def talep_kaydet(mesaj: str, musteri_id: str, siparis_no: str, kanal: str, operation_key: str) -> dict:
    """Gelen talebi YENI durumunda kaydeder; aynı operation_key ikinci kayıt açmaz."""
    return V.talep_kaydet(mesaj, musteri_id or None, siparis_no or None, kanal, operation_key)


@mcp.tool()
@trace_tool
def analiz_kaydet(talep_no: str, analiz_json: str) -> dict:
    """Agent analizini (öneri + taslak) ONAY_BEKLIYOR olarak saklar; bu bir karar değildir."""
    return V.analiz_kaydet(talep_no, json.loads(analiz_json))


@mcp.tool()
@trace_tool
def karar_kaydet(talep_no: str, karar: str, onay_token: str, gerekli_onay: str, ai_onerisi: str, ai_taslak: str,
                 gonderilen_yanit: str, eskalasyon_birimi: str, gerekce: str, dayanak: str, operation_key: str) -> dict:
    """Çalışan kararını kaydeder. Geçerli, kullanılmamış onay token'ı ve yeterli rol zorunludur."""
    return V.karar_kaydet(talep_no, karar, onay_token, gerekli_onay, ai_onerisi, ai_taslak, gonderilen_yanit,
                          eskalasyon_birimi or None, gerekce, dayanak, operation_key)


@mcp.tool()
@trace_tool
def talep_getir(talep_no: str) -> dict:
    """Talep, analiz, kararlar ve agent adım olaylarını getirir."""
    return V.talep_getir(talep_no)


@mcp.tool()
@trace_tool
def talep_listele(limit: int = 50) -> dict:
    """Son talepleri listeler."""
    return {"talepler": V.talep_listele(limit)}


@mcp.tool()
@trace_tool
def olay_kaydet(thread_id: str, talep_no: str, node_name: str, event_type: str, details: str, operation_key: str) -> dict:
    """LangGraph düğüm olayını workflow_events tablosuna ekler."""
    return V.workflow_event(thread_id, talep_no or None, node_name, event_type, json.loads(details), operation_key)


if __name__ == "__main__":
    print("=" * 60)
    print(f"OpsPilot MCP SERVER — http://{MCP_HOST}:{MCP_PORT}/mcp (yalnızca yerel)")
    print("SQLite:", V.init_db())
    print("=" * 60, flush=True)
    mcp.run(transport="streamable-http")
