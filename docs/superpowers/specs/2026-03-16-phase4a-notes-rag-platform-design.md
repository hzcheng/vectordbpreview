# Phase 4A Notes RAG Platform Design

## Goal
在当前学习计划中，先形成一版可落地的平台接入草图 `v0.1`：以“问笔记”为主域、以“问订单”为次级独立域，建立一个支持异步索引更新、权限过滤和引用返回的 RAG 平台底座。

## Scope
- 第一版主域是 `笔记内容问答`。
- `订单数据问答` 保留独立入口和独立检索域，但不进入当前主链路。
- 用户显式选择“问笔记”或“问订单”，第一版不做跨域自动路由。
- 笔记域采用双层索引：
  - `标题/摘要向量`
  - `正文 chunk 向量`
- 输出目标是最终答案加引用，不是纯搜索结果列表。
- 索引更新策略采用“主库存储成功后，异步刷新向量索引”。

## Non-Goals
- 不做跨域统一召回或统一问答入口。
- 不做复杂 ACL 模型，只先支持“个人域 + 共享域”。
- 不做强一致的同步索引刷新。
- 不做复杂 rerank pipeline、多跳检索或自动 query rewrite。
- 不在 Phase 4A 就决定 Milvus 的全部底层实现细节，这些由 Phase 5 验证。

## Context
- 用户当前优先级是先尽快形成自己平台的接入方案，再回头把 Milvus 的内部机制搞透。
- 第一版核心业务对象是笔记内容，订单数据后续作为独立域接入。
- 笔记检索既需要文档级语义判断，也需要片段级证据定位，因此单一向量层不足以支撑目标输出。
- 权限模型同时存在个人私有笔记和共享空间笔记，权限过滤必须在召回阶段生效。

## Design Summary
第一版平台采用“共享平台底座 + 域内独立检索策略”的结构：

- 平台统一提供主存储对接、索引任务、embedding 任务、向量写入、权限过滤上下文和问答编排框架。
- 笔记域和订单域各自保持独立 schema、索引、召回策略和提示词，不混合建模。
- 笔记域的主查询链路为：
  - 先用 `head index` 决定“哪些笔记值得看”
  - 再用 `chunk index` 决定“哪些片段适合作为答案证据”
  - 最终将证据组织后交给 LLM 生成答案并返回引用

## System Boundaries

### 1. Business Primary Storage
- 笔记和订单首先写入业务主库。
- 主库是事实来源，负责稳定主键、版本号、归属关系、删除状态和权限基础信息。
- 向量库只是检索投影层，不承担事实一致性职责。

### 2. Index Task Layer
- 主库写入成功后产生索引刷新任务。
- 索引任务按 `domain + object_id + version` 驱动。
- 第一版重点处理：
  - `notes.head`
  - `notes.chunk`
- 订单域后续可扩展为 `orders.record` 等独立任务类型。

### 3. Vector Retrieval Layer
- 每个业务域独立维护索引，不混放。
- 笔记域最少有两个索引：
  - `note_head_index`
  - `note_chunk_index`
- 订单域保留独立 collection / pipeline，不与笔记域联合召回。

### 4. QA Orchestration Layer
- 用户显式选择“问笔记”或“问订单”。
- 系统根据入口进入对应域的检索链路。
- 笔记域链路负责召回候选、组装证据并调用 LLM 生成最终答案。

### 5. Permission Filtering Layer
- 权限过滤必须在召回阶段执行。
- 检索请求必须携带用户身份和可访问空间范围。
- 不能先召回后裁剪，否则存在越权和错误生成风险。

### 6. Answer Output Layer
- 返回最终答案。
- 同时返回引用片段列表。
- 第一版内部保留 `debug_context`，便于后续调优和排障。

## Notes Domain Data Model

### Business Keys
- `note_id`
  - 笔记稳定主键，不因内容修改而变化。
- `note_version`
  - 笔记内容版本号，每次修改递增。
- `space_id`
  - 所属空间；个人空间也统一抽象为 `space_id`。
- `owner_user_id`
  - 拥有者或创建者。

### Head Index
- 索引名：`note_head_index`
- 职责：文档级粗召回，判断哪篇笔记值得进一步检索。
- 推荐索引主键：
  - `head_doc_id = note_id + ":" + note_version`

建议字段：
- `head_doc_id`
- `note_id`
- `note_version`
- `space_id`
- `owner_user_id`
- `scope_type`
- `visibility`
- `is_deleted`
- `title`
- `summary`
- `tags`
- `updated_at`
- `vector`

### Chunk Index
- 索引名：`note_chunk_index`
- 职责：片段级证据召回，为最终答案提供依据。
- 推荐索引主键：
  - `chunk_doc_id = note_id + ":" + note_version + ":" + chunk_seq`

建议字段：
- `chunk_doc_id`
- `note_id`
- `note_version`
- `chunk_seq`
- `space_id`
- `owner_user_id`
- `scope_type`
- `visibility`
- `is_deleted`
- `chunk_text`
- `chunk_token_count`
- `section_title`
- `updated_at`
- `vector`

## Why Two Indexes
- `head index` 负责文档级主题判断。
- `chunk index` 负责片段级证据定位。
- 如果两类对象混在一起，排序、过滤、排障和评估都更容易失焦。
- 第一版建议明确分治：
  - `note_head_index` 回答“查哪些笔记”
  - `note_chunk_index` 回答“用哪些片段回答”

## Metadata Principle
向量库中保留“检索最小闭包”，即只保存对召回、过滤、引用和排障必需的字段，不复制主库中大量不参与检索的业务信息。

原则：

```text
主库负责事实一致性，向量库负责检索可用性。
```

## Update Flow And Versioning

### Write Path
```text
用户编辑笔记
-> 主库存储成功，生成 note_version
-> 写入索引刷新任务
-> worker 生成 head 对象和 chunk 对象
-> 计算 embedding
-> 写入 note_head_index 和 note_chunk_index
-> 两类索引都成功后，切换 current_indexed_version
-> 旧版本延迟清理
```

### Core Rules
- 切分和 embedding 都必须绑定 `note_version`，不能只绑定 `note_id`。
- 索引发布按“整版切换”，不允许半版切换。
- `head` 和 `chunk` 两类索引都完成后，才将该版本标记为可检索。
- 删除先做软删除和可见性控制，再做延迟物理清理。

### Control Fields
建议在主库或控制表中维护：
- `latest_note_version`
- `current_indexed_version`
- `index_status`
- `last_index_error`
- `last_indexed_at`

### Status Semantics
- `latest_note_version == current_indexed_version`
  - 索引追平主库，可安全召回最新内容。
- `latest_note_version > current_indexed_version`
  - 主库已更新，但索引尚未追平，允许短时间滞后。
- `index_status == failed`
  - 索引刷新失败，必须进入可观测和可重试状态。

### Failure Recovery
异步索引任务必须满足：
- 可重试
- 幂等
- 可观测

原则：

```text
笔记更新按版本驱动，索引发布按整版切换，失败任务必须可重试且可观测。
```

## Retrieval Flow For Ask Notes

### Main Query Path
```text
用户选择“问笔记”
-> 解析用户身份与可访问空间
-> 生成查询向量
-> 查询 note_head_index，拿到候选笔记
-> 在候选 note_id 范围内查询 note_chunk_index
-> 合并、去重、截断证据片段
-> 交给 LLM 生成答案
-> 返回 answer + citations
```

### Why Head-Then-Chunk
- 只查 `chunk` 容易噪音高、上下文碎、调试困难。
- `head` 层更适合做文档级语义意图判断。
- `chunk` 层更适合做答案证据定位。
- 两阶段召回比第一版直接并行融合更容易控制和解释。

### Initial Retrieval Parameters
- `head_top_k = 20`
- `chunk_top_k = 40`
- 最终送入 LLM 的证据片段控制在 `6-12` 条，按 token 预算截断

### Candidate Constraint
第一版建议在 `chunk` 检索阶段叠加候选笔记范围：

```text
chunk filter =
  base permission filter
  + note_version = current_indexed_version
  + note_id in head recall candidates
```

## Permission And Filter Model

### Required Filter Fields
- `scope_type`
- `space_id`
- `owner_user_id`
- `visibility`
- `is_deleted`
- `note_version`

### First-Version Permission Logic
- 个人笔记：
  - `scope_type = personal`
  - `owner_user_id = current_user_id`
- 共享笔记：
  - `scope_type = shared`
  - `space_id in accessible_space_ids`
- 通用过滤：
  - `is_deleted = false`
  - `visibility` 为可访问状态
  - `note_version = current_indexed_version`

### Query Context Required By Retrieval
检索请求不能只有自然语言问题，最少需要：
- `query_text`
- `domain = notes`
- `current_user_id`
- `accessible_space_ids`
- `include_personal`
- `include_shared`
- `top_k`

可选扩展：
- `time_range`
- `tag_filters`

原则：

```text
检索请求必须显式携带用户可访问范围，索引必须保留支撑权限过滤与引用的最小 metadata 闭包。
```

## Answer Shape
问笔记接口建议至少返回：
- `answer`
- `citations`
- `debug_context`（第一版内部调试可选）

`citations` 建议包含：
- `note_id`
- `note_title`
- `chunk_seq`
- `snippet`
- `scope_type`
- `space_id`

`debug_context` 可包含：
- head candidates 数量
- chunk candidates 数量
- 送入 LLM 的证据条数
- 过滤条件摘要

## Recommended Platform Direction
在当前需求下，推荐的整体方案是：

- 使用共享平台底座承载通用能力
- 域内保持独立索引和独立召回策略
- 第一版主打 `notes RAG`
- `orders` 先做独立入口和独立接入，不做跨域混检

## Phase 5 Validation Questions
下一阶段不做泛化阅读，而是围绕以下假设验证 Milvus 机制：

1. 异步写入与延迟索引发布是否天然符合 Milvus 的写入和 segment 生命周期。
2. `note_head_index` 和 `note_chunk_index` 分 collection 是否比混合建模更稳。
3. `note_version` 驱动的整版切换在 Milvus 查询和过滤模型里是否自然。
4. `owner_user_id / space_id / scope_type / is_deleted` 这类 metadata filter 是否适合承担权限过滤职责。
5. `note_id in candidate_ids` 约束 chunk 检索在 Milvus 中是否表达自然、代价可控。
6. 旧版本短暂保留和后台清理是否符合 Milvus 的删除、compaction 和 segment 管理心智模型。
7. “个人域 + 共享域”的权限表达是否足以支撑第一版，不需要过早引入复杂 ACL。
8. 订单域继续保持独立 collection / pipeline 是否是合理默认值。

## Success Criteria
- 形成一版可讨论的平台接入草图 `v0.1`。
- 明确笔记域的双层索引结构、异步更新策略和权限过滤方式。
- 将后续 Milvus 学习收束为围绕平台假设的定向验证，而不是泛泛扫文档。

## One-Sentence Summary
第一版先把“问笔记”做成一个可控的、权限安全的、异步索引的双层 RAG 系统；订单域保留独立入口，不做跨域混检。
