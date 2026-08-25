# Wander — 本地生活推荐 Agent

> 「吃喝玩乐」本地生活推荐 Agent：一句话需求，LangGraph 编排「需求解析 → 多源检索 → 结构化抽取 → 打分排序 → 流式卡片」全流程。

## 简介

Wander 是一个「吃 / 喝 / 玩 / 乐」本地生活推荐 Agent。用户用自然语言说一句「帮我找附近性价比高的日料店」，Agent 自主完成理解需求、多源检索、结构化抽取、打分排序，并生成推荐卡片，同时以流式方式展示思考过程与工具调用轨迹。

## 特性

- **一句话闭环**：输入「位置 + 需求」→ 检索 → 抽取 → 打分 → 推荐卡片。
- **多轮偏好记忆**：记住「不吃辣 / 预算 / 口味」，二次筛选自动复用。
- **RAG 语义召回**：历史结果 / 收藏做向量检索，支持「氛围好的约会餐厅」这类模糊需求。
- **收藏 / 历史记录**：持久化查询历史与收藏。
- **可拔插工具层**：高德 / 百度 / WebSearch 通过配置切换，未配置 Key 时自动降级，主链路照常跑通。
- **确定性打分**：评分 / 热度 / 距离 / 预算 / 偏好匹配加权，不靠 LLM 拍脑袋。

## 技术栈

| 层 | 选型 |
|---|---|
| 语言 | Python 3.11+ |
| Agent 编排 | LangGraph |
| LLM | DeepSeek（`deepseek-chat`） |
| 后端 | FastAPI + SSE（流式） |
| 数据库 | MySQL 8+（SQLAlchemy + Alembic） |
| 向量库 | Chroma（本地持久化） |
| Embedding | SiliconFlow（备选本地 `bge-small-zh`） |
| 前端 | 原生 HTML + JS + SSE |

## 快速开始

1. `pip install -e ".[dev]"`
2. `cp .env.example .env` 并填入 `DEEPSEEK_API_KEY`、`AMAP_API_KEY`、`MYSQL_URL`
3. `alembic upgrade head`
4. `uvicorn food_agent.api.main:app --port 8000`
5. 浏览器打开 http://localhost:8000

> 提示：如果切换 embedding（配置或清空 `SILICONFLOW_API_KEY`），需先删除 `./chroma_data`（不同 embedding 的向量维度不一致，混用会导致检索失败）。

## 架构

```
需求解析 → 检索（高德 POI / 口碑 / 向量召回，并行）→ 结构化抽取 → 打分排序 → 生成卡片 → 记忆更新
```

- 多轮追问靠 LangGraph `checkpointer` 持久化会话状态；「太贵了换便宜的」回到排序节点复用候选，不重新检索。
- 结构化输出由 Pydantic schema 约束，保证下游排序与前端渲染拿到稳定 JSON。
- Graph 只依赖抽象接口，具体 provider 通过「注册表 + 配置」装配（`.env` 指定启用项）。

## 已知限制（MVP）

- **WebSearch 未接线**：WebSearch（Tavily）工具已装配并有测试，但检索链路暂未接入；spec「三检索并行」中的 web 检索留待下一增量。
- **偏好记忆仅写入链路**：偏好记忆当前只实现「抽取 + 持久化」；存量偏好自动注入后续排序的「读回路」留待下一增量。
- **收藏 / 历史仅写入链路**：收藏 / 历史当前只实现「写入」；历史与收藏的查询 / 列表端点尚未实现（表结构已就绪，免迁移）。

## 当前状态

**设计阶段** —— 架构与数据模型已完成设计，代码实现进行中。

完整设计文档见 [`docs/superpowers/specs/2026-08-25-food-explorer-agent-design.md`](docs/superpowers/specs/2026-08-25-food-explorer-agent-design.md)。

## 目录结构（计划）

```
wander/
├── src/food_agent/
│   ├── graph/      # LangGraph 状态图
│   ├── tools/      # 检索工具接口 + provider
│   ├── rag/        # Chroma + embedding
│   ├── memory/     # 偏好记忆
│   ├── ranking/    # 确定性打分
│   ├── models/     # Pydantic schema
│   ├── api/        # FastAPI + SSE
│   └── storage/    # SQLAlchemy + Alembic
├── frontend/       # 原生 HTML + JS
└── tests/
```

## Roadmap

- [ ] 核心闭环（解析 → 检索 → 抽取 → 打分 → 卡片）
- [ ] 多轮偏好记忆
- [ ] RAG 向量检索
- [ ] 收藏 / 历史记录
- [ ] 单元测试（打分排序、schema 校验、工具参数构造）
