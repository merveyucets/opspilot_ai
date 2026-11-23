"""Ollama /api/chat istemcisi.

Ders kodu `7. Gün Kodlar Tekrar/llm_yardimci.py` → `chat(system, prompt, json_mode)`'dan geliştirildi:
- `format` olarak "json" yerine JSON şeması verilebilir (yapılandırılmış çıktı)
- `think` parametresi (qwen3 gibi modeller): düşünme metni Ollama'da ayrı `thinking` alanında gelir
- Süre, token sayısı ve bitiş nedeni (done_reason) ölçüm için döndürülür
"""
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import OLLAMA_URL, LLM_TIMEOUT_SN  # noqa: E402


@dataclass
class LLMYaniti:
    icerik: str          # message.content
    dusunme: str         # message.thinking (yoksa "")
    sure_sn: float       # duvar saati süresi
    uretilen_token: int  # eval_count
    bitis_nedeni: str    # "stop" | "length" ...


def chat(model: str, system: str, prompt: str, format_: dict | str | None = None,
         think: bool | None = None, options: dict | None = None) -> LLMYaniti:
    """Sistem + kullanıcı mesajıyla tek seferlik sohbet çağrısı yapar (stream kapalı)."""
    body = {
        "model": model,
        "stream": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "options": options or {"temperature": 0},
    }
    if format_ is not None:
        body["format"] = format_
    if think is not None:
        body["think"] = think
    req = request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with request.urlopen(req, timeout=LLM_TIMEOUT_SN) as r:
        obj = json.loads(r.read().decode("utf-8"))
    mesaj = obj.get("message", {})
    return LLMYaniti(
        icerik=mesaj.get("content", ""),
        dusunme=mesaj.get("thinking", "") or "",
        sure_sn=round(time.perf_counter() - t0, 2),
        uretilen_token=int(obj.get("eval_count", 0)),
        bitis_nedeni=str(obj.get("done_reason", "")),
    )
