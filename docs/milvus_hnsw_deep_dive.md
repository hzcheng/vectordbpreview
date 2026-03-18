# Milvus HNSW 深度拆解

## 这份文档回答什么

这次只盯住一个索引：`HNSW`。

目标是把下面 5 件事讲清楚：

1. `HNSW` 的算法原理到底是什么
2. 用一个直观例子理解它为什么比暴力搜索快
3. `HNSW` 在 Milvus 里什么时候构建、是不是异步构建
4. `HNSW` 在 Milvus 查询侧的内存形态是什么
5. `HNSW` 在 Milvus / Knowhere / 对象存储里的磁盘承载方式是什么

这份文档会严格区分两层：

- **算法层**：HNSW 作为 ANN 图索引本身怎么工作
- **Milvus 实现层**：Milvus 如何调度、构建、保存、加载 HNSW

---

## 第一部分：先用一句话抓住 HNSW

HNSW = **Hierarchical Navigable Small World**。

最短解释：

> 它把所有向量组织成一张“多层导航图”，搜索时先在高层图里快速靠近目标区域，再在底层图里精细搜索最近邻。

如果你只记一句话，就记这句。

---

## 第二部分：HNSW 的算法原理

## 2.1 为什么需要它

假设你有 1000 万个向量。

如果每次查询都拿查询向量和 1000 万个向量逐个算距离，那就是 `FLAT / brute-force` 思路：

- 结果最准确
- 但是代价太高

HNSW 的目标不是“完全精确”，而是：

> 用少得多的距离计算，尽量逼近真正最近邻。

它属于 **ANN（Approximate Nearest Neighbor）**。

---

## 2.2 它为什么叫“Hierarchical”

因为它不是只有一张图，而是 **多层图**。

一个形象化想法：

- **顶层**：节点很少，像高速公路，只负责快速跨大区域移动
- **中层**：节点更多，像城市主干道
- **底层**：节点最多，像街区道路，负责最后的精细定位

不是每个点都会出现在所有层。

通常：

- 少数节点会出现在高层
- 大多数节点只会出现在底层

所以搜索过程像：

1. 先从高层某个入口点开始
2. 每次都往“更像查询向量”的邻居方向走
3. 到这一层走不动了，就下降一层
4. 到最底层后，在局部区域里展开更充分的候选搜索

---

## 2.3 它为什么叫“Small World”

因为它利用了 **small-world graph** 的性质：

- 图里大多数边是“局部近邻边”
- 但还保留一些“长跳跃边”

这很像现实世界交通网络：

- 你可以在本地街道里精细移动
- 也可以通过高速路一下跳很远

所以你不需要遍历所有点，就能比较快地接近目标区域。

---

## 2.4 HNSW 搜索过程的直觉版

假设你要找一个“像猫”的向量。

图里每个节点是一条向量记录，每条边连接“相近”的向量。

### 第一步：从入口点出发

入口点可能离“猫”很远，比如更像“汽车”。

但在高层图里，节点少、边跨得远，所以你可以很快从：

`汽车 -> 宠物 -> 狗 -> 猫科`

逐渐靠近目标语义区域。

### 第二步：逐层往下

到了更低层，图更密，局部结构更细。

这时你不再只做“大跳跃”，而是开始在“宠物 / 猫科 / 家猫 / 幼猫”这些局部近邻里继续比较。

### 第三步：底层候选扩展

到底层后，HNSW 不只是“贪心地沿一条路走到底”，而是维护一个候选集：

- 当前最值得继续扩展的节点
- 当前已经见过的候选节点
- 当前 topK 的最好结果

这样可以避免因为早期某次局部决策不好而彻底走偏。

这就是为什么 `ef` 很重要：

- `ef` 越大，搜索时保留和扩展的候选越多
- recall 往往越高
- 延迟也往往更高

---

## 2.5 HNSW 建图过程的直觉版

插入一个新节点时，不是随便连边，而是：

1. 先给这个点随机决定一个最高层级
2. 从当前全局入口点出发，先在高层找到大致位置
3. 逐层往下，在每层找到一批近邻候选
4. 选出一部分节点连边
5. 这些被连接的旧节点，也可能需要回连到新节点

所以 HNSW 的图不是一次性静态生成，而是一个 **逐步插入、逐步维护邻接关系** 的结构。

---

## 2.6 3 个最重要参数

Milvus 客户端暴露的 HNSW 参数很直接：

- 构建参数：`M`、`efConstruction`
- 查询参数：`ef`

对应代码见：

- `milvus/client/index/hnsw.go:23`
- `milvus/client/index/hnsw.go:38`
- `milvus/client/index/hnsw.go:72`

### `M`

可以把它理解成：

> 每个节点大致允许保留多少条邻接边

直觉上：

- `M` 小：图更省内存，构建更轻，搜索可能更容易走偏
- `M` 大：图更密，内存更大，构建更贵，搜索 recall 往往更好

### `efConstruction`

可以把它理解成：

> 建图时“挑邻居”允许看的候选范围有多大

直觉上：

- 小：建图快，但图质量差
- 大：建图慢，但图质量通常更好

### `ef`

可以把它理解成：

> 查询时保留多少候选继续探索

直觉上：

- 小：更快，可能漏召回
- 大：更稳，延迟更高

---

## 第三部分：用一个小例子直观感受 HNSW

## 3.1 先想象一个二维平面

假设底层有这些点：

- A: `(0, 0)`
- B: `(1, 0)`
- C: `(2, 0)`
- D: `(8, 8)`
- E: `(9, 8)`
- F: `(9, 9)`

很明显，它们分成两团：

- 左边一团：A、B、C
- 右上角一团：D、E、F

现在查询点 `q = (8.5, 8.7)`。

真正最近的显然应该在 `D/E/F` 附近。

### 暴力检索怎么做

它会算：

- `dist(q, A)`
- `dist(q, B)`
- `dist(q, C)`
- `dist(q, D)`
- `dist(q, E)`
- `dist(q, F)`

一个都不放过。

### HNSW 怎么想

先假设高层只有少量代表节点，比如：

- 顶层：B、E
- 底层：A、B、C、D、E、F

搜索从入口点 B 开始。

1. 在顶层比较：
   - B 离 q 很远
   - E 离 q 很近
   - 所以快速跳到 E
2. 下到底层，以 E 为中心展开：
   - 看 E 的邻居 D、F
   - 发现 D/E/F 都非常接近 q
3. 最后返回 `E`、`F`、`D`

这里最关键的不是“完全没算远处点”，而是：

> 它通过图导航，很快把搜索预算集中到了真正可能有答案的局部区域。

这就是 HNSW 的核心价值。

---

## 3.2 再给一个“语义”版例子

假设文档 embedding 大致形成下面几团：

- 编程语言
- 数据库
- 宠物
- 旅游

你查的是：

`"milvus hnsw build path"`

HNSW 的导航过程可以想成：

1. 高层：先从“技术类”大区域靠近
2. 中层：从“数据库”进一步靠近“向量数据库”
3. 底层：在 “Milvus / Faiss / ANN / HNSW” 这群局部点里细搜

所以它不像树那样强制分叉，也不像 IVF 那样先硬分桶，而更像：

> 沿着相似性图，一步步往“更像查询”的方向导航。

---

## 第四部分：HNSW 的优点和代价

## 4.1 它擅长什么

- 高 recall
- 查询延迟通常很稳
- 不依赖像 IVF 那样的 coarse quantizer 训练
- 对很多语义检索场景很常用

## 4.2 它的代价是什么

- **内存占用通常比 IVF 类更重**
- 构建成本不低
- 图结构比较复杂，更新和压缩不像倒排那样简单

Milvus 配置里甚至直接有一句默认注释：

> `HNSW index needs more memory to load.`

对应：

- `milvus/pkg/util/paramtable/component_param.go:4505`

所以实践里经常把 HNSW 看成：

> 用内存换 recall 和查询质量的一类图索引。

---

## 第五部分：Milvus 里 HNSW 的对外参数接口

Milvus 客户端定义了 HNSW 的对外参数：

- `M`
- `efConstruction`
- 查询参数 `ef`

对应：

- `milvus/client/index/hnsw.go:23`
- `milvus/client/index/hnsw.go:38`
- `milvus/client/index/hnsw.go:72`

参数约束在本地 checker 里可见：

- `efConstruction` 范围：`1 ~ 2147483647`
- `M` 范围：`1 ~ 2048`

对应：

- `milvus/internal/util/indexparamcheck/constraints.go:18`
- `milvus/internal/util/indexparamcheck/constraints.go:20`

HNSW 支持的主要 metric 类型：

- `L2`
- `IP`
- `COSINE`

对应：

- `milvus/internal/util/indexparamcheck/constraints.go:67`

通用向量索引参数校验入口在：

- `milvus/internal/util/indexparamcheck/vector_index_checker.go:44`
- `milvus/internal/util/indexparamcheck/vector_index_checker.go:81`
- `milvus/internal/util/indexparamcheck/vector_index_checker.go:129`

这里的重要结论是：

> 在 Milvus 里，HNSW 不是一个“特殊硬编码索引”，而是走通用向量索引校验链，再交给底层 Knowhere 去验证具体参数。

---

## 第六部分：HNSW 在 Milvus 里什么时候构建

## 6.1 结论先说

对 **sealed segment** 来说，HNSW 构建是：

> **异步调度的后台任务**

不是用户 `CreateIndex` 那一刻同步卡住等建完。

证据链：

- DataNode 收到建索引请求后，不直接在 RPC 里完成构建，而是创建 `IndexBuildTask`
- 再把任务放进 `TaskQueue.Enqueue`

对应：

- `milvus/internal/datanode/index_services.go:41`
- `milvus/internal/datanode/index_services.go:104`
- `milvus/internal/datanode/index_services.go:265`
- `milvus/internal/datanode/index_services.go:308`

在任务执行体里：

- `PreExecute()` 组装参数
- `Execute()` 调 `indexcgowrapper.CreateIndex(...)`
- `PostExecute()` 再 `Upload()`

对应：

- `milvus/internal/datanode/index/task_index.go:151`
- `milvus/internal/datanode/index/task_index.go:228`
- `milvus/internal/datanode/index/task_index.go:326`
- `milvus/internal/datanode/index/task_index.go:342`

所以从系统行为看：

1. 用户声明 field 需要 HNSW
2. Milvus 在 segment 级生成 build task
3. DataNode 后台异步构建
4. 构建完后上传索引文件
5. QueryNode 后续加载该 segment index

---

## 6.2 构建发生在什么数据上

构建任务里会把这些信息打包进 `BuildIndexInfo`：

- collection / partition / segment / field
- insert files
- field schema
- index params / type params
- 当前 index engine version

对应：

- `milvus/internal/datanode/index/task_index.go:285`

这说明 HNSW 不是直接对“整张 collection 全量内存”建一个大图，而是：

> 对某个 **segment 的向量字段数据** 单独构建 HNSW 工件。

这与 Milvus 的 segment-based 索引承载模型一致。

---

## 6.3 真正执行构建的是谁

`Execute()` 里调用的是：

- `indexcgowrapper.CreateIndex(...)`

对应：

- `milvus/internal/datanode/index/task_index.go:326`

而 C++ 侧桥接代码会：

1. 解析 `BuildIndexInfo`
2. 创建 `FileManagerContext`
3. 通过 `IndexFactory::CreateIndex(...)` 创建索引实例
4. 调 `index->Build()`

对应：

- `milvus/internal/core/src/indexbuilder/index_c.cpp:171`
- `milvus/internal/core/src/indexbuilder/index_c.cpp:206`
- `milvus/internal/core/src/indexbuilder/index_c.cpp:295`
- `milvus/internal/core/src/indexbuilder/index_c.cpp:301`

向量索引创建器 `VecIndexCreator` 也很直接：

- 通过 `IndexFactory` 创建索引对象
- 调 `BuildWithDataset()` 或 `Build()`
- 完成后 `Upload()`

对应：

- `milvus/internal/core/src/indexbuilder/VecIndexCreator.cpp:47`
- `milvus/internal/core/src/indexbuilder/VecIndexCreator.cpp:62`
- `milvus/internal/core/src/indexbuilder/VecIndexCreator.cpp:109`

这里最稳的结论是：

> Milvus 本身负责任务调度、元数据、文件管理；HNSW 的核心图构建逻辑主要由底层 `Knowhere` 索引实现承担。

---

## 第七部分：growing segment 会直接用 HNSW 吗

## 7.1 结论

**通常不是。**

Milvus 对 growing segment 使用的是 **临时 / interim index** 思路。

源码明确写着：

> 对 dense vector，growing 和 temp index 使用 `IVFFLAT_CC / SCANN_DVR`

对应：

- `milvus/internal/core/src/segcore/IndexConfigGenerator.cpp:37`
- `milvus/internal/core/src/segcore/IndexConfigGenerator.cpp:48`

所以要非常注意区分：

- **sealed segment 的正式索引**：可以是 `HNSW`
- **growing segment 的临时索引**：通常不是 `HNSW`

这意味着：

> 你在 Milvus 查询一条“刚写进去、还在 growing segment”的数据时，走的未必是正式 HNSW 图。

---

## 7.2 为什么要这样设计

因为 growing segment 是：

- 会持续追加数据的
- 需要支持 `AddWithDataset`
- 需要快速维持可查询性

而 sealed segment 的正式索引更像：

- 数据边界稳定
- 允许一次性做更重的图构建
- 生成可持久化和可加载的正式索引工件

所以在工程上很自然会拆成：

- growing：先用适合在线增量维护的 interim index
- sealed：再异步构建正式 HNSW

---

## 第八部分：HNSW 在 QueryNode / segcore 里的内存组织

## 8.1 先说一个容易误解的点

在 Go 层，QueryNode 并不是直接拿一个 `HNSWGraph` 结构体来跑查询。

更准确地说：

> Go 层持有的是 segment / index metadata；真正的向量索引运行体主要在 segcore / Knowhere 侧。

在 sealed segment 加载向量索引时：

- `LoadVecIndex()` 先根据索引参数估算加载资源
- 再把 `cache_index` 放进 `vector_indexings_`
- 同时记录 `has_raw_data`

对应：

- `milvus/internal/core/src/segcore/ChunkedSegmentSealedImpl.cpp:171`
- `milvus/internal/core/src/segcore/ChunkedSegmentSealedImpl.cpp:199`
- `milvus/internal/core/src/segcore/ChunkedSegmentSealedImpl.cpp:218`
- `milvus/internal/core/src/segcore/ChunkedSegmentSealedImpl.cpp:221`

这说明 Query 时的 HNSW 运行体更像是：

- `vector_indexings_` 里的一个向量索引对象引用
- 背后实际载入的索引数据由 segcore / Knowhere 管理

---

## 8.2 加载资源怎么估算

向量索引加载时，Milvus 调 `VecIndexLoadResource()`：

- 根据 `index_type`
- `index_version`
- `index_size`
- `num_rows`
- `dim`
- `enable_mmap`

去估算内存 / 磁盘成本，并判断 `has_raw_data`

对应：

- `milvus/internal/core/src/index/IndexFactory.cpp:150`
- `milvus/internal/core/src/index/IndexFactory.cpp:162`
- `milvus/internal/core/src/index/IndexFactory.cpp:172`

这里的资源估算走的是 Knowhere 的静态接口：

- `EstimateLoadResource(...)`
- `HasRawData(...)`

对应：

- `milvus/internal/core/src/index/IndexFactory.cpp:187`
- `milvus/internal/core/src/index/IndexFactory.cpp:194`

因此从 Milvus 视角看，HNSW 的运行时内存组织可以总结成：

1. `SegmentIndex` 元数据记录它的文件和大小
2. QueryNode/segcore 根据索引参数估算加载成本
3. `vector_indexings_` 保存该 field 的可查询向量索引入口
4. 真实图结构和内部 buffer 由 Knowhere 索引对象持有

---

## 8.3 HNSW 会不会保留 raw vector

Milvus 在向量索引加载时会关心 `has_raw_data`。

对应：

- `milvus/internal/core/src/index/IndexFactory.cpp:172`
- `milvus/internal/core/src/segcore/ChunkedSegmentSealedImpl.cpp:210`

这说明某些向量索引在加载后可能仍然能提供 raw data 语义，Milvus 会据此决定是否驱逐 field raw data cache。

但需要谨慎：

> **从 Milvus 这一层代码，我们能确认它会查询 `HasRawData()`；但对 HNSW 在不同引擎版本下是否总是保留原始向量副本，最终仍由 Knowhere 实现决定。**

也就是说：

- **Milvus 有“是否包含 raw data”的抽象**
- **HNSW 具体是否保留、如何保留，是底层索引实现细节**

---

## 8.4 mmap 能不能用于 HNSW

Milvus 在向量索引加载资源评估时，如果：

- `mmap_enable = true`
- 且该索引类型支持 mmap

就会把 `enable_mmap = true` 填入 config。

对应：

- `milvus/internal/core/src/index/IndexFactory.cpp:162`

而本地单测里能看到专门的：

- `BuildEmbListHNSWIndexWithMmap`

对应：

- `milvus/internal/core/src/common/VectorArrayStorageV2Test.cpp:388`

因此一个比较稳妥的结论是：

> 至少在当前本地代码基线上，Milvus/Knowhere 体系已经把 HNSW 纳入了 mmap 能力测试范围。

但这里仍要注意：

- “支持 mmap” 不等于“完全不占内存”
- 更像是“某些索引文件可按 mmap 方式参与加载”

---

## 第九部分：HNSW 在硬盘 / 对象存储上的组织方式

## 9.1 先说 Milvus 的外层组织

Milvus 把真正可服务的索引记录成 `SegmentIndex`：

- `IndexFileKeys`
- `IndexSerializedSize`
- `IndexMemSize`
- `CurrentIndexVersion`
- `IndexType`

对应：

- `milvus/internal/metastore/model/segment_index.go:9`

这说明：

> 在 Milvus 的元数据层，HNSW 不是“某个 collection 的一个大文件”，而是 segment 级的一组索引文件工件。

---

## 9.2 索引文件路径骨架

segment index 文件路径构造函数是：

- `{rootPath}/index_files/{buildID}/{indexVersion}/{partID}/{segID}/{fileKey}`

对应：

- `milvus/pkg/util/metautil/segment_index.go:9`

所以如果你看到一个 HNSW segment 索引，它在对象存储上的主路径骨架通常可理解成：

```text
rootPath/index_files/{buildID}/{indexVersion}/{partitionID}/{segmentID}/{fileKey}
```

这层是 **Milvus 外层文件组织**。

---

## 9.3 每个文件内部怎么包

Milvus 不会直接把“裸 HNSW 二进制”原样扔出去，而是通过 `IndexFileBinlogCodec` 包一层：

1. 先写一个 `IndexParams` blob
2. 再把每个 index blob 逐个封装
3. descriptor/extra 里附带：
   - `indexBuildID`
   - `version`
   - `collectionID`
   - `partitionID`
   - `segmentID`
   - `fieldID`
   - `indexName`
   - `indexID`
   - `key`

对应：

- `milvus/internal/storage/index_data_codec.go:40`
- `milvus/internal/storage/index_data_codec.go:91`
- `milvus/internal/storage/index_data_codec.go:115`
- `milvus/internal/storage/index_data_codec.go:187`
- `milvus/internal/storage/index_data_codec.go:203`
- `milvus/internal/storage/index_data_codec.go:208`

这说明磁盘层有两层：

### 外层：Milvus 的 index binlog 封装

- 有完整 segment / field / build 元信息
- QueryCoord / QueryNode 可以按统一协议处理

### 内层：Knowhere 导出的 index blob

- 这里面才是 HNSW 具体的图结构二进制
- blob 的精确内部字段和切片方式主要由 Knowhere 控制

所以最稳妥的结论是：

> **Milvus 能确定“外层怎么包、怎么命名、怎么追踪”；但 HNSW 图内部的精确二进制布局并不是 Milvus 这一层统一定义的。**

---

## 9.4 为什么 `IndexFileKeys` 往往只存最后一级文件名

构建完成后，DataNode 在 `PostExecute()` 里会遍历上传结果，取每个远程文件名的最后一段作为 `fileKey` 保存：

- `saveFileKeys = append(saveFileKeys, fileKey)`

对应：

- `milvus/internal/datanode/index/task_index.go:367`
- `milvus/internal/datanode/index/task_index.go:369`
- `milvus/internal/datanode/index/task_index.go:374`

这和前面的路径函数正好拼起来：

- 元数据里存 `fileKey`
- 真正路径由 `{buildID}/{indexVersion}/{partID}/{segID}` + `fileKey` 还原

---

## 第十部分：Milvus 里的 HNSW 查询路径怎么理解

当 sealed segment 上的 HNSW 已经构建并加载后，查询侧大致是：

1. QueryNode 收到 search/query 相关请求
2. 对应 segment 的 vector field 已经有 `vector_indexings_`
3. segcore/Knowhere 使用已加载索引执行 ANN 搜索
4. 再与 filter / reduce / rerank 等链路拼接

这里要记住：

> HNSW 主要解决的是“候选召回”阶段的 ANN 搜索问题，不负责最终业务排序。

---

## 第十一部分：把“Milvus 里的 HNSW”压缩成一个心智模型

你可以把它压缩成下面这张图：

```text
用户声明 field 使用 HNSW
  -> Index (field-level definition)
  -> segment sealed 后生成 index build task
  -> DataNode 后台异步构建 HNSW
  -> Knowhere 产出 HNSW index blobs
  -> Milvus 用 IndexFileBinlogCodec 包装并上传
  -> SegmentIndex 记录 fileKeys / serializedSize / memSize / version
  -> QueryNode/segcore 加载该 segment 的 HNSW
  -> Search 时使用该已加载 HNSW 做 ANN 召回
```

同时要补一句：

```text
growing segment
  -> 不是正式 HNSW
  -> 而是 interim dense-vector index（如 IVFFLAT_CC / SCANN_DVR）
```

---

## 第十二部分：最容易混淆的 4 个点

## 12.1 “Milvus 使用 HNSW” 不等于 “所有搜索都直接在 HNSW 上做”

因为 growing segment 通常不是正式 HNSW。

## 12.2 “HNSW 落盘了” 不等于 “Milvus 自己定义了 HNSW 图文件内部格式”

Milvus 定义的是外层承载和元数据封装，内部图二进制主要由 Knowhere 管理。

## 12.3 “HNSW 查询快” 不等于 “它比 IVF 一定更省资源”

HNSW 往往更吃内存。

## 12.4 “CreateIndex” 不等于 “同步立即建完”

在当前 Milvus 基线里，segment 级正式索引构建是后台异步任务。

---

## 第十三部分：如果你要继续深挖，推荐怎么读源码

推荐顺序：

1. **对外参数层**
   - `milvus/client/index/hnsw.go`
   - `milvus/internal/util/indexparamcheck/constraints.go`
   - `milvus/internal/util/indexparamcheck/vector_index_checker.go`
2. **任务调度层**
   - `milvus/internal/datanode/index_services.go`
   - `milvus/internal/datanode/index/task_index.go`
3. **构建桥接层**
   - `milvus/internal/core/src/indexbuilder/index_c.cpp`
   - `milvus/internal/core/src/indexbuilder/VecIndexCreator.cpp`
4. **加载与运行时层**
   - `milvus/internal/core/src/index/IndexFactory.cpp`
   - `milvus/internal/core/src/segcore/ChunkedSegmentSealedImpl.cpp`
5. **持久化与路径层**
   - `milvus/internal/storage/index_data_codec.go`
   - `milvus/pkg/util/metautil/segment_index.go`
   - `milvus/internal/metastore/model/segment_index.go`
6. **growing vs sealed 的边界**
   - `milvus/internal/core/src/segcore/IndexConfigGenerator.cpp`

---

## 最后一段总结

如果只用 4 句话总结：

1. **算法上**，HNSW 是多层导航图，靠“高层快速定位 + 底层精细扩展”做近似最近邻搜索。
2. **参数上**，`M` 控制图连边规模，`efConstruction` 控制建图探索强度，`ef` 控制查询探索强度。
3. **Milvus 实现上**，正式 HNSW 是 **segment 级、后台异步构建、QueryNode/segcore 加载后服务** 的索引工件。
4. **存储上**，Milvus 管的是 `SegmentIndex + index_files/... + index binlog wrapper`，而 HNSW 图本身的具体二进制布局主要由 Knowhere 决定。
