# Milvus 索引类型、内存组织与磁盘组织

## 这份文档要回答什么

你这次关心的是 3 件事：

1. **Milvus 里到底有哪些索引类型？分别对应什么数据类型？**
2. **这些索引在内存里是怎么被组织和加载的？**
3. **这些索引落到硬盘 / 对象存储后，又是怎么组织的？**

这份文档会同时区分两层：

- **Milvus 代码层的稳定事实**
- **索引算法层的心智模型**

因为这两层很容易被混在一起。

举例：

- “`SegmentIndex` 记录 `IndexFileKeys`” 是 **Milvus 代码层事实**
- “HNSW 在内存里像多层图” 是 **算法层心智模型**

二者都重要，但不是同一层。

---

## 先给出一张总图

```text
用户创建索引
  -> field-level index definition
  -> DataCoord 记录 Index / SegmentIndex 元数据
  -> DataNode 基于 sealed segment 的 field data 构建索引
  -> index files / sidecar files 持久化到对象存储
  -> QueryCoord 发现 segment 已有可用索引
  -> QueryNode 把 index files 加载进 segcore runtime
  -> Search / Query 在 segcore 内使用索引执行
```

最重要的一句先记住：

> 在 Milvus 里，索引先定义在 field 上，但真正可服务的是 **segment 级工件**，最终由 QueryNode 加载进 segcore。

---

## 第一部分：Milvus 里有哪些索引类型

## 1.1 最稳定的分类方式

先别按索引名字记，先按 **数据类型** 记。

### A. Dense Vector 索引

主要对应：

- `FloatVector`
- `Float16Vector`
- `BFloat16Vector`
- `Int8Vector`
- 部分情况下 `ArrayOfVector`

当前本地代码里可见的主要 dense vector 索引类型包括：

- `FLAT`
- `IVF_FLAT`
- `IVF_PQ`
- `IVF_SQ8`
- `IVF_RABITQ`
- `HNSW`
- `IVF_HNSW`
- `AUTOINDEX`
- `DISKANN`
- `SCANN`
- `GPU_IVF_FLAT`
- `GPU_IVF_PQ`
- `GPU_CAGRA`
- `GPU_BRUTE_FORCE`

对外定义入口：

- `milvus/client/index/common.go:33`
- `milvus/client/index/flat.go:5`
- `milvus/client/index/ivf.go:5`
- `milvus/client/index/hnsw.go:7`
- `milvus/client/index/scann.go:5`
- `milvus/client/index/disk_ann.go:1`
- `milvus/client/index/gpu.go:1`

### B. Binary Vector 索引

主要对应：

- `BinaryVector`

当前代码里可见的主要 binary vector 索引类型包括：

- `BIN_FLAT`
- `BIN_IVF_FLAT`

### C. Sparse Vector 索引

主要对应：

- `SparseFloatVector`

当前代码里可见的主要 sparse vector 索引类型包括：

- `SPARSE_INVERTED_INDEX`
- `SPARSE_WAND`

对应入口：

- `milvus/client/index/sparse.go:1`

### D. Scalar / JSON / Array / String 索引

主要对应：

- `Bool`
- 各类整数
- `Float` / `Double`
- `VarChar` / `String`
- `Array`
- `JSON`
- `Timestamptz`

当前代码里可见的主要 scalar 索引类型包括：

- `INVERTED`
- `BITMAP`
- `STL_SORT`
- `Trie`
- `HYBRID`（内部 checker 可见）
- `NGRAM`（内部 checker 可见）

对应入口：

- `milvus/client/index/scalar.go:1`
- `milvus/client/index/json.go:1`
- `milvus/internal/util/indexparamcheck/conf_adapter_mgr.go:31`

### E. Geometry 索引

主要对应：

- `Geometry`

当前代码里可见的索引类型：

- `RTREE`

对应入口：

- `milvus/client/index/rtree.go:1`
- `milvus/internal/util/indexparamcheck/rtree_checker.go:1`

### F. Specialized / 扩展型索引

代码里还可见：

- `MINHASH_LSH`

对应入口：

- `milvus/client/index/minhash.go:1`

这一类在这次阅读里我没有继续追到完整 checker / runtime 链路，所以后面主体部分以 **主线稳定索引** 为主：dense/binary/sparse/scalar/json/geometry。

---

## 1.2 “索引类型 -> 数据类型” 对照表

下面这张表是这次最重要的第一张表。

| 索引类型 | 主要字段类型 | 作用 |
|---|---|---|
| `FLAT` | Dense float / int8 向量 | 暴力 KNN / 精确召回 |
| `IVF_FLAT` | Dense float / int8 向量 | coarse quantizer + list 召回 |
| `IVF_PQ` | Dense float / int8 向量 | IVF + product quantization |
| `IVF_SQ8` | Dense float / int8 向量 | IVF + scalar quantization |
| `IVF_RABITQ` | Dense 向量 | IVF + 量化变体 |
| `HNSW` | 多种向量类型，依赖 `vecindexmgr` 支持 | 图索引 ANN |
| `IVF_HNSW` | Dense 向量 | IVF 与图结构结合 |
| `SCANN` | Dense float 向量 | Google ScaNN 风格 ANN |
| `DISKANN` | Dense 向量 | 磁盘友好 ANN |
| `BIN_FLAT` | Binary vector | 二值向量暴力检索 |
| `BIN_IVF_FLAT` | Binary vector | 二值向量 IVF |
| `SPARSE_INVERTED_INDEX` | Sparse vector | 稀疏向量倒排 |
| `SPARSE_WAND` | Sparse vector | 稀疏向量 WAND |
| `INVERTED` | bool / arithmetic / string / array / JSON | 过滤谓词优化 |
| `BITMAP` | bool / int / string / array，且不能是 PK | 低基数字段过滤 |
| `STL_SORT` | numeric / string / timestamptz | 排序或范围过滤辅助 |
| `Trie` | string | 字符串词典型结构 |
| `NGRAM` | varchar / JSON(cast varchar) | n-gram 字符串检索辅助 |
| `HYBRID` | bool / int / float / string / array | BITMAP + INVERTED 思路 |
| `RTREE` | geometry | 空间索引 |

其中对“哪些字段类型合法”的最关键源码入口是：

- `milvus/internal/util/indexparamcheck/vector_index_checker.go:115`
- `milvus/internal/util/indexparamcheck/inverted_checker.go:23`
- `milvus/internal/util/indexparamcheck/bitmap_index_checker.go:10`
- `milvus/internal/util/indexparamcheck/trie_checker.go:11`
- `milvus/internal/util/indexparamcheck/stl_sort_checker.go:12`
- `milvus/internal/util/indexparamcheck/ngram_index_checker.go:17`
- `milvus/internal/util/indexparamcheck/rtree_checker.go:16`

---

## 第二部分：Milvus 代码层，索引在系统里怎么组织

## 2.1 先区分 3 层对象

### 层 1：`Index` —— field 级定义

在 `milvus/internal/metastore/model/index.go:9`：

```text
Index
  CollectionID
  FieldID
  IndexID
  IndexName
  TypeParams
  IndexParams
  UserIndexParams
```

这层表达的是：

> 某个 field 想建什么索引、参数是什么

它回答的是“意图”，不是最终可查询工件。

### 层 2：`SegmentIndex` —— segment 级构建结果

在 `milvus/internal/metastore/model/segment_index.go:8`：

```text
SegmentIndex
  SegmentID
  IndexID
  BuildID
  IndexState
  IndexFileKeys
  IndexSerializedSize
  IndexMemSize
  CurrentIndexVersion
  CurrentScalarIndexVersion
  IndexType
```

这层表达的是：

> 某个 segment 上，某个 field 的某种索引，已经构建出了哪些文件、大小多少、状态如何

所以最稳的结论是：

> Milvus 真正服务时依赖的是 `SegmentIndex`，而不是单独一个 collection 级全局大索引。

### 层 3：QueryNode runtime —— segcore 里的已加载索引

在 `milvus/internal/querynodev2/segments/segment.go:1018` 和
`milvus/internal/querynodev2/segments/load_index_info.go:17`：

- Go 层先把索引信息封装成 `LoadIndexInfo`
- 然后通过 `AppendIndexV2`
- 再 `UpdateSealedSegmentIndex`
- 最终把索引装进 segcore

这说明 QueryNode 的索引内存态分两部分：

```text
Go 层:
  fieldIndexes / index metadata / resource cache

C++ segcore 层:
  真正可用于 search/filter 的索引对象
```

---

## 第三部分：索引在内存里怎么组织

这里分成两类看最清楚：

1. **Milvus 代码层运行时结构**
2. **算法层的典型内存形态**

---

## 3.1 Milvus 代码层：索引在内存里不是一个 Go map 就完了

### A. DataCoord / Meta 层

DataCoord 内存里主要持有的是：

- `Index`
- `SegmentIndex`
- 构建状态
- file keys / size / version

这部分是 **控制面元数据**，不是实际搜索索引本体。

### B. DataNode 构建阶段

在 `milvus/internal/datanode/index/task_index.go:20`：

- `indexBuildTask` 会拿到 segment、field、index params、field data paths
- 基于 raw field data / optional scalar fields 构建索引
- 构建过程中会创建底层 `indexcgowrapper.CodecIndex`

这部分可以理解成：

```text
DataNode build memory
  raw field data
  + build params
  + temporary builder objects
  -> produce index blobs/files
```

### C. QueryNode sealed segment

在 `milvus/internal/querynodev2/segments/segment.go:290`，`LocalSegment` 主要持有：

```text
LocalSegment
├── fieldIndexes       // 已知索引元数据
├── fieldJSONStats     // JSON key stats
├── bloomFilterSet     // PK side structure
├── bm25Stats          // BM25 统计
└── csegment           // 真正的 segcore segment
```

这里最关键的一点是：

> Go 层 `LocalSegment` 并不直接存完整 HNSW 图或 IVF 倒排桶；真正的索引主体在 segcore / knowhere 那层。

### D. QueryNode growing segment

这部分最容易被忽略。

在 `milvus/internal/core/src/segcore/IndexConfigGenerator.cpp:24` 可以看到：

- Dense vector 的 growing / temp index 使用 **interim index**
  - `IVFFLAT_CC`
  - 或 `SCANN_DVR`
- Sparse vector 的 growing / temp index 使用
  - `SPARSE_WAND_CC`
  - 或 `SPARSE_INVERTED_INDEX_CC`

也就是说：

> growing segment 并不是“完全没索引”；它有一套偏临时、偏内存态的 interim index 机制。

而在 `milvus/internal/core/src/segcore/SegmentGrowingImpl.cpp:280` 又能看到：

- 对 dense vector interim index，是否持有 raw data 取决于 interim index 类型
- `IVF_FLAT_CC` 更像“索引里带 raw data”
- `SCANN_DVR` 更像“索引不持有全部 raw data，需要 raw data 另算”

这正好解释了 growing 和 sealed 的一个重要差别：

```text
Growing segment
  = raw data + interim index + mutable runtime state

Sealed segment
  = immutable segment + loaded final index files
```

---

## 3.2 算法层：各种索引在内存中的典型形态

这一节是 **算法层心智模型**，不是 Milvus 字节级文件格式承诺。

### 1. `FLAT`

最简单。

你可以把它理解为：

```text
raw vectors in contiguous memory
```

即：

- 不做复杂图或量化结构
- 搜索时对原始向量直接计算距离

它更像“没有复杂附加索引结构的向量数据视图”。

### 2. `IVF_FLAT`

算法层可理解为：

```text
coarse centroids
  + inverted lists
  + each list stores raw vectors / row references
```

也就是：

- 一组 coarse centroid
- 每个向量先被分配到某个 list
- 查询先 probe 若干 list，再在 list 内比较

### 3. `IVF_PQ`

算法层可理解为：

```text
coarse centroids
  + inverted lists
  + PQ codebooks
  + compressed vector codes
```

相比 `IVF_FLAT`：

- 倒排桶里存的不是完整 raw vector
- 而是压缩编码

所以它本质上是：

- 更省内存 / 磁盘
- recall 与精度需要更多权衡

### 4. `IVF_SQ8`

算法层可理解为：

```text
coarse centroids
  + inverted lists
  + scalar-quantized vector payload
```

和 `IVF_PQ` 一样属于压缩类，但压缩方式不同。

### 5. `HNSW`

算法层最经典心智模型：

```text
multi-layer navigable graph
  top sparse layers
  bottom dense layer
```

内存里主要是：

- 节点
- 邻接边
- 分层入口
- 向量或可比较表示

所以 HNSW 的核心不是“桶”，而是“图”。

### 6. `SCANN`

算法层可理解为：

```text
partition structure
  + quantization / compressed representation
  + optional raw data for rerank
```

而当前 client 参数里的 `with_raw_data` 又说明：

- 有些配置下索引会保留 raw data
- 有些配置下更偏压缩表示 + 重排

### 7. `DISKANN`

算法层可理解为：

```text
disk-resident graph / neighbor structure
  + small memory-resident routing/cache part
```

这和普通纯内存 ANN 最大区别是：

- 主体数据 / 图结构更多在磁盘
- 查询时允许 disk IO 参与

代码层也印证了这点：在 `milvus/internal/querynodev2/segments/index_attr_cache.go:20`，
`DISKANN` 的资源估算显式拆成 memory 与 disk。

### 8. `SPARSE_INVERTED_INDEX`

算法层可理解为：

```text
term / dimension -> postings list
```

即：

- 稀疏向量的非零维度相当于词项
- 每个维度维护 posting list

### 9. `SPARSE_WAND`

算法层可理解为：

```text
inverted lists
  + top-k pruning friendly upper bounds
```

比普通 sparse inverted 更偏 top-k 剪枝。

### 10. `INVERTED`

对标量 / JSON / array / string 过滤来说，可以理解为：

```text
value/token -> rowID / offset postings
```

对 JSON path 索引，还会先把 JSON path + cast type 固定出来。

### 11. `BITMAP`

算法层可理解为：

```text
value -> bitmap(row membership)
```

它非常适合：

- 低基数字段
- 枚举字段
- bool 字段

### 12. `STL_SORT`

算法层可理解为：

```text
sorted values / offsets
```

它更偏：

- 范围过滤
- 有序比较

### 13. `Trie`

算法层可理解为：

```text
prefix tree / dictionary structure
```

适合字符串类字段。

### 14. `NGRAM`

算法层可理解为：

```text
string -> ngram tokens -> inverted postings
```

更偏字符串模糊匹配/包含。

### 15. `RTREE`

算法层可理解为：

```text
bounding box hierarchy
```

用于 geometry 空间对象。

---

## 3.3 一张“索引内存组织”总图

```text
Growing segment
├── raw field data
├── pk map / timestamps
├── interim vector index (optional)
└── mutable insert/delete runtime state

Sealed segment on QueryNode
├── Go metadata
│   ├── fieldIndexes
│   ├── fieldJSONStats
│   ├── bloomFilterSet
│   └── bm25Stats
└── segcore loaded runtime
    ├── vector index objects
    ├── scalar/text/json index objects
    └── optional raw field data / mmap views
```

---

## 第四部分：索引在磁盘 / 对象存储上怎么组织

## 4.1 主线结论

Milvus 的索引落盘不是：

```text
collection -> one global index file
```

而是更接近：

```text
segment
  -> field
    -> index files / sidecar files
```

并且 DataCoord 元数据里只先记录：

- `IndexFileKeys`

真正的完整路径会在需要时拼出来。

---

## 4.2 向量 / 标量索引文件主路径

在 `milvus/pkg/util/metautil/segment_index.go:9`：

```text
{rootPath}/index_files/{buildID}/{indexVersion}/{partID}/{segID}/{fileKey}
```

这是最值得记住的一条路径规则。

也就是说，向量索引和标量索引主文件都挂在：

```text
index_files/
```

下面。

### 一个例子

```text
files/index_files/1001/1/222/333/HNSW_SQ_3
```

可读成：

- `1001` = buildID
- `1` = indexVersion
- `222` = partitionID
- `333` = segmentID
- `HNSW_SQ_3` = 某个 fileKey

这个路径例子在
`milvus/internal/datanode/importv2/copy_segment_utils.go:700`
附近的注释和测试中也能看到。

---

## 4.3 索引文件内部怎么编码

在 `milvus/internal/storage/index_data_codec.go:17` 的 `IndexFileBinlogCodec` 里：

- 会先序列化 `index params`
- 再逐个序列化 index blob
- 每个 blob 的 descriptor / extra 信息里带：
  - `indexBuildID`
  - `version`
  - `collectionID`
  - `partitionID`
  - `segmentID`
  - `fieldID`
  - `indexName`
  - `indexID`
  - `key`

所以磁盘层不是只有“裸文件内容”，而是：

```text
index blob
  + index identity metadata
  + params blob
```

也就是说：

> `IndexFileKeys` 只是 DataCoord 元数据里记的文件键；实际对象存储中对应的是带完整标识信息的索引 blob/file 集合。

---

## 4.4 QueryNode 如何拿到这些文件

在 `milvus/internal/querynodev2/segments/segment_loader.go:2214`：

- `SegmentLoadInfo` 里带 `IndexInfos`
- 每个 `FieldIndexInfo` 里带 `IndexFilePaths`
- loader 逐个调用 `loadFieldIndex`
- `LocalSegment.LoadIndex` 最终把这些路径送入 segcore

所以 QueryNode 读盘/读对象存储时，看到的不是“field name”，而是：

```text
segment load info
  -> field index info
    -> index file paths
      -> load into segcore
```

---

## 4.5 Sidecar 工件：JSON / BM25 / Text 不一定走同一条文件路径

这一点很关键。

### JSON key stats

在 `milvus/internal/datanode/index/task_stats.go:680` 之后和
`milvus/internal/querynodev2/segments/segment.go:1089`：

- JSON key stats 是单独生成的一类 sidecar 工件
- QueryNode 通过 `LoadJSONKeyIndex` 单独加载

所以它不是普通 ANN index file，但也是：

- segment 级
- field 级
- query runtime 可加载

### BM25 stats

在 `milvus/internal/querynodev2/segments/segment_loader.go:616` 和
`milvus/internal/querynodev2/segments/segment.go:95`：

- BM25 stats 也是单独的 sidecar 日志/文件
- QueryNode 会单独加载到 `bm25Stats`

所以：

```text
vector/scalar index files    -> 主索引工件
json key stats / bm25 stats  -> sidecar 工件
```

二者都属于索引体系，但不是完全同一种文件形态。

---

## 第五部分：把“索引类型”和“内存/磁盘组织”真正串起来

## 5.1 一张总表

| 类别 | 代表索引 | QueryNode 内存主形态 | 磁盘主形态 |
|---|---|---|---|
| Dense vector | `HNSW` / `IVF_*` / `SCANN` / `DISKANN` | Go 层 metadata + segcore 内向量索引对象 | `index_files/...` 下的 segment 级 index files |
| Binary vector | `BIN_FLAT` / `BIN_IVF_FLAT` | 同上，但数据类型是 binary vector | `index_files/...` |
| Sparse vector | `SPARSE_INVERTED_INDEX` / `SPARSE_WAND` | segcore 内稀疏 posting / WAND 结构 | `index_files/...` |
| Scalar | `INVERTED` / `BITMAP` / `STL_SORT` / `Trie` | segcore 内标量索引对象；部分场景配 mmap/raw data | `index_files/...` |
| JSON | `INVERTED(JSON path)` + `JSON key stats` | segcore JSON index + `fieldJSONStats` metadata | 主索引走 `index_files/...`，JSON key stats 走 sidecar logs |
| Text/BM25 | sparse inverted + BM25 stats | `bm25Stats` + 稀疏索引 runtime | BM25 stats logs + index files |
| Geometry | `RTREE` | segcore 内空间索引对象 | `index_files/...` |

---

## 5.2 你可以怎么理解“各种索引在内存中是如何组织的”

如果只用一句话回答：

> 在 Milvus 里，索引的 **Milvus 代码层内存组织** 统一表现为“Go metadata + segcore loaded index object”，而不同索引算法的差异主要体现在 segcore / knowhere 内部对象的组织方式上。

再展开一点：

- `HNSW` 的差异在 **图结构**
- `IVF_*` 的差异在 **centroid + inverted lists + raw/quantized payload**
- `SCANN` 的差异在 **partition + quantization + rerank/raw-data option**
- `DISKANN` 的差异在 **更多索引主体驻留磁盘**
- `INVERTED/BITMAP/Trie/STL_SORT` 的差异在 **标量值到行集合/偏移集合的组织方式**
- `RTREE` 的差异在 **空间层级结构**

所以：

```text
Milvus 系统视角:
  统一都像 "segment-level artifact loaded into segcore"

算法视角:
  每类索引内部结构完全不同
```

---

## 5.3 你可以怎么理解“各种索引在硬盘上是如何组织的”

如果只用一句话回答：

> 在 Milvus 里，索引磁盘组织的统一骨架是 **segment 级文件集合**，主索引大多挂在 `index_files/{buildID}/{indexVersion}/{partID}/{segID}/...` 下面，另有 JSON/BM25/text 等 sidecar 工件。

---

## 第六部分：我建议你接下来怎么继续深挖

如果你下一步还想继续，我最推荐这两条线：

### 方向 1：专门深挖某一类 ANN 索引

比如：

- `HNSW`
- `IVF_PQ`
- `DISKANN`

我可以继续帮你做成这种格式：

```text
算法原理
-> Milvus build path
-> QueryNode load path
-> 内存心智模型
-> 磁盘文件心智模型
-> 小例子
```

### 方向 2：专门深挖标量 / JSON 索引

比如：

- `INVERTED`
- `BITMAP`
- `JSON path + JSON key stats`

这条线会很适合理解：

- metadata filter 到底怎么加速
- 为什么 JSON 相关优化不是单一个 index file

---

## 最后一句总结

> Milvus 的索引体系不是“给 collection 建一个索引”这么简单，而是 “field 级定义 + segment 级工件 + QueryNode/segcore 加载执行” 的三层体系；真正的差异既体现在算法结构，也体现在 growing / sealed / on-disk 的不同承载方式上。
