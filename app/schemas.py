
"""HTTP contract models for the API.
These Pydantic models are the public request/response shapes. 
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["high", "medium", "low"]


class Source(BaseModel):
    title: str
    url: str
    service: str


class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, description="Conversation key.")
    question: str = Field(..., min_length=1, description="User's natural-language question.")
    debug: bool = Field(default=False, description="Include retrieval trace in the response.")


class ChatDebug(BaseModel):
    """Optional retrieval trace, returned only when the request sets debug=true."""

    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Response body for POST /chat."""

    request_id: str
    session_id: str
    answer: str
    sources: list[Source] = Field(default_factory=list)
    confidence: Confidence
    iterations: int = Field(..., ge=0, description="Agent tool-loop iterations used.")
    debug: ChatDebug | None = None


class HealthResponse(BaseModel):
    """Response body for GET /health.
    """

    status: str
    providers: dict[str, str]
