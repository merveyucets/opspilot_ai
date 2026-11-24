"""Panel için politika maddesi metinleri (atıfa tıklanınca gösterilen tam metin).

Kaynak, RAG'in indekslediği Markdown dosyalarının kendisidir (data/politikalar/). Gizli dokümanlar (GZL-*,
erişim 'gizli') hiç yüklenmez: panelden de gizli içerik okunamaz (altın kural 4). Model gerektirmez.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from config import DATA_DIR, POLICY_DIR

MADDE_RE = re.compile(r"^## Madde (\d+) — (.+)$", re.M)
BASLIK_RE = re.compile(r"^# ([A-Z]+-[A-Z]+-\d{3}) — (.+)$", re.M)


def _gizli_kodlar() -> set[str]:
    meta = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))
    kayitlar = meta.get("dokumanlar", meta) if isinstance(meta, dict) else meta
    gizli = set()
    for k, v in (kayitlar.items() if isinstance(kayitlar, dict) else ((d.get("kod"), d) for d in kayitlar)):
        if isinstance(v, dict) and v.get("erisim") == "gizli":
            gizli.add(v.get("kod", k))
    return gizli


@lru_cache(maxsize=1)
def maddeler() -> dict[tuple[str, int], dict]:
    """(kod, madde_no) → {kod, dokuman, madde_no, baslik, metin}. Gizli dokümanlar hariç."""
    gizli = _gizli_kodlar()
    sonuc = {}
    for dosya in sorted(POLICY_DIR.glob("*.md")):
        metin = dosya.read_text(encoding="utf-8")
        b = BASLIK_RE.search(metin)
        if not b:
            continue
        kod, dokuman = b.group(1), b.group(2).strip()
        if kod.startswith("GZL-") or kod in gizli:
            continue
        basliklar = list(MADDE_RE.finditer(metin))
        for i, m in enumerate(basliklar):
            son = basliklar[i + 1].start() if i + 1 < len(basliklar) else len(metin)
            govde = metin[m.end():son].strip()
            sonuc[(kod, int(m.group(1)))] = {"kod": kod, "dokuman": dokuman, "madde_no": int(m.group(1)),
                                             "baslik": m.group(2).strip(), "metin": govde}
    return sonuc


def madde_getir(kod: str, madde_no: int) -> dict | None:
    return maddeler().get((kod, int(madde_no)))
