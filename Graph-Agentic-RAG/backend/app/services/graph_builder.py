"""Knowledge graph building service."""
import json
import re
from typing import List, Dict, Any

from app.services.document_processor import processor
from app.services.llm_service import llm_service
from app.services.project_manager import project_manager
from app.utils.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    RELATION_EXTRACTION_PROMPT
)


class GraphBuilder:
    """Build knowledge graph from documents."""

    def __init__(self):
        self.entity_map: Dict[str, str] = {}  # name -> entity_id

    async def extract_entities_from_chunk(self, chunk: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract entities from a text chunk."""
        prompt = ENTITY_EXTRACTION_PROMPT.format(chunk_text=chunk["text"])

        try:
            response = await llm_service.call([{"role": "user", "content": prompt}])
            entities = self._parse_entities_response(response)
            return entities
        except Exception as e:
            print(f"Entity extraction error: {e}")
            return []

    async def extract_relations_from_chunk(self, chunk: Dict[str, Any], entities: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Extract relations from a text chunk given entities."""
        if not entities:
            return []

        entities_json = json.dumps(entities, ensure_ascii=False)
        prompt = RELATION_EXTRACTION_PROMPT.format(
            chunk_text=chunk["text"],
            entities_json=entities_json
        )

        try:
            response = await llm_service.call([{"role": "user", "content": prompt}])
            relations = self._parse_relations_response(response)
            return relations
        except Exception as e:
            print(f"Relation extraction error: {e}")
            return []

    def _parse_entities_response(self, response: str) -> List[Dict[str, str]]:
        """Parse entity extraction response with better error handling."""
        try:
            # 尝试多种JSON提取方式
            json_str = None

            # 方式1: 提取完整的JSON块
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group()

            if json_str:
                # 尝试直接解析
                try:
                    data = json.loads(json_str)
                    if "entities" in data:
                        return data["entities"]
                except json.JSONDecodeError:
                    # 方式2: 尝试修复常见的JSON格式问题
                    fixed_json = self._fix_json_string(json_str)
                    try:
                        data = json.loads(fixed_json)
                        if "entities" in data:
                            return data["entities"]
                    except json.JSONDecodeError:
                        pass

            # 方式3: 尝试从文本中提取entities数组
            entities = self._extract_entities_fallback(response)
            if entities:
                return entities

            return []
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            print(f"Failed to parse entities: {e}")
            return []

    def _parse_relations_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse relation extraction response with better error handling."""
        try:
            json_str = None
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group()

            if json_str:
                try:
                    data = json.loads(json_str)
                    if "relations" in data:
                        return data["relations"]
                except json.JSONDecodeError:
                    fixed_json = self._fix_json_string(json_str)
                    try:
                        data = json.loads(fixed_json)
                        if "relations" in data:
                            return data["relations"]
                    except json.JSONDecodeError:
                        pass

            # 方式3: 尝试从文本中提取relations数组
            relations = self._extract_relations_fallback(response)
            if relations:
                return relations

            return []
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            print(f"Failed to parse relations: {e}")
            return []

    def _fix_json_string(self, json_str: str) -> str:
        """尝试修复常见的JSON格式问题"""
        fixed = json_str

        # 修复单引号问题
        fixed = fixed.replace("'", '"')

        # 修复缺少引号的键
        fixed = re.sub(r'(\w+):', r'"\1":', fixed)

        # 修复多余逗号
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

        # 修复中文字符问题 - 确保值被正确引号包围
        fixed = re.sub(r'("\w+":\s*)([^"{\[\d])', r'\1"\2', fixed)

        return fixed

    def _extract_entities_fallback(self, response: str) -> List[Dict[str, str]]:
        """从文本中回退提取实体"""
        entities = []
        # 尝试匹配 "name": "xxx" 或 'name': 'xxx' 模式
        name_pattern = r'["\']name["\']:\s*["\']([^"\']+)["\']'
        type_pattern = r'["\']type["\']:\s*["\']([^"\']+)["\']'
        desc_pattern = r'["\']description["\']:\s*["\']([^"\']*)["\']'

        # 尝试提取所有匹配的实体
        names = re.findall(name_pattern, response)
        types = re.findall(type_pattern, response)
        descs = re.findall(desc_pattern, response)

        for i, name in enumerate(names):
            entity = {
                "name": name,
                "type": types[i] if i < len(types) else "CONCEPT",
                "description": descs[i] if i < len(descs) else ""
            }
            entities.append(entity)

        return entities

    def _extract_relations_fallback(self, response: str) -> List[Dict[str, Any]]:
        """从文本中回退提取关系"""
        relations = []
        source_pattern = r'["\']source["\']:\s*["\']([^"\']+)["\']'
        target_pattern = r'["\']target["\']:\s*["\']([^"\']+)["\']'
        rel_pattern = r'["\']relation["\']:\s*["\']([^"\']+)["\']'

        sources = re.findall(source_pattern, response)
        targets = re.findall(target_pattern, response)
        rels = re.findall(rel_pattern, response)

        for i in range(min(len(sources), len(targets))):
            relation = {
                "source": sources[i],
                "target": targets[i],
                "relation": rels[i] if i < len(rels) else "相关",
                "description": ""
            }
            relations.append(relation)

        return relations

    async def build_graph_from_file(self, file_path: str, file_name: str, progress_callback=None) -> Dict[str, Any]:
        """Build knowledge graph from a document file."""
        graph = project_manager.get_current_project()
        if graph is None:
            raise ValueError("No project selected")

        # Clear existing graph for this project
        graph.clear()
        self.entity_map.clear()

        # Process file into chunks
        chunks = processor.process_file(file_path, file_name)
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i + 1, total_chunks, f"Processing chunk {i + 1}/{total_chunks}")

            # Extract entities
            entities = await self.extract_entities_from_chunk(chunk)

            # Add entities to graph
            for entity in entities:
                entity_id = graph.add_entity(
                    name=entity.get("name", ""),
                    entity_type=entity.get("type", "CONCEPT"),
                    description=entity.get("description", ""),
                    chunk_id=chunk.get("id", "")
                )
                self.entity_map[entity.get("name", "")] = entity_id

            # Extract relations
            relations = await self.extract_relations_from_chunk(chunk, entities)

            # Get chunk text for source
            chunk_text = chunk.get("text", "")[:500]  # Limit text length

            # Add relations to graph
            for relation in relations:
                source_name = relation.get("source", "")
                target_name = relation.get("target", "")

                source_id = self.entity_map.get(source_name, graph.get_entity_by_name(source_name))
                target_id = self.entity_map.get(target_name, graph.get_entity_by_name(target_name))

                if source_id and target_id:
                    graph.add_relation(
                        source_id=source_id,
                        target_id=target_id,
                        relation_type=relation.get("relation", "相关"),
                        description=relation.get("description", ""),
                        source_text=chunk_text,
                        chunk_id=chunk.get("id", "")
                    )

        # Save the project
        project_manager.save_project(graph.project_id)

        return graph.to_visualization_data()


# Global graph builder instance
graph_builder = GraphBuilder()
