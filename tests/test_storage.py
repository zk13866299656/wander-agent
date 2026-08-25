import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from food_agent.models.schemas import Preference, PreferenceKey
from food_agent.storage.models import Base, PreferenceRow, SessionRow
from food_agent.storage.db import upsert_preference


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_upsert_preference_same_key_value_overwrites(db_session):
    upsert_preference(db_session, Preference(key=PreferenceKey.BUDGET, value="100", weight=1.0))
    upsert_preference(db_session, Preference(key=PreferenceKey.BUDGET, value="100", weight=2.0))
    rows = db_session.query(PreferenceRow).all()
    assert len(rows) == 1 and rows[0].value == "100" and rows[0].weight == 2.0


def test_session_row_roundtrip(db_session):
    db_session.add(SessionRow(thread_id="t1", title="找日料"))
    db_session.commit()
    assert db_session.query(SessionRow).filter_by(thread_id="t1").one().title == "找日料"
