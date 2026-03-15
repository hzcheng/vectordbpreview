# Task Plan: 48-Hour Vector Database and Milvus Learning Plan

## Goal
在 48 小时内，从零建立对向量、Embedding、ANN 检索、向量数据库应用场景、数据平台集成方式的系统理解，并能沿着官方文档与源码入口深入研究 Milvus 2.6.x 的向量检索实现路径。

## Current Phase
Phase 2 收尾 / Phase 3 准备 - 最小语义检索 Demo 设计

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
- [ ] 输出一页“场景-问题-方案”对照表
- **Status:** in_progress

### Phase 3: 快速上手小项目（12-20h）
- [ ] 用 Milvus Lite 或本地 Milvus 做一个最小语义检索 Demo
- [ ] 数据集规模控制在 100-1000 条文本，避免环境噪音
- [ ] 完成一次 keyword search 与 vector search 的对比
- [ ] 增加 metadata filter、topK、简单评估样例
- **Status:** pending

### Phase 4: 面向数据平台的集成视角（20-28h）
- [ ] 设计向量数据在数据平台中的接入链路
- [ ] 明确 schema、主键、metadata、更新策略、重建索引策略
- [ ] 理解在线写入、批量导入、冷热分层、召回与重排职责边界
- [ ] 输出一版“接入我自己的数据平台”的技术草图
- **Status:** pending

### Phase 5: Milvus 架构与数据流（28-38h）
- [ ] 阅读 Milvus 官方架构文档与 Data Processing 文档
- [ ] 理解 Proxy、Coordinator、Streaming Node、Query Node、Data Node 各自职责
- [ ] 理解 WAL、segment、flush、handoff、compaction、index build、search fan-out
- [ ] 画出写路径和查路径时序图
- **Status:** pending

### Phase 6: Milvus 源码深潜（38-46h）
- [ ] 锁定一个目标版本再读源码，避免跨版本混淆
- [ ] 顺着写入路径读核心目录与模块边界
- [ ] 顺着查询路径读 query plan、segment、index、reduce 流程
- [ ] 记录 10 个“看懂源码前必须先搞清楚”的术语
- **Status:** pending

### Phase 7: 巩固与输出（46-48h）
- [ ] 复盘向量数据库适用边界与常见误区
- [ ] 写出“如果要集成到我的平台，我会怎么做”
- [ ] 写出“Milvus 内核我已经看懂了哪些、还没看懂哪些”
- [ ] 形成下一阶段深入阅读清单
- **Status:** pending

## Key Questions
1. 向量究竟表示什么，为什么它能支持语义检索？
2. ANN、精确检索、过滤、重排分别解决什么问题？
3. 向量数据库与 Elasticsearch / PostgreSQL / Redis 的边界在哪里？
4. 在数据平台里，embedding 生成、存储、更新、回流该如何设计？
5. Milvus 当前版本的核心写路径、查路径、索引构建路径分别经过哪些组件？
6. 官方文档与不同版本源码之间有哪些结构变化，应该如何避免误读？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 用项目根目录下的 `task_plan.md`、`findings.md`、`progress.md` 持久化学习状态 | 新会话可直接恢复上下文并回答当前进度 |
| 48 小时拆成 7 个阶段，先上层场景、再小项目、最后 Milvus 内核 | 先建立直觉，再进入实现细节，学习效率最高 |
| 小项目优先使用 Milvus Lite / 本地最小环境 | 环境阻力最低，适合快速验证“向量检索到底在干什么” |
| Milvus 深入部分默认以 2.6.x 架构为基线 | 截至 2026-03-14，GitHub Releases 页面将 `v2.6.7` 标记为 Latest |
| 阅读源码前必须先锁定版本 | Milvus 2.3 / 2.5 / 2.6 在组件职责描述上存在差异，混读容易误判 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes
- 每完成一个阶段，立刻更新 `progress.md`
- 任何 Milvus 文档、Issue、源码入口的发现先写入 `findings.md`
- 下一次会话恢复时，先读 `task_plan.md`，再读 `findings.md` 和 `progress.md`
- 当前基线进度：Phase 1 已完成；Phase 2 的核心学习与口头检查已完成，但“场景-问题-方案”对照表尚未单独整理成文
- 当前执行重点：开始最小 Demo 的设计与实验准备，同时保留 Phase 2 收尾项待补齐
