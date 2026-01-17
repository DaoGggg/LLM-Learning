"""LangGraph Agent for conversation with knowledge graph integration."""
import json
import re
from typing import List, TypedDict, Annotated, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.services.llm_service import get_llm_response
from app.services.project_manager import project_manager
from app.utils.prompts import (
    DECISION_PROMPT,
    GRAPH_QUERY_PROMPT,
    RESPONSE_WITH_GRAPH_PROMPT,
    RESPONSE_DIRECT_PROMPT
)


class AgentState(TypedDict):
    """State for the agent graph."""
    messages: Annotated[List[BaseMessage], "append"]
    last_user_message: str
    route_decision: str
    should_use_graph: bool
    graph_context: str
    graph_retrieved_entities: List[Dict[str, Any]]
    graph_retrieval_chain: List[Dict[str, Any]]  # 召回链路详情
    response: str


async def chat_node(state: AgentState) -> AgentState:
    """Handle chat message."""
    messages = state["messages"]
    last_user_message = ""
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            last_user_message = last_msg.content
    return {**state, "last_user_message": last_user_message}


async def decide_router(state: AgentState) -> AgentState:
    """Decide whether to use knowledge graph or answer directly."""
    question = state["last_user_message"]

    # Check if graph has data
    graph = project_manager.get_current_project()
    if graph is None or graph.get_statistics()["node_count"] == 0:
        return {**state, "route_decision": "direct_answer", "should_use_graph": False}

    # Use LLM to decide
    prompt = DECISION_PROMPT.format(question=question)
    try:
        decision = await get_llm_response([HumanMessage(content=prompt)], temperature=0.3)
        decision = decision.strip().lower()

        if "use_graph" in decision:
            return {**state, "route_decision": "use_graph", "should_use_graph": True}
        else:
            return {**state, "route_decision": "direct_answer", "should_use_graph": False}
    except Exception as e:
        print(f"Decision error: {e}")
        return {**state, "route_decision": "direct_answer", "should_use_graph": False}


async def retrieve_from_graph(state: AgentState) -> AgentState:
    """Retrieve relevant information from knowledge graph."""
    question = state["last_user_message"]

    graph = project_manager.get_current_project()
    if graph is None:
        return {
            **state,
            "graph_context": "未找到知识图谱",
            "graph_retrieved_entities": [],
            "graph_retrieval_chain": []
        }

    # Generate query keywords
    query_prompt = GRAPH_QUERY_PROMPT.format(question=question)
    try:
        query_response = await get_llm_response([HumanMessage(content=query_prompt)], temperature=0.3)

        # Parse keywords
        json_match = re.search(r'\{[\s\S]*\}', query_response)
        if json_match:
            query_data = json.loads(json_match.group())
            keywords = query_data.get("keywords", [])
            entities = query_data.get("entities", [])
        else:
            keywords = [question]
            entities = []
    except Exception as e:
        print(f"Query generation error: {e}")
        keywords = [question]
        entities = []

    # Search graph
    graph_context_parts = []
    retrieved_entities = []
    retrieval_chain = []  # 召回链路

    # Search by keywords
    for keyword in keywords[:5]:
        results = graph.search_entities(keyword)

        if results:
            # 记录搜索关键词
            retrieval_chain.append({
                "step": f"搜索关键词: {keyword}",
                "found": len(results),
                "entities": []
            })

        for result in results[:3]:
            neighbors = graph.get_neighbors(result.id)
            context = f"实体: {result.name} ({result.entity_type})\n描述: {result.description}"

            entity_info = {
                "name": result.name,
                "type": result.entity_type,
                "description": result.description,
                "chunk_id": result.chunk_id,
                "neighbors": []
            }

            neighbor_list = []
            if neighbors:
                context += "\n相关实体:"
                for neighbor in neighbors[:3]:
                    context += f"\n  - {neighbor.get('name', '')} [{neighbor.get('relation', '')}]"
                    neighbor_info = {
                        "name": neighbor.get("name", ""),
                        "relation": neighbor.get("relation", ""),
                        "type": neighbor.get("type", "")
                    }
                    neighbor_list.append(neighbor_info)
                    entity_info["neighbors"].append(neighbor_info)

            graph_context_parts.append(context)
            retrieved_entities.append(entity_info)

            # 记录每个实体的召回信息
            if len(retrieval_chain) > 0:
                retrieval_chain[-1]["entities"].append({
                    "name": result.name,
                    "type": result.entity_type,
                    "matched_by": keyword,
                    "neighbors": neighbor_list
                })

    # Build context string
    graph_context = "\n\n".join(graph_context_parts) if graph_context_parts else "未找到相关信息"

    return {
        **state,
        "graph_context": graph_context,
        "graph_retrieved_entities": retrieved_entities,
        "graph_retrieval_chain": retrieval_chain
    }


async def generate_response(state: AgentState) -> AgentState:
    """Generate final response based on state."""
    question = state["last_user_message"]

    if state["should_use_graph"]:
        prompt = RESPONSE_WITH_GRAPH_PROMPT.format(
            question=question,
            graph_context=state["graph_context"]
        )
    else:
        prompt = RESPONSE_DIRECT_PROMPT.format(question=question)

    try:
        response = await get_llm_response([HumanMessage(content=prompt)], temperature=0.7)
        return {**state, "response": response}
    except Exception as e:
        return {**state, "response": f"生成回答时出错: {str(e)}"}


async def add_message_node(state: AgentState) -> AgentState:
    """Add assistant message to state."""
    messages = list(state["messages"])
    messages.append(AIMessage(content=state["response"]))
    return {**state, "messages": messages}


# Route selector function
def route_decision(state: AgentState) -> str:
    """Select next node based on route decision."""
    return state.get("route_decision", "direct_answer")


# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("chat", chat_node)
workflow.add_node("decide", decide_router)
workflow.add_node("retrieve", retrieve_from_graph)
workflow.add_node("generate", generate_response)
workflow.add_node("add_message", add_message_node)

# Add edges
workflow.set_entry_point("chat")
workflow.add_edge("chat", "decide")

workflow.add_conditional_edges(
    "decide",
    route_decision,
    {
        "use_graph": "retrieve",
        "direct_answer": "generate"
    }
)

workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "add_message")
workflow.add_edge("add_message", END)


# Create compiled app
_app = None

def get_app():
    """Get the compiled app."""
    global _app
    if _app is None:
        _app = workflow.compile()
    return _app


async def invoke_agent(question: str, history: List[BaseMessage] = None) -> Dict[str, Any]:
    """Invoke the agent with a question."""
    if history is None:
        history = []

    # Create initial state
    initial_state = {
        "messages": history + [HumanMessage(content=question)],
        "last_user_message": question,
        "route_decision": "",
        "should_use_graph": False,
        "graph_context": "",
        "graph_retrieved_entities": [],
        "graph_retrieval_chain": [],
        "response": ""
    }

    # Compile and run
    app = get_app()

    # Run the graph
    final_state = await app.ainvoke(initial_state)

    return {
        "response": final_state["response"],
        "used_graph": final_state.get("should_use_graph", False),
        "retrieved_entities": final_state.get("graph_retrieved_entities", []),
        "retrieval_chain": final_state.get("graph_retrieval_chain", []),
        "route_decision": final_state.get("route_decision", "")
    }


async def stream_agent(question: str, history: List[BaseMessage] = None):
    """Stream the agent response."""
    if history is None:
        history = []

    initial_state = {
        "messages": history + [HumanMessage(content=question)],
        "last_user_message": question,
        "route_decision": "",
        "should_use_graph": False,
        "graph_context": "",
        "graph_retrieved_entities": [],
        "graph_retrieval_chain": [],
        "response": ""
    }

    app = get_app()

    async for chunk in app.astream_log(initial_state, include_types=["llm"]):
        if isinstance(chunk, dict) and "chunk" in chunk:
            content = chunk["chunk"].get("content", "")
            if content:
                yield content
