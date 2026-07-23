"""FastAPI application entrypoint.
"""

from fastapi import Depends, FastAPI

from app.config import Settings, get_settings
from app.schemas import HealthResponse

app = FastAPI(
    title="AWS Docs Agentic RAG Assistant",
    version="0.1.0",
    description="Agentic chatbot over a curated set of official AWS documentation.",
)


@app.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness plus active provider configuration.
    """
    return HealthResponse(
        status="ok",
        providers={
            "llm": settings.llm_provider,
            "embeddings": settings.embeddings_provider,
            "persistence": settings.persistence,
            "region": settings.aws_region,
        },
    )
