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
EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma")
# GPU yok → CPU. Sınıflandırma için küçük/hızlı model, taslak için daha güçlü model.
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "qwen2.5:1.5b")
WRITER_MODEL = os.getenv("WRITER_MODEL", "qwen2.5:latest")

# --- RAG parametreleri (Gün 5-6, "Temel Kavramlar" rehberi §2-4, §8) ---
CHUNK_SIZE = 900          # karakter; başlık bazlı bölümlemeden sonra uzun bölümler için
CHUNK_OVERLAP = 120
RETRIEVAL_K = 8           # ilk vektör aramasında aday sayısı
RERANK_TOP_N = 3          # LLM'e verilecek son parça sayısı
CLASSIFY_OPTIONS = {"temperature": 0, "num_predict": 200, "seed": 42}
WRITER_OPTIONS = {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096, "num_predict": 700, "seed": 42}

# --- Servisler (Gün 7-8) ---
MCP_HOST, MCP_PORT = "127.0.0.1", 8001
MCP_URL = os.getenv("OPSPILOT_MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}/mcp")
API_PORT = 8000
N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
INGEST_API_KEY = os.getenv("OPSPILOT_INGEST_KEY", "")   # n8n → /ingest için; koda yazılmaz
