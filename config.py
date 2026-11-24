"""OpsPilot AI — tüm ayarlar tek merkezde. Ortam değişkeniyle (.env / PowerShell $env:) değiştirilebilir."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
POLICY_DIR = DATA_DIR / "politikalar"
RUNTIME_DIR = ROOT / "runtime"            # oluşan veritabanları (git'e girmez)
CHROMA_DIR = RUNTIME_DIR / "chroma_opspilot"
DB_PATH = Path(os.getenv("OPSPILOT_DB", str(RUNTIME_DIR / "opspilot.sqlite3")))
CHECKPOINT_PATH = RUNTIME_DIR / "langgraph_checkpoints.sqlite3"
COLLECTION = "opspilot_politikalar_v1"

# --- Ollama (Gün 1-4) ---
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Faz 3 ızgarasıyla seçildi (eval/raporlar/rag_izgara.md): bge-m3 + 900 parçalama + rerank ağırlığı 1.0
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
# GPU yok → CPU. Sınıflandırıcı Faz 3 ölçümüyle seçildi (eval/raporlar/siniflandirma_*.md):
# qwen3:8b düşünme kapalı — v1 21/30, v2 26/30 (iyimser), görülmemiş demo seti 4/6, ~22 sn/talep.
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "qwen3:8b")
CLASSIFIER_THINK = False   # düşünme açıkken +2 doğru ama ~4 kat süre (89 sn/talep)
# Yazım (öneri + yanıt taslağı): qwen3:8b düşünme kapalı — qwen2.5 7B aynı talepte tutarsız öneri üretti (D01)
WRITER_MODEL = os.getenv("WRITER_MODEL", "qwen3:8b")
WRITER_THINK = False if WRITER_MODEL.startswith("qwen3") else None   # qwen3 düşünme varsayılanı açık
KARAR_OPTIONS = {"temperature": 0.1, "num_ctx": 6144, "num_predict": 1400, "repeat_penalty": 1.1, "seed": 42}

# --- RAG parametreleri (Gün 5-6, "Temel Kavramlar" rehberi §2-4, §8) ---
CHUNK_SIZE = 900          # karakter; başlık bazlı bölümlemeden sonra uzun bölümler için
CHUNK_OVERLAP = 120
RETRIEVAL_K = 8           # ilk vektör aramasında aday sayısı
RERANK_TOP_N = 3          # LLM'e verilecek son parça sayısı
RRF_SABITI = 60           # Çoklu sorgu birleştirme (Reciprocal Rank Fusion) için standart sabit
# Agent araması (Faz 9, eval/raporlar/arama_talep_test.md): müşteri mesajı tek sorgu. Arama ölçümünde ilk 5 madde
# beklenen maddelerin hepsini 10/30 talepte, ilk 3 madde 7/30 talepte getirdi; ancak karar ölçümünde v1 3 maddeyle
# ölçüldüğü için varsayılan 3'tür (v3 talimatı 5 maddeyle ölçüldü). LLM'in yazdığı arama sorularıyla çoklu sorgu
# (RRF / dönüşümlü) iyileştirmedi (9/30). Yöntem None → yalnızca müşteri mesajı.
AGENT_ARAMA_YONTEMI = os.getenv("AGENT_ARAMA_YONTEMI") or None
AGENT_ARAMA_TOP_N = int(os.getenv("AGENT_ARAMA_TOP_N", "3"))
# Öneri talimatı (eval/raporlar/karar_degerlendirme_test_v*.md):
#   v1 = Faz 8 talimatı, ek bilgisi modele gitmez; 3 madde ile 16/30 (teslim varsayılanı, ölçülmüş)
#   v2 = (yalnızca ölçüm kaydı) v1 + "ek var/yok" satırı + 5 madde; 12/30, geri alındı
#   v3 = v1 + politikanın karar adımları + kapsamı daraltılmış ek bilgisi + politika istisnası cümlesi (Faz 9)
KARAR_TALIMAT_SURUMU = os.getenv("KARAR_TALIMAT_SURUMU", "v1")
# Hibrit rerank: skor = SEMANTIK_AGIRLIK * anlamsal benzerlik + (1 - SEMANTIK_AGIRLIK) * kelime örtüşmesi.
# Faz 3 ızgarasında bge-m3 için en iyi değer 1.0 çıktı (kelime örtüşmesi katkı sağlamadı); eval/raporlar/rag_izgara.md
SEMANTIK_AGIRLIK = float(os.getenv("SEMANTIK_AGIRLIK", "1.0"))
# Faz 3 embedding karşılaştırmasının adayları (eval/rag_eval.py --all)
EMBED_MODEL_ADAYLARI = ["embeddinggemma", "bge-m3", "qwen3-embedding:0.6b"]
# num_ctx, KARAR_OPTIONS ile AYNI tutulur: aynı model farklı bağlam boyutuyla çağrılırsa Ollama modeli yeniden yükler (ölçüldü).
CLASSIFY_OPTIONS = {"temperature": 0, "num_predict": 200, "num_ctx": 6144, "seed": 42}
# Düşünme (thinking) açık modellerde düşünme metni de token bütçesinden yer; 200 token yetmez (ölçüldü: qwen3:8b).
CLASSIFY_THINK_OPTIONS = {"temperature": 0, "num_predict": 1536, "seed": 42}
LLM_TIMEOUT_SN = int(os.getenv("LLM_TIMEOUT_SN", "600"))   # CPU'da 7-8B modeller için
# Faz 3 sınıflandırma karşılaştırmasının adayları: (model, think) — think=None: parametre gönderilmez
LLM_ADAYLARI = [("qwen2.5:1.5b", None), ("qwen2.5:latest", None), ("qwen3:8b", False), ("qwen3:8b", True)]
WRITER_OPTIONS = {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096, "num_predict": 700, "seed": 42}

# --- Servisler (Gün 7-8) ---
MCP_HOST, MCP_PORT = "127.0.0.1", 8001
MCP_URL = os.getenv("OPSPILOT_MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}/mcp")
API_PORT = 8000
N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
INGEST_API_KEY = os.getenv("OPSPILOT_INGEST_KEY", "")   # n8n → /ingest için; koda yazılmaz
