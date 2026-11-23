"""Chroma vektör indeksi.

Ders kodu `d5_03_embeddings.py` (OllamaEmbeddings) ve `d5_04_index.py`'den (langchain_chroma, diskte indeks)
geliştirildi. OpsPilot eklemeleri:
- Her embedding modeli için ayrı koleksiyon (Faz 3 karşılaştırması)
- Kosinüs uzaklığı açıkça seçilir
- İçerik özeti (SHA-256): politika metni değişirse parça sayısı aynı kalsa bile yeniden indekslenir
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import CHROMA_DIR, OLLAMA_URL, EMBED_MODEL, CHUNK_SIZE  # noqa: E402
from app.rag.chunker import tum_dokumanlari_parcala, belgelere_cevir, Chunk  # noqa: E402

CHROMA_BASE = CHROMA_DIR


def embedding_client(model_adi: str = EMBED_MODEL) -> OllamaEmbeddings:
    """Ollama embedding istemcisi (ders: d5_03_embeddings.embedding_client)."""
    return OllamaEmbeddings(model=model_adi, base_url=OLLAMA_URL)


def koleksiyon_adi(embed_model: str, chunk_size: int = CHUNK_SIZE) -> str:
    """Embedding modeli ve parça boyutuna göre koleksiyon adı üretir."""
    temiz = embed_model.replace(":", "_").replace("/", "_").replace(".", "_").replace("-", "_")
    return f"opspilot_pol_{temiz}_c{chunk_size}"


def get_store(embed_model: str = EMBED_MODEL, chunk_size: int = CHUNK_SIZE) -> Chroma:
    """Modelin koleksiyonunu açar (ders: d5_05_search.get_store)."""
    return Chroma(
        collection_name=koleksiyon_adi(embed_model, chunk_size),
        embedding_function=embedding_client(embed_model),
        persist_directory=str(CHROMA_BASE),
        collection_configuration={"hnsw": {"space": "cosine"}},
        client_settings=Settings(anonymized_telemetry=False),
    )


def icerik_ozeti(parcalar: list[Chunk]) -> str:
    """Parçaların kimlik, metin ve metadata'sından SHA-256 özeti üretir."""
    h = hashlib.sha256()
    for p in parcalar:
        h.update(json.dumps([p.id, p.icerik, p.metadata], ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def _ozet_dosyasi(embed_model: str, chunk_size: int) -> Path:
    return CHROMA_BASE / f"{koleksiyon_adi(embed_model, chunk_size)}.ozet"


def indeksle(
    embed_model: str = EMBED_MODEL,
    parcalar: list[Chunk] | None = None,
    force: bool = False,
    batch_size: int = 16,
    chunk_size: int = CHUNK_SIZE,
) -> tuple[str, int, float]:
    """Politika parçalarını Chroma'ya yazar; içerik değişmemişse yeniden indekslemez.

    Returns:
        (koleksiyon_adı, parça_sayısı, indeksleme_süresi_sn — güncelse 0.0)
    """
    if parcalar is None:
        parcalar = tum_dokumanlari_parcala(chunk_size)
    kol_adi = koleksiyon_adi(embed_model, chunk_size)
    ozet = icerik_ozeti(parcalar)
    ozet_yolu = _ozet_dosyasi(embed_model, chunk_size)
    CHROMA_BASE.mkdir(parents=True, exist_ok=True)

    store = get_store(embed_model, chunk_size)
    kayitli = ozet_yolu.read_text(encoding="utf-8").strip() if ozet_yolu.exists() else ""
    if not force and kayitli == ozet and len(store.get(include=[])["ids"]) == len(parcalar):
        print(f"Koleksiyon '{kol_adi}' güncel ({len(parcalar)} parça). Yeniden indekslenmedi.")
        return kol_adi, len(parcalar), 0.0

    store.delete_collection()
    store = get_store(embed_model, chunk_size)
    belgeler = belgelere_cevir(parcalar)

    print(f"'{kol_adi}' indeksleniyor ({len(belgeler)} parça, model={embed_model})...")
    t0 = time.perf_counter()
    for i in range(0, len(belgeler), batch_size):
        grup = belgeler[i:i + batch_size]
        store.add_documents(grup, ids=[b.metadata["chunk_id"] for b in grup])
    sure = round(time.perf_counter() - t0, 2)
    ozet_yolu.write_text(ozet, encoding="utf-8")
    print(f"Tamamlandı: {len(belgeler)} parça {sure} sn.")
    return kol_adi, len(belgeler), sure


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Politikaları Chroma'ya indeksler.")
    parser.add_argument("--model", default=EMBED_MODEL, help="Ollama embedding model adı")
    parser.add_argument("--force", action="store_true", help="İçerik aynı olsa da yeniden oluştur")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Bu boyutu aşan maddeler bölünür")
    args = parser.parse_args()
    indeksle(args.model, force=args.force, chunk_size=args.chunk_size)
