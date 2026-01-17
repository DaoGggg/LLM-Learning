"""Knowledge graph management using NetworkX."""
import networkx as nx
from typing import Dict, List, Optional, Any
from collections import defaultdict


class GraphManager:
    """Manage knowledge graph operations with NetworkX."""

    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.entity_counter = 0

    def add_entity(self, name: str, entity_type: str, description: str = "", chunk_id: str = "") -> str:
        """Add an entity to the graph."""
        entity_id = f"entity_{self.entity_counter}"
        self.entity_counter += 1

        self.graph.add_node(
            entity_id,
            name=name,
            label=entity_type,
            description=description,
            chunk_id=chunk_id
        )

        return entity_id

    def add_relation(self, source_id: str, target_id: str, relation_type: str, description: str = ""):
        """Add a relation between entities."""
        if source_id in self.graph.nodes and target_id in self.graph.nodes:
            self.graph.add_edge(
                source_id,
                target_id,
                relation=relation_type,
                description=description
            )

    def get_entity_by_name(self, name: str) -> Optional[str]:
        """Find entity ID by name."""
        for node_id, data in self.graph.nodes(data=True):
            if data.get("name") == name:
                return node_id
        return None

    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        """Search entities by name or description."""
        results = []
        for node_id, data in self.graph.nodes(data=True):
            name = data.get("name", "").lower()
            desc = data.get("description", "").lower()
            if query.lower() in name or query.lower() in desc:
                results.append({
                    "id": node_id,
                    **data
                })
        return results

    def get_neighbors(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get all neighbors of an entity."""
        neighbors = []
        if entity_id in self.graph.nodes:
            for neighbor in self.graph.neighbors(entity_id):
                edge_data = self.graph.edges[entity_id, neighbor]
                neighbor_data = self.graph.nodes[neighbor]
                neighbors.append({
                    "id": neighbor,
                    **neighbor_data,
                    "relation": edge_data.get("relation", ""),
                    "edge_description": edge_data.get("description", "")
                })
        return neighbors

    def get_entity_info(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get full information about an entity."""
        if entity_id in self.graph.nodes:
            return {
                "id": entity_id,
                **self.graph.nodes[entity_id]
            }
        return None

    def get_graph_data(self) -> Dict[str, Any]:
        """Export graph data for visualization."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "name": data.get("name", ""),
                "category": data.get("label", "Unknown"),
                "description": data.get("description", "")[:200],
                "chunkId": data.get("chunk_id", "")
            })

        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "relation": data.get("relation", ""),
                "description": data.get("description", "")
            })

        return {"nodes": nodes, "edges": edges}

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "entity_types": self._count_entity_types(),
            "relation_types": self._count_relation_types()
        }

    def _count_entity_types(self) -> Dict[str, int]:
        """Count entities by type."""
        counts = defaultdict(int)
        for _, data in self.graph.nodes(data=True):
            entity_type = data.get("label", "Unknown")
            counts[entity_type] += 1
        return dict(counts)

    def _count_relation_types(self) -> Dict[str, int]:
        """Count relations by type."""
        counts = defaultdict(int)
        for _, _, data in self.graph.edges(data=True):
            rel_type = data.get("relation", "Unknown")
            counts[rel_type] += 1
        return dict(counts)

    def clear(self):
        """Clear the graph."""
        self.graph.clear()
        self.entity_counter = 0

    def merge_from(self, other: "GraphManager"):
        """Merge another graph into this one."""
        for node_id, data in other.graph.nodes(data=True):
            self.add_entity(
                name=data.get("name", ""),
                entity_type=data.get("label", ""),
                description=data.get("description", ""),
                chunk_id=data.get("chunk_id", "")
            )

        for source, target, data in other.graph.edges(data=True):
            self.add_relation(
                source_id=source,
                target_id=target,
                relation_type=data.get("relation", ""),
                description=data.get("description", "")
            )


# Global graph manager instance
graph_manager = GraphManager()
