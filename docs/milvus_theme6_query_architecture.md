# Milvus Theme 6: 查询架构

## 这一题要解决什么问题
Theme 5 讲的是查询要依赖哪些 segment 级索引工件。Theme 6 要解决的是:

> 当一次 search/query 真的发生时，Milvus 的哪些组件分别负责入口编排、全局协调、目标分发、局部执行和结果归并？

这一题的重点不是把所有函数都串起来，而是先把查询侧的角色边界钉死。否则 Theme 7 一旦进入完整流程，你会很容易把:

- Proxy 和 QueryCoord 混在一起
- QueryCoord 和 QueryNode 混在一起
- RootCoord/DataCoord/StreamingNode/DataNode 的支撑作用混成“也在执行 query”

## 先给出一个总图

可以先把查询架构压缩成下面这张图:

```text
client
  -> Proxy
     -> parse / validate / compile plan / choose channels
     -> talk to MixCoord-backed brokers and shard clients
  -> QueryCoord
     -> maintain target/distribution/replica global view
     -> decide what should be loaded / reopened / updated
  -> QueryNode
     -> hold collections / segments / indexes
     -> execute search/query on local or delegated shard view
  -> supporting components
     -> RootCoord: schema / collection metadata authority
     -> DataCoord: recovery info / segment state / index state authority
     -> DataNode: data, stats, index artifacts producer
     -> StreamingNode: WAL/streaming freshness infrastructure
```

Theme 6 最重要的一句话是:

> Query architecture 不是“Proxy 把请求直接扔给 QueryNode”。中间还有一层专门维护 target、distribution、replica 和 segment 可服务视图的 QueryCoord。

## 第 1 层: Proxy 是查询入口，不是最终执行器

### Proxy 的职责
`internal/proxy/task_search.go` 和 `task_query.go` 显示，Proxy 在查询侧首先做的是:

- 获取 collection id / schema / collection info
- 解析 output fields
- 校验 partition key / partition names
- 解析表达式和搜索参数
- 生成查询计划相关结构
- 选择 shard/channel 级请求路径

所以 Proxy 的正确定位是:

> 请求编排器和协议翻译器。

它负责把“SDK 层的一次 search/query 请求”变成“Milvus 内部可以执行的任务和计划”。

### Proxy 不做什么
Proxy 不直接持有大部分 segment 数据，不是最终 ANN 执行现场，也不是全局 segment 分配者。

这从 `searchTask` / `queryTask` 的成员也能看出来:

- 它持有 schema、mixCoord client、shard client manager、lb policy
- 它会准备 request、缓存 meta、做 reduce/requery 策略
- 但它并不直接持有 segment manager

这说明 Proxy 更像前门和编排层，而不是后端执行器。

### `impl.go` 的意义
`internal/proxy/impl.go` 更适合作为 Theme 6 的“服务外壳入口”。它说明 Proxy 不只是 task 文件集合，而是一个对外 gRPC/HTTP 组件，负责:

- 对外服务接口
- meta cache 失效
- 请求接入和健康检查

因此 Theme 6 阅读时要把 `impl.go` 看成“服务壳”，把 `task_search.go` / `task_query.go` 看成“实际查询入口逻辑”。

## 第 2 层: QueryCoord 是查询控制平面

### QueryCoord 的职责
`internal/querycoordv2/server.go` 是 Theme 6 最关键的总入口之一。它的字段非常能说明问题:

- `meta`
- `dist`
- `targetMgr`
- `cluster`
- `nodeMgr`
- `jobScheduler`
- `taskScheduler`
- `checkerController`
- 多个 observer

从这些字段就能看出 QueryCoord 的角色不是“跑 query”，而是:

- 维护查询侧元数据
- 维护 segment/channel 分布视图
- 维护当前/下一目标(target)
- 管理 replicas 与 QueryNodes
- 触发 load / reopen / update 等任务

所以 QueryCoord 的正确定位是:

> 查询控制平面。

### TargetManager: 目标视图
`internal/querycoordv2/meta/target_manager.go` 非常关键。它说明 QueryCoord 内部会维护:

- `current target`
- `next target`

并能回答:

- 某 collection 当前应该服务哪些 growing segments
- 哪些 sealed segments 是当前目标
- 哪些 dm channels 应该被关注

这意味着 QueryCoord 不是只记录“集群里有什么 segment”，而是维护:

> 当前查询服务应该以什么 segment/channel 视图为准。

### DistributionManager: 现实分布视图
`internal/querycoordv2/meta/dist_manager.go` 则回答另一个问题:

- 这些 segment / channel / leader view 实际分布在哪些 QueryNodes 上

所以 target 和 distribution 是两件事:

- target 是“应该服务什么”
- distribution 是“当前实际上分布在哪里”

Theme 6 必须把这两个概念分开。

### QueryCoord 不直接做 search
虽然 QueryCoord 对查询架构至关重要，但它本身不执行 search/query 算法。它负责的是:

- 保证该加载的东西被加载
- 保证缺失索引/缺失 stats 的 segment 被 reopen/update
- 保证 replica 和 node 分布可服务

真正算 ANN / predicate / retrieve 的还是 QueryNode。

## 第 3 层: QueryNode 是真正的查询执行平面

### QueryNode 的职责
`internal/querynodev2/server.go` 里的字段已经把 QueryNode 的执行身份写得很清楚:

- `manager *segments.Manager`
- `loader segments.Loader`
- `scheduler`
- `delegators`
- `pipelineManager`
- `clusterManager`
- `chunkManager`

所以 QueryNode 的正确定位是:

> 真正持有 segment/index 并执行 search/query 的工作节点。

### segments.Manager: 本地数据与索引视图
`internal/querynodev2/segments/manager.go` 显示 QueryNode 内部会统一管理:

- collection manager
- segment manager
- loader

而 segment manager 又明确区分:

- `growing segments`
- `sealed segments`

这说明 QueryNode 不是简单“收到请求就 RPC 下发”，而是本地拥有一份完整的可查询 segment 视图。

### Loader: 把存储层工件变成运行时对象
结合 Theme 5 的 `segment_loader.go`，你可以看到 QueryNode 会负责:

- load segment data
- load delta logs
- load index
- load bloom filter set
- load bm25/json stats

所以 QueryNode 是“把对象存储和元数据存储中的工件加载到执行现场”的组件。

### Scheduler: 真实执行的调度器
`server.go` 里的 `scheduler` 字段说明 QueryNode 不是直接在 gRPC handler 里同步暴力执行，而是有自己的查询调度层。

这意味着 QueryNode 在架构上还承担:

- 控制并发
- 控制资源占用
- 组织本地 query/search 执行任务

## 第 4 层: ShardDelegator 是 QueryNode 内部的查询编排器

很多人学到 Theme 6 时会以为 QueryNode 内部就是“segment manager + 执行器”。其实还不够。

### delegator 的职责
`internal/querynodev2/delegator/delegator.go` 里 `ShardDelegator` 的接口非常说明问题。它能做:

- `Search`
- `Query`
- `GetStatistics`
- `SyncDistribution`
- `LoadGrowing`
- `LoadSegments`
- `ReleaseSegments`
- `ProcessInsert`
- `ProcessDelete`
- `SyncTargetVersion`
- `UpdateSchema`

这说明 delegator 不是纯辅助类，而是 QueryNode 内部围绕 shard/channel 组织查询视图和执行的核心对象。

### 为什么需要 delegator
因为 QueryNode 不是只查自己本地一个 segment 列表。它要面对的是:

- growing + sealed 并存
- channel/shard 维度的数据组织
- delete buffer 和 streaming 数据
- local segments 与集群分布状态的结合

所以你可以把 delegator 理解成:

> QueryNode 内部按 shard 组织查询执行和数据视图的一层。

它连接了:

- QueryCoord 下发的分布/目标变化
- QueryNode 本地的 segment/index/runtime
- 实际 search/query 接口

## 第 5 层: RootCoord 和 DataCoord 在查询侧是“支撑控制面”，不是执行面

Theme 6 很重要的一点，是把它们在查询架构中的角色说准确。

### RootCoord 的角色
RootCoord 不是 search executor，但它仍然和查询架构相关，因为它是 collection/schema 的权威来源之一。

`internal/rootcoord/broker.go` 表明 RootCoord 会通过 broker 和 mixCoord 协作完成:

- release collection / partitions
- watch channels
- get query segment info
- drop collection index

因此在查询侧，RootCoord 更像:

- collection / schema / channel watch 的控制面上游
- DDL 变化和查询侧视图同步的源头

### DataCoord 的角色
虽然 Theme 6 重点不在 DataCoord，但 QueryCoord 依赖它提供恢复和 segment 视图。

`internal/querycoordv2/meta/coordinator_broker.go` 很关键。它说明 QueryCoord 会通过 broker 拿到:

- `DescribeCollection`
- `GetRecoveryInfo`
- `GetRecoveryInfoV2`
- `GetSegmentInfo`
- `GetIndexInfo`

这些能力背后对应的并不是 QueryNode 自己推断，而是从协调层上游拿正式元数据和恢复信息。

所以 DataCoord 在查询架构里的角色是:

> 提供 segment/index/recovery 相关事实来源，帮助 QueryCoord 形成 target 和 distribution 的正确视图。

### 它们为什么不算查询执行器
因为它们回答的是:

- 应该查什么
- 数据在哪里
- schema 是什么
- 哪些 segment/index 已经可服务

而不是亲自做:

- ANN
- predicate evaluation
- result reduce

## 第 6 层: StreamingNode 和 DataNode 在查询侧属于“新鲜度与工件供给层”

### StreamingNode
`internal/streamingnode/server/server.go` 显示 StreamingNode 的核心是:

- `walManager`
- handler service
- manager service

它本质上服务于 WAL/streaming 路径和流式分发，不是查询执行节点。

但在查询架构里它仍然重要，因为它影响:

- 近实时写入如何进入可见路径
- shard/channel 级流式状态怎样被维护

因此 StreamingNode 在查询侧更像:

> 新鲜度基础设施，而不是 query executor。

### DataNode
`internal/datanode/services.go` 明确写出 DataNode 的主职责是:

- 持久化 insert logs
- compaction
- import
- index/stats task worker

这说明 DataNode 也不是查询执行器。

但它在查询架构里提供的是:

- insert/delta/stats/index 工件
- compaction 后的新 segment 结果
- JSON/text/BM25/pk stats 等 sidecar 产物

这些东西最终都会被 QueryNode 加载，用于服务查询。

所以 DataNode 在查询侧的正确定位是:

> 查询所依赖的数据与索引工件生产者。

## 第 7 层: MixCoord / broker 让查询控制面拿到跨组件事实

在当前源码里，不能只看 `Proxy -> QueryCoord -> QueryNode` 这条直线。

`internal/querycoordv2/meta/coordinator_broker.go` 和 `internal/rootcoord/broker.go` 都表明:

- QueryCoord / RootCoord 经常通过 `mixCoord` 拿到跨组件能力
- broker 是查询控制面向上游协调层要“事实”的统一通道

这在 Theme 6 里很重要，因为它说明:

> 查询架构中的“控制面信息”不是从单一模块里长出来的，而是通过 broker 从多个协调组件汇总而来。

## Theme 6 的正确心智模型

把上面压缩一下，可以得到 5 句最关键的话:

### 1. Proxy 是入口编排层
- 校验、翻译、计划化、按 shard/channel 下发

### 2. QueryCoord 是查询控制平面
- 维护 target、distribution、replica、load/reopen/update 任务

### 3. QueryNode 是查询执行平面
- 持有 collection/segment/index/runtime，真正执行 search/query

### 4. Delegator 是 QueryNode 内部按 shard 组织查询视图和执行的核心层

### 5. RootCoord、DataCoord、StreamingNode、DataNode 为查询提供 schema、segment/recovery 事实、新鲜度机制和数据/索引工件，但不是最终 query executor

## Theme 6 的源码目录

### 查询入口与请求编排
- `milvus/internal/proxy`

### 查询控制平面
- `milvus/internal/querycoordv2`
- `milvus/internal/querycoordv2/meta`
- `milvus/internal/querycoordv2/checkers`
- `milvus/internal/querycoordv2/task`

### 查询执行平面
- `milvus/internal/querynodev2`
- `milvus/internal/querynodev2/segments`
- `milvus/internal/querynodev2/delegator`
- `milvus/internal/querynodev2/pipeline`

### 查询侧依赖的上游协调与支撑组件
- `milvus/internal/rootcoord`
- `milvus/internal/datacoord`
- `milvus/internal/streamingnode`
- `milvus/internal/streamingcoord`
- `milvus/internal/datanode`

## Theme 6 的关键文件

### Proxy 入口
- `milvus/internal/proxy/impl.go`
- `milvus/internal/proxy/task_search.go`
- `milvus/internal/proxy/task_query.go`

这三份文件回答:

- 查询请求如何进入系统
- Proxy 做哪些前置编排和校验

### QueryCoord 总入口与全局视图
- `milvus/internal/querycoordv2/server.go`
- `milvus/internal/querycoordv2/meta/target_manager.go`
- `milvus/internal/querycoordv2/meta/dist_manager.go`
- `milvus/internal/querycoordv2/checkers/index_checker.go`

这几份文件回答:

- QueryCoord 持有哪些全局状态
- target 和 distribution 怎么区分
- 为什么 QueryCoord 会触发 reopen / index update

### QueryNode 执行入口
- `milvus/internal/querynodev2/server.go`
- `milvus/internal/querynodev2/segments/manager.go`
- `milvus/internal/querynodev2/delegator/delegator.go`

这几份文件回答:

- QueryNode 内部有哪些执行组件
- segment 如何被管理
- shard delegator 如何组织执行

### 查询侧依赖的 broker / 上游协调接口
- `milvus/internal/querycoordv2/meta/coordinator_broker.go`
- `milvus/internal/rootcoord/broker.go`

这两份文件回答:

- QueryCoord / RootCoord 如何向上游协调层获取 schema、recovery info、segment info、index info

### 新鲜度与工件供给层
- `milvus/internal/streamingnode/server/server.go`
- `milvus/internal/datanode/services.go`

这两份文件回答:

- StreamingNode 为什么更偏 WAL/streaming 基础设施
- DataNode 为什么更偏数据/索引工件生产，而不是执行查询

## 建议阅读顺序

### 第 1 轮: 先看查询入口
1. `milvus/internal/proxy/impl.go`
2. `milvus/internal/proxy/task_search.go`
3. `milvus/internal/proxy/task_query.go`

这一轮的目标是先固定 Proxy 的职责边界。

### 第 2 轮: 再看 QueryCoord 的全局控制面
1. `milvus/internal/querycoordv2/server.go`
2. `milvus/internal/querycoordv2/meta/target_manager.go`
3. `milvus/internal/querycoordv2/meta/dist_manager.go`
4. `milvus/internal/querycoordv2/meta/coordinator_broker.go`

这一轮的目标是搞清 current target、next target、distribution 和 broker 这些关键词。

### 第 3 轮: 看 QueryNode 的执行面
1. `milvus/internal/querynodev2/server.go`
2. `milvus/internal/querynodev2/segments/manager.go`
3. `milvus/internal/querynodev2/delegator/delegator.go`

这一轮的目标是知道 QueryNode 内部怎样把 collection/segment/shard 组织成可执行的查询现场。

### 第 4 轮: 最后补齐查询侧的支撑组件
1. `milvus/internal/rootcoord/broker.go`
2. `milvus/internal/streamingnode/server/server.go`
3. `milvus/internal/datanode/services.go`

这一轮的目标是把“谁不是 query executor，但为什么仍然对查询架构重要”这件事看清楚。

## 这一题学完后你应该能回答

1. Proxy、QueryCoord、QueryNode 三者在查询架构中的职责边界分别是什么？
2. target 和 distribution 有什么本质区别？
3. 为什么 QueryNode 里还需要 delegator，而不是只靠 segment manager？
4. RootCoord、DataCoord、StreamingNode、DataNode 为什么和查询架构有关，但又不能被叫做查询执行器？
