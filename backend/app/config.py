from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    # Storage
    data_dir: str = str(DATA_DIR)
    database_url: str = f"sqlite:///{(DATA_DIR / 'evidencedesk.db').as_posix()}"
    chroma_dir: str = str(DATA_DIR / "chroma")
    upload_dir: str = str(DATA_DIR / "uploads")
    eval_reports_dir: str = str(DATA_DIR / "eval_reports")

    # Ollama / model provider
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768

    # Optional hosted provider (disabled by default; never required for the basic prototype)
    hosted_provider_enabled: bool = False
    hosted_provider_api_key: str = ""
    hosted_provider_model: str = ""

    # Upload limits
    max_upload_mb: int = 50
    max_pages_per_doc: int = 500

    # Chunking
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 200

    # Retrieval
    retrieval_top_k: int = 8
    retrieval_candidate_k: int = 25
    retrieval_mode: str = "hybrid"  # vector | keyword | hybrid | hybrid_rerank
    rrf_k: int = 60
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_enabled: bool = True

    # Generation / verification
    generation_timeout_s: float = 120.0
    max_retry: int = 1
    min_claims_for_answer: int = 1
    weak_support_threshold: float = 0.5

    # CORS
    frontend_origin: str = "http://localhost:5173"


settings = Settings()

for d in (settings.data_dir, settings.chroma_dir, settings.upload_dir, settings.eval_reports_dir):
    Path(d).mkdir(parents=True, exist_ok=True)
