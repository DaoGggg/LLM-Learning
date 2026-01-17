"""Project management API endpoints."""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services.project_manager import project_manager

router = APIRouter()


# Request/Response models
class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    stats: dict = None


class SetCurrentProjectRequest(BaseModel):
    project_id: str


class EntityEditRequest(BaseModel):
    name: str
    entity_type: str
    description: str = ""
    chunk_id: str = ""


class RelationEditRequest(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    description: str = ""
    source_text: str = ""


class RelationUpdateRequest(BaseModel):
    relation_type: str
    description: str = ""


# Project endpoints
@router.get("/projects")
async def list_projects() -> List[ProjectResponse]:
    """List all projects."""
    return project_manager.list_projects()


@router.post("/projects")
async def create_project(request: CreateProjectRequest) -> ProjectResponse:
    """Create a new project."""
    if not request.name or len(request.name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Project name is required")
    return project_manager.create_project(request.name, request.description)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    if project_manager.delete_project(project_id):
        return {"success": True, "message": "Project deleted"}
    raise HTTPException(status_code=404, detail="Project not found")


@router.post("/projects/current")
async def set_current_project(request: SetCurrentProjectRequest):
    """Set current project."""
    if project_manager.set_current_project(request.project_id):
        return {"success": True, "project_id": request.project_id}
    raise HTTPException(status_code=404, detail="Project not found")


@router.get("/projects/current")
async def get_current_project():
    """Get current project info."""
    project_id = project_manager.get_current_project_id()
    if project_id:
        projects = project_manager.list_projects()
        for p in projects:
            if p["id"] == project_id:
                return p
    return {"id": None, "name": None, "stats": {"node_count": 0, "edge_count": 0}}


# Graph data endpoints
@router.get("/graph")
async def get_graph_data():
    """Get current project's graph data."""
    graph = project_manager.get_current_project()
    if graph is None:
        return {"nodes": [], "edges": []}
    return graph.to_visualization_data()


@router.get("/graph/stats")
async def get_graph_stats():
    """Get current project's graph statistics."""
    graph = project_manager.get_current_project()
    if graph is None:
        return {"node_count": 0, "edge_count": 0, "entity_types": {}, "relation_types": {}}
    return graph.get_statistics()


# Entity endpoints
@router.get("/graph/entities/search")
async def search_entities(query: str):
    """Search entities in current project."""
    graph = project_manager.get_current_project()
    if graph is None:
        return {"entities": []}
    entities = graph.search_entities(query)
    return {
        "entities": [
            {"id": e.id, "name": e.name, "type": e.entity_type, "description": e.description}
            for e in entities
        ]
    }


@router.get("/graph/entity/{entity_id}")
async def get_entity(entity_id: str):
    """Get entity details."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=404, detail="No project selected")
    entity = graph.entities.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    neighbors = graph.get_neighbors(entity_id)
    return {
        "entity": entity.to_dict(),
        "neighbors": neighbors
    }


@router.post("/graph/entity")
async def add_entity(request: EntityEditRequest):
    """Add a new entity to current project."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="No project selected")
    if not request.name or not request.entity_type:
        raise HTTPException(status_code=400, detail="Name and type are required")
    entity_id = graph.add_entity(
        name=request.name,
        entity_type=request.entity_type,
        description=request.description,
        chunk_id=request.chunk_id
    )
    project_manager.save_project(graph.project_id)
    return {"success": True, "entity_id": entity_id}


@router.put("/graph/entity/{entity_id}")
async def update_entity(entity_id: str, request: EntityEditRequest):
    """Update an entity."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="No project selected")
    if graph.update_entity(entity_id,
                           name=request.name if request.name else None,
                           entity_type=request.entity_type if request.entity_type else None,
                           description=request.description if request.description else None):
        project_manager.save_project(graph.project_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Entity not found")


@router.delete("/graph/entity/{entity_id}")
async def delete_entity(entity_id: str):
    """Delete an entity."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="No project selected")
    if graph.delete_entity(entity_id):
        project_manager.save_project(graph.project_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Entity not found")


# Relation endpoints
@router.post("/graph/relation")
async def add_relation(request: RelationEditRequest):
    """Add a relation."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="No project selected")
    if not request.source_id or not request.target_id or not request.relation_type:
        raise HTTPException(status_code=400, detail="Source, target, and relation type are required")
    if graph.add_relation(request.source_id, request.target_id, request.relation_type, request.description, request.source_text):
        project_manager.save_project(graph.project_id)
        return {"success": True}
    raise HTTPException(status_code=400, detail="Invalid source or target entity")


@router.get("/graph/relation")
async def get_relation(source_id: str, target_id: str):
    """Get relation details."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="No project selected")
    relation = graph.get_relation(source_id, target_id)
    if relation is None:
        raise HTTPException(status_code=404, detail="Relation not found")

    # Get entity names
    source_entity = graph.entities.get(source_id)
    target_entity = graph.entities.get(target_id)

    return {
        "source_id": relation.source_id,
        "target_id": relation.target_id,
        "source_name": source_entity.name if source_entity else "",
        "target_name": target_entity.name if target_entity else "",
        "relation_type": relation.relation_type,
        "description": relation.description,
        "source_text": relation.source_text,
        "chunk_id": relation.chunk_id
    }


@router.put("/graph/relation")
async def update_relation(source_id: str, target_id: str, request: RelationUpdateRequest):
    """Update a relation."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="No project selected")
    if graph.update_relation(source_id, target_id, request.relation_type, request.description):
        project_manager.save_project(graph.project_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Relation not found")


@router.delete("/graph/relation")
async def delete_relation(source_id: str, target_id: str):
    """Delete a relation."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="No project selected")
    if graph.delete_relation(source_id, target_id):
        project_manager.save_project(graph.project_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Relation not found")
