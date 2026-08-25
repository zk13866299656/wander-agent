from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from food_agent.api.main import create_app
from food_agent.models.schemas import Poi
from food_agent.storage.db import add_favorite
from food_agent.storage.models import Base, FavoriteRow


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_add_favorite_dedupes(db_session):
    poi = Poi(id="1", name="某日料", source="amap")
    add_favorite(db_session, poi)
    add_favorite(db_session, poi)
    assert db_session.query(FavoriteRow).filter_by(poi_id="1").count() == 1


async def test_favorite_endpoint():
    """POST /favorite 写库 + 向量索引（全 mock，不碰真实 MySQL/Chroma/网络）。"""
    calls = []

    class FakeVectorStore:
        def add_pois(self, pois):
            calls.append(pois)

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    with patch("food_agent.api.main.add_favorite"), \
         patch("food_agent.api.main.get_session", return_value=FakeSession()), \
         patch("food_agent.api.main.VectorStore", FakeVectorStore):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/favorite",
                json={"poi": {"id": "1", "name": "某日料", "source": "amap",
                              "rating": 4.5, "avg_price": 120.0,
                              "distance_m": 1000, "tags": ["标签1"]}},
            )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert len(calls) == 1
    assert calls[0][0].id == "1"
    assert calls[0][0].name == "某日料"
    assert calls[0][0].source == "amap"
