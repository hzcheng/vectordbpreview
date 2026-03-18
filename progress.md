# Progress Log

## Current Snapshot
- **Overall progress:** Phase 1、Phase 2、Phase 3、Phase A、Phase B、Phase C、Theme 1、Theme 2、Theme 3、Theme 4、Theme 5、Theme 6、Theme 7 已完成；并已进入索引专项深挖阶段，当前已补完数据布局、索引布局与 HNSW 专题
- **Current checkpoint:** All 7 themes complete
- **Status:** milvus_7_themes_complete
- **Last updated:** 2026-03-18 01:35 UTC
- **Next recommended action:** `HNSW` 专题已完成；如果继续深挖，建议按 `IVF_PQ -> INVERTED/BITMAP -> JSON key stats` 的顺序，继续做“算法结构 + build path + load path + storage wrapper”专项串读

## Session: 2026-03-18

### HNSW Deep Dive
- **Status:** complete
- **Started:** 2026-03-18 01:35 UTC
- Actions taken:
  - 围绕用户提出的 “HNSW 原理、直观例子、Milvus 中的工作方式、内存组织、硬盘存储格式、构建时机” 六个问题，补读了 `client/index/hnsw.go`、`indexparamcheck`、`datanode/index_services.go`、`datanode/index/task_index.go`、`indexbuilder`、`segcore`、`IndexFactory`、`index_data_codec`、`segment_index` 等关键入口。
  - 明确了 HNSW 在算法层是“多层导航图 + small-world 候选扩展”的 ANN 结构，并补了一套二维点集和语义检索两种直观例子。
  - 明确了 sealed segment 的 HNSW 构建走 DataNode 后台异步任务，而 growing segment 通常走 `IVFFLAT_CC / SCANN_DVR` 一类 interim index，不直接等同于正式 HNSW。
  - 明确了 QueryNode/segcore 侧的 HNSW 运行体由向量索引入口 + Knowhere 索引对象承载，Milvus 主要管理 segment 级元数据、资源估算、加载流程和外层文件组织。
  - 新增一份 HNSW 专题文档，便于后续直接继续深挖 HNSW 与其他索引的差异。
- Files created/modified:
  - docs/milvus_hnsw_deep_dive.md (created)
  - findings.md (updated)
  - progress.md (updated)

## Session: 2026-03-18

### Index Deep Dive
- **Status:** complete
- **Started:** 2026-03-18 00:40 UTC
- Actions taken:
  - 围绕用户提出的“Milvus 的索引有哪些、分别对应什么数据类型、在内存和硬盘上如何组织”的问题，补读了 `client/index`、`indexparamcheck`、`vecindexmgr`、`metastore/model`、`datacoord`、`datanode/index`、`querynodev2/segments`、`segcore` 等关键源码入口。
  - 明确了索引体系的三层模型：field 级 `Index` 定义、segment 级 `SegmentIndex` 工件、QueryNode/segcore 中的已加载运行时索引对象。
  - 梳理了主线索引类型与数据类型映射，并区分了主索引工件与 JSON/BM25/text 等 sidecar 工件。
  - 整理了 growing segment interim index、sealed segment loaded index、`index_files/...` 路径骨架与 `IndexFileBinlogCodec` 编码方式。
  - 新增一份索引专题文档，便于后续继续按具体索引类型深挖。
- Files created/modified:
  - docs/milvus_index_types_memory_disk.md (created)
  - findings.md (updated)
  - progress.md (updated)

## Session: 2026-03-17

### Data Layout Deep Dive
- **Status:** complete
- **Started:** 2026-03-17 09:25 UTC
- Actions taken:
  - 围绕用户提出的“各种类型数据在内存和硬盘上如何组织”问题，补读了 `insert_data`、`data_codec`、`rw`、`querynodev2/segments` 等核心源码入口。
  - 明确了写入侧内存主模型是 `InsertData -> map[fieldID]FieldData`，不同字段类型分别映射到 `[]int64`、`[]string`、`[][]byte`、拍平向量缓冲区等具体列式结构。
  - 明确了持久化主模型在 `StorageV1` 下表现为 segment 内按 field 切分的 insert/stats/delta logs，在 `StorageV2/V3` 下表现为 packed parquet / column groups / manifest。
  - 新增一份带图表和简单例子的专题文档，便于后续继续深挖 segment、binlog 和 segcore。
- Files created/modified:
  - docs/milvus_data_memory_disk_layout.md (created)
  - findings.md (updated)
  - progress.md (updated)

## Session: 2026-03-14

### Phase 0: 计划初始化
- **Status:** complete
- **Started:** 2026-03-14 01:54 UTC
- Actions taken:
  - 建立了 48 小时学习路线，覆盖概念、场景、小项目、平台集成、Milvus 架构、Milvus 源码深潜。
  - 确认用项目根目录的持久化文件保存学习状态，支持新会话恢复。
  - 补充了 Milvus 官方架构、数据处理、版本入口，避免后续深潜时版本漂移。
- Files created/modified:
  - task_plan.md (created)
  - findings.md (created)
  - progress.md (created)

### Phase 1: 向量与检索基础
- **Status:** complete
- Actions taken:
  - 完成 Lesson 1: 向量、embedding、相似度、距离度量、dense/sparse/multi-vector、TopK、ANN 基础。
  - 新增学习笔记文件，供后续会话恢复时直接读取。
  - 完成口头检查：Phase 1 核心概念基本过关，`inner product` 和 `multi-vector` 还需再巩固一轮。
- Files created/modified:
  - phase1_vectors_basics.md (created)
  - findings.md (updated)
  - progress.md

### Phase 2: 向量数据库应用场景
- **Status:** in_progress
- Actions taken:
  - 完成 Lesson 1: RAG、语义搜索、推荐、多模态检索、去重聚类、召回重排六类场景梳理。
  - 总结了完整检索链路：切分 -> embedding -> 入库 -> ANN -> filter -> rerank -> 返回。
  - 明确了“什么时候适合用向量数据库，什么时候不适合”。
  - 完成 Phase 2 口头检查，已能说明 RAG 召回层、混合检索、非适用场景，以及平台集成时的部分关键设计点。
- Files created/modified:
  - phase2_vector_db_applications.md (created)
  - findings.md (updated)
  - progress.md

## Session: 2026-03-15

### Progress Sync
- **Status:** complete
- **Started:** 2026-03-15 06:50 UTC
- Actions taken:
  - 基于 `phase1_vectors_basics.md` 确认 Phase 1 内容完整，状态同步为完成。
  - 基于 `phase2_vector_db_applications.md` 确认 Phase 2 的核心学习和口头检查已完成，但“场景-问题-方案”对照表仍待单独整理。
  - 统一 `task_plan.md` 与 `progress.md` 的当前检查点为“Phase 2 收尾 / Phase 3 准备”，避免文件间状态矛盾。
- Files created/modified:
  - task_plan.md (updated)
  - progress.md (updated)

### Phase 3 Design
- **Status:** complete
- **Started:** 2026-03-15 06:50 UTC
- Actions taken:
  - 确定 Phase 3 采用 `Python + Milvus Lite + 本地中文样本数据` 的默认方案。
  - 明确 Demo 的最小范围：样本数据、embedding、Milvus Lite 入库、keyword/vector/filter 对比。
  - 补充成功标准、文件结构、依赖选择和测试策略。
  - 将设计写入正式 spec 文件，作为后续 implementation plan 的输入。
- Files created/modified:
  - docs/superpowers/specs/2026-03-15-phase3-milvus-lite-demo-design.md (created)
  - findings.md (updated)
  - task_plan.md (updated)
  - progress.md (updated)

### Phase 3 Plan
- **Status:** complete
- **Started:** 2026-03-15 07:16 UTC
- Actions taken:
  - 基于 Phase 3 spec 写出 implementation plan，拆分为数据与检索基线、向量检索链路、端到端验证三大块。
  - 记录用户明确同意跳过 `worktree`，直接在当前工作区继续实现。
  - 为后续实现明确了 TDD 顺序、验证命令和最终验收标准。
- Files created/modified:
  - docs/superpowers/plans/2026-03-15-phase3-milvus-lite-demo.md (created)
  - progress.md (updated)

### Phase 3 Implementation
- **Status:** complete
- **Started:** 2026-03-15 07:16 UTC
- Actions taken:
  - 创建了 `phase3_demo` 目录结构、133 条中文样本数据、数据加载模块和关键词检索基线。
  - 实现了本地轻量 embedder、Milvus Lite collection 构建、向量检索和 metadata filter 查询。
  - 通过 `systematic-debugging` 定位了 embedder 回退特征导致的错误召回，并增加回归测试后修正。
  - 写出 README 和 sample run 文档，保留实际构建与查询结果供后续复盘。
- Files created/modified:
  - phase3_demo/requirements.txt (created)
  - phase3_demo/README.md (created)
  - phase3_demo/data/sample_docs.json (created)
  - phase3_demo/src/demo_data.py (created)
  - phase3_demo/src/retrieval.py (created)
  - phase3_demo/src/vector_store.py (created)
  - phase3_demo/src/build_demo.py (created)
  - phase3_demo/src/search_demo.py (created)
  - phase3_demo/tests/conftest.py (created)
  - phase3_demo/tests/test_demo_data.py (created)
  - phase3_demo/tests/test_retrieval.py (created)
  - phase3_demo/tests/test_vector_store.py (created)
  - phase3_demo/tests/test_search_demo.py (created)
  - phase3_demo/results/sample_run.md (created)
  - findings.md (updated)
  - task_plan.md (updated)
  - progress.md (updated)

### Sequence Adjustment
- **Status:** complete
- **Started:** 2026-03-15 13:54 UTC
- Actions taken:
  - 和用户讨论了是否应当先深入学习 Milvus 内部机制，再开始平台接入设计。
  - 明确用户当前优先级是“先尽快形成自己平台的接入方案，再回头把 Milvus 的内部机制搞透”。
  - 将原顺序调整为 `Phase 4A -> Phase 5 -> Phase 4B -> Phase 6`，避免平台方案被源码学习阻塞。
  - 写入阶段重排设计说明与执行计划，并同步三份持久化状态文件。
- Files created/modified:
  - docs/superpowers/specs/2026-03-15-learning-sequence-reorder-design.md (created)
  - docs/superpowers/plans/2026-03-15-learning-sequence-reorder.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Phase 2 Closure
- **Status:** complete
- **Started:** 2026-03-15 14:04 UTC
- Actions taken:
  - 基于已有 Phase 2 学习笔记，整理了一页“场景-问题-方案”对照表。
  - 将 RAG、语义搜索、推荐、多模态检索、去重聚类、召回重排六类典型场景统一映射到问题类型、向量数据库角色、方案形态、风险和平台关注点。
  - 把该矩阵作为 Phase 4A 的直接输入，补充了平台接入草图前必须先回答的 5 个问题。
- Files created/modified:
  - docs/scenario_problem_solution_matrix.md (created)
  - task_plan.md (updated)
  - progress.md (updated)

### Phase 4A Design
- **Status:** complete
- **Started:** 2026-03-16 05:58 UTC
- Actions taken:
  - 围绕“问笔记”为主域、“问订单”为次级独立域，完成了平台接入草图的结构化讨论。
  - 明确了笔记域采用 `标题/摘要向量 + 正文 chunk 向量` 的双层索引，并将输出目标定为“最终答案 + 引用”。
  - 确认权限模型为“个人域 + 共享域并存”，且权限过滤必须在召回阶段执行。
  - 确认索引更新采用“主库存储成功后异步刷新、按版本整版切换”的策略。
  - 将以上内容写成正式 spec，并列出需要在 Phase 5 用 Milvus 架构验证的关键假设。
- Files created/modified:
  - docs/superpowers/specs/2026-03-16-phase4a-notes-rag-platform-design.md (created)
  - findings.md (updated)
  - progress.md (updated)

### Milvus-First Replan
- **Status:** complete
- **Started:** 2026-03-16 05:58 UTC
- Actions taken:
  - 根据用户新增的三个后续议题，重新评估了当前主线是否仍应继续围绕平台接入和后续对接展开。
  - 用户明确要求当前先不要讨论 RedDB，也不要继续讨论 RAG 平台，而是先从 Milvus 本身如何解决向量场景问题入手。
  - 将后续主线重排为 `Phase A -> Phase B -> Phase C -> Phase D -> Phase E`，分别覆盖版本与术语、混合数据模型、存储与索引承载、查询引擎与计算层、未来对接抽象问题。
  - 将旧的 `notes RAG` 平台 spec 和 RedDB 对接议题降级为冻结背景材料，不再作为当前主任务推进。
  - 写入新的重排设计说明与执行计划，并同步三份持久化状态文件。
- Files created/modified:
  - docs/superpowers/specs/2026-03-16-milvus-first-research-replan-design.md (created)
  - docs/superpowers/plans/2026-03-16-milvus-first-research-replan.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Phase A: Version Lock And Terms Baseline
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 基于官方 Releases 与当前文档入口，将研究基线锁定到 `Milvus 2.6.x`，并用 `v2.6.7` 作为本轮阅读的 release 快照。
  - 整理了后续必须统一使用的术语表，包括 `segment`、`growing`、`sealed`、`WAL`、`flush`、`handoff`、`compaction`、`shard`、`channel`、`query plan`。
  - 明确了后续文档入口优先级：`What's new in v2.6.x`、`Architecture Overview`、`Data Processing`、schema/field/JSON 页面。
- Files created/modified:
  - docs/milvus_version_and_terms.md (created)
  - findings.md (updated)
  - task_plan.md (updated)
  - progress.md (updated)

### Phase B: Mixed Data Model
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 输出了 `Milvus 混合数据模型` 说明，明确 collection/schema/field 是逻辑对象模型的骨架。
  - 归纳了 vector field、scalar field、JSON field 的职责边界，并强调“向量召回 + 结构化过滤”是联合模型，而不是两个独立系统。
  - 记录了下一阶段需要验证的未决问题，包括 segment 中各类字段的物理承载和过滤执行路径。
- Files created/modified:
  - docs/milvus_mixed_data_model.md (created)
  - findings.md (updated)
  - task_plan.md (updated)
  - progress.md (updated)

### Phase C: Storage And Index Carriers
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 基于 `Architecture Overview`、`Data Processing` 和 compaction 文档，整理了从 WAL 到 growing/sealed segment，再到索引工件和查询节点加载的承载关系。
  - 把对象存储、元数据存储、查询节点内存三类承载边界明确拆开，避免把“哪里保存数据”和“哪里执行查询”混为一谈。
  - 对主键辅助结构等细节采用“文档事实 + 工作推断”区分写法，保留了后续源码验证入口。
- Files created/modified:
  - docs/milvus_storage_and_index_map.md (created)
  - findings.md (updated)
  - task_plan.md (updated)
  - progress.md (updated)

### Theme-Driven Learning Redesign
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 根据用户新要求，把后续学习方式从“继续 Phase D/E”收紧为“严格按 7 个主题推进，一题一文档”。
  - 明确每个主题讲完原理后，都必须同步给出本地源码目录、关键文件和建议阅读顺序。
  - 确认本地 Milvus 源码路径为 `/Projects/work/vectordbpreview/milvus`，后续所有源码入口均以此路径为准。
- Files created/modified:
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Theme-Driven Learning Spec
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 将已经确认的“7 个主题、一题一文档、每题映射本地源码树”的学习设计写成正式 spec。
  - 明确了每份主题文档的统一结构、范围边界、执行顺序和风险控制方式。
  - 为后续从 Theme 1 到 Theme 7 的连续推进提供了稳定的书面基线。
- Files created/modified:
  - docs/superpowers/specs/2026-03-16-milvus-7-theme-learning-design.md (created)
  - progress.md (updated)

### Theme-Driven Learning Plan
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 将 7 个主题的学习执行顺序写成正式 implementation plan。
  - 明确了每个主题要检查的源码目录、候选关键文件和持久化更新步骤。
  - 确认当前将按计划直接执行 Theme 1，而不是只停留在计划层。
- Files created/modified:
  - docs/superpowers/plans/2026-03-16-milvus-7-theme-learning.md (created)
  - progress.md (updated)

### Theme 1: Concepts And Source Entrypoints
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 基于前置概念文档、术语基线和本地源码树，整理出 Milvus 的最小概念集合。
  - 把概念层源码入口固定为 `client/entity -> client/index -> pkg/proto -> internal/metastore/model -> internal/querynodev2/segments` 这条阅读路径。
  - 产出了首份主题文档，覆盖原理、关键目录、关键文件和建议阅读顺序。
- Files created/modified:
  - docs/milvus_theme1_concepts.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Theme 2: Architecture And Component Boundaries
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 基于本地启动入口、组件包装层和核心 runtime 目录，整理出 Milvus 的访问层、协调层、工作节点层和存储层架构。
  - 明确了 `cmd/roles -> cmd/components -> internal/*` 这一条本地源码阅读主线，用来把官方架构图映射到当前代码树。
  - 产出了 Theme 2 文档，覆盖原理、关键目录、关键文件和建议阅读顺序。
- Files created/modified:
  - docs/milvus_theme2_architecture.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Theme 3: Write Path And Segment Lifecycle Entry
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 基于 Proxy、streaming/WAL、DataNode、flushcommon、DataCoord 目录，整理了 Milvus 当前写路径的动态链路。
  - 固定了写路径的源码主线：`task_insert -> task_insert_streaming -> data_sync_service -> sync_manager -> segment_manager`。
  - 产出了 Theme 3 文档，覆盖原理、关键目录、关键文件和建议阅读顺序。
- Files created/modified:
  - docs/milvus_theme3_write_path.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Theme 4: Data Organization And Schema/Field Model
- **Status:** complete
- **Started:** 2026-03-16 06:30 UTC
- Actions taken:
  - 基于 `client/entity`、`client/row`、`internal/metastore/model`、`internal/storage`、`internal/querynodev2/segments`，整理了 collection/schema/field 到运行时列式 FieldData 的完整映射。
  - 明确了 dynamic field 的真实落地方式：RootCoord 在 schema 中追加动态 JSON 字段，client 将 schema 外字段打包进该列，导入路径会在缺失时补齐空 JSON。
  - 固定了 Theme 4 的源码主线：`entity schema/field -> row/data -> rootcoord dynamic field -> storage InsertData -> query runtime schema copy`。
- Files created/modified:
  - docs/milvus_theme4_data_organization.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Theme 5: Index Organization And Segment-Level Artifacts
- **Status:** complete
- **Started:** 2026-03-16 06:45 UTC
- Actions taken:
  - 基于 `client/index`、`internal/metastore/model`、`internal/datacoord`、`internal/datanode/index`、`internal/querynodev2/segments`、`internal/querynodev2/pkoracle`，整理了“field 级索引定义 -> segment 级索引工件 -> query runtime 加载”的完整链路。
  - 明确了向量索引、标量索引、JSON/text sidecar 工件和主键 bloom/stats helper 都依附于 segment 生命周期，只是作用目标和加载模型不同。
  - 固定了 Theme 5 的源码主线：`client index -> metastore segment_index -> datacoord task_index/task_stats -> datanode build -> querynode load/pkoracle`。
- Files created/modified:
  - docs/milvus_theme5_index_organization.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Theme 6: Query Architecture And Role Boundaries
- **Status:** complete
- **Started:** 2026-03-16 07:05 UTC
- Actions taken:
  - 基于 `internal/proxy`、`internal/querycoordv2`、`internal/querynodev2`、`internal/rootcoord`、`internal/datanode`、`internal/streamingnode`，整理了查询侧的入口层、控制平面、执行平面和支撑层边界。
  - 明确了 QueryCoord 的 `target` 与 `distribution` 双视图、QueryNode 的 `segments.Manager + Loader + Delegator` 执行组合，以及 RootCoord/DataCoord/StreamingNode/DataNode 在查询侧的非执行型支撑角色。
  - 固定了 Theme 6 的源码主线：`proxy task_search/query -> querycoord target/dist/broker -> querynode server/segments/delegator -> supporting brokers/services`。
- Files created/modified:
  - docs/milvus_theme6_query_architecture.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Theme 7: Query Flow And End-To-End Execution Chain
- **Status:** complete
- **Started:** 2026-03-16 07:20 UTC
- **Completed:** 2026-03-16 11:13 UTC
- Actions taken:
  - 围绕 `Proxy -> plan parser -> QueryNode service entry -> shardDelegator -> worker SearchSegments/QuerySegments -> QueryNode reduce -> Proxy final reduce` 这条热路径，补全了查询执行动态链路。
  - 明确了 `waitTSafe` 负责可读时间边界、`PinReadableSegments` 负责当前可读 segment 视图、`organizeSubTask/executeSubTasks` 负责 shard 内子任务组织。
  - 明确了 QueryCoord 在 Theme 7 中的正确位置：通常不在每次请求的同步 RPC 栈里，但它维护的 target/distribution/leader 视图是热路径成立的前提。
  - 明确了 search 与 query 在收尾阶段的关键差异：search 走 pipeline 化的 `reduce/rerank/requery/organize/highlight/order_by` 组合，而 query 走 retrieve reducer。
- Files created/modified:
  - docs/milvus_theme7_query_flow.md (created)
  - task_plan.md (updated)
  - findings.md (updated)
  - progress.md (updated)

### Session Sync: Ready For New Conversation
- **Status:** complete
- **Started:** 2026-03-17 08:51 UTC
- Actions taken:
  - 复核了 `task_plan.md`、`findings.md`、`progress.md` 的当前状态，确认 7 个主题已经全部完成。
  - 确认 Theme 7 文档已经存在，当前学习主线处于可安全恢复状态。
  - 刷新了 `progress.md` 的快照时间，方便下一次会话直接衔接当前进度。
- Files created/modified:
  - progress.md (updated)

## Recommended Deliverables
- 一页向量数据库场景矩阵
- 一个最小 Milvus 语义检索 Demo
- 一张“我的数据平台如何接入向量检索”的架构草图
- 一份 Milvus 数据流和源码模块图

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| 学习状态持久化 | 新会话读取 `task_plan.md`、`findings.md`、`progress.md` | 能恢复计划和当前进度 | 文件已创建，具备恢复基础 | ✓ |
| Phase 3 单元测试 | `pytest phase3_demo/tests -v` | 全部通过 | 9 passed | ✓ |
| Phase 3 建库 | `python3 phase3_demo/src/build_demo.py` | 成功创建本地 Milvus Lite 数据库 | 构建 `phase3_demo/demo.db` 成功，写入 133 条样本 | ✓ |
| Phase 3 查询 | `python3 phase3_demo/src/search_demo.py` | 输出 keyword/vector/filtered 三段结果 | 三段输出均正常，且结果符合预期 | ✓ |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
|           |       | 1       |            |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | 已完成前置基础学习、Milvus-first 的 A/B/C 文档，以及 Theme 1 到 Theme 7 七份主题文档，当前处于 7 题主线收官状态 |
| Where am I going? | 接下来可按 7 份文档顺序复习，或进入 QueryNode / QueryCoord 的专项源码深读 |
| What's the goal? | 不只要理解 Milvus 的概念和架构，还要把每个主题都映射到本地源码树里的关键目录和关键文件 |
| What have I learned? | Theme 7 已把查询热路径固定为：Proxy 编译计划并按 shard 分发，QueryNode 通过 delegator 等待可读时间点并固定可读 segment 视图，再经 worker/task/scheduler 执行，最后由 QueryNode 和 Proxy 两层归并结果 |
| What have I done? | 已完成基础学习、本地 Demo、Milvus-first 研究重排、7 主题学习设计与计划，以及 Theme 1 到 Theme 7 全部文档落盘 |

## Resume Instructions
- 新会话先读取 `task_plan.md`
- 再读取 `findings.md`
- 最后读取 `progress.md`
- 读取后优先回答：当前进度、下一步、是否偏离计划
