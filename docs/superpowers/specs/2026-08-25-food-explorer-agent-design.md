# 本地生活推荐 Agent 设计文档（Wander）

- 日期：2026-08-25
- 状态：已评审（2026-08-25）
- 作者：用户 + Claude Code

## 1. 目标与定位

一个「吃喝玩乐」本地生活推荐 Agent：用户用自然语言说一句「帮我找附近性价比高的日料店」，Agent 自主完成「理解需求 → 多源检索 → 结构化抽取 → 打分排序 → 生成推荐卡片」，并以流式方式展示思考过程与工具调用轨迹。

**简历定位**：与上一个「纯手搓 Java 求职 Agent」形成互补。上一个证明「懂 Agent 底层原理」，这一个证明「会用业界主流框架（LangChain/LangGraph）+ 落地完整业务场景」。

## 2. 业务场景与范围

### 覆盖品类（吃 / 喝 / 玩 / 乐）

品类不是写死的，需求解析节点用 LLM 把自然语言映射成「品类关键词 + 高德 POI 分类」，任意品类走同一流程：

- **吃**：中餐、日料、火锅、烧烤、甜品、小吃…
- **喝**：咖啡厅、奶茶、酒吧、茶馆…
- **玩**：KTV、密室逃脱、桌游、电影院、剧本杀…
- **乐**：景点、博物馆、游乐园、演出、运动场馆…

### MVP 范围（本次实现）

- 核心闭环：输入「位置 + 需求」→ 检索 → 结构化抽取 → 打分排序 → 推荐卡片。
- 多轮偏好记忆：记住「不吃辣 / 预算 / 口味」等，二次筛选复用。
- RAG 向量检索：历史结果 / 收藏做语义召回，支持「氛围好的约会餐厅」这类模糊需求。
- 收藏 / 历史记录：持久化查询历史与收藏。

### 明确不做（后续延伸）

- 「吃 + 玩组合」的行程规划（先吃日料再看电影并排路线）。
- 登录注册 / 多用户系统（先单用户 demo，匿名身份即可）。
- 移动端定位（先由用户输入地点/城市名，再经高德地理编码解析坐标）。

## 3. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11+ | |
| Agent 编排 | LangGraph | 状态图建模多步推荐流程 |
| LLM | DeepSeek（`deepseek-chat`） | 延续上个项目，有 Key、成本低 |
| 后端 | FastAPI + SSE | 主流、原生流式 |
| 数据库 | MySQL 8+（SQLAlchemy + Alembic） | 仅存业务数据（会话/消息/收藏/偏好） |
| 会话持久化 | SQLite（`langgraph-checkpoint-sqlite`） | 官方支持、零配置，单用户 demo 足够 |
| 向量库 | Chroma（本地持久化） | 零额外服务 |
| Embedding | 硅基流动 SiliconFlow 免费 API（备选本地 `bge-small-zh`） | DeepSeek 无 embedding 接口 |
| 前端 | 原生 HTML + JS + SSE | 复用上个项目模式 |

## 4. 架构（LangGraph 状态图）

```
用户输入「杭州西湖附近，性价比高的日料」
        │
        ▼
┌─────────────────┐  解析出 {地点, 品类, 预算, 口味禁忌, 偏好}
│ ① 需求解析      │  并合并历史偏好 ──────────────────────────┐
└────────┬────────┘                                         │
         ▼                                                  │
┌─────────────────┐  并行调用三个检索：                       │
│ ② 检索          │  · PoiSearchTool（高德/百度 POI）        │
│                 │  · WebSearchTool（口碑/热门，可选）       │
│                 │  · 向量库语义召回（历史收藏/相似偏好）     │
└────────┬────────┘                                         │
         ▼                                                  │
┌─────────────────┐  LLM 把杂乱结果抽取成统一候选 JSON        │
│ ③ 结构化抽取     │  (店名/评分/价格/距离/标签/来源/理由)      │
└────────┬────────┘                                         │
         ▼                                                  │
┌─────────────────┐  确定性打分：评分+热度+距离+预算+偏好匹配   │
│ ④ 打分排序       │  （不靠 LLM 拍脑袋）                     │
└────────┬────────┘                                         │
         ▼                                                  │
┌─────────────────┐  生成推荐文本 + 结构化卡片 JSON           │
│ ⑤ 生成卡片       │  供前端渲染成卡片列表                     │
└────────┬────────┘                                         │
         ▼                                                  │
┌─────────────────┐  LLM 抽取本轮偏好 → 写入记忆库(upsert) ────┘
│ ⑥ 记忆更新       │
└─────────────────┘
```

- **多轮/追问**：靠 LangGraph `checkpointer`（SQLite）持久化会话状态。「追问 vs 新查询」由需求解析节点内的轻量路由判定：LLM 判断 + 关键词规则兜底（「太贵 / 换 / 便宜」等）。判定为追问时，不重新检索，回到「排序」节点对上一轮候选重新过滤排序；判定为新查询则走完整检索链路。
- **结构化输出**：LLM 抽取 / 生成均通过 Pydantic schema 约束，保证下游排序与前端渲染拿到稳定 JSON。
- **流式输出**：通过 LangGraph `astream_events` + FastAPI SSE 把「节点流转 + 工具调用轨迹」推到前端，粒度控制在节点级 + 工具调用级，不做 token 级。
- **并行检索实现**：三个检索在「检索」节点内部用 `asyncio.gather` 并行，graph 结构保持线性。
- **向量召回冷启动**：首次查询无历史收藏时，语义召回返回空，不影响主链路。

## 5. 工具层（可拔插，不硬编码）

Graph 只依赖抽象接口，不 import 具体 provider。具体实现通过「注册表 + 配置」装配（`.env` 指定启用项）。

```python
class PoiSearchTool(ABC):      # 搜店：附近 + 品类
    def search(self, query, location, radius, category) -> list[Poi]

class WebSearchTool(ABC):      # 搜口碑：热门 / 平台提及
    def search(self, query) -> list[SearchResult]
```

| 接口 | 实现（provider） | 默认 | 说明 |
|---|---|---|---|
| `PoiSearchTool` | `AmapPoiSearch` | ✅ | 高德 POI：评分/距离/价格/标签 |
| `PoiSearchTool` | `BaiduMapPoiSearch` | 可选 | 百度地图 Place API，做跨源交叉印证 |
| `WebSearchTool` | `TavilySearch` | 可选 | 质量最好，有免费额度 |
| `WebSearchTool` | `DuckDuckGoSearch` | 可选 | 免费，国内可能不通 |

**口碑信号的现实处理**：主用 POI 自带的「评分 + 评论数」（高德/百度都有，免费国内可用）；`WebSearchTool` 作为「热门/平台提及」加分项。**未配置搜索 Key 时自动降级为纯 POI 评分**，主链路照常跑通，演示不卡在第三方额度。

**评分缺失降级**：高德普通 POI 仅认证商户带 `biz_ext.rating`，大量小店无评分。打分时按「评分 → 评论数/热度 → 中性分」逐级兜底，不直接淘汰无评分项。

**品类分类码映射**：不维护大静态映射表，由需求解析节点用 LLM 把品类映射到高德 `types` 分类码，并以 `keywords` 关键词搜索兜底，覆盖 LLM 不认识的品类。

## 6. 数据模型（MySQL）

| 表 | 用途 |
|---|---|
| `session` | 会话元数据（thread_id、创建时间、标题摘要），供「历史会话列表」展示；thread_id 关联 SQLite checkpointer |
| `message` | 对话消息（用户输入 + Agent 输出），供前端展示历史 |
| `favorite` | 收藏（用户收藏的店铺） |
| `preference` | 偏好记忆（封闭类型 + 同类 upsert 覆盖） |

候选店不单独建表 —— 追问复用依赖 checkpointer state 中已保存的候选（SQLite 持久化），避免与业务库重复存储。

偏好记忆沿用上个项目的成熟思路：**封闭类型 + 唯一键 + 同类 upsert**，保证表不随对话膨胀。

## 7. 错误处理

- 工具失败（高德/搜索 Key 失效、限流）→ 降级：仅用可用源，并在结果中标注「部分来源不可用」。
- LLM 结构化输出失败 → 重试 + fallback 解析（宽松 schema）。
- 检索结果为空 → 引导用户换条件 / 扩大范围（半径或品类）。
- LLM 调用超时 → 带重试的客户端（延续上个项目 3 次重试经验）。

## 8. 测试策略

pytest，重点覆盖确定性逻辑（最好测、最该测）：

- 打分排序（加权逻辑、预算/偏好匹配、边界）。
- 结构化抽取的 JSON schema 校验（Pydantic 校验器）。
- 工具参数构造（高德 API 请求 URL / 签名 / 分类码映射）。
- 集成测试：mock 工具跑通整条 graph 链路。

## 9. 项目结构

```
wander/
├── pyproject.toml
├── README.md
├── .env.example            # 各 API Key 模板
├── src/food_agent/
│   ├── graph/              # LangGraph: state + nodes + edges
│   ├── tools/              # PoiSearchTool / WebSearchTool 接口 + provider 实现 + 注册表
│   ├── rag/                # Chroma + embedding + retriever
│   ├── memory/             # 偏好抽取 / 存储
│   ├── ranking/            # 确定性打分排序
│   ├── models/             # Pydantic 结构化 schema
│   ├── api/                # FastAPI + SSE
│   └── storage/            # SQLAlchemy 模型 + Alembic 迁移
├── frontend/               # index.html + app.js（SSE + 卡片渲染）
└── tests/
```

> 本地环境：MySQL 8 直连（本机已装）；`.env` 配置 MySQL 连接 + 各 API Key。暂不引入 Docker，后续如需再补 docker-compose。

## 10. 成功标准（DoD）

- `pip install` + 填 `.env`（高德 Key、DeepSeek Key）即可本地跑通。
- 一条「找附近日料店」能端到端产出结构化推荐卡片。
- 追问「换便宜的」能复用候选、不重新检索。
- 未配 WebSearch Key 时，仅靠高德 POI 也能完整出结果。
- 工具 provider 可仅通过配置切换，不改主流程。
- 打分排序 / schema 校验有单元测试覆盖。

## 11. 评审决策记录（2026-08-25）

| 决策点 | 结论 |
|---|---|
| checkpointer 存储 | 官方 `langgraph-checkpoint-sqlite`；MySQL 仅存业务数据（session/message/favorite/preference） |
| 候选店缓存 | 不单独建表，复用 checkpointer state |
| 追问路由 | 需求解析节点内 LLM 判断 + 关键词规则兜底 |
| 流式粒度 | 节点级 + 工具调用级（`astream_events` + SSE） |
| 高德评分缺失 | 评分 → 评论数/热度 → 中性分 逐级兜底 |
| 品类分类码 | LLM 映射 + `keywords` 兜底，不维护静态大表 |
| 向量召回冷启动 | 空结果不影响主链路 |
| 部署 | 本机 MySQL 8 直连，暂不引入 Docker |
