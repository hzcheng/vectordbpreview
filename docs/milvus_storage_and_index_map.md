# Milvus Storage And Index Map

## Purpose
这份文档回答 `Phase C` 的核心问题: Milvus 里的数据先去哪里、segment 如何演化、索引由谁承载，以及查询侧何时从 growing 视图切换到 sealed/indexed 视图。

## High-Level Map

```text
client write
  -> WAL / message path
  -> Data Node consumes and organizes data
  -> growing segment
  -> flush
  -> persisted segment-related artifacts in object storage
  -> sealed segment
  -> index build on sealed data
  -> index artifacts persisted in object storage
  -> Query Node loads growing or sealed/indexed data for serving
  -> handoff shifts serving responsibility toward sealed/indexed view
  -> compaction rewrites/merges segments over time
```

这不是单机库里“写文件然后直接查文件”的路径，而是典型的存储/计算分离路径: 持久化对象主要在存储层，查询节点按需加载可服务的数据和索引。

## Verified Model From Docs

### 1. WAL And Ingestion Path
- 当前架构文档明确把 `WAL Storage` 列为独立存储层能力之一。
- `Data Processing` 路径显示，写入先进入日志/消息链路，再由数据处理侧继续消费与组织。
- 这意味着 WAL 不是“额外备份文件”，而是写入顺序、可靠性和下游异步处理的基础入口。

### 2. Growing Segment
- 新写入数据先以 `growing segment` 形态进入查询可见路径。
- growing 的意义是“数据已经进入系统、可被服务链路看到，但还没有完成最终稳定化和索引化”。
- 它解决的是近实时可见性，而不是最终最优查询形态。

### 3. Flush And Sealed Segment
- `flush` 把 growing 路径上的数据推进到持久化对象。
- `sealed segment` 表示该 segment 不再作为继续追加写入的主要目标，而是进入更稳定的只读/可索引生命周期。
- 一旦 segment sealed，后续更适合围绕它构建向量索引和稳定查询服务。

### 4. Persisted Data Carriers
- 当前官方架构把 `Object Storage` 和 `Meta Store` 分开描述。
- 对 `Phase C` 而言，最重要的抽象不是每种内部文件后缀，而是:
  - **对象存储承载数据与索引工件**
  - **元数据存储承载 collection/segment/index 的状态与位置信息**

### 5. Query-Side Handoff
- 查询侧不会永远依赖 growing segment 服务。
- 当 sealed segment 和其索引准备好后，系统会把服务责任向 sealed/indexed 视图转移，这就是当前研究里最该关注的 `handoff`。
- 这个过程解释了为什么 Milvus 能同时兼顾“刚写入就能搜到”和“稳定数据能走更高效查询路径”。

### 6. Compaction
- compaction 用来重写或合并 segments。
- 它服务于碎片治理、删除影响处理和长期查询效率，而不是简单地“压缩文件体积”。
- 因为 compaction 会改变 segment 组织，所以后续研究要把它放进“数据生命周期”而不是“离线维护脚本”里理解。

## Index Carrier Map

## Vector Indexes
- 向量索引建立在 sealed 数据之上，而不是 growing 写入态之上。
- 它们的工件由存储层承载，查询节点按需加载后参与 ANN/search。
- 因此，向量索引的本质不是 collection 级全局单体，而是和 segment 生命周期强关联的工件集合。

## Scalar Or Inverted-Style Indexes
- 当前混合字段模型意味着标量过滤不能只靠“结果出来后再在应用层裁剪”。
- 在 `Phase C` 的抽象层面，应把标量/倒排类索引理解为“附着于字段与 segment 生命周期的过滤加速工件”。
- 它们和向量索引的目标不同:
  - 向量索引优化候选召回
  - 标量/倒排类索引优化过滤裁剪

## Primary-Key Lookup Aids
- **文档级稳定结论:** 主键不会参与相似度计算，但系统必须保留足够的主键相关元数据，才能支持实体定位、删除传播和查询结果归属。
- **当前工作推断:** 在 segment 生命周期周围，Milvus 会依赖 segment 级统计/删除相关工件和主键辅助结构来帮助定位记录。
- **仍待源码确认:** 主键辅助结构在对象存储和查询节点内存中的精确表示形式，留到后续 Phase D 或源码阶段再锁定。

上面这部分我刻意区分了“文档明确给出的结论”和“从数据处理路径合理推出的结构角色”，避免把源码级细节伪装成文档事实。

## Text Diagram: Data And Index Carriers

```text
WAL storage
  carries: write-ahead events before durable data organization

Object storage
  carries: persisted segment-related data artifacts
  carries: vector/scalar index artifacts

Meta store
  carries: collection / segment / index metadata and state

Query node memory
  carries: serving-time loaded growing data, sealed data, and indexes
```

## Stable Conclusions
- Milvus 的核心不是“直接把向量写进本地 ANN 文件”，而是通过 WAL、segment 生命周期、对象存储和查询节点加载共同完成服务。
- growing 和 sealed 的区别，本质上是数据生命周期和服务路径的区别。
- 向量索引与标量过滤能力都应被理解为“依附在 segment 生命周期上的工件”，而不是脱离 segment 的全局魔法层。
- handoff 是连接实时可见性和稳定高效查询的关键桥梁。

## Open Questions For Phase D
- query 请求进入后，如何决定查 growing 还是 sealed，或者两者并查?
- segment 级结果是如何在 Query Node 侧 merge/reduce 的?
- 标量过滤在执行链路中的前置、并行和后置位置分别在哪里?
- 主键辅助结构在运行时具体由哪些组件维护?

## Sources
- https://milvus.io/docs/architecture_overview.md
- https://milvus.io/docs/data_processing.md
- https://milvus.io/docs/compact_data.md

