# Findings & Decisions

## Requirements
- 用户需要一个 48 小时以内的学习计划，从零掌握向量数据、向量数据库、AI 检索场景。
- 学习计划必须同时覆盖上层应用场景与下层技术细节。
- 需要包含一个简单的小项目体验，帮助快速建立直觉。
- 需要进一步深入研究 Milvus 的向量部分实现细节。
- 需要把学习进度持久化到文件，使新会话可以恢复状态并回答“当前学习进度”。

## Research Findings
- HNSW 最稳妥的心智模型是“多层导航图”：高层负责跨区域快速逼近，底层负责局部候选扩展；`M` 控制图稠密度，`efConstruction` 控制建图候选宽度，`ef` 控制查询候选宽度。
- 在当前 Milvus 基线里，sealed segment 的 HNSW 构建是 DataNode 后台异步任务：`CreateJob/CreateJobV2 -> IndexBuildTask enqueue -> Execute(CreateIndex) -> PostExecute(Upload)`，而不是用户请求线程内同步建完。
- HNSW 的正式索引工件是 segment 级的，不是 collection 级单体；元数据层通过 `SegmentIndex.IndexFileKeys / IndexSerializedSize / IndexMemSize / CurrentIndexVersion / IndexType` 追踪该 segment 的 HNSW 工件。
- growing segment 通常不会直接使用正式 HNSW；当前 segcore 配置会给 dense vector 选择 `IVFFLAT_CC` 或 `SCANN_DVR` 一类 interim index，因此“刚写入数据的查询路径”和“sealed segment 正式 HNSW 路径”需要分开理解。
- Query 侧的 HNSW 运行体不在 Go struct 里裸露为图对象；Milvus 主要在 QueryNode/segcore 中维护向量索引入口和资源估算，真实图结构及其内部 buffer 由 Knowhere 索引对象持有。
- HNSW 的外层磁盘承载由 Milvus 统一组织为 `index_files/{buildID}/{indexVersion}/{partID}/{segID}/{fileKey}`；每个 blob 再经 `IndexFileBinlogCodec` 加一层 descriptor/extra metadata 封装，而 HNSW 图内部二进制布局主要由 Knowhere 管理。
- 当前对 “Milvus 索引体系” 的最稳妥心智模型应拆成 3 层：`Index`（field 级定义）、`SegmentIndex`（segment 级构建结果）、QueryNode/segcore 已加载索引对象（运行时可服务形态）。
- `milvus/client/index/common.go` 暴露的主要索引族包括 dense vector（`FLAT`、`IVF_*`、`HNSW`、`SCANN`、`DISKANN`、`AUTOINDEX`、GPU 系列）、binary vector（`BIN_FLAT`、`BIN_IVF_FLAT`）、sparse vector（`SPARSE_INVERTED_INDEX`、`SPARSE_WAND`）、scalar/string/json（`INVERTED`、`BITMAP`、`STL_SORT`、`Trie`）、geometry（`RTREE`），另有 `MINHASH_LSH` 等 specialized 分支。
- `milvus/internal/util/indexparamcheck/*checker.go` 表明不同索引支持的数据类型边界是明确校验的：向量索引统一经 `vecIndexChecker + vecindexmgr` 校验，`INVERTED` 支持 bool/arithmetic/string/array/JSON，`BITMAP` 支持 bool/int/string/array 且不能建在主键上，`Trie` 仅支持 string，`STL_SORT` 支持 numeric/string/timestamptz，`NGRAM` 支持 varchar/JSON(cast varchar)，`RTREE` 仅支持 geometry。
- `milvus/internal/metastore/model/segment_index.go` 中的 `IndexFileKeys`、`IndexSerializedSize`、`IndexMemSize`、`CurrentIndexVersion`、`CurrentScalarIndexVersion` 说明真正可服务的索引不是 collection 级单体，而是 segment 级文件集合及其版本化元数据。
- QueryNode 上的索引内存形态不是“Go struct 直接持有 HNSW/IVF 本体”；`LocalSegment` 在 Go 层主要维护 `fieldIndexes`、`fieldJSONStats`、`bm25Stats` 等 metadata，真正的索引主体通过 `LoadIndexInfo -> AppendIndexV2 -> UpdateSealedSegmentIndex` 装入 segcore。
- `milvus/internal/core/src/segcore/IndexConfigGenerator.cpp` 和 `SegmentGrowingImpl.cpp` 说明 growing segment 也有 interim index：dense 向量会转成 `IVFFLAT_CC` 或 `SCANN_DVR` 一类临时索引，sparse 向量会转成 `SPARSE_*_CC`，因此 “growing 完全无索引” 是错误心智模型。
- `milvus/internal/querynodev2/segments/index_attr_cache.go` 说明不同索引的运行时资源模型显式不同：`DISKANN` 是 memory+disk 混合加载模型，`INVERTED` 会把 index size 与 binlog data disk size 一起计入，普通内存索引则按内存放大系数估算。
- `milvus/internal/storage/index_data_codec.go` 表明索引文件会先序列化 index params，再序列化各 index blob；descriptor/extra 信息里会附带 `indexBuildID`、`version`、`collectionID`、`partitionID`、`segmentID`、`fieldID`、`indexName`、`indexID`、`key`，因此磁盘层不是“裸索引文件”，而是带完整身份信息的 segment 级索引工件。
- `milvus/pkg/util/metautil/segment_index.go` 表明向量/标量索引主路径骨架是 `{rootPath}/index_files/{buildID}/{indexVersion}/{partID}/{segID}/{fileKey}`；JSON key stats、BM25 stats、text sidecar 属于与主索引并列的附加工件，而不是完全相同的文件组织。
- 当前对 “Milvus 数据组织” 的最稳妥心智模型应拆成 4 层：逻辑模型（collection/schema/field）、写入侧内存模型（`InsertData -> map[fieldID]FieldData`）、查询侧内存模型（`LocalSegment` Go wrapper + `segcore CSegment`）、持久化模型（insert/stats/delta/index logs 或 packed parquet + manifest）。
- `milvus/internal/storage/insert_data.go` 明确说明写入侧内存不是 `[]Row`，而是按 `FieldID` 拆开的列；标量通常对应 `[]int64`/`[]string` 等，JSON 对应 `[][]byte`，向量列则是拍平后的连续缓冲区加 `Dim`。
- nullable 字段的核心表达不是“特殊值占位”，而是 `Data + ValidData`；nullable vector 额外带 `LogicalToPhysicalMapping`，说明逻辑行和物理向量缓冲区位置可能不一一直接对应。
- `milvus/internal/storage/data_codec.go` 的 `InsertCodec.Serialize` 会按 schema 遍历每个 field，为每个 field 单独创建 binlog writer 并写整列 payload；这直接证明 V1 持久化主线是 segment 内再按 field 切分，而不是把整行对象序列化成一个大块。
- `milvus/internal/storage/binlog_util.go` 里的路径注释表明 insert/stats log 的典型路径形态是 `[log_type]/collID/partID/segID/fieldID/fileName`；可把它理解为 “先 segment，再 field，再 file”。
- `milvus/internal/storage/rw.go` 已把持久化格式区分为 `StorageV1`、`StorageV2(parquet packed)`、`StorageV3(manifest)`；新版格式虽然不再总是直观表现为“一字段一旧式 binlog 文件”，但本质仍是列式组织，只是升级为 column group + packed files + manifest。
- `milvus/internal/querynodev2/segments/segment.go` 说明 QueryNode 上的 `LocalSegment` 主要持有 metadata、bloom filter、field binlog/index 信息和缓存指标；真正的查询执行态数据与索引主要在 `segcore CSegment` 中，因此“segment 在查询内存里长什么样”不能只看 Go struct 字段。
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
- 如果当前优先级是“尽快形成自己的平台接入方案”，不应该先把大量时间投入源码深潜；更高效的顺序是先产出平台初稿，再用 Milvus 架构和数据流去验证和修订。
- Milvus 架构学习在“带着平台假设去验证”时价值最高；如果没有先形成平台草图，后续阅读容易停留在组件记忆层面。
- 对当前平台目标而言，第一版更应该聚焦单一主域；当前主域应是“笔记内容问答”，订单数据先作为次级独立域接入，而不是一开始就做跨域统一召回。
- 针对笔记问答，单一向量层不足以同时解决“找哪篇笔记”和“找哪段证据”两个问题；第一版更适合采用 `标题/摘要向量 + 正文 chunk 向量` 的双层索引。
- 在“个人域 + 共享域并存”的模型下，权限过滤必须在召回阶段生效，不能依赖召回后裁剪结果。
- 当主存储先写成功、向量索引异步刷新时，平台设计必须显式建模 `note_version`、`current_indexed_version` 和索引状态，否则无法控制短暂不一致。
- 当前新的主任务不再是平台设计，而是先研究 Milvus 本身对向量场景的底层解决方式。
- 在进入任何外部系统对接讨论之前，必须先建立 Milvus 的四层心智模型：数据模型、存储组织、索引承载、查询/计算执行。
- 当前阶段 RedDB 相关问题应明确冻结，直到具备足够的 RedDB 资料再单独展开。
- `Phase A` 已将当前研究基线锁定在 `Milvus 2.6.x`，并以 `v2.6.7` 作为 2026-03-16 的 release 快照；后续默认不再混读 `2.5.x` 或更旧文档。
- `Architecture Overview`、`Data Processing`、schema/field/JSON 文档已经足够构成当前 `Phase A/B` 的稳定入口，源码目录映射留到 Phase C/D 再做。
- 从当前文档基线看，Milvus 的逻辑对象不是“单列向量 + 松散 metadata”，而是 `collection/schema/field` 定义下的混合实体模型。
- 向量字段负责召回，scalar/JSON 字段负责过滤和解释，这是后续理解查询执行链路的最小正确模型。
- JSON 字段适合承载半结构化长尾属性，但高频过滤、权限和生命周期控制字段仍应优先显式建模为稳定 scalar field。
- `Phase C` 的稳定抽象已经形成: 写入先走 WAL/消息路径，数据经 Data Node 组织为 growing segment，flush 后进入持久化对象与 sealed 生命周期，再围绕 sealed 数据构建并加载索引。
- 当前理解下，Milvus 的对象存储承载的是数据和索引工件，元数据存储承载的是位置和状态；查询节点按需加载 growing/sealed 数据与索引参与服务。
- handoff 是当前最关键的生命周期切换点，它把“近实时可见”与“稳定高效检索”连接起来。
- 对标量/倒排类索引和主键辅助结构的最细粒度表示，当前仍不应假装已经确定；在没有源码证据前，只能先锁定到 segment 生命周期级别的抽象。
- 用户已明确新的学习输出形式：严格按 7 个主题推进，分别是“相关概念、整体架构、数据写入流程、数据组织格式、索引组织方式、查询架构、查询流程串联”。
- 用户明确要求每讲完一个主题，都要产出对应文档，避免知识只停留在会话上下文里。
- 用户明确要求每个主题讲完原理后，直接给出本地源码目录、关键文件和建议阅读顺序。
- 本地 Milvus 源码树已确认位于 `/Projects/work/vectordbpreview/milvus`，关键目录包括 `internal/proxy`、`internal/datanode`、`internal/datacoord`、`internal/querynodev2`、`internal/querycoordv2`、`internal/rootcoord`、`internal/storage`、`pkg/proto`。
- Theme 1 已经确定了 Milvus 的最小概念集合：vector、embedding、similarity/distance、ANN、collection、schema/field、segment、growing/sealed、WAL、flush、handoff、compaction、shard/channel、index、query plan。
- Theme 1 的源码入口应遵循“client/entity -> pkg/proto -> internal/metastore/model -> internal/querynodev2/segments 与 parser”这条顺序，而不是一开始就直接跳进执行细节。
- `milvus/client/entity/schema.go`、`milvus/client/entity/collection.go`、`milvus/client/index/common.go` 适合作为概念层第一入口，因为它们最直接暴露了 collection、schema、field、index 的外部建模方式。
- `milvus/internal/metastore/model/collection.go`、`segment.go`、`index.go` 是把对外概念映射到系统内部 metadata 模型的关键过渡层。
- `milvus/pkg/proto/planpb/plan.pb.go` 和 `milvus/internal/querynodev2/segments/manager.go` 说明 query plan 和 segment 并不是抽象名词，而是执行侧的正式结构。
- Theme 2 已形成稳定架构分层：Access Layer（Proxy）、Coordinator Layer（RootCoord/DataCoord/QueryCoord/StreamingCoord/MixCoord）、Worker Layer（QueryNode/DataNode/StreamingNode）、Storage Layer（WAL/Object Storage/Meta Store）。
- `milvus/cmd/roles/roles.go` 是理解当前版本角色组合方式的总入口；它比单看官方组件图更贴近本地源码的真实启动结构。
- `milvus/cmd/components/*.go` 负责把角色名映射到具体 server 实现，适合作为从系统总图进入具体组件的过渡层。
- `milvus/internal/rootcoord/root_coord.go`、`milvus/internal/datacoord/server.go`、`milvus/internal/querycoordv2/server.go` 分别对应元数据根协调、数据生命周期协调、查询分布协调三类核心控制平面。
- `milvus/internal/querynodev2/server.go`、`milvus/internal/datanode/services.go`、`milvus/internal/streamingnode/server/server.go` 对应真正的执行平面与流式路径工作节点。
- Theme 3 已经把写路径固定为 `Proxy 预处理 -> channel 拆分与 repack -> WAL/streaming append -> DataNode flowgraph -> sync/flush -> DataCoord 生命周期协调`。
- `milvus/internal/proxy/task_insert.go` 说明 Proxy 在写路径上首先做的是 schema 校验、row ID/timestamp 分配和字段检查，而不是最终持久化。
- `milvus/internal/proxy/task_insert_streaming.go` 表明当前写入路径会把 repacked messages append 到 streaming WAL，而不是直接把最终 segment 文件写到对象存储。
- `milvus/internal/flushcommon/pipeline/data_sync_service.go` 是理解 DataNode 写路径运行时的关键文件，因为它把 vchannel、flowgraph、metacache、syncMgr、chunkManager 串在了一起。
- `milvus/internal/datacoord/segment_manager.go` 说明 growing segment 的分配、seal、flushable 判断是全局生命周期问题，由 DataCoord 协调，而不是 DataNode 单独决定。
- Theme 4 已固定数据组织主线：逻辑上以 `collection/schema/field` 建模，运行时以 `FieldID -> FieldData` 的列式结构组织向量、标量和 JSON 数据。
- `milvus/client/entity/field.go` 说明 field 不只是名称和类型，还包含 `PrimaryKey`、`AutoID`、`TypeParams`、`IndexParams`、`IsDynamic`、`IsPartitionKey`、`IsClusteringKey`、`Nullable` 等系统语义。
- `milvus/client/row/schema.go` 和 `milvus/client/row/data.go` 表明 client 侧虽然接收 row-oriented 输入，但会在发送前重排为按列组织的数据；schema 外字段在启用 dynamic field 时会被打包成 JSON 列。
- `milvus/internal/rootcoord/create_collection_task.go` 表明 dynamic field 的真实落地方式是在 schema 中追加一列 `IsDynamic=true` 的 JSON 字段，而不是取消 schema。
- `milvus/client/column/json.go` 和 `milvus/internal/datanode/importv2/util.go` 共同说明 dynamic field 在写入和导入链路上都被当作真实 JSON 列处理；缺失时会补齐 `{}`。
- `milvus/internal/storage/insert_data.go` 说明运行时字段数据通过 `InsertData.Data map[FieldID]FieldData` 组织，不同数据类型分别落到 `FloatVectorFieldData`、`JSONFieldData`、各类 scalar field data 等具体实现。
- `milvus/internal/metastore/model/field.go` 与 `milvus/internal/metastore/model/collection.go` 说明 schema 进入 metastore 后，`IsDynamic`、`IsPartitionKey`、`StructArrayFields`、`EnableDynamicField`、channel 信息等关键语义仍会保留。
- `milvus/internal/querycoordv2/meta/collection_manager.go` 与 `milvus/internal/querynodev2/segments/collection.go` 说明 QueryCoord 和 QueryNode 会继续持有并更新 `CollectionSchema`，schema 是贯穿 client、control plane、query runtime 的长生命周期对象。
- Theme 5 已固定索引组织主线：索引先定义在 field 上，但真正可服务的是 segment 级工件；`Index` 表达 field 级索引意图，`SegmentIndex` 表达某 segment 上的具体构建结果。
- `milvus/internal/metastore/model/segment_index.go` 说明 segment 索引元数据会显式记录 `SegmentID`、`IndexID`、`BuildID`、`IndexFileKeys`、`IndexState`、`CurrentIndexVersion`、`CurrentScalarIndexVersion`，这直接证明索引服务单元是 segment，而不是 collection 全局单体。
- `milvus/internal/datacoord/index_service.go`、`task_index.go` 与 `milvus/internal/datanode/index/task_index.go` 共同说明向量/标量显式索引采用“DataCoord 异步派发 segment 级任务 -> DataNode 实际构建 -> index files 持久化”的链路。
- `milvus/internal/storage/index_data_codec.go` 说明索引文件在存储层会带上 `collectionID`、`partitionID`、`segmentID`、`fieldID`、`indexID` 等标识，索引工件在编码层也是 segment 级对象。
- `milvus/internal/datanode/index/task_stats.go` 与 `milvus/internal/querynodev2/segments/segment_loader.go` 说明 JSON key stats、text/BM25 一类 sidecar 工件虽然不是传统 ANN index file，但同样按 field/segment 生成并由查询侧单独加载。
- `milvus/internal/storage/pk_statistics.go`、`stats.go`、`milvus/internal/querynodev2/pkoracle/pk_oracle.go`、`bloom_filter_set.go` 说明主键辅助结构的核心是 min/max + bloom filter + segment candidate pruning；它们不是 ANN 索引，但同样依附于 segment 生命周期并参与查询/删除定位。
- `milvus/internal/querycoordv2/checkers/index_checker.go` 与 `milvus/internal/querynodev2/segments/index_attr_cache.go` 说明 QueryCoord/QueryNode 不只是“有没有索引”二元判断，还会根据 segment 缺失索引、JSON key stats 和不同 index type 的资源模型来决定 reopen/load 行为。
- Theme 6 已固定查询架构主线：Proxy 是入口编排层，QueryCoord 是查询控制平面，QueryNode 是实际执行平面；RootCoord/DataCoord/StreamingNode/DataNode 为查询提供 schema、segment 事实、新鲜度和工件供给，但不是最终 query executor。
- `milvus/internal/proxy/task_search.go` 与 `task_query.go` 说明 Proxy 的核心职责是拿 schema/meta、校验请求、生成计划相关结构、翻译输出字段并按 shard/channel 组织内部请求，而不是直接持有 segment 执行查询。
- `milvus/internal/querycoordv2/server.go`、`meta/target_manager.go`、`meta/dist_manager.go` 说明 QueryCoord 内部同时维护 target 视图和 distribution 视图：前者回答“应该服务什么”，后者回答“现在分布在哪里”。
- `milvus/internal/querycoordv2/meta/coordinator_broker.go` 说明 QueryCoord 要依赖 broker 从上游协调层拿 `DescribeCollection`、`GetRecoveryInfoV2`、`GetSegmentInfo`、`GetIndexInfo` 等事实来源，这些信息不是 QueryNode 自己推断出来的。
- `milvus/internal/querynodev2/server.go`、`segments/manager.go`、`delegator/delegator.go` 说明 QueryNode 的执行面由 `segments.Manager + Loader + Scheduler + ShardDelegator` 共同组成；delegator 是按 shard/channel 组织查询视图和执行的关键层。
- `milvus/internal/rootcoord/broker.go` 说明 RootCoord 在查询侧更偏向 schema/channel watch 和 release/index-drop 等控制面协作，而不是执行 search/query。
- `milvus/internal/streamingnode/server/server.go` 与 `milvus/internal/datanode/services.go` 说明 StreamingNode/DataNode 在查询架构中的角色分别更偏向 WAL/streaming 新鲜度基础设施和数据/索引工件生产，而不是查询执行现场。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 用 Milvus Lite 或最小本地 Milvus 做第一个小项目 | 能在 1-2 小时内跑通完整链路，优先获得感性认识 |
| 小项目先做文本语义检索，不先做图片或多模态 | 数据准备最简单，便于把注意力放在向量检索流程本身 |
| 把学习成果拆成四类输出：概念卡片、场景矩阵、平台接入草图、Milvus 模块图 | 这样既能帮助记忆，也能直接服务后续平台集成 |
| Milvus 深潜从官方文档入口开始，再映射到 GitHub 源码目录 | 先建立组件边界，再读代码实现，成本更低 |
| Phase 3 Demo 采用 `Python + Milvus Lite + 本地中文样本数据` | 在真实向量数据库体验和最小环境成本之间取得平衡 |
| Phase 3 同时保留 `keyword search` 与 `vector search` 两条路径 | 方便直接对比词面匹配与语义检索的差异 |
| Phase 3 样本记录最少包含 `id/text/category/source` | 既能做向量检索，也能展示 metadata filter |
| Phase 3 最终使用本地轻量 embedder，而不是下载式大模型 embedding | 当前开发环境中 `sentence-transformers` 依赖过重；先保证 Milvus Lite 检索链路可稳定运行 |
| 在当前 Codex 沙箱内运行 Milvus Lite 需要提权 | 本地 unix socket 绑定会被沙箱限制，提权后构建与查询脚本均可正常运行 |
| 后续学习顺序采用 `Phase 4A -> Phase 5 -> Phase 4B -> Phase 6` | 先尽快拿到平台接入草图，再用 Milvus 机制验证和修订，比先读透内核再设计更符合当前目标 |
| Phase 4A 主域定为 `notes RAG`，`orders` 保留独立次级域 | 当前最接近真实上线需求的是笔记问答，订单域先避免把第一版复杂度拉高 |
| 笔记域采用 `note_head_index + note_chunk_index` 双层索引 | 文档级粗召回和片段级证据定位职责不同，分层设计更利于调试、评估和后续验证 |
| 笔记索引刷新采用“主库提交后异步更新，按版本整版切换” | 符合当前实时性与稳定性的取舍，也为后续 Milvus 机制验证提供明确假设 |
| 第一版权限模型只做“个人域 + 共享域”的召回期过滤 | 先保证检索安全边界和工程可落地性，复杂 ACL 留待后续扩展 |
| 当前主线切换为 `Milvus-first` 研究 | 用户当前要求是先从 Milvus 本身入手，理解其如何组织数据、索引和执行查询，而不是继续平台或对接讨论 |
| 旧的 `notes RAG` spec 保留但冻结 | 作为背景材料保留，不再作为当前主线推进 |
| RedDB 议题明确延期 | 等获取 RedDB 资料后再单独开线，不在当前研究中提前绑定假设 |
| `Phase A` 的版本锁定采用 `Milvus 2.6.x / v2.6.7` | 用单一主版本建立稳定术语和组件心智模型，避免后续研究出现版本漂移 |
| `Phase B` 的混合数据模型以 `collection/schema/field` 为主骨架 | 这样最利于后续连接 segment 生命周期、索引承载和查询执行 |
| `Phase C` 的存储与索引图先区分“文档事实”和“工作推断” | 需要在保持推进速度的同时控制认知误差 |
| 后续学习材料改为“7 个主题，一题一文档” | 让学习路径和产出结构严格对齐，便于恢复会话和后续复习 |
| 每个主题都必须映射到本地源码树，而不是停留在官方文档抽象层 | 用户目标包含源码阅读能力，不只是概念理解 |
| Theme 1 的源码阅读顺序先从 `client/entity` 和 `client/index` 开始 | 先固定对外概念，再进入 proto、metastore 和 query runtime 更稳 |
| 概念层不急着读完整执行逻辑，先抓 `schema`、`collection`、`segment`、`index`、`plan` 五类入口 | 这样能避免一开始被 QueryNode/DataNode 的实现细节淹没 |
| Theme 2 的第一入口应是 `cmd/roles/roles.go` | 先理解角色如何被组合启动，再进入单个组件职责更稳 |
| 架构学习时先区分控制平面和执行平面 | 否则容易把 QueryCoord/DataCoord 和 QueryNode/DataNode 的职责混在一起 |
| Theme 3 的写路径阅读应先看 Proxy 的 insert task，再看 DataNode/flushcommon，最后看 DataCoord | 先固定请求如何变成消息，再理解消息如何被消费和协调 |
| flush 要按“flowgraph + sync manager + segment lifecycle”理解 | 避免把 flush 误解成单个 RPC 或单个函数调用 |
| Theme 4 的阅读顺序先从 `client/entity` 和 `client/row` 开始，再进入 `rootcoord`、`metastore`、`storage` | 先建立逻辑对象模型，再看动态字段和内部列式承载，成本最低 |
| Theme 5 的阅读顺序先区分 `Index` 和 `SegmentIndex` | 先搞清 field 级索引定义和 segment 级索引工件的边界，再读构建和加载链路不容易混乱 |
| Theme 6 的阅读顺序先看 Proxy、再看 QueryCoord、最后看 QueryNode | 先固定入口和控制面，再进执行面，能避免把“谁调度”与“谁执行”混在一起 |
| Theme 7 的热路径骨架是 `Proxy PreExecute/Execute/PostExecute -> QueryNode service entry -> shardDelegator waitTSafe/PinReadableSegments -> worker SearchSegments/QuerySegments -> QueryNode reduce -> Proxy final reduce` | 这样能把 Theme 6 的角色边界落到真实调用链上，形成从 API 到代码的完整心智模型 |
| `PlanNode` 在 Proxy 侧由 `planparserv2` 编译完成，QueryNode 消费的是内部计划而不是原始 DSL/expr | 这是“用户请求语义”与“执行层”之间的关键边界 |
| QueryCoord 通常不在每次 search/query 的同步 RPC 栈里，但它提前维护的 target/distribution/leader 视图是热路径成立的前提 | 这样才能正确理解 QueryCoord 是控制面而不是中央执行器 |
| QueryNode 的 `Search/Query` 和 `SearchSegments/QuerySegments` 是两层入口：前者面向 shard/channel 级请求，后者面向 worker/segment 子任务 | 这解释了为什么 QueryNode 内部既有 channel 级 delegator，又有 segment task/scheduler |
| `waitTSafe` 解决“现在能不能读”，`PinReadableSegments` 解决“现在该读哪些 segment” | 这是理解 consistency、freshness 和 segment lifecycle 怎样进入查询热路径的最小模型 |
| 结果归并分两层：QueryNode 先把同一 shard 的 worker/segment 结果归并，Proxy 再把多个 shard/channel 结果归并为最终响应 | 不区分这两层就会误解 search/query 的 reduce 行为 |
| search 的 Proxy 收尾是 pipeline 化的，可根据 `advanced search / needRequery / functionScore / orderBy / highlighter` 动态选择 `reduce/rerank/requery/organize/highlight/order_by` 组合 | 这解释了为什么 search 的后处理明显比 query 更复杂 |
| query 的 Proxy 收尾更接近 retrieve reducer：它重点处理 aggregate/group by/output shaping，而不是 search 风格的 rerank/requery 链 | 这样能把 search 与 query 放回统一骨架下理解差异 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Milvus 文档版本之间存在架构表述差异 | 计划中明确要求先锁定版本，再读源码和数据流程 |

## Resources
- Milvus HNSW Deep Dive: /Projects/work/vectordbpreview/docs/milvus_hnsw_deep_dive.md
- Milvus Index Types Memory And Disk Layout: /Projects/work/vectordbpreview/docs/milvus_index_types_memory_disk.md
- Milvus Data Memory And Disk Layout: /Projects/work/vectordbpreview/docs/milvus_data_memory_disk_layout.md
- Milvus GitHub 仓库: https://github.com/milvus-io/milvus
- Milvus Releases: https://github.com/milvus-io/milvus/releases
- Milvus What's New in v2.6.x: https://milvus.io/docs/whats_new.md
- Milvus Architecture Overview: https://milvus.io/docs/zh/architecture_overview.md
- Milvus Architecture Overview (current): https://milvus.io/docs/architecture_overview.md
- Milvus Main Components: https://milvus.io/docs/zh/v2.5.x/main_components.md
- Milvus Data Processing: https://milvus.io/docs/pt/data_processing.md
- Milvus Data Processing (current): https://milvus.io/docs/data_processing.md
- Milvus Schema Explained: https://milvus.io/docs/schema.md
- Milvus Add Fields to an Existing Collection: https://milvus.io/docs/add-fields-to-an-existing-collection.md
- Milvus Use JSON Field: https://milvus.io/docs/use-json-fields.md
- Milvus 项目主页与 Quickstart: https://github.com/milvus-io/milvus
- Phase 1 Lesson 1 笔记: /Projects/work/vectordbpreview/phase1_vectors_basics.md
- Phase 2 Lesson 1 笔记: /Projects/work/vectordbpreview/phase2_vector_db_applications.md
- Phase 3 Design Spec: /Projects/work/vectordbpreview/docs/superpowers/specs/2026-03-15-phase3-milvus-lite-demo-design.md
- Learning Sequence Reorder Design Spec: /Projects/work/vectordbpreview/docs/superpowers/specs/2026-03-15-learning-sequence-reorder-design.md
- Phase 4A Notes RAG Design Spec: /Projects/work/vectordbpreview/docs/superpowers/specs/2026-03-16-phase4a-notes-rag-platform-design.md
- Milvus-First Research Replan Design Spec: /Projects/work/vectordbpreview/docs/superpowers/specs/2026-03-16-milvus-first-research-replan-design.md
- Phase 3 Implementation Plan: /Projects/work/vectordbpreview/docs/superpowers/plans/2026-03-15-phase3-milvus-lite-demo.md
- Learning Sequence Reorder Plan: /Projects/work/vectordbpreview/docs/superpowers/plans/2026-03-15-learning-sequence-reorder.md
- Milvus-First Research Replan: /Projects/work/vectordbpreview/docs/superpowers/plans/2026-03-16-milvus-first-research-replan.md
- Phase A Version And Terms Baseline: /Projects/work/vectordbpreview/docs/milvus_version_and_terms.md
- Phase B Mixed Data Model: /Projects/work/vectordbpreview/docs/milvus_mixed_data_model.md
- Phase C Storage And Index Map: /Projects/work/vectordbpreview/docs/milvus_storage_and_index_map.md
- Theme 1 Concepts: /Projects/work/vectordbpreview/docs/milvus_theme1_concepts.md
- Theme 2 Architecture: /Projects/work/vectordbpreview/docs/milvus_theme2_architecture.md
- Theme 3 Write Path: /Projects/work/vectordbpreview/docs/milvus_theme3_write_path.md
- Theme 4 Data Organization: /Projects/work/vectordbpreview/docs/milvus_theme4_data_organization.md
- Theme 5 Index Organization: /Projects/work/vectordbpreview/docs/milvus_theme5_index_organization.md
- Theme 6 Query Architecture: /Projects/work/vectordbpreview/docs/milvus_theme6_query_architecture.md
- Theme 7 Query Flow: /Projects/work/vectordbpreview/docs/milvus_theme7_query_flow.md
- Phase 3 Demo README: /Projects/work/vectordbpreview/phase3_demo/README.md
- Phase 3 Sample Output: /Projects/work/vectordbpreview/phase3_demo/results/sample_run.md
- Local Milvus source tree: /Projects/work/vectordbpreview/milvus

## Visual/Browser Findings
- 官方架构页显示 Milvus 当前强调访问层、协调层、工作节点、存储层四层结构。
- 官方组件页显示当前文档中常见组件包括 Proxy、Coordinator、Streaming Node、Query Node、Data Node，以及 Meta Store / Object Storage / WAL Storage。
- 官方 Data Processing 页对写入、索引、查询路径给出了非常适合作为源码阅读路线的时序说明。
