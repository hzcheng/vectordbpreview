# Milvus Theme 1: 相关概念

## 这一题要解决什么问题
这一题不是要你立刻看懂 Milvus 的所有实现，而是先把后面 6 个主题都会反复出现的核心名词固定下来。只有这些概念站稳了，后面讲架构、写入、索引、查询时才不会变成一堆目录名和组件名的堆砌。

这一题的目标是建立一个最小概念集合，并把这些概念映射到本地源码树 `/Projects/work/vectordbpreview/milvus` 中最值得作为入口的目录和文件。

## 最小概念集合

### 1. Vector
向量是模型把原始对象编码后的数值表示。Milvus 不负责生成向量，但负责保存向量、为向量建索引、执行向量检索。

你可以把它理解成:

```text
原始对象 -> embedding 模型 -> 向量 -> Milvus 存储与检索
```

### 2. Embedding
embedding 是“把文本、图片、音频、用户行为等对象编码成向量”的过程。它属于模型层，不属于 Milvus 内核本身。

Milvus 的边界是: 接收已经生成好的向量，然后组织这些向量与其他字段。

### 3. Similarity / Distance
向量检索本质上是在问“谁和查询向量最像”。常见度量包括:

- cosine
- L2
- inner product

这些度量不是 UI 参数，而是后续索引、搜索参数、查询计划都要依赖的基础语义。

### 4. ANN
ANN 是 Approximate Nearest Neighbor，近似最近邻检索。它的工程意义不是“乱搜”，而是用召回率换时延和成本，让大规模检索可用。

后面当你看到 HNSW、IVF、DISKANN、SCANN 这些词时，不要把它们当成孤立算法名，而要把它们看成 ANN 的不同组织方式。

### 5. Collection
collection 是 Milvus 里最顶层的数据容器。你可以把它先类比成一张表，但它不是单纯的关系表，而是“围绕向量检索组织的一组实体”。

collection 下面会绑定:

- schema
- fields
- shard / channel
- consistency level
- properties

### 6. Schema / Field
schema 定义 collection 的数据合同，field 是 schema 的具体列。

Milvus 不是“只存一列向量”的系统。它的 field 至少可以分成:

- vector field
- scalar field
- JSON field
- primary key field

后面“数据组织格式”这一题会展开这部分，但 Theme 1 先记住: Milvus 的对象模型是混合字段模型。

### 7. Segment
segment 是 Milvus 组织数据、构建索引、执行检索的基本单元。

一个重要直觉是: Milvus 不会把整个 collection 当成一个大块直接扫描，而是把数据拆成多个 segment 来管理。

### 8. Growing Segment / Sealed Segment
segment 有生命周期。

- `growing`：仍在接收新数据
- `sealed`：不再继续追加写入，更适合索引和稳定查询

这个概念在写入流程、索引组织、查询流程三题里都会反复出现。

### 9. WAL
WAL 是写前日志抽象。你现在只需要理解两点:

- 写入不是直接“落成最终数据文件”
- 写入先进入日志/消息链路，再被后续组件组织成可查询的数据形态

### 10. Flush / Handoff / Compaction
这三个词最好一开始就区分清楚:

- `flush`：把 growing 路径的数据推进到持久化对象
- `handoff`：查询服务责任向 sealed/indexed 视图切换
- `compaction`：对 segment 重写、合并、整理

它们都和生命周期有关，但不是一回事。

### 11. Shard / Channel
Milvus 是分布式系统，写入和服务不是靠单一内存结构完成的。

- `shard` 更偏逻辑分片
- `channel` 更偏组件间传播写入与状态的通道

后面讲整体架构和写入流程时，这两个概念会把“一个 collection”拆解成真正可运行的系统路径。

### 12. Index
index 是 Milvus 用来加速检索和过滤的结构，不只包含向量索引，也包含标量/倒排类索引能力。

这一题先记住两点:

- index 通常依附于字段
- index 又和 segment 生命周期强相关

### 13. Query Plan
query plan 是一次搜索或查询在执行前形成的逻辑计划。它至少要回答:

- 查哪些 segment
- 用什么向量类型和度量
- 有哪些过滤条件
- 怎么归并结果

Theme 6 和 Theme 7 会把它展开成完整查询流程。

## 一个最小心智模型

如果把 Milvus 压缩成一句话，可以先这么记:

> Milvus 是一个围绕 collection/schema/field 组织混合数据，用 segment 和 index 承载存储与检索，并通过 query plan 驱动执行的向量数据库系统。

再把它拆成一条最小链路:

```text
对象 -> embedding -> vector + scalar/json fields
-> collection/schema
-> segments
-> indexes
-> search/query plan
-> query execution
```

后面 7 个主题，实际上就是把这条链一段一段讲透。

## 这些概念之间怎么连起来

### 从数据建模角度
- collection 是容器
- schema/field 是数据合同
- vector/scalar/JSON 是字段类型

### 从生命周期角度
- 数据先进入 growing segment
- 再经历 flush
- 再进入 sealed / indexed 服务路径

### 从执行角度
- query/search 会先形成 plan
- plan 决定查哪些 segment、走哪些索引和过滤逻辑

### 从系统角度
- shard/channel 让 collection 能被分布式地写入和服务
- WAL、compaction、handoff 让系统在实时性和稳定性之间取得平衡

## 本地源码目录怎么对应这些概念

### 第一层: 客户端和对外建模
- `milvus/client/entity`
- `milvus/client/index`
- `milvus/client/milvusclient`

这一层适合先看“Milvus 对外暴露了哪些概念”。如果你要先建立 collection、schema、field、index 的直觉，这里是最轻量的入口。

### 第二层: 协议与计划结构
- `milvus/pkg/proto/planpb`
- `milvus/pkg/proto/querypb`
- `milvus/pkg/proto/indexpb`
- `milvus/pkg/proto/datapb`

这一层适合看“系统内部怎样正式表达 plan、query、index、data”。如果你只看 client 层，容易把概念停留在 API 名字；看 proto 才能知道系统真正交换什么结构。

### 第三层: 元数据模型
- `milvus/internal/metastore/model`

这一层适合看 collection、segment、index 在系统内部如何作为 catalog / metadata 模型被表示。

### 第四层: 运行时 segment 与查询侧概念
- `milvus/internal/querynodev2/segments`
- `milvus/internal/querynodev2/pkoracle`
- `milvus/internal/parser/planparserv2`

这一层开始进入真正运行时。它把“segment 是什么”“query plan 是什么”从概念推进到执行结构。

## Theme 1 的关键文件

### 对外概念入口
- `milvus/client/entity/schema.go`
- `milvus/client/entity/collection.go`
- `milvus/client/entity/segment.go`
- `milvus/client/index/common.go`

这些文件回答的是:

- collection 和 schema 在客户端如何表示
- field 和 dynamic field 的基本概念是什么
- segment 在对外 API 里至少暴露哪些状态
- Milvus 支持哪些 index type

### 协议与计划入口
- `milvus/pkg/proto/planpb/plan.pb.go`
- `milvus/pkg/proto/querypb/query_coord.pb.go`
- `milvus/pkg/proto/indexpb/index_coord.pb.go`

这些文件回答的是:

- 查询计划里有哪些操作类型和向量类型
- query 相关组件交换什么消息
- index 相关组件交换什么消息

### 系统内部元数据入口
- `milvus/internal/metastore/model/collection.go`
- `milvus/internal/metastore/model/segment.go`
- `milvus/internal/metastore/model/index.go`

这些文件回答的是:

- collection 内部有哪些元信息
- segment 的系统内部表示长什么样
- index metadata 里记录了什么

### 运行时概念入口
- `milvus/internal/querynodev2/segments/manager.go`
- `milvus/internal/parser/planparserv2/plan_parser_v2.go`
- `milvus/internal/querynodev2/pkoracle/pk_oracle.go`

这些文件回答的是:

- growing / sealed segment 在运行时如何被管理
- plan 是如何被解析和组织的
- 主键相关辅助结构在查询侧如何帮助定位数据

## 建议阅读顺序

### 第 1 轮: 建立外部名词表
1. `milvus/client/entity/collection.go`
2. `milvus/client/entity/schema.go`
3. `milvus/client/index/common.go`
4. `milvus/client/entity/segment.go`

这轮目标不是理解执行，而是先把 collection、schema、field、index、segment 的名字固定下来。

### 第 2 轮: 看系统内部怎么正式表示这些概念
1. `milvus/internal/metastore/model/collection.go`
2. `milvus/internal/metastore/model/segment.go`
3. `milvus/internal/metastore/model/index.go`
4. `milvus/pkg/proto/planpb/plan.pb.go`

这轮目标是把“对外 API 概念”转换成“系统内部数据结构概念”。

### 第 3 轮: 看运行时概念如何真正落地
1. `milvus/internal/querynodev2/segments/manager.go`
2. `milvus/internal/parser/planparserv2/plan_parser_v2.go`
3. `milvus/internal/querynodev2/pkoracle/pk_oracle.go`

这轮目标是把 concept 过渡到 runtime，把 segment、plan、pk helper 从名词变成执行对象。

## 这一题学完后你应该能回答

1. embedding 和 Milvus 的边界在哪里？
2. collection、schema、field、segment、index 各自解决什么问题？
3. 为什么 Milvus 既要有 client/entity 这一层，又要有 proto/model 这一层？
4. growing segment 和 sealed segment 为什么必须区分？
5. query plan 为什么是独立概念，而不只是“查询请求”本身？

## 和下一题怎么衔接
Theme 1 解决的是“名词表”和“源码入口”。Theme 2 会回答这些概念在系统里是怎么组织成整体架构的，也就是:

- Proxy 在哪一层
- Coordinator 在哪一层
- Query Node / Data Node / Streaming Node 各自为什么存在
- 这些组件如何围绕 collection、segment、channel 这些概念协同

## 相关前置文档
- `docs/milvus_version_and_terms.md`
- `phase1_vectors_basics.md`
- `docs/milvus_mixed_data_model.md`
- `docs/milvus_storage_and_index_map.md`

