"""Prompt templates for entity extraction, relation extraction, and agent decisions."""

# Entity extraction prompt
ENTITY_EXTRACTION_PROMPT = """你是一个实体提取专家。请从以下文本中提取知识图谱实体。

任务要求：
1. 识别文本中的命名实体（人物、地点、机构、事件、概念等）
2. 为每个实体指定类型
3. 提供简洁的描述

文本：
{chunk_text}

请以JSON格式输出，格式如下：
{{
    "entities": [
        {{
            "name": "实体名称",
            "type": "实体类型（PER/LOC/ORG/EVENT/CONCEPT）",
            "description": "实体的简要描述"
        }}
    ]
}}

只输出JSON，不要其他内容。"""

# Relation extraction prompt
RELATION_EXTRACTION_PROMPT = """你是一个关系抽取专家。根据以下实体信息，从原文中识别实体之间的关系。

原文：
{chunk_text}

已识别的实体：
{entities_json}

请识别这些实体之间的关系，以JSON格式输出：
{{
    "relations": [
        {{
            "source": "源实体名称",
            "target": "目标实体名称",
            "relation": "关系类型（朋友、属于、发生在、相关等）",
            "description": "关系的简要描述"
        }}
    ]
}}

只输出JSON，不要其他内容。"""

# Agent decision prompt - decides whether to use knowledge graph
DECISION_PROMPT = """你是一个智能助手，需要决定是否需要查询知识图谱来回答用户问题。

用户问题：{question}

请判断：
1. 问题是否与特定的人物、地点、事件、概念相关？
2. 问题是否需要从知识图谱中检索信息？
3. 或者可以直接根据常识回答？

请只输出 "use_graph" 或 "direct_answer"，不要其他内容。

判断标准：
- 如果问题涉及特定实体、概念、事件，需要查询知识图谱 → use_graph
- 如果问题是闲聊或常识问题 → direct_answer"""

# Graph query prompt - generates query keywords
GRAPH_QUERY_PROMPT = """根据用户问题，生成用于查询知识图谱的关键词。

用户问题：{question}

请提取查询关键词（可以是实体名称、关系类型、概念等），以JSON格式输出：
{{
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "entities": ["相关实体名称1", "相关实体名称2"]
}}

只输出JSON，不要其他内容。"""

# Response generation prompt - uses graph context
RESPONSE_WITH_GRAPH_PROMPT = """你是一个智能助手。请根据知识图谱信息回答用户问题。

用户问题：{question}

知识图谱信息：
{graph_context}

请基于以上信息回答问题。如果知识图谱中没有相关信息，请说明。

回答时：
1. 优先使用知识图谱中的信息
2. 如果信息不完整，可以补充常识
3. 保持回答简洁准确"""

# Response generation prompt - direct answer
RESPONSE_DIRECT_PROMPT = """你是一个智能助手。请直接回答用户问题。

用户问题：{question}

请简洁准确地回答。"""
