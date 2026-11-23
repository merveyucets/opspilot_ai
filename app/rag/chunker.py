"""Politika dokümanlarını madde bazlı parçalara ayırır.

Ders kodu `d5_01_documents.py` (meta.json ile metadata) ve `d5_02_chunks.py`'den (chunk_id) geliştirildi:
karakter bölücü yerine politika yapısına uygun madde bazlı bölme kullanılır.

Her `## Madde N — Başlık` bloğu bir parça olur.
Uzun maddeler (config.CHUNK_SIZE üzerindeyse) alt madde / paragraf düzeyinde bölünür.
Her parçanın metadata'sı: kod, baslik, madde_no, madde_baslik, kategori, erisim, kaynak.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
import sys

from langchain_core.documents import Document

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import DATA_DIR, POLICY_DIR, CHUNK_SIZE, CHUNK_OVERLAP  # noqa: E402

MADDE_RE = re.compile(r"^##\s+Madde\s+(\d+)\s+[—–-]\s*(.+)$", re.MULTILINE)


@dataclass
class Chunk:
    """Tek bir bilgi parçası."""
    id: str              # "POL-IADE-001_M3" veya "POL-IADE-001_M3_p1"
    kod: str             # "POL-IADE-001"
    baslik: str          # Doküman başlığı
    madde_no: int        # 3
    madde_baslik: str    # "Cayma Süresi"
    kategori: str        # meta.json'daki kategori
    erisim: str          # "ic" | "gizli"
    icerik: str          # Metin içeriği
    metadata: dict = field(default_factory=dict)


def _parcala_uzun_metni(metin: str, max_uzunluk: int, overlap: int) -> list[str]:
    """Uzun metni paragraf veya alt madde sınırlarından böler."""
    if len(metin) <= max_uzunluk:
        return [metin]

    parcalar = []
    # Paragraflara göre ayır
    paragraflar = metin.split("\n\n")
    mevcut = ""
    for p in paragraflar:
        if mevcut and len(mevcut) + len(p) + 2 > max_uzunluk:
            parcalar.append(mevcut.strip())
            if overlap > 0 and len(mevcut) > overlap:
                mevcut = mevcut[-overlap:] + "\n\n" + p
            else:
                mevcut = p
        else:
            mevcut = mevcut + "\n\n" + p if mevcut else p

    if mevcut.strip():
        parcalar.append(mevcut.strip())

    return parcalar if parcalar else [metin]


def dokumani_parcala(dosya_adi: str, metin: str, meta_bilgi: dict, chunk_size: int = CHUNK_SIZE) -> list[Chunk]:
    """Tek bir politika dokümanını madde düzeyinde parçalara ayırır."""
    kod = meta_bilgi.get("kod", "")
    baslik = meta_bilgi.get("baslik", "")
    kategori = meta_bilgi.get("kategori", "")
    erisim = meta_bilgi.get("erisim", "ic")

    # Madde başlıklarını bul
    eslesmeler = list(MADDE_RE.finditer(metin))
    if not eslesmeler:
        # Madde formatında değilse tek chunk döndür
        return [
            Chunk(
                id=f"{kod}_tam",
                kod=kod,
                baslik=baslik,
                madde_no=0,
                madde_baslik="Genel",
                kategori=kategori,
                erisim=erisim,
                icerik=metin.strip(),
                metadata={
                    "kod": kod,
                    "baslik": baslik,
                    "madde_no": 0,
                    "madde_baslik": "Genel",
                    "kategori": kategori,
                    "erisim": erisim,
                    "kaynak": f"{kod} Genel",
                },
            )
        ]

    chunks = []
    for i, match in enumerate(eslesmeler):
        madde_no = int(match.group(1))
        madde_baslik = match.group(2).strip()

        # Bu maddenin başlangıç ve bitiş indeksleri
        baslangic = match.start()
        bitis = eslesmeler[i + 1].start() if i + 1 < len(eslesmeler) else len(metin)

        madde_metni = metin[baslangic:bitis].strip()

        # Doküman kodunu ve başlığını chunk başına ekle (vektör/BM25 eşleşmesini güçlendirir)
        baslik_eki = f"[{kod} - {baslik}]\n"
        icerik_tam = baslik_eki + madde_metni

        # Uzunluk kontrolü
        if len(icerik_tam) > chunk_size:
            alt_parcalar = _parcala_uzun_metni(madde_metni, chunk_size - len(baslik_eki), CHUNK_OVERLAP)
            for part_idx, alt_metin in enumerate(alt_parcalar, 1):
                chunk_id = f"{kod}_M{madde_no}_p{part_idx}"
                chunk_icerik = f"[{kod} - {baslik} (Madde {madde_no})]\n{alt_metin}"
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        kod=kod,
                        baslik=baslik,
                        madde_no=madde_no,
                        madde_baslik=madde_baslik,
                        kategori=kategori,
                        erisim=erisim,
                        icerik=chunk_icerik,
                        metadata={
                            "kod": kod,
                            "baslik": baslik,
                            "madde_no": madde_no,
                            "madde_baslik": madde_baslik,
                            "kategori": kategori,
                            "erisim": erisim,
                            "kaynak": f"{kod} Madde {madde_no}",
                            "part": part_idx,
                        },
                    )
                )
        else:
            chunk_id = f"{kod}_M{madde_no}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    kod=kod,
                    baslik=baslik,
                    madde_no=madde_no,
                    madde_baslik=madde_baslik,
                    kategori=kategori,
                    erisim=erisim,
                    icerik=icerik_tam,
                    metadata={
                        "kod": kod,
                        "baslik": baslik,
                        "madde_no": madde_no,
                        "madde_baslik": madde_baslik,
                        "kategori": kategori,
                        "erisim": erisim,
                        "kaynak": f"{kod} Madde {madde_no}",
                        "part": 0,
                    },
                )
            )

    return chunks


def tum_dokumanlari_parcala(chunk_size: int = CHUNK_SIZE) -> list[Chunk]:
    """Tüm politika dokümanlarını okur ve parçalar (chunk_size üstündeki maddeler bölünür)."""
    meta_path = DATA_DIR / "meta.json"
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    tum_chunks = []
    for dosya_adi, meta_bilgi in sorted(meta.items()):
        dosya_yolu = POLICY_DIR / dosya_adi
        if not dosya_yolu.exists():
            continue
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            metin = f.read()
        chunks = dokumani_parcala(dosya_adi, metin, meta_bilgi, chunk_size)
        tum_chunks.extend(chunks)

    return tum_chunks


def belgelere_cevir(parcalar: list[Chunk]) -> list[Document]:
    """Parçaları LangChain Document listesine çevirir (ders: d5_01/d5_02); metadata'ya chunk_id eklenir."""
    return [Document(page_content=p.icerik, metadata={**p.metadata, "chunk_id": p.id}) for p in parcalar]


if __name__ == "__main__":
    parcalar = tum_dokumanlari_parcala()
    print(f"Toplam parça sayısı: {len(parcalar)}")
    gizli = sum(1 for p in parcalar if p.erisim == "gizli")
    ic = sum(1 for p in parcalar if p.erisim == "ic")
    print(f"İç kullanım: {ic}, Gizli: {gizli}")
    for p in parcalar[:5]:
        print(f"  [{p.id}] {p.metadata['kaynak']} ({len(p.icerik)} kar)")
