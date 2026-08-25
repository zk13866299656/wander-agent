from __future__ import annotations

from langgraph.graph import END, StateGraph

from food_agent.graph import nodes
from food_agent.graph.state import GraphState

FOLLOWUP_KEYWORDS = ("太贵", "贵了", "换一家", "换", "便宜")


def route_after_parse(state: GraphState) -> str:
    """追问路由：LLM 判定 + 关键词规则兜底，命中则跳过检索、回到排序复用候选。"""
    if state["parsed"].is_followup:
        return "rank"
    if any(kw in (state["user_input"] or "") for kw in FOLLOWUP_KEYWORDS):
        return "rank"
    return "retrieve"


def build_graph(checkpointer):
    g = StateGraph(GraphState)
    g.add_node("parse", nodes.parse_node)
    g.add_node("retrieve", nodes.retrieve_node)
    g.add_node("extract", nodes.extract_node)
    g.add_node("rank", nodes.rank_node)
    g.add_node("card", nodes.card_node)
    g.add_node("memory", nodes.memory_node)

    g.set_entry_point("parse")
    g.add_conditional_edges("parse", route_after_parse, {"retrieve": "retrieve", "rank": "rank"})
    g.add_edge("retrieve", "extract")
    g.add_edge("extract", "rank")
    g.add_edge("rank", "card")
    g.add_edge("card", "memory")
    g.add_edge("memory", END)
    return g.compile(checkpointer=checkpointer)
