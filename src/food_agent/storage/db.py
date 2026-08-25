from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from food_agent.config import settings
from food_agent.models.schemas import Preference
from food_agent.storage.models import PreferenceRow

_engine = create_engine(settings.mysql_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)

def get_engine():
    return _engine

def get_session() -> Session:
    return SessionLocal()

def upsert_preference(session: Session, pref: Preference) -> None:
    row = session.query(PreferenceRow).filter_by(key=pref.key.value, value=pref.value).one_or_none()
    if row:
        row.weight = pref.weight
    else:
        session.add(PreferenceRow(key=pref.key.value, value=pref.value, weight=pref.weight))
    session.commit()
