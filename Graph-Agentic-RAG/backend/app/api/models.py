"""Pydantic models for API requests and responses."""
from typing import List, Optional
from pydantic import BaseModel


# Request models
class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    history: Optional[List[dict]] = None


class UploadResponse(BaseModel):
    """Upload response model."""
    success: bool
    file_name: str
    message: str


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    used_graph: bool


class GraphData(BaseModel):
    """Graph data response model."""
    nodes: List[dict]
    edges: List[dict]


class GraphStats(BaseModel):
    """Graph statistics response model."""
    node_count: int
    edge_count: int
    entity_types: dict
    relation_types: dict


class EntitySearchResponse(BaseModel):
    """Entity search response model."""
    entities: List[dict]
