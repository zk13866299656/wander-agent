from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from food_agent.config import settings
from food_agent.models.schemas import Poi, Preference
from food_agent.storage.models import FavoriteRow, PreferenceRow

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


def add_favorite(session: Session, poi: Poi) -> None:
    """收藏写入：按 poi_id 去重，已存在则跳过；仅在新增时提交一次。"""
    if session.query(FavoriteRow).filter_by(poi_id=poi.id).one_or_none() is None:
        session.add(FavoriteRow(poi_id=poi.id, name=poi.name))
        session.commit()
