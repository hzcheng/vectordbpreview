# Task Plan: Milvus-First Vector Database Research Plan

## Goal
先研究 Milvus 本身是如何解决向量场景问题的，建立对其概念体系、整体架构、写入流程、混合数据组织、索引承载、查询架构与查询流程的系统理解；每个主题都要同步映射到本地源码目录 `/Projects/work/vectordbpreview/milvus`，并且一题一文档落盘；RAG 平台与 RedDB 对接问题暂时冻结，待后续资料齐备后再单独展开。

## Current Phase
全部 7 个主题已完成

## Phases

### Phase 1: 向量与检索基础（0-6h）
- [x] 理解什么是向量、Embedding、相似度、距离度量
- [x] 理解 dense vector、sparse vector、multi-vector 的区别
- [x] 理解为什么“语义相近”可以通过近邻检索实现
- [x] 能用自己的话解释 cosine / L2 / inner product 的使用场景
- **Status:** complete

### Phase 2: 向量数据库应用场景（6-12h）
- [x] 梳理 AI 中最常见的 6 类场景：RAG、语义搜索、推荐、多模态检索、去重聚类、召回重排
- [x] 识别“什么时候该用向量数据库，什么时候不该用”
- [x] 理解向量检索链路：切分 -> embedding -> 入库 -> ANN -> filter -> rerank -> 返回
- [x] 输出一页“场景-问题-方案”对照表
- **Status:** complete

### Phase 3: 快速上手小项目（12-20h）
- [x] 用 Milvus Lite 或本地 Milvus 做一个最小语义检索 Demo
- [x] 数据集规模控制在 100-1000 条文本，避免环境噪音
- [x] 完成一次 keyword search 与 vector search 的对比
- [x] 增加 metadata filter、topK、简单评估样例
- **Status:** complete

### Frozen Background: 已完成但暂不推进的材料
- [x] 一版 `notes RAG` 平台接入草图已形成 spec
- [x] 冻结 RedDB 对接讨论，等待相关资料到位后再展开
- **Status:** frozen_background

### Phase A: 版本锁定与术语基线
- [x] 锁定本轮研究所依据的 Milvus 版本与文档版本
- [x] 建立统一术语表：segment、growing、sealed、WAL、flush、handoff、compaction、shard、channel、query plan
- [x] 明确后续阅读的核心模块与文档入口
- **Status:** complete

### Phase B: 数据模型与混合存储格式
- [x] 研究向量、标量、JSON 字段在 Milvus 中的表达方式
- [x] 理解 collection、schema、field 在混合数据模型中的角色
- [x] 形成一页“Milvus 混合数据模型”说明
- **Status:** complete

### Phase C: 存储组织与索引承载
- [x] 研究 WAL、growing segment、sealed segment 与持久化之间的关系
- [x] 研究向量索引、标量/倒排类索引、主键查询辅助结构的承载方式
- [x] 形成一张“数据与索引承载关系图”
- **Status:** complete

### Theme 1: 相关概念
- [x] 讲清向量、embedding、相似度、ANN、segment、collection、index 等最小概念集合
- [x] 把概念映射到本地源码目录与关键文件入口
- [x] 产出一份“相关概念”文档
- **Status:** complete

### Theme 2: 整体架构
- [x] 讲清访问层、协调层、工作节点、存储层的整体架构
- [x] 把架构组件映射到本地源码目录与关键文件入口
- [x] 产出一份“整体架构”文档
- **Status:** complete

### Theme 3: 数据写入流程
- [x] 讲清请求进入、WAL/消息链路、Data Node 处理、flush/seal 的主流程
- [x] 把写入链路映射到本地源码目录与关键文件入口
- [x] 产出一份“数据写入流程”文档
- **Status:** complete

### Theme 4: 向量数据和其他数据的组织格式
- [x] 讲清 collection/schema/field、向量字段、标量字段、JSON 字段的组织方式
- [x] 把数据组织映射到本地源码目录与关键文件入口
- [x] 产出一份“数据组织格式”文档
- **Status:** complete

### Theme 5: 不同数据索引的组织方式
- [x] 讲清向量索引、标量/倒排类索引、主键辅助结构与 segment 生命周期的关系
- [x] 把索引组织映射到本地源码目录与关键文件入口
- [x] 产出一份“索引组织方式”文档
- **Status:** complete

### Theme 6: 查询架构
- [x] 讲清 Proxy、Coordinator、Query Node、Streaming Node、Data Node 在查询侧的职责边界
- [x] 把查询架构映射到本地源码目录与关键文件入口
- [x] 产出一份“查询架构”文档
- **Status:** complete

### Theme 7: 查询流程串联
- [x] 讲清 query/search 从入口到结果归并的完整链路
- [x] 把查询执行流程映射到本地源码目录与关键文件入口
- [x] 产出一份“查询流程串联”文档
- **Status:** complete

## Key Questions
1. 向量究竟表示什么，为什么它能支持语义检索？
2. ANN、精确检索、过滤、重排分别解决什么问题？
3. 向量数据库与 Elasticsearch / PostgreSQL / Redis 的边界在哪里？
4. 向量、标量、JSON 等混合字段在 Milvus 中是如何被组织与表达的？
5. Milvus 的数据、segment、索引与查询引擎之间是怎样协同工作的？
6. 如果未来要把 Milvus 的核心机制映射到其他系统，需要先抽象出哪些边界？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 用项目根目录下的 `task_plan.md`、`findings.md`、`progress.md` 持久化学习状态 | 新会话可直接恢复上下文并回答当前进度 |
| 48 小时拆成 7 个阶段，先上层场景、再小项目、最后 Milvus 内核 | 先建立直觉，再进入实现细节，学习效率最高 |
| 小项目优先使用 Milvus Lite / 本地最小环境 | 环境阻力最低，适合快速验证“向量检索到底在干什么” |
| Milvus 研究阶段仍以 2.6.x 架构为工作基线 | 需要先在一个稳定主版本内建立完整心智模型，避免跨版本混读 |
| 暂时冻结 `notes RAG` 平台草图与 RedDB 对接议题 | 用户当前目标是先研究 Milvus 本身如何解决向量场景问题 |
| 新主线改为 `Phase A -> Phase B -> Phase C -> Phase D -> Phase E` | 先理解版本、术语、数据模型、索引承载和查询执行，再为未来对接抽象边界 |
| Phase A 基线锁定到 `Milvus 2.6.x / v2.6.7` 与对应当前官方文档族 | 先消除版本漂移，再进入 segment、索引和执行链路研究 |
| 混合数据模型按 `collection/schema/field` 骨架理解 | 后续存储、索引和查询执行都依赖这层逻辑边界 |
| Phase C 先采用“文档明确事实 + 显式标注推断”的写法 | 现阶段先建立可用的承载关系图，不在没有源码证据时伪装细节确定性 |
| 新学习主线改为“7 个主题，一题一文档” | 便于每个主题都形成独立可复习材料，并减少后续会话中的状态丢失 |
| 每个主题在讲完原理后必须映射到本地源码树 `/Projects/work/vectordbpreview/milvus` | 用户目标不只是理解文档，还要把架构与源码目录、关键文件对应起来 |
| 每份主题文档都要包含“关键目录、关键文件、建议阅读顺序” | 方便从概念直接过渡到源码阅读 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes
- 每完成一个阶段，立刻更新 `progress.md`
- 任何 Milvus 文档、Issue、源码入口的发现先写入 `findings.md`
- 下一次会话恢复时，先读 `task_plan.md`，再读 `findings.md` 和 `progress.md`
- 当前基线进度：Phase 1、Phase 2、Phase 3 已完成；原 `Phase 4A notes RAG` 草图降级为冻结背景材料
- 当前执行重点已完成：7 个主题文档已经全部落盘，后续可按文档顺序进入专题复习或专项源码深读
