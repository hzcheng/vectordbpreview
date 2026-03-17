# Milvus Version And Terms Baseline

## Purpose
这份文档锁定本轮研究的版本和术语基线，避免后续把 `2.5.x`、`2.6.x`、旧架构文档和当前实现混在一起阅读。

## Version Lock

### Release baseline
- **Research branch:** `Milvus 2.6.x`
- **Pinned release snapshot:** `v2.6.7`
- **Pin date:** `2026-03-16 UTC`
- **Reason:** GitHub Releases 页面当日将 `v2.6.7` 标记为 Latest，而 `2.5.x` 仍在维护；后续研究应在单一主版本内建立完整心智模型，再处理跨版本差异。

### Documentation baseline
- **Primary doc family:** `milvus.io` 当前文档中与 `2.6.x` 一致的页面
- **Allowed doc entry types:**
  - `What's new in v2.6.x`
  - `Architecture Overview`
  - `Data Processing`
  - schema / field / JSON field 相关页面
- **Exclusion rule:** 后续阅读默认不混用 `2.5.x` 或更旧版本页面；如果必须引用旧文档，只能用于解释术语漂移，并且要显式标注版本。

## Core Reading Entry Points

### Phase A-B
- `What's new in v2.6.x`
- `Architecture Overview`
- `Data Processing`
- schema / field / JSON field 文档

### Phase C
- `Data Processing`
- 存储与索引相关文档
- segment / compaction / flush / filtering 相关说明

### Phase D
- `Architecture Overview`
- 查询、过滤、search / query 执行链路文档
- 运行时组件职责说明

## Runtime Components To Track Later
- `Proxy`
- `Root Coordinator`
- `Data Coordinator`
- `Query Coordinator`
- `Streaming Node`
- `Data Node`
- `Query Node`
- `WAL Storage`
- `Object Storage`
- `Meta Store`

本阶段先锁定这些组件名和职责边界，源码级目录映射留到后续 Phase C/D 再做，避免过早陷入实现细节。

## Glossary

### Segment
Milvus 管理和执行查询的基本数据单元。一个 collection 中的数据不会被当成单一大表直接扫描，而是切分成多个 segment 进行写入、封存、索引和查询。

### Growing Segment
仍在接收增量写入、尚未完成持久化和封存的 segment。它通常代表“最近写入但还没转入稳定只读形态”的数据视图。

### Sealed Segment
已经封存、默认不再继续追加写入的 segment。sealed 之后更适合构建向量索引、执行稳定查询和参与后续 compaction。

### WAL
Write-Ahead Log。写入先进入日志链路，再异步展开为下游的数据持久化、segment 组织和索引构建，从而提供写入顺序与可靠性基础。

### Flush
把 growing 状态下的增量数据推进到持久化对象和 sealed 生命周期中的动作。它不是“查询完成”的同义词，而是写入数据从流式态向持久态推进的关键节点。

### Handoff
查询侧把早期服务视图切换到更稳定的 sealed/indexed segment 视图的过程。它的重点不是单纯“复制数据”，而是服务责任从一类执行路径切换到另一类执行路径。

### Compaction
对多个 segment 进行重写、合并或清理的过程，用来降低碎片、处理删除影响，并改善后续查询和存储效率。

### Shard
collection 写入并行度和数据分发的逻辑分片单位。它决定写入流如何被拆开，而不是最终用户直接感知的业务分区。

### Channel
Milvus 在组件之间传播写入和状态事件所依赖的日志/消息通道抽象。阅读后续资料时要区分物理通道和虚拟通道，不要把 channel 误解成 SQL 中的连接概念。

### Query Plan
一次 query/search 在执行前形成的逻辑计划，至少要回答“查哪些 segment、做哪类向量匹配、叠加哪些标量或 JSON 过滤、如何归并结果”这几个问题。

## Working Conventions For Later Phases
- 遇到组件职责冲突时，以 `2.6.x` 基线文档优先。
- 遇到“旧文档提到 Index Node、当前文档强调 Data Node/Streaming Node”的情况，先记录为版本差异，不立即混合归纳。
- 遇到 `segment`、`flush`、`handoff` 等词时，优先从“生命周期切换”角度理解，而不是从单机数据库术语套译。

## Sources
- https://github.com/milvus-io/milvus/releases
- https://milvus.io/docs/whats_new.md
- https://milvus.io/docs/architecture_overview.md
- https://milvus.io/docs/data_processing.md

