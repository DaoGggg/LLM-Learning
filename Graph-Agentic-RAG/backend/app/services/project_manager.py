"""Project and knowledge graph management."""
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import datetime


@dataclass
class Entity:
    """Entity in the knowledge graph."""
    id: str
    name: str
    entity_type: str
    description: str = ""
    chunk_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Relation:
    """Relation between entities."""
    source_id: str
    target_id: str
    relation_type: str
    description: str = ""
    source_text: str = ""  # 原始构建时引用的文本
    chunk_id: str = ""     # 所属文本块ID

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KnowledgeGraph:
    """Knowledge graph for a project."""
    project_id: str
    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: List[Relation] = field(default_factory=list)
    entity_counter: int = 0

    def add_entity(self, name: str, entity_type: str, description: str = "", chunk_id: str = "") -> str:
        """Add an entity to the graph."""
        entity_id = f"entity_{self.entity_counter}"
        self.entity_counter += 1
        self.entities[entity_id] = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            description=description,
            chunk_id=chunk_id
        )
        return entity_id

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relations."""
        if entity_id not in self.entities:
            return False
        del self.entities[entity_id]
        # Remove related relations
        self.relations = [r for r in self.relations if r.source_id != entity_id and r.target_id != entity_id]
        return True

    def update_entity(self, entity_id: str, name: str = None, entity_type: str = None, description: str = None) -> bool:
        """Update an entity."""
        if entity_id not in self.entities:
            return False
        entity = self.entities[entity_id]
        if name is not None:
            entity.name = name
        if entity_type is not None:
            entity.entity_type = entity_type
        if description is not None:
            entity.description = description
        return True

    def add_relation(self, source_id: str, target_id: str, relation_type: str, description: str = "", source_text: str = "", chunk_id: str = "") -> bool:
        """Add a relation between entities."""
        if source_id not in self.entities or target_id not in self.entities:
            return False
        self.relations.append(Relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            description=description,
            source_text=source_text,
            chunk_id=chunk_id
        ))
        return True

    def delete_relation(self, source_id: str, target_id: str) -> bool:
        """Delete a relation."""
        original_len = len(self.relations)
        self.relations = [r for r in self.relations if not (
            r.source_id == source_id and r.target_id == target_id
        )]
        return len(self.relations) < original_len

    def update_relation(self, source_id: str, target_id: str, relation_type: str = None, description: str = None) -> bool:
        """Update a relation."""
        for relation in self.relations:
            if relation.source_id == source_id and relation.target_id == target_id:
                if relation_type is not None:
                    relation.relation_type = relation_type
                if description is not None:
                    relation.description = description
                return True
        return False

    def get_relation(self, source_id: str, target_id: str) -> Optional[Relation]:
        """Get a relation by source and target."""
        for relation in self.relations:
            if relation.source_id == source_id and relation.target_id == target_id:
                return relation
        return None

    def get_entity_by_name(self, name: str) -> Optional[str]:
        """Find entity ID by name."""
        for entity_id, entity in self.entities.items():
            if entity.name == name:
                return entity_id
        return None

    def search_entities(self, query: str) -> List[Entity]:
        """Search entities by name or description."""
        results = []
        query_lower = query.lower()
        for entity in self.entities.values():
            if query_lower in entity.name.lower() or query_lower in entity.description.lower():
                results.append(entity)
        return results

    def get_neighbors(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get all neighbors of an entity."""
        neighbors = []
        if entity_id not in self.entities:
            return neighbors
        for relation in self.relations:
            if relation.source_id == entity_id:
                target = self.entities.get(relation.target_id)
                if target:
                    neighbors.append({
                        "id": target.id,
                        "name": target.name,
                        "type": target.entity_type,
                        "relation": relation.relation_type,
                        "description": relation.description
                    })
            elif relation.target_id == entity_id:
                source = self.entities.get(relation.source_id)
                if source:
                    neighbors.append({
                        "id": source.id,
                        "name": source.name,
                        "type": source.entity_type,
                        "relation": relation.relation_type,
                        "description": relation.description
                    })
        return neighbors

    def to_visualization_data(self) -> Dict[str, Any]:
        """Export graph data for visualization."""
        nodes = []
        for entity in self.entities.values():
            nodes.append({
                "id": entity.id,
                "name": entity.name,
                "category": entity.entity_type,
                "description": entity.description[:200],
                "chunkId": entity.chunk_id
            })

        edges = []
        for relation in self.relations:
            edges.append({
                "source": relation.source_id,
                "target": relation.target_id,
                "relation": relation.relation_type,
                "description": relation.description,
                "sourceText": relation.source_text,
                "chunkId": relation.chunk_id
            })

        return {"nodes": nodes, "edges": edges}

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        entity_types = {}
        for entity in self.entities.values():
            entity_types[entity.entity_type] = entity_types.get(entity.entity_type, 0) + 1

        relation_types = {}
        for relation in self.relations:
            relation_types[relation.relation_type] = relation_types.get(relation.relation_type, 0) + 1

        return {
            "node_count": len(self.entities),
            "edge_count": len(self.relations),
            "entity_types": entity_types,
            "relation_types": relation_types
        }

    def clear(self):
        """Clear the graph."""
        self.entities.clear()
        self.relations.clear()
        self.entity_counter = 0

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps({
            "project_id": self.project_id,
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "relations": [r.to_dict() for r in self.relations],
            "entity_counter": self.entity_counter
        }, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, data: dict) -> "KnowledgeGraph":
        """Deserialize from JSON."""
        graph = cls(project_id=data["project_id"])
        graph.entities = {
            k: Entity(**v) for k, v in data.get("entities", {}).items()
        }
        graph.relations = [Relation(**r) for r in data.get("relations", [])]
        graph.entity_counter = data.get("entity_counter", 0)
        return graph


class ProjectManager:
    """Manage multiple projects and their knowledge graphs."""

    def __init__(self, projects_dir: str = "./data/projects"):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.projects: Dict[str, KnowledgeGraph] = {}
        self.current_project_id: Optional[str] = None
        self._load_projects()

    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new project."""
        project_id = self._generate_project_id(name)
        graph = KnowledgeGraph(project_id=project_id)

        project_info = {
            "id": project_id,
            "name": name,
            "description": description,
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        }

        self.projects[project_id] = graph
        self._save_project_metadata(project_id, project_info)
        self.current_project_id = project_id

        return project_info

    def _generate_project_id(self, name: str) -> str:
        """Generate a unique project ID."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        hash_name = hashlib.md5(f"{name}{timestamp}".encode()).hexdigest()[:8]
        return f"project_{hash_name}"

    def _save_project_metadata(self, project_id: str, info: dict):
        """Save project metadata to JSON."""
        meta_file = self.projects_dir / project_id / "metadata.json"
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    def _load_projects(self):
        """Load all projects from disk."""
        if not self.projects_dir.exists():
            return
        for project_dir in self.projects_dir.iterdir():
            if project_dir.is_dir():
                meta_file = project_dir / "metadata.json"
                graph_file = project_dir / "graph.json"
                if meta_file.exists() and graph_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            info = json.load(f)
                        with open(graph_file, "r", encoding="utf-8") as f:
                            graph_data = json.load(f)
                        self.projects[info["id"]] = KnowledgeGraph.from_json(graph_data)
                    except Exception as e:
                        print(f"Failed to load project {project_dir}: {e}")

    def save_project(self, project_id: str):
        """Save a project to disk."""
        if project_id not in self.projects:
            return
        graph = self.projects[project_id]
        project_dir = self.projects_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        json_data = graph.to_json()
        print(f"[ProjectManager] Saving project {project_id} with {len(graph.entities)} entities, {len(graph.relations)} relations")
        with open(project_dir / "graph.json", "w", encoding="utf-8") as f:
            f.write(json_data)

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects."""
        projects = []
        for project_dir in self.projects_dir.iterdir():
            if project_dir.is_dir():
                meta_file = project_dir / "metadata.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            info = json.load(f)
                        # Add statistics
                        if info["id"] in self.projects:
                            info["stats"] = self.projects[info["id"]].get_statistics()
                        else:
                            info["stats"] = {"node_count": 0, "edge_count": 0}
                        projects.append(info)
                    except Exception:
                        continue
        return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_project(self, project_id: str) -> Optional[KnowledgeGraph]:
        """Get a project's graph."""
        return self.projects.get(project_id)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        if project_id not in self.projects:
            return False
        del self.projects[project_id]
        # Delete from disk
        import shutil
        project_dir = self.projects_dir / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir)
        if self.current_project_id == project_id:
            self.current_project_id = None
        return True

    def set_current_project(self, project_id: str) -> bool:
        """Set current project."""
        if project_id in self.projects:
            self.current_project_id = project_id
            return True
        return False

    def get_current_project(self) -> Optional[KnowledgeGraph]:
        """Get current project graph."""
        if self.current_project_id:
            graph = self.projects.get(self.current_project_id)
            if graph:
                print(f"[ProjectManager] get_current_project: {self.current_project_id}, entities={len(graph.entities)}")
            else:
                print(f"[ProjectManager] get_current_project: project {self.current_project_id} not found in memory!")
            return graph
        print("[ProjectManager] get_current_project: no current project set")
        return None

    def get_current_project_id(self) -> Optional[str]:
        """Get current project ID."""
        return self.current_project_id


# Global project manager instance
project_manager = ProjectManager()
