import asyncio
from unittest.mock import patch

import httpx
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from food_agent.api.main import create_app
from food_agent.graph.build import build_graph
from food_agent.models.schemas import ParsedRequest, Poi


class FakeVectorStore:
    def search(self, query, k=5):
        return []


@pytest.fixture
async def sse_cleanup():
    """sse-starlette spawns a detached shutdown-watcher task on the running
    loop; cancel it after the test so it doesn't outlive the loop and emit a
    "Task was destroyed but it is pending!" warning."""
    yield
    loop = asyncio.get_running_loop()
    current = asyncio.current_task()
    for task in asyncio.all_tasks(loop):
        if task is not current and task.get_coro().cr_code.co_name == "_shutdown_watcher":
            task.cancel()
    await asyncio.sleep(0)


async def test_chat_streams_nodes_and_cards(tmp_path, sse_cleanup):
    req = ParsedRequest(location="杭州西湖", categories=["日料"], lnglat=(120.15, 30.28))
    poi = Poi(id="1", name="某日料", rating=4.5, review_count=100,
              avg_price=120, distance_m=1000, source="amap")

    class FakePoiTool:
        def search(self, query, location, radius, categories):
            return [poi]

    app = create_app()
    with patch("food_agent.graph.nodes.complete_with_retry", return_value=req), \
         patch("food_agent.graph.nodes.get_enabled_tools", return_value={"poi": FakePoiTool()}), \
         patch("food_agent.rag.store.VectorStore", return_value=FakeVectorStore()):
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as saver:
            app.state.graph = build_graph(saver)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/chat",
                    json={"thread_id": "t1", "message": "杭州西湖附近日料"},
                )

    assert resp.status_code == 200
    body = resp.text
    assert "event: node" in body
    assert "event: cards" in body
    assert "某日料" in body
