"""
Pydantic models for API request/response schemas.
"""
import logging
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class IngestReq(BaseModel):
    """Request model for document ingestion."""
    force_rebuild: bool = False  # Set to True to rebuild entire index


class IngestResp(BaseModel):
    """Response model for document ingestion."""
    files_indexed: int
    total_vectors: int
    mode: str  # "incremental" or "full_rebuild"


class QueryReq(BaseModel):
    """Request model for RAG queries."""
    q: Optional[str] = None  # Accept "q" field
    query: Optional[str] = None  # Also accept "query" field (fallback)
    k: int = 4

    def get_query(self) -> str:
        """Get query from either 'q' or 'query' field."""
        if self.q:
            return self.q
        elif self.query:
            logger.warning("⚠️ Frontend sent 'query' instead of 'q' - using fallback")
            return self.query
        else:
            raise ValueError("Either 'q' or 'query' field is required")


class QueryResp(BaseModel):
    """Response model for RAG queries."""
    answer: str
    sources: list[str]


class RetrieveResp(BaseModel):
    """Response model for retrieval-only endpoint."""
    count: int
    results: list[dict]
    mode: str
