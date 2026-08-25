from __future__ import annotations

from langgraph.graph import END, StateGraph

from food_agent.graph import nodes
from food_agent.graph.state import GraphState


def route_after_parse(state: GraphState) -> str:
    """追问路由：判定为追问则跳过检索、回到排序复用候选。"""
    return "rank" if state["parsed"].is_followup else "retrieve"


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
