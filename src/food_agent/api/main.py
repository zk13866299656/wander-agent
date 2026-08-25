from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from food_agent.graph.build import build_graph
from food_agent.models.schemas import Poi
from food_agent.rag.store import VectorStore
from food_agent.storage.db import add_favorite, get_session

logger = logging.getLogger(__name__)

NODE_NAMES = {"parse", "retrieve", "extract", "rank", "card", "memory"}
DEFAULT_CHECKPOINT_PATH = "./checkpoints.sqlite"
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


class ChatIn(BaseModel):
    thread_id: str
    message: str


class FavoriteIn(BaseModel):
    poi: Poi


def create_app(checkpoint_path: str = DEFAULT_CHECKPOINT_PATH) -> FastAPI:
    """Build the FastAPI app; checkpointer + graph are created lazily in lifespan.

    A sync ``SqliteSaver`` has no async methods (``aget_tuple`` raises
    ``NotImplementedError``), so it cannot back ``astream_events``; use
    ``AsyncSqliteSaver`` instead. Graph nodes stay synchronous — LangGraph runs
    them in a worker thread under ``astream_events``.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncSqliteSaver.from_conn_string(checkpoint_path) as saver:
            app.state.graph = build_graph(saver)
            yield

    app = FastAPI(title="Wander 本地生活推荐 Agent", lifespan=lifespan)

    @app.post("/chat")
    async def chat(body: ChatIn, request: Request) -> EventSourceResponse:
        graph = getattr(request.app.state, "graph", None)
        if graph is None:
            raise HTTPException(status_code=503, detail="graph not initialized")

        async def event_stream() -> AsyncIterator[dict]:
            config = {"configurable": {"thread_id": body.thread_id}}
            async for event in graph.astream_events(
                {"user_input": body.message}, config, version="v2"
            ):
                kind = event["event"]
                name = event.get("name")
                if kind == "on_chain_start" and name in NODE_NAMES:
                    yield {"event": "node", "data": name}
                elif kind == "on_chain_end" and name == "card":
                    cards = event["data"]["output"]["cards"]
                    payload = [card.model_dump(mode="json") for card in cards]
                    yield {"event": "cards", "data": json.dumps(payload, ensure_ascii=False)}

        return EventSourceResponse(event_stream())

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/app.js")
    async def app_js() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "app.js")

    @app.post("/favorite")
    def favorite(body: FavoriteIn) -> dict:
        """收藏：写 favorite 表（主链路）+ 向量索引（尽力而为，失败仅降级）。"""
        with get_session() as s:
            add_favorite(s, body.poi)
        try:
            VectorStore().add_pois([body.poi])
        except Exception:
            logger.warning("收藏向量索引写入失败", exc_info=True)
        return {"ok": True}

    return app


app = create_app()
