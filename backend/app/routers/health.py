from fastapi import APIRouter

from app.llm_client import provider

router = APIRouter()


@router.get("/api/health")
def health():
    ollama_ok, ollama_msg = provider.is_available()
    return {
        "status": "ok",
        "ollama": {"available": ollama_ok, "message": ollama_msg},
    }
