# Milvus Theme 5: 不同数据索引的组织方式

## 这一题要解决什么问题
Theme 4 解决的是“数据本身怎么组织”。Theme 5 要继续往前推进一步:

> Milvus 里的不同索引，到底是怎么挂在 field、segment 和查询服务路径上的？

如果这题只记“Milvus 支持 HNSW、IVF、Bitmap、Inverted”这些名字，其实还没有真正理解系统。真正要建立的是下面这个判断框架:

- 索引是定义在 field 上，还是落在 segment 上？
- 哪些索引工件在对象存储里，哪些只在查询节点内存里？
- growing segment 和 sealed segment 对索引的依赖程度有什么不同？
- 主键相关结构算不算索引，它在系统里怎样帮助查询和删除？

## 先给出总模型

可以先把 Theme 5 压缩成下面这张图:

```text
field-level index definition
  -> collection metadata records index intent
  -> sealed segment becomes index build target
  -> per-segment index task produces index files / stats files
  -> metadata records segment-index relation
  -> QueryCoord notices index-ready state
  -> QueryNode loads index or stats helpers for serving
```

这里最重要的一点是:

> Milvus 里的索引不是“collection 级一个全局大索引”，而是“field 定义 + segment 级工件 + query runtime 加载”共同组成的体系。

## 第 1 层: 先区分“索引定义”和“索引工件”

### 索引定义是 field 级意图
在 `milvus/client/index/common.go` 和 `milvus/client/index/scalar.go` 里，你能看到 client 对外暴露的是 index type。

典型向量索引类型包括:

- `FLAT`
- `IVF_FLAT`
- `IVF_PQ`
- `IVF_SQ8`
- `HNSW`
- `DISKANN`
- `SCANN`
- `SPARSE_INVERTED_INDEX`
- `SPARSE_WAND`

典型标量索引类型包括:

- `Trie`
- `STL_SORT`
- `INVERTED`
- `BITMAP`
- `RTREE`

这些定义回答的是:

- 某个 field 想建什么类型的索引
- 这个索引有哪些参数

但它们还不是最终可查询的工件。

### 索引工件是 segment 级产物
到了 `internal/metastore/model/index.go` 和 `internal/metastore/model/segment_index.go`，你会看到系统内部把索引拆成两层:

- `Index`
  表示 collection/field 维度上的索引定义
- `SegmentIndex`
  表示某个 segment 上某个 index 的实际构建结果

`SegmentIndex` 里会记录:

- `SegmentID`
- `CollectionID`
- `IndexID`
- `BuildID`
- `IndexState`
- `IndexFileKeys`
- `IndexSerializedSize`
- `IndexMemSize`
- `CurrentIndexVersion`
- `CurrentScalarIndexVersion`
- `IndexType`

所以 Theme 5 的第一条稳定结论是:

> 在 Milvus 里，“我要给某字段建索引”和“某个 segment 上已经有一份可加载的索引文件”是两件不同的事。

## 第 2 层: 向量索引的组织方式

### 1. 向量索引先是 field 上的定义
向量索引首先依附于某个 vector field。你在 client 侧选 `HNSW` 还是 `IVF_FLAT`，本质是在声明这个 field 的 ANN 组织方式。

### 2. 真正构建发生在 sealed segment 上
`internal/datacoord/index_service.go` 的注释已经写得很直白:

- CreateIndex 是异步的
- DataCoord 会拿到“所有 flushed segments”
- 然后给这些 segments 记录索引任务
- 后台 builder 再把任务分发给 worker 执行

这说明向量索引不是对 growing segment 实时重建的，而是围绕 flushed/sealed segment 组织。

### 3. DataCoord 用 segment 级 task 管理向量索引
`internal/datacoord/task_index.go` 里的 `indexBuildTask` 说明:

- 每个任务直接绑定一个 `SegmentIndex`
- 构建前会检查 segment 是否健康
- 会读取 segment 上该 field 的 binlog
- 小 segment 或 no-train index 甚至会直接标记为 finished

这说明向量索引的最小构建单位是:

```text
segment + field + index definition
```

而不是整个 collection。

### 4. DataNode 负责真正执行构建
`internal/datanode/index/task_index.go` 说明 worker 侧收到的是 `CreateJobRequest`，它会:

- 基于 field 的 binlog 路径准备数据
- 解析 index/type params
- 调用 `indexcgowrapper` 和底层 index engine 真正建索引

因此向量索引的组织路径可以概括为:

```text
field index definition
  -> DataCoord segment index task
  -> DataNode index build task
  -> index files persisted
```

### 5. 查询侧按 segment 加载向量索引
`internal/querynodev2/segments/segment_loader.go` 里的 `LoadIndex` 和 `loadFieldIndex` 表明:

- QueryNode 加载的是 `FieldIndexInfo.IndexFilePaths`
- 它会过滤掉 `index params` 这类非主体文件
- 然后把真正的 index files 交给 segment runtime 加载

`internal/querynodev2/segments/load_index_info.go` 进一步说明，最终索引是通过 segcore/CGO 层被装配进查询运行时的。

所以向量索引的服务形态不是“每次查对象存储”，而是:

- 对象存储承载索引工件
- QueryNode 按 segment 把它们加载进运行时

## 第 3 层: 标量索引的组织方式

### 标量索引仍然是 field 级定义
`client/index/scalar.go` 表明标量索引也是标准 index type，而不是查询优化器里偷偷生成的临时结构。

也就是说，`INVERTED`、`Trie`、`STL_SORT`、`BITMAP` 这些首先还是 field 级声明。

### 但标量索引的目标不是 ANN，而是过滤裁剪
向量索引解决的是“候选召回”，标量索引解决的是“如何更快过滤或定位满足条件的记录”。

Theme 5 不要把这两者混为一谈:

- 向量索引主要服务 search recall
- 标量索引主要服务 predicate/filter

### 标量索引同样落为 segment 级工件
`internal/metastore/model/segment_index.go` 里有 `CurrentScalarIndexVersion`，这非常关键。

它说明 Milvus 并没有把标量索引看成纯 collection 级抽象，而是也把它们和 segment 上的具体工件绑定起来。

`internal/storage/index_data_codec.go` 进一步说明，索引工件会被编码为带有:

- `indexBuildID`
- `collectionID`
- `partitionID`
- `segmentID`
- `fieldID`
- `indexName`
- `indexID`

等信息的 blob/binlog 形式。

这就再次证明:

> 不论是向量索引还是标量索引，真正进入存储层时都已经是 segment 级工件。

### 查询侧会根据索引类型估算不同资源形态
`internal/querynodev2/segments/index_attr_cache.go` 很有代表性。它会根据 index type 估算:

- 需要多少内存
- 需要多少磁盘
- 是否支持 disk load / mmap

例如:

- `DISKANN` 有明显的 disk-oriented 资源模型
- `INVERTED` 会把相关 binlog 与 index 一起考虑磁盘占用

这说明标量索引和向量索引在查询侧不只是“名字不同”，而是加载模型和资源模型都不同。

## 第 4 层: JSON / Text / Stats 类索引是另一种“索引工件”

Theme 5 最容易忽略的是: Milvus 当前不只有传统意义上的“一个 index file”，还有一类 stats/index sidecar 工件。

### JSON key stats
`internal/datanode/index/task_stats.go` 中的 `createJSONKeyStats` 表明:

- 它会遍历启用了 JSON key stats 的字段
- 基于该字段的 insert binlogs 生成 json key stats 文件
- 结果按 field 保存到 `datapb.JsonKeyStats`

而 `internal/querynodev2/segments/segment_loader.go` 中的 `LoadJSONIndex` 又表明:

- QueryNode 会单独加载 `JsonKeyStatsLogs`
- 并把它们送入 segment runtime

这说明 JSON 相关过滤优化不是和向量索引完全同一套文件，但它同样是:

- field 级能力
- segment 级工件
- query runtime 可加载对象

### Text / BM25
从 `internal/datanode/index/task_stats.go` 和相关搜索结果可以看到，BM25/text 侧也会生成专门的 stats 或 index 产物。

这类工件的意义更接近:

- 为全文/词项类能力提供辅助结构
- 和普通 ANN 索引不同
- 但依然跟 segment 生命周期绑定

因此 Theme 5 可以把它们归入一类:

> 非 ANN 的过滤/文本/JSON sidecar 索引工件

## 第 5 层: 主键辅助结构的组织方式

主键这部分特别重要，因为它和“索引”既相似又不完全一样。

### 主键辅助结构不服务相似度，但服务定位和裁剪
`internal/storage/pk_statistics.go` 和 `internal/storage/stats.go` 表明系统会维护:

- PK min/max
- PK bloom filter
- PrimaryKeyStats

这些结构不做 ANN，但它们可以快速回答:

- 某个 pk 有没有可能在这个 segment 里
- 删除或精确定位时该先查哪些 segment

### QueryNode 用 pkoracle 管这些候选关系
`internal/querynodev2/pkoracle/pk_oracle.go` 和 `bloom_filter_set.go` 说明:

- QueryNode 会把 segment 的 bloom-filter-based 候选结构注册到 `PkOracle`
- `Get` / `BatchGet` 会返回“哪些 segments 可能包含该 pk”
- sealed segment 会加载历史 stats
- growing 侧还可能维护 currentStat

因此主键辅助结构的正确理解不是“一个普通 field index”，而是:

> 一组围绕 pk 定位、删除传播和 segment 剪枝的统计/过滤辅助结构。

### 它们同样依附于 segment 生命周期
`segment_loader.go` 里的 `LoadBloomFilterSet` 说明 QueryNode 会从 stats logs 里加载这些结构。

这意味着主键辅助结构和普通 index 的共同点是:

- 都是 segment 级产物
- 都需要加载进查询节点

不同点是:

- 它们更像 segment pruning / pk routing helper
- 而不是 search recall index

## 第 6 层: 为什么所有索引最终都要回到 segment 生命周期

因为 Milvus 的服务单元本来就是 segment。

### growing segment
growing segment 的主要目标是近实时可见性。它更依赖原始数据和运行时结构，而不是完整的 sealed index 工件。

### sealed segment
sealed segment 是索引真正稳定附着的地方。无论是:

- vector index
- scalar index
- JSON key stats
- BM25/text sidecar
- pk bloom/stats helper

都更自然地围绕 sealed segment 生成、持久化和加载。

### compaction 会改写索引归属
因为 compaction 会重写或合并 segment，所以 Theme 5 要有一个非常重要的意识:

> 索引不是永远固定在“那一批原始 segment”上。只要 segment 变了，索引工件和 stats/helper 工件也必须跟着重建或迁移。

## Theme 5 的正确心智模型

把上面压缩一下，可以得到 Theme 5 最重要的 4 句话:

### 1. 索引先定义在 field 上，但真正可服务的是 segment 上的索引工件

### 2. 向量索引、标量索引、JSON/text sidecar、主键辅助结构，都是 segment 生命周期上的不同工件

### 3. QueryNode 服务时不是“现场建索引”，而是加载已经构建好的 segment 级工件

### 4. compaction / handoff / reopen 会让索引组织始终和 segment 生命周期一起变化

## Theme 5 的源码目录

### 对外索引类型与参数
- `milvus/client/index`

### 内部索引元数据与 segment 级索引关系
- `milvus/internal/metastore/model`
- `milvus/internal/datacoord`

### 实际索引构建与 stats 工件生成
- `milvus/internal/datanode/index`
- `milvus/internal/storage`

### 查询侧索引加载与主键辅助结构
- `milvus/internal/querynodev2/segments`
- `milvus/internal/querynodev2/pkoracle`
- `milvus/internal/querycoordv2/checkers`

### 更底层的索引实现入口
- `milvus/internal/util/vecindexmgr`
- `milvus/internal/core/src/index`

## Theme 5 的关键文件

### 对外索引类型
- `milvus/client/index/common.go`
- `milvus/client/index/scalar.go`

这两份文件回答:

- Milvus 对外暴露了哪些向量/标量索引类型
- 哪些索引首先是 field 级定义

### 内部索引元数据
- `milvus/internal/metastore/model/index.go`
- `milvus/internal/metastore/model/segment_index.go`
- `milvus/internal/datacoord/index_meta.go`

这三份文件回答:

- field 级索引定义如何保存
- segment 级索引构建结果如何保存
- DataCoord 如何维护 segment-index 元数据

### 索引构建链路
- `milvus/internal/datacoord/index_service.go`
- `milvus/internal/datacoord/task_index.go`
- `milvus/internal/datanode/index/task_index.go`

这三份文件回答:

- CreateIndex 如何变成异步任务
- segment 级 build task 如何被分配
- worker 如何真正执行索引构建

### stats / JSON / 主键辅助结构
- `milvus/internal/datacoord/task_stats.go`
- `milvus/internal/datanode/index/task_stats.go`
- `milvus/internal/storage/pk_statistics.go`
- `milvus/internal/storage/stats.go`

这几份文件回答:

- JSON key stats / text / BM25 一类 sidecar 工件如何被生成
- pk bloom/min-max 这类辅助结构如何被保存

### 查询侧加载与服务
- `milvus/internal/querynodev2/segments/segment_loader.go`
- `milvus/internal/querynodev2/segments/load_index_info.go`
- `milvus/internal/querynodev2/segments/index_attr_cache.go`
- `milvus/internal/querycoordv2/checkers/index_checker.go`
- `milvus/internal/querynodev2/pkoracle/pk_oracle.go`
- `milvus/internal/querynodev2/pkoracle/bloom_filter_set.go`

这几份文件回答:

- QueryNode 如何加载 segment index
- QueryCoord 如何发现 segment 缺索引并触发 reopen/update
- pk helper 如何在查询侧做 segment 剪枝

### 更底层索引实现
- `milvus/internal/util/vecindexmgr/vector_index_mgr.go`
- `milvus/internal/core/src/index/IndexFactory.cpp`
- `milvus/internal/core/src/index/VectorMemIndex.cpp`
- `milvus/internal/core/src/index/VectorDiskIndex.cpp`
- `milvus/internal/core/src/index/ScalarIndex.cpp`
- `milvus/internal/core/src/index/JsonInvertedIndex.cpp`

这几份文件适合在你已经理解上层组织方式之后，再去看 Milvus 底层到底怎样区分内存向量索引、磁盘向量索引和标量/JSON 索引实现。

## 建议阅读顺序

### 第 1 轮: 先固定“有哪些索引类型”
1. `milvus/client/index/common.go`
2. `milvus/client/index/scalar.go`
3. `milvus/internal/util/vecindexmgr/vector_index_mgr.go`

这一轮的目标是先知道 Milvus 到底把哪些东西当作 vector index，哪些东西当作 scalar index。

### 第 2 轮: 再看索引如何从 field 定义变成 segment 级元数据
1. `milvus/internal/metastore/model/index.go`
2. `milvus/internal/metastore/model/segment_index.go`
3. `milvus/internal/datacoord/index_meta.go`

这一轮的目标是理解“index definition”和“segment index artifact”之间的区别。

### 第 3 轮: 看向量索引和标量索引如何真正构建
1. `milvus/internal/datacoord/index_service.go`
2. `milvus/internal/datacoord/task_index.go`
3. `milvus/internal/datanode/index/task_index.go`
4. `milvus/internal/storage/index_data_codec.go`

这一轮的目标是搞清异步索引构建链路，以及 index files 怎样进入存储层。

### 第 4 轮: 看 stats/helper 类工件
1. `milvus/internal/datacoord/task_stats.go`
2. `milvus/internal/datanode/index/task_stats.go`
3. `milvus/internal/storage/pk_statistics.go`
4. `milvus/internal/storage/stats.go`

这一轮的目标是把 JSON key stats、BM25/text sidecar、pk bloom helper 这类“不是传统 ANN 文件但同样参与索引组织”的东西放进统一心智模型。

### 第 5 轮: 最后看查询侧如何加载与利用这些工件
1. `milvus/internal/querycoordv2/checkers/index_checker.go`
2. `milvus/internal/querynodev2/segments/segment_loader.go`
3. `milvus/internal/querynodev2/segments/load_index_info.go`
4. `milvus/internal/querynodev2/segments/index_attr_cache.go`
5. `milvus/internal/querynodev2/pkoracle/pk_oracle.go`
6. `milvus/internal/querynodev2/pkoracle/bloom_filter_set.go`

这一轮的目标是把“索引文件已经生成”过渡到“查询节点怎样真正用它们服务”。

### 第 6 轮: 如果还想继续深挖底层实现
1. `milvus/internal/core/src/index/IndexFactory.cpp`
2. `milvus/internal/core/src/index/VectorMemIndex.cpp`
3. `milvus/internal/core/src/index/VectorDiskIndex.cpp`
4. `milvus/internal/core/src/index/ScalarIndex.cpp`
5. `milvus/internal/core/src/index/JsonInvertedIndex.cpp`

这一轮的目标是进入 segcore / C++ 实现层，研究真正的数据结构和算法实现。

## 这一题学完后你应该能回答

1. 为什么 Milvus 里的索引不是“collection 级一个大索引”，而是 segment 级工件集合？
2. 向量索引、标量索引、JSON/text sidecar、主键辅助结构之间最大的组织差异是什么？
3. QueryNode 为什么既要加载 index files，又要加载 stats/bloom 这类辅助工件？
4. compaction 和 reopen 为什么会直接影响索引组织方式？
