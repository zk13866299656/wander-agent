# Wander 本地生活推荐 Agent — MVP 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「一句话需求 → 检索 → 结构化抽取 → 打分排序 → 流式推荐卡片」端到端闭环，满足设计文档 DoD。

**Architecture:** LangGraph 状态图编排多步流程，确定性打分模块与可拔插工具层分离，业务数据存 MySQL、会话状态存 SQLite checkpointer，FastAPI + SSE 流式输出，前端原生 HTML + JS 渲染卡片。

**Tech Stack:** Python 3.11+、LangGraph + langgraph-checkpoint-sqlite、DeepSeek（OpenAI 兼容）、FastAPI + SSE、SQLAlchemy + Alembic + MySQL 8、Chroma、SiliconFlow embedding、原生前端。

**Spec:** `docs/superpowers/specs/2026-08-25-food-explorer-agent-design.md`

## Global Constraints

- Python `>=3.11`。
- LLM 用 DeepSeek `deepseek-chat`（OpenAI 兼容接口，`base_url=https://api.deepseek.com`）。
- LangGraph checkpointer 用 `langgraph-checkpoint-sqlite`（官方），**不用** MySQL checkpointer；MySQL 8 仅存业务数据。
- 候选店**不单独建表**，追问复用 checkpointer state。
- 高德评分缺失降级：评分 → 评论数/热度 → 中性分，逐级兜底，不淘汰无评分项。
- 品类→高德分类码：LLM 映射 + `keywords` 兜底，不维护静态大表。
- 向量召回冷启动：空结果不影响主链路。
- 工具 provider 通过 `.env` 配置装配，未配置时自动降级（如无 WebSearch Key → 纯 POI 评分）。
- 流式粒度：节点级 + 工具调用级（`astream_events` + SSE），不做 token 级。
- 暂不引入 Docker，本机 MySQL 8 直连。
- **git commit 用中文 + 规范前缀**（`feat:` / `fix:` / `docs:` / `test:` / `refactor:`）。

---

## 文件结构总览

```
wander/
├── pyproject.toml
├── .env.example
├── README.md                          # 已存在，Task 12 补「快速开始」
├── src/food_agent/
│   ├── __init__.py
│   ├── config.py                      # pydantic-settings，读 .env
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                 # ParsedRequest / Poi / Candidate / Card / Preference
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py                  # DeepSeek 客户端 + 重试 + 结构化输出
│   ├── ranking/
│   │   ├── __init__.py
│   │   └── scorer.py                  # 确定性打分 + 排序
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                    # PoiSearchTool / WebSearchTool 抽象 + 注册表
│   │   ├── amap.py                    # 高德 POI provider
│   │   ├── web.py                     # Tavily / DuckDuckGo provider（可选）
│   │   └── registry.py                # 按配置装配启用项
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py                      # engine + sessionmaker
│   │   └── models.py                  # SessionRow / MessageRow / FavoriteRow / PreferenceRow
│   ├── memory/
│   │   ├── __init__.py
│   │   └── extract.py                 # LLM 抽取偏好 + upsert
│   ├── rag/
│   │   ├── __init__.py
│   │   └── store.py                   # Chroma + embedding + retriever
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py                   # GraphState TypedDict
│   │   ├── nodes.py                   # parse / retrieve / extract / rank / card / memory
│   │   └── build.py                   # 建图 + 追问路由 + checkpointer
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py                    # FastAPI + SSE
│   └── runner.py                      # 从命令行跑一次对话（无前端调试用）
├── frontend/
│   ├── index.html
│   └── app.js
├── alembic.ini
├── alembic/                           # Task 6 生成
└── tests/
    ├── test_schemas.py
    ├── test_ranking.py
    ├── test_amap.py
    ├── test_storage.py
    ├── test_favorite.py
    ├── test_memory.py
    ├── test_rag.py
    └── test_graph.py                  # 集成：mock 工具跑通整条 graph
```

---

## Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`, `.env.example`, `src/food_agent/__init__.py`, `src/food_agent/config.py`, `src/food_agent/models/__init__.py`, `src/food_agent/llm/__init__.py`, `src/food_agent/ranking/__init__.py`, `src/food_agent/tools/__init__.py`, `src/food_agent/storage/__init__.py`, `src/food_agent/memory/__init__.py`, `src/food_agent/rag/__init__.py`, `src/food_agent/graph/__init__.py`, `src/food_agent/api/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: `Settings`（`food_agent.config.settings`），后续所有任务读它拿 Key / 连接串。

- [ ] **Step 1: 写 `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "food-agent"
version = "0.1.0"
description = "本地生活推荐 Agent（吃喝玩乐）"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2",
    "langgraph-checkpoint-sqlite>=1.0",
    "langchain-openai>=0.2",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sse-starlette>=2.0",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pymysql>=1.1",
    "chromadb>=0.5",
    "httpx>=0.27",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "ruff>=0.4"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: 写 `src/food_agent/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    amap_api_key: str = ""
    baidu_map_api_key: str = ""
    tavily_api_key: str = ""

    siliconflow_api_key: str = ""
    siliconflow_embedding_model: str = "BAAI/bge-m3"

    mysql_url: str = "mysql+pymysql://root:password@localhost:3306/food_agent?charset=utf8mb4"
    chroma_dir: str = "./chroma_data"

settings = Settings()
```

- [ ] **Step 3: 写 `.env.example`**

```ini
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
AMAP_API_KEY=
BAIDU_MAP_API_KEY=
TAVILY_API_KEY=
SILICONFLOW_API_KEY=
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3
MYSQL_URL=mysql+pymysql://root:password@localhost:3306/food_agent?charset=utf8mb4
CHROMA_DIR=./chroma_data
```

- [ ] **Step 4: 建目录与空 `__init__.py`**

```bash
mkdir -p src/food_agent/{models,llm,ranking,tools,storage,memory,rag,graph,api} tests
touch src/food_agent/__init__.py src/food_agent/{models,llm,ranking,tools,storage,memory,rag,graph,api}/__init__.py tests/__init__.py
```

- [ ] **Step 5: 安装依赖并验证**

```bash
pip install -e ".[dev]"
python -c "from food_agent.config import settings; print(settings.deepseek_model)"
```

Expected: 打印 `deepseek-chat`。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: 初始化项目脚手架与依赖配置"
```

---

## Task 2: Pydantic 数据模型

**Files:**
- Create: `src/food_agent/models/schemas.py`, `tests/test_schemas.py`

**Interfaces:**
- Produces: `ParsedRequest`、`Poi`、`Candidate`、`RecommendationCard`、`Preference`、`PreferenceKey`。字段名全项目唯一权威定义在这里，后续任务 import 自 `food_agent.models.schemas`。

- [ ] **Step 1: 写失败测试 `tests/test_schemas.py`**

```python
import pytest
from pydantic import ValidationError
from food_agent.models.schemas import ParsedRequest, Poi, Preference, PreferenceKey

def test_parsed_request_defaults():
    req = ParsedRequest(location="杭州西湖")
    assert req.categories == [] and req.is_followup is False and req.budget_max is None

def test_parsed_request_rejects_bad_lnglat():
    with pytest.raises(ValidationError):
        ParsedRequest(location="x", lnglat=(999, 0))

def test_poi_rating_bounds():
    with pytest.raises(ValidationError):
        Poi(id="1", name="x", source="amap", rating=6.0)

def test_preference_key_is_closed_enum():
    p = Preference(key=PreferenceKey.DIET_TABOO, value="不吃辣")
    assert p.key == PreferenceKey.DIET_TABOO
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_schemas.py -v`
Expected: 全部 FAIL（`ModuleNotFoundError: food_agent.models.schemas`）

- [ ] **Step 3: 写实现 `src/food_agent/models/schemas.py`**

```python
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class PreferenceKey(str, Enum):
    DIET_TABOO = "diet_taboo"
    BUDGET = "budget"
    TASTE = "taste"

class ParsedRequest(BaseModel):
    """需求解析节点输出"""
    location: str
    lnglat: tuple[float, float] | None = None
    categories: list[str] = Field(default_factory=list)
    amap_types: list[str] = Field(default_factory=list)
    budget_max: float | None = Field(default=None, ge=0)
    diet_taboos: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    is_followup: bool = False

    @field_validator("lnglat")
    @classmethod
    def _check_lnglat(cls, v):
        if v is not None and not (-180 <= v[0] <= 180 and -90 <= v[1] <= 90):
            raise ValueError("lnglat 越界")
        return v

class Poi(BaseModel):
    id: str
    name: str
    address: str | None = None
    category: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    avg_price: float | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    source: str
    lnglat: tuple[float, float] | None = None

class Candidate(Poi):
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)

class RecommendationCard(BaseModel):
    name: str
    rating: float | None
    avg_price: float | None
    distance_m: float | None
    tags: list[str]
    score: float
    reasons: list[str]

class Preference(BaseModel):
    key: PreferenceKey
    value: str
    weight: float = 1.0
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_schemas.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/food_agent/models tests/test_schemas.py
git commit -m "feat: 定义结构化数据模型（Pydantic schema）"
```

---

## Task 3: 确定性打分排序

**Files:**
- Create: `src/food_agent/ranking/scorer.py`, `tests/test_ranking.py`

**Interfaces:**
- Consumes: `Poi`、`ParsedRequest`、`Candidate`（来自 Task 2）。
- Produces: `score_candidate(poi: Poi, req: ParsedRequest) -> Candidate`、`rank(pois: list[Poi], req: ParsedRequest, top_k: int = 10) -> list[Candidate]`、`WEIGHTS` 常量。

- [ ] **Step 1: 写失败测试 `tests/test_ranking.py`**

```python
from food_agent.models.schemas import ParsedRequest, Poi
from food_agent.ranking.scorer import rank, score_candidate, WEIGHTS

def _poi(name, rating=None, review_count=None, avg_price=None, distance_m=None, tags=None):
    return Poi(id=name, name=name, source="amap", rating=rating,
               review_count=review_count, avg_price=avg_price,
               distance_m=distance_m, tags=tags or [])

def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

def test_higher_rating_wins():
    req = ParsedRequest(location="x")
    a = _poi("a", rating=4.5, review_count=100, distance_m=1000)
    b = _poi("b", rating=3.0, review_count=100, distance_m=1000)
    assert rank([a, b], req)[0].name == "a"

def test_missing_rating_uses_neutral_not_zero():
    req = ParsedRequest(location="x")
    p = _poi("p", rating=None, review_count=None, distance_m=None)
    s = score_candidate(p, req).score
    assert s > 0  # 无评分给中性分，不直接淘汰

def test_over_budget_penalized():
    req = ParsedRequest(location="x", budget_max=100)
    cheap = _poi("cheap", rating=4.0, review_count=50, avg_price=80, distance_m=1000)
    dear = _poi("dear", rating=4.0, review_count=50, avg_price=300, distance_m=1000)
    assert rank([cheap, dear], req)[0].name == "cheap"

def test_preference_match_boosts():
    req = ParsedRequest(location="x", preferences=["性价比高"])
    hit = _poi("hit", rating=4.0, review_count=50, distance_m=1000, tags=["性价比高"])
    miss = _poi("miss", rating=4.0, review_count=50, distance_m=1000, tags=[])
    assert rank([hit, miss], req)[0].name == "hit"

def test_top_k_limit():
    req = ParsedRequest(location="x")
    pois = [_poi(str(i), rating=4.0, distance_m=1000) for i in range(20)]
    assert len(rank(pois, req, top_k=5)) == 5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_ranking.py -v`
Expected: FAIL（`ModuleNotFoundError: food_agent.ranking.scorer`）

- [ ] **Step 3: 写实现 `src/food_agent/ranking/scorer.py`**

```python
from __future__ import annotations
import math
from food_agent.models.schemas import Candidate, ParsedRequest, Poi

WEIGHTS = {"rating": 0.30, "heat": 0.20, "distance": 0.20, "budget": 0.15, "preference": 0.15}
NEUTRAL_RATING = 2.5   # 无评分时的中性分（0-5 中点）
MAX_DISTANCE_M = 5000  # 距离衰减上限

def _rating_score(p: Poi) -> float:
    return (p.rating if p.rating is not None else NEUTRAL_RATING) / 5.0

def _heat_score(p: Poi) -> float:
    if p.review_count is None:
        return 0.0
    return min(math.log10(p.review_count + 1) / 5.0, 1.0)

def _distance_score(p: Poi) -> float:
    if p.distance_m is None:
        return 0.5
    return max(0.0, 1.0 - p.distance_m / MAX_DISTANCE_M)

def _budget_score(p: Poi, req: ParsedRequest) -> float:
    if req.budget_max is None or p.avg_price is None:
        return 1.0
    if p.avg_price <= req.budget_max:
        return 1.0
    return max(0.0, 1.0 - (p.avg_price - req.budget_max) / req.budget_max)

def _preference_score(p: Poi, req: ParsedRequest) -> float:
    if not req.preferences:
        return 1.0
    text = f"{p.name} {p.category or ''} {' '.join(p.tags)}"
    hits = sum(1 for pref in req.preferences if pref in text)
    return hits / len(req.preferences)

def score_candidate(p: Poi, req: ParsedRequest) -> Candidate:
    score = (
        WEIGHTS["rating"] * _rating_score(p)
        + WEIGHTS["heat"] * _heat_score(p)
        + WEIGHTS["distance"] * _distance_score(p)
        + WEIGHTS["budget"] * _budget_score(p, req)
        + WEIGHTS["preference"] * _preference_score(p, req)
    )
    if req.diet_taboos:
        text = f"{p.name} {p.category or ''} {' '.join(p.tags)}"
        if any(t in text for t in req.diet_taboos):
            score *= 0.3
    return Candidate(**p.model_dump(), score=round(score, 4))

def rank(pois: list[Poi], req: ParsedRequest, top_k: int = 10) -> list[Candidate]:
    cands = [score_candidate(p, req) for p in pois]
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands[:top_k]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_ranking.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/food_agent/ranking tests/test_ranking.py
git commit -m "feat: 确定性打分排序（评分/热度/距离/预算/偏好加权 + 降级）"
```

---

## Task 4: LLM 客户端（DeepSeek）

**Files:**
- Create: `src/food_agent/llm/client.py`, `tests/test_llm.py`

**Interfaces:**
- Produces: `build_llm() -> ChatOpenAI`、`complete_with_retry(messages, response_format=None, retries=3) -> object | str`。后续 parse / extract / 偏好抽取节点都用它。

- [ ] **Step 1: 写失败测试 `tests/test_llm.py`**

```python
from unittest.mock import patch
from food_agent.llm.client import complete_with_retry

def test_retry_on_failure():
    with patch("food_agent.llm.client.build_llm") as mk:
        mk.return_value.invoke.side_effect = [RuntimeError("x"), RuntimeError("y"), "ok"]
        out = complete_with_retry([{"role": "user", "content": "hi"}], retries=3)
        assert out == "ok"
        assert mk.return_value.invoke.call_count == 3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现 `src/food_agent/llm/client.py`**

```python
from __future__ import annotations
import time
from langchain_openai import ChatOpenAI
from food_agent.config import settings

def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.2,
    )

def complete_with_retry(messages, response_format=None, retries=3):
    """带重试的 LLM 调用。response_format 传 Pydantic 类时返回结构化对象，否则返回 str。"""
    llm = build_llm()
    last: Exception | None = None
    for attempt in range(retries):
        try:
            if response_format is not None:
                return llm.with_structured_output(response_format).invoke(messages)
            return llm.invoke(messages).content
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_llm.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/food_agent/llm tests/test_llm.py
git commit -m "feat: 封装 DeepSeek LLM 客户端（带重试 + 结构化输出）"
```

---

## Task 5: 工具抽象 + 高德 POI provider

**Files:**
- Create: `src/food_agent/tools/base.py`, `src/food_agent/tools/amap.py`, `src/food_agent/tools/registry.py`, `tests/test_amap.py`

**Interfaces:**
- Consumes: `Poi`（Task 2）、`settings`（Task 1）。
- Produces:
  - `class PoiSearchTool(ABC)`：`search(query, location, radius, categories) -> list[Poi]`
  - `class WebSearchTool(ABC)`：`search(query) -> list[SearchResult]`
  - `AmapPoiSearch(PoiSearchTool)`
  - `build_amap_params(lnglat, types, keywords, radius) -> dict`（**纯函数，可测**）
  - `map_category_to_types(categories) -> list[str]`（**纯函数，可测**）
  - `get_enabled_tools() -> dict`（注册表）

- [ ] **Step 1: 写失败测试 `tests/test_amap.py`**

```python
from food_agent.tools.amap import AmapPoiSearch, build_amap_params, map_category_to_types

def test_map_category_to_types_falls_back_to_keywords():
    # 不认识「日料」分类码时返回空，靠 keywords 兜底
    assert map_category_to_types(["日料"]) == []

def test_build_amap_params_uses_keywords_when_no_types():
    params = build_amap_params(lnglat=(120.15, 30.28), types=[], keywords="日料", radius=3000)
    assert params["location"] == "120.15,30.28"
    assert params["keywords"] == "日料"
    assert params["radius"] == 3000
    assert "types" not in params or params["types"] == ""

def test_amap_search_parses_response(monkeypatch):
    class FakeResp:
        def json(self):
            return {"status": "1", "pois": [
                {"id": "1", "name": "某日料", "biz_ext": {"rating": "4.5", "cost": "120"},
                 "location": "120.15,30.28", "type": "日料店"}
            ]}
        def raise_for_status(self):
            return None
    def fake_get(*a, **k):
        return FakeResp()
    monkeypatch.setattr("food_agent.tools.amap.httpx.get", fake_get)
    tool = AmapPoiSearch(api_key="test")
    pois = tool.search(query="日料", location=(120.15, 30.28), radius=3000, categories=["日料"])
    assert pois[0].name == "某日料" and pois[0].rating == 4.5 and pois[0].source == "amap"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_amap.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 `src/food_agent/tools/base.py`**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from food_agent.models.schemas import Poi

class PoiSearchTool(ABC):
    @abstractmethod
    def search(self, query: str, location: tuple[float, float], radius: int,
               categories: list[str]) -> list[Poi]: ...

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

class WebSearchTool(ABC):
    @abstractmethod
    def search(self, query: str) -> list[SearchResult]: ...
```

- [ ] **Step 4: 写 `src/food_agent/tools/amap.py`**

```python
from __future__ import annotations
import httpx
from food_agent.models.schemas import Poi
from food_agent.tools.base import PoiSearchTool

AMAP_AROUND_URL = "https://restapi.amap.com/v5/place/around"

def map_category_to_types(categories: list[str]) -> list[str]:
    """品类关键词 → 高德 types 分类码。MVP 由 LLM 在解析阶段直接产出 amap_types，
    这里仅作兜底（返回空表示不传 types、改用 keywords）。"""
    return []

def build_amap_params(lnglat: tuple[float, float], types: list[str], keywords: str,
                      radius: int) -> dict:
    params = {
        "location": f"{lnglat[0]},{lnglat[1]}",
        "keywords": keywords,
        "radius": radius,
        "sortrule": "weight",
    }
    if types:
        params["types"] = "|".join(types)
    return params

class AmapPoiSearch(PoiSearchTool):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, location: tuple[float, float], radius: int,
               categories: list[str]) -> list[Poi]:
        types = map_category_to_types(categories)
        params = build_amap_params(location, types, keywords=query, radius=radius)
        params["key"] = self.api_key
        resp = httpx.get(AMAP_AROUND_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return []
        pois: list[Poi] = []
        for item in data.get("pois", []):
            biz = item.get("biz_ext") or {}
            lng, lat = item["location"].split(",")
            pois.append(Poi(
                id=item["id"], name=item["name"], address=item.get("address"),
                category=item.get("type"),
                rating=float(biz["rating"]) if biz.get("rating") else None,
                avg_price=float(biz["cost"]) if biz.get("cost") else None,
                source="amap", lnglat=(float(lng), float(lat)),
            ))
        return pois
```

- [ ] **Step 5: 写 `src/food_agent/tools/registry.py`**

```python
from __future__ import annotations
from food_agent.config import settings
from food_agent.tools.amap import AmapPoiSearch

def get_enabled_tools() -> dict:
    """按 .env 装配启用项；未配置 Key 的 provider 自动跳过。"""
    tools: dict = {}
    if settings.amap_api_key:
        tools["poi"] = AmapPoiSearch(settings.amap_api_key)
    # WebSearch 在 Task 6 补上
    return tools
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/test_amap.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/food_agent/tools tests/test_amap.py
git commit -m "feat: 工具抽象层与高德 POI provider（参数构造可测）"
```

---

## Task 6: 存储层（SQLAlchemy + Alembic）

**Files:**
- Create: `src/food_agent/storage/db.py`, `src/food_agent/storage/models.py`, `tests/test_storage.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/`（首次迁移）

**Interfaces:**
- Consumes: `settings`（Task 1）、`Preference`/`PreferenceKey`（Task 2）。
- Produces:
  - `SessionRow` / `MessageRow` / `FavoriteRow` / `PreferenceRow`（SQLAlchemy ORM）
  - `get_engine()`、`get_session()`（sessionmaker）
  - `upsert_preference(session, pref: Preference) -> None`（同类 key+value 覆盖）

- [ ] **Step 1: 写失败测试 `tests/test_storage.py`**（用 SQLite 内存库，不依赖本机 MySQL）

```python
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
    upsert_preference(db_session, Preference(key=PreferenceKey.BUDGET, value="100"))
    upsert_preference(db_session, Preference(key=PreferenceKey.BUDGET, value="150"))
    rows = db_session.query(PreferenceRow).all()
    assert len(rows) == 1 and rows[0].value == "150"

def test_session_row_roundtrip(db_session):
    db_session.add(SessionRow(thread_id="t1", title="找日料"))
    db_session.commit()
    assert db_session.query(SessionRow).filter_by(thread_id="t1").one().title == "找日料"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 `src/food_agent/storage/db.py`**

```python
from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from food_agent.config import settings
from food_agent.models.schemas import Preference
from food_agent.storage.models import PreferenceRow

_engine = create_engine(settings.mysql_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)

def get_session() -> Session:
    return SessionLocal()

def upsert_preference(session: Session, pref: Preference) -> None:
    row = session.query(PreferenceRow).filter_by(key=pref.key.value, value=pref.value).one_or_none()
    if row:
        row.weight = pref.weight
    else:
        session.add(PreferenceRow(key=pref.key.value, value=pref.value, weight=pref.weight))
    session.commit()
```

- [ ] **Step 4: 写 `src/food_agent/storage/models.py`**

```python
from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class SessionRow(Base):
    __tablename__ = "session"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MessageRow(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class FavoriteRow(Base):
    __tablename__ = "favorite"
    id: Mapped[int] = mapped_column(primary_key=True)
    poi_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PreferenceRow(Base):
    __tablename__ = "preference"
    __table_args__ = (UniqueConstraint("key", "value", name="uq_preference_key_value"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(255))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/test_storage.py -v`
Expected: 2 passed

- [ ] **Step 6: 生成 Alembic 迁移**

```bash
alembic init alembic
# 手动把 env.py 的 target_metadata 指到 food_agent.storage.models.Base.metadata
alembic revision --autogenerate -m "init session message favorite preference"
alembic upgrade head
```

Expected: `alembic upgrade head` 在本机 MySQL 8 建出 4 张表。

- [ ] **Step 7: Commit**

```bash
git add src/food_agent/storage alembic.ini alembic tests/test_storage.py
git commit -m "feat: 存储层（SQLAlchemy 模型 + Alembic 迁移 + 偏好 upsert）"
```

---

## Task 7: WebSearch 工具（可选 + 降级）

**Files:**
- Create: `src/food_agent/tools/web.py`, `tests/test_web.py`
- Modify: `src/food_agent/tools/registry.py`

**Interfaces:**
- Consumes: `WebSearchTool` / `SearchResult`（Task 5）、`settings`。
- Produces: `TavilySearch(WebSearchTool)`、`DuckDuckGoSearch(WebSearchTool)`；`registry.get_enabled_tools()` 仅在配了 Key 时挂 `web`。

- [ ] **Step 1: 写失败测试 `tests/test_web.py`**

```python
from food_agent.config import settings
from food_agent.tools.registry import get_enabled_tools

def test_web_search_absent_without_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setattr(settings, "amap_api_key", "test")
    assert "web" not in get_enabled_tools()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_web.py -v`
Expected: FAIL（`get_enabled_tools` 还没有 web 逻辑）

- [ ] **Step 3: 写 `src/food_agent/tools/web.py`**

```python
from __future__ import annotations
import httpx
from food_agent.tools.base import SearchResult, WebSearchTool

class TavilySearch(WebSearchTool):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str) -> list[SearchResult]:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": self.api_key, "query": query, "max_results": 5},
            timeout=10,
        )
        resp.raise_for_status()
        return [
            SearchResult(title=r["title"], url=r["url"], snippet=r.get("content", ""))
            for r in resp.json().get("results", [])
        ]

class DuckDuckGoSearch(WebSearchTool):
    def search(self, query: str) -> list[SearchResult]:
        return []  # 免费但国内可能不通，默认返回空并标注降级
```

- [ ] **Step 4: 更新 `src/food_agent/tools/registry.py`**

```python
from food_agent.config import settings
from food_agent.tools.amap import AmapPoiSearch
from food_agent.tools.web import TavilySearch

def get_enabled_tools() -> dict:
    tools: dict = {}
    if settings.amap_api_key:
        tools["poi"] = AmapPoiSearch(settings.amap_api_key)
    if settings.tavily_api_key:
        tools["web"] = TavilySearch(settings.tavily_api_key)
    return tools
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/test_web.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add src/food_agent/tools tests/test_web.py
git commit -m "feat: WebSearch 工具（Tavily，未配置时自动降级）"
```

---

## Task 8: 偏好记忆（抽取 + 存储）

**Files:**
- Create: `src/food_agent/memory/extract.py`, `tests/test_memory.py`

**Interfaces:**
- Consumes: `complete_with_retry`（Task 4）、`Preference`（Task 2）、`upsert_preference`（Task 6）。
- Produces: `extract_preferences(user_text: str) -> list[Preference]`、`remember(session, user_text) -> list[Preference]`。

- [ ] **Step 1: 写失败测试 `tests/test_memory.py`**

```python
from unittest.mock import patch
from food_agent.models.schemas import Preference, PreferenceKey
from food_agent.memory.extract import extract_preferences

def test_extract_preferences_parses_closed_keys(monkeypatch):
    class FakePrefs:
        prefs = [Preference(key=PreferenceKey.DIET_TABOO, value="不吃辣")]
    monkeypatch.setattr("food_agent.memory.extract.complete_with_retry",
                        lambda msgs, response_format: FakePrefs())
    out = extract_preferences("我不吃辣，预算 100 以内")
    assert out[0].value == "不吃辣"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_memory.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 `src/food_agent/memory/extract.py`**

```python
from __future__ import annotations
from pydantic import BaseModel, Field
from food_agent.models.schemas import Preference
from food_agent.llm.client import complete_with_retry
from food_agent.storage.db import upsert_preference

class PreferenceList(BaseModel):
    prefs: list[Preference] = Field(default_factory=list)

_SYSTEM = (
    "从用户这句话里抽取可复用的饮食偏好，只输出封闭类型："
    "diet_taboo（口味禁忌）、budget（预算）、taste（口味偏好）。没有则不输出该项。"
)

def extract_preferences(user_text: str) -> list[Preference]:
    msgs = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_text},
    ]
    result = complete_with_retry(msgs, response_format=PreferenceList)
    return result.prefs
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_memory.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/food_agent/memory tests/test_memory.py
git commit -m "feat: 偏好抽取（LLM 封闭类型 + 结构化输出）"
```

---

## Task 9: RAG 向量检索（Chroma + embedding）

**Files:**
- Create: `src/food_agent/rag/store.py`, `tests/test_rag.py`

**Interfaces:**
- Consumes: `settings`、`Poi`（Task 2）。
- Produces: `VectorStore` 类，方法 `add_pois(pois: list[Poi])`、`search(query: str, k: int = 5) -> list[Poi]`。冷启动（无数据）返回 `[]`，不抛异常。

- [ ] **Step 1: 写失败测试 `tests/test_rag.py`**

```python
from food_agent.rag.store import VectorStore

def test_empty_store_returns_empty(monkeypatch):
    store = VectorStore.__new__(VectorStore)  # 跳过 __init__，不连真实 Chroma
    monkeypatch.setattr(store, "_collection", None)
    assert store.search("日料", k=5) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_rag.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 `src/food_agent/rag/store.py`**

```python
from __future__ import annotations
import chromadb
from food_agent.config import settings
from food_agent.models.schemas import Poi

class VectorStore:
    """Chroma 本地持久化。embedding 用 SiliconFlow 远程；未配置时用 Chroma 默认。
    冷启动（无历史数据）search 返回空列表，不影响主链路。"""
    def __init__(self):
        self._client = chromadb.PersistentClient(path=settings.chroma_dir)
        self._collection = self._client.get_or_create_collection(name="favorites")

    def add_pois(self, pois: list[Poi]) -> None:
        if not pois:
            return
        self._collection.upsert(
            ids=[p.id for p in pois],
            documents=[f"{p.name} {p.category or ''} {' '.join(p.tags)}" for p in pois],
        )

    def search(self, query: str, k: int = 5) -> list[Poi]:
        if self._collection is None or self._collection.count() == 0:
            return []
        res = self._collection.query(query_texts=[query], n_results=k)
        # 命中结果需回查业务库取完整 Poi；MVP 先返回空占位，Task 12 端到端前补
        return []
```

> 注：`search` 的完整回查（doc id → 完整 Poi）依赖业务库，在 Task 12 集成时补全；本任务只验证冷启动降级与接口。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_rag.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/food_agent/rag tests/test_rag.py
git commit -m "feat: RAG 向量存储（Chroma + 冷启动降级）"
```

---

## Task 10: LangGraph 编排（节点 + 追问路由 + checkpointer）

**Files:**
- Create: `src/food_agent/graph/state.py`, `src/food_agent/graph/nodes.py`, `src/food_agent/graph/build.py`, `tests/test_graph.py`

**Interfaces:**
- Consumes: `ParsedRequest`/`Poi`/`Candidate`/`RecommendationCard`（Task 2）、`complete_with_retry`（Task 4）、`get_enabled_tools`（Task 5/7）、`rank`（Task 3）。
- Produces:
  - `GraphState`（TypedDict：`user_input`, `parsed: ParsedRequest`, `pois: list[Poi]`, `candidates: list[Candidate]`, `cards: list[RecommendationCard]`）
  - `parse_node` / `retrieve_node` / `extract_node` / `rank_node` / `card_node` / `memory_node`
  - `build_graph(checkpointer) -> CompiledGraph`
  - `route_after_parse(state) -> "retrieve" | "rank"`（追问路由）

- [ ] **Step 1: 写失败集成测试 `tests/test_graph.py`**（mock 工具与 LLM，跑通整条图）

```python
from unittest.mock import patch
from langgraph.checkpoint.sqlite import SqliteSaver
from food_agent.models.schemas import ParsedRequest, Poi
from food_agent.graph.build import build_graph

def test_full_flow_with_mocked_tools(tmp_path):
    req = ParsedRequest(location="杭州西湖", categories=["日料"], lnglat=(120.15, 30.28))
    poi = Poi(id="1", name="某日料", rating=4.5, review_count=100,
              avg_price=120, distance_m=1000, source="amap")

    class FakePoiTool:
        def search(self, query, location, radius, categories):
            return [poi]

    with patch("food_agent.graph.nodes.complete_with_retry", return_value=req), \
         patch("food_agent.graph.nodes.get_enabled_tools", return_value={"poi": FakePoiTool()}):
        with SqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as ckpt:
            graph = build_graph(ckpt)
            result = graph.invoke(
                {"user_input": "杭州西湖附近日料"},
                {"configurable": {"thread_id": "t1"}},
            )
    assert len(result["cards"]) == 1
    assert result["cards"][0].name == "某日料"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_graph.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 `src/food_agent/graph/state.py`**

```python
from __future__ import annotations
from typing import TypedDict
from food_agent.models.schemas import Candidate, ParsedRequest, Poi, RecommendationCard

class GraphState(TypedDict, total=False):
    user_input: str
    parsed: ParsedRequest
    pois: list[Poi]
    candidates: list[Candidate]
    cards: list[RecommendationCard]
```

- [ ] **Step 4: 写 `src/food_agent/graph/nodes.py`**（核心节点）

```python
from __future__ import annotations
import asyncio
from food_agent.llm.client import complete_with_retry
from food_agent.models.schemas import ParsedRequest, Poi, Candidate, RecommendationCard
from food_agent.ranking.scorer import rank
from food_agent.tools.registry import get_enabled_tools
from food_agent.graph.state import GraphState

def parse_node(state: GraphState) -> dict:
    msgs = [{"role": "user", "content": state["user_input"]}]
    parsed = complete_with_retry(msgs, response_format=ParsedRequest)
    return {"parsed": parsed}

def retrieve_node(state: GraphState) -> dict:
    parsed: ParsedRequest = state["parsed"]
    tools = get_enabled_tools()
    poi_tool = tools.get("poi")
    pois: list[Poi] = []
    if poi_tool is not None and parsed.lnglat is not None:
        # 并行：POI 检索 + 向量召回（冷启动为空）
        loop_results = asyncio.run(
            asyncio.gather(
                _search_poi(poi_tool, parsed),
                _search_rag(parsed),
            )
        )
        pois = loop_results[0] + loop_results[1]
    return {"pois": pois}

async def _search_poi(poi_tool, parsed):
    return poi_tool.search(parsed.categories[0] if parsed.categories else "",
                           parsed.lnglat, 3000, parsed.categories)

async def _search_rag(parsed):
    from food_agent.rag.store import VectorStore
    try:
        return VectorStore().search(" ".join(parsed.categories), k=5)
    except Exception:
        return []

def extract_node(state: GraphState) -> dict:
    # 结构化抽取：把散乱 POI 统一成候选。MVP 直接透传（POI 已结构化），
    # 多源 WebSearch 结果合并的抽取逻辑在 Task 12 补。
    return {"pois": state["pois"]}

def rank_node(state: GraphState) -> dict:
    candidates = rank(state["pois"], state["parsed"], top_k=10)
    return {"candidates": candidates}

def card_node(state: GraphState) -> dict:
    cards = [
        RecommendationCard(name=c.name, rating=c.rating, avg_price=c.avg_price,
                           distance_m=c.distance_m, tags=c.tags, score=c.score,
                           reasons=c.reasons)
        for c in state["candidates"]
    ]
    return {"cards": cards}

def memory_node(state: GraphState) -> dict:
    # 偏好记忆写入（Task 8 的 extract + upsert），MVP 先占位，Task 12 接通
    return {}
```

- [ ] **Step 5: 写 `src/food_agent/graph/build.py`**

```python
from __future__ import annotations
from langgraph.graph import END, StateGraph
from food_agent.graph.state import GraphState
from food_agent.graph import nodes

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
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/test_graph.py -v`
Expected: 1 passed

- [ ] **Step 7: Commit**

```bash
git add src/food_agent/graph tests/test_graph.py
git commit -m "feat: LangGraph 编排（节点 + 追问路由 + SQLite checkpointer）"
```

---

## Task 11: FastAPI + SSE 流式接口

**Files:**
- Create: `src/food_agent/api/main.py`

**Interfaces:**
- Consumes: `build_graph`（Task 10）、`SqliteSaver`、`settings`。
- Produces: FastAPI app，`POST /chat`（body `{"thread_id": ..., "message": ...}`）→ SSE 流，事件按顺序为 `node`（节点名）、`cards`（最终卡片 JSON）。

- [ ] **Step 1: 写 `src/food_agent/api/main.py`**

```python
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from food_agent.graph.build import build_graph

app = FastAPI(title="Wander 本地生活推荐 Agent")
_checkpointer = SqliteSaver.from_conn_string("./checkpoints.sqlite")
_graph = build_graph(_checkpointer)

class ChatIn(BaseModel):
    thread_id: str
    message: str

@app.post("/chat")
async def chat(body: ChatIn):
    async def event_stream():
        async for event in _graph.astream_events(
            {"user_input": body.message},
            {"configurable": {"thread_id": body.thread_id}},
            version="v2",
        ):
            kind = event["event"]
            if kind == "on_chain_start" and "node" in (event.get("tags") or []):
                yield {"event": "node", "data": event["name"]}
            if kind == "on_chain_end" and event["name"] == "card":
                yield {"event": "cards", "data": event["data"]["output"]["cards"]}
    return EventSourceResponse(event_stream())

def run():
    import uvicorn
    uvicorn.run("food_agent.api.main:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 2: 冒烟测试（需 `deepseek_api_key` + `amap_api_key`）**

Run: `uvicorn food_agent.api.main:app --port 8000`
Expected: 启动无报错，`curl -N -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"thread_id":"t1","message":"杭州西湖附近日料"}'` 能收到 SSE 事件流。

- [ ] **Step 3: Commit**

```bash
git add src/food_agent/api
git commit -m "feat: FastAPI + SSE 流式接口（节点轨迹 + 卡片）"
```

---

## Task 12: 前端 + 端到端收尾

**Files:**
- Create: `frontend/index.html`, `frontend/app.js`
- Modify: `README.md`（补「快速开始」）、`src/food_agent/rag/store.py`（补完整回查）、`src/food_agent/graph/nodes.py`（接通 memory_node）

**Interfaces:**
- Consumes: `/chat` SSE 接口（Task 11）。
- Produces: 浏览器可打开的单页，输入框 → SSE 流 → 节点轨迹 + 推荐卡片列表。

- [ ] **Step 1: 写 `frontend/index.html`**

```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>Wander · 吃喝玩乐推荐</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; }
    #trace { color: #888; font-size: 14px; min-height: 1.5em; }
    .card { border: 1px solid #eee; border-radius: 8px; padding: 12px 16px; margin: 8px 0; }
    .card .name { font-size: 18px; font-weight: 600; }
    .card .meta { color: #666; font-size: 13px; }
  </style>
</head>
<body>
  <h1>Wander · 吃喝玩乐推荐</h1>
  <input id="msg" placeholder="试试：杭州西湖附近，性价比高的日料" style="width:70%" />
  <button id="send">推荐</button>
  <div id="trace"></div>
  <div id="cards"></div>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 写 `frontend/app.js`**

```javascript
const threadId = "t" + Math.random().toString(36).slice(2);
const traceEl = document.getElementById("trace");
const cardsEl = document.getElementById("cards");

document.getElementById("send").onclick = async () => {
  const message = document.getElementById("msg").value;
  cardsEl.innerHTML = "";
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, message }),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    for (const line of buf.split("\n")) {
      if (line.startsWith("data: ")) {
        const { event, data } = JSON.parse(line.slice(6));
        if (event === "node") traceEl.textContent = "思考中 → " + data;
        if (event === "cards") renderCards(data);
      }
    }
    buf = "";
  }
};

function renderCards(cards) {
  cardsEl.innerHTML = cards.map((c) => `
    <div class="card">
      <div class="name">${c.name} ${"★".repeat(Math.round((c.rating || 0))) || ""}</div>
      <div class="meta">评分 ${c.rating ?? "—"} · 人均 ¥${c.avg_price ?? "—"} · ${c.distance_m ?? "—"}m · 综合 ${c.score.toFixed(2)}</div>
    </div>`).join("");
}
```

- [ ] **Step 3: 接通 `memory_node` 与 RAG 回查**

`nodes.memory_node` 改为调用 `extract_preferences` + `upsert_preference`（Task 8 接口）；`rag.store.VectorStore.search` 补「doc id → 完整 Poi」回查。具体以真实数据联调为准。

- [ ] **Step 4: 端到端验收（对照 DoD）**

在 `.env` 填 `DEEPSEEK_API_KEY`、`AMAP_API_KEY` 后：
1. `pip install -e ".[dev]"` 成功。
2. `alembic upgrade head` 建表成功。
3. `uvicorn food_agent.api.main:app --port 8000` + 打开 `frontend/index.html`，一条「找附近日料店」端到端出卡片。
4. 追问「换便宜的」复用候选、不重新检索。
5. 注释掉 `TAVILY_API_KEY`，仅靠高德 POI 仍出结果。

- [ ] **Step 5: 补 README「快速开始」**

在 `README.md` 增加：

```markdown
## 快速开始

1. `pip install -e ".[dev]"`
2. `cp .env.example .env` 并填入 `DEEPSEEK_API_KEY`、`AMAP_API_KEY`、`MYSQL_URL`
3. `alembic upgrade head`
4. `uvicorn food_agent.api.main:app --port 8000`
5. 浏览器打开 `frontend/index.html`
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: 前端卡片渲染 + 端到端闭环 + README 快速开始"
```

---

## Task 13: 收藏链路（写库 + 向量索引）

**Files:**
- Create: `tests/test_favorite.py`
- Modify: `src/food_agent/storage/db.py`, `src/food_agent/rag/store.py`, `src/food_agent/api/main.py`, `frontend/index.html`, `frontend/app.js`

**Interfaces:**
- Consumes: `FavoriteRow`（Task 6）、`VectorStore.add_pois`（Task 9）、`Poi`（Task 2）。
- Produces: `add_favorite(session, poi: Poi) -> None`；`POST /favorite`（body `{"poi": {...Poi 字段}}`，写 favorite 表 + 向量库）；前端收藏按钮。

- [ ] **Step 1: 写失败测试 `tests/test_favorite.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_favorite.py -v`
Expected: FAIL（`add_favorite` 不存在）

- [ ] **Step 3: 在 `storage/db.py` 加 `add_favorite`**

```python
from food_agent.models.schemas import Poi
from food_agent.storage.models import FavoriteRow

def add_favorite(session: Session, poi: Poi) -> None:
    if session.query(FavoriteRow).filter_by(poi_id=poi.id).one_or_none() is None:
        session.add(FavoriteRow(poi_id=poi.id, name=poi.name))
        session.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_favorite.py -v`
Expected: 1 passed

- [ ] **Step 5: 在 `api/main.py` 加 `POST /favorite`**

```python
from food_agent.models.schemas import Poi
from food_agent.storage.db import add_favorite, get_session
from food_agent.rag.store import VectorStore

class FavoriteIn(BaseModel):
    poi: Poi

@app.post("/favorite")
async def favorite(body: FavoriteIn):
    with get_session() as s:
        add_favorite(s, body.poi)
    VectorStore().add_pois([body.poi])  # 同步进向量库，供语义召回
    return {"ok": True}
```

- [ ] **Step 6: 前端加收藏按钮**

`app.js` 卡片渲染处给每张卡片加一个「收藏」按钮，点击 `fetch("/favorite", {method:"POST", body: JSON.stringify({poi: {...}})})`。卡片 `data-*` 属性暂存 Poi 原始字段，供回传。

- [ ] **Step 7: Commit**

```bash
git add src/food_agent/storage/db.py src/food_agent/api/main.py src/food_agent/rag/store.py frontend tests/test_favorite.py
git commit -m "feat: 收藏链路（写 favorite 表 + 向量索引 + POST /favorite）"
```

---

## 自查清单（Self-Review 结论）

- **Spec 覆盖**：核心闭环（Task 2/3/10/11）、多轮偏好（Task 8 + Task 12 接通）、RAG（Task 9）、收藏/历史（Task 6 建表 + Task 13 收藏写入链路）。
- **占位扫描**：`extract_node` 的「多源合并抽取」、`memory_node` 的「接通」、`VectorStore.search` 的「回查」三处标注为 Task 12 补全，均已给出目标接口，非无界 TODO。
- **类型一致性**：`Poi`/`Candidate`/`RecommendationCard`/`ParsedRequest` 字段全程统一；`rank` / `score_candidate` / `get_enabled_tools` / `complete_with_retry` 签名跨任务一致。

### 收藏链路

- 已拆为独立 Task 13（收藏写库 + 向量索引 + `POST /favorite` + 前端按钮），见上方。
