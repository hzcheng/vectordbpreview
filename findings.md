# Findings & Decisions

## Requirements
- 用户需要一个 48 小时以内的学习计划，从零掌握向量数据、向量数据库、AI 检索场景。
- 学习计划必须同时覆盖上层应用场景与下层技术细节。
- 需要包含一个简单的小项目体验，帮助快速建立直觉。
- 需要进一步深入研究 Milvus 的向量部分实现细节。
- 需要把学习进度持久化到文件，使新会话可以恢复状态并回答“当前学习进度”。

## Research Findings
- 向量数据库的学习顺序不应该从内核开始，而应该从“向量是什么、为什么能检索、在哪些 AI 场景里有价值”开始，否则容易把索引和架构细节学成孤立知识。
- Milvus 官方资料显示，当前学习 Milvus 最稳妥的方式是分三层阅读：架构总览 -> Data Processing -> 源码目录与关键模块。
- Milvus 官方文档当前强调 shared-storage、storage/compute disaggregation、水平扩展，这意味着理解 Milvus 时不能只把它当成“带 HNSW 的单机库”。
- Milvus 的写入和查询核心概念包括 shard、vchannel/pchannel、WAL、growing segment、sealed segment、flush、handoff、compaction、index build。
- 官方文档的不同版本对组件职责存在变化。例如旧版文档常强调 `Index Node` 执行索引构建，当前 Data Processing 文档则描述为 `Data Node` 执行部分索引相关流程。因此深读实现细节时必须先锁定版本。
- 截至 2026-03-14，GitHub Releases 页面将 `v2.6.7` 标记为 Latest；同页也能看到 `2.5.x` 分支仍在持续维护。对内核研究而言，应先选定一个版本分支再读源码。
- Phase 1 Lesson 1 已覆盖的稳定知识包括：向量、embedding、相似度、距离度量、dense vector、sparse vector、multi-vector、TopK、ANN。
- 向量检索本质上依赖“表示学习 + 相似度度量”，其中 embedding 质量通常比 ANN 参数更影响最终召回质量。
- Cosine 更强调方向相似；L2 更强调欧氏空间距离；inner product 同时受方向和长度影响，若向量归一化则往往与 cosine 接近。
- 向量数据库的价值不在“理解内容”，而在“对 embedding 结果做高效索引与检索”。
- 向量数据库的典型工作位置在检索链路的中段，而不是最前面的建模环节或最后面的生成环节。
- 一个成熟 AI 检索系统通常是混合检索系统：vector recall + keyword recall + metadata filter + rerank。
- “召回”和“重排”应该区分看待。向量数据库擅长低延迟召回候选集，不负责最终最优业务排序。
- 引入向量数据库前要先判断问题是不是语义相似问题；如果本质是精确匹配，往往不应优先使用。
- Phase 1 口头检查结果：用户已基本掌握向量、embedding、ANN、dense/sparse vector 的核心概念；`inner product` 与 `multi-vector` 的定义还需要再收紧一次。
- Multi-vector 的更准确定义是“同一个对象对应多个向量表示”，常见于文档分 chunk、标题/正文分字段编码、ColBERT 这类 token-level late interaction 方法。
- Phase 2 口头检查结果：用户已理解 RAG 中向量数据库的召回层角色、混合检索必要性和“何时不该优先使用向量数据库”；在平台集成问题上，已经能主动提出数据模型、索引、单向量/多向量三个关键设计点。
- 平台集成时，除了数据模型、索引策略、单向量/多向量选择，还必须尽早设计 embedding 生成/更新链路、metadata schema、权限过滤和重建策略。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 用 Milvus Lite 或最小本地 Milvus 做第一个小项目 | 能在 1-2 小时内跑通完整链路，优先获得感性认识 |
| 小项目先做文本语义检索，不先做图片或多模态 | 数据准备最简单，便于把注意力放在向量检索流程本身 |
| 把学习成果拆成四类输出：概念卡片、场景矩阵、平台接入草图、Milvus 模块图 | 这样既能帮助记忆，也能直接服务后续平台集成 |
| Milvus 深潜从官方文档入口开始，再映射到 GitHub 源码目录 | 先建立组件边界，再读代码实现，成本更低 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Milvus 文档版本之间存在架构表述差异 | 计划中明确要求先锁定版本，再读源码和数据流程 |

## Resources
- Milvus GitHub 仓库: https://github.com/milvus-io/milvus
- Milvus Releases: https://github.com/milvus-io/milvus/releases
- Milvus Architecture Overview: https://milvus.io/docs/zh/architecture_overview.md
- Milvus Main Components: https://milvus.io/docs/zh/v2.5.x/main_components.md
- Milvus Data Processing: https://milvus.io/docs/pt/data_processing.md
- Milvus 项目主页与 Quickstart: https://github.com/milvus-io/milvus
- Phase 1 Lesson 1 笔记: /Projects/work/vectordbpreview/phase1_vectors_basics.md
- Phase 2 Lesson 1 笔记: /Projects/work/vectordbpreview/phase2_vector_db_applications.md

## Visual/Browser Findings
- 官方架构页显示 Milvus 当前强调访问层、协调层、工作节点、存储层四层结构。
- 官方组件页显示当前文档中常见组件包括 Proxy、Coordinator、Streaming Node、Query Node、Data Node，以及 Meta Store / Object Storage / WAL Storage。
- 官方 Data Processing 页对写入、索引、查询路径给出了非常适合作为源码阅读路线的时序说明。
