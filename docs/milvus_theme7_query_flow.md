# Milvus Theme 7: 查询流程串联

## 这一题要解决什么问题
Theme 6 讲的是查询侧各个角色的职责边界。Theme 7 要解决的是:

> 一次 `search` / `query` 真正发生时，Milvus 是怎样把请求从 Proxy 一路推进到 QueryNode，再把多个 shard 的局部结果归并成最终结果的？

这一题不是再讲“谁负责什么”，而是讲:

- 请求是怎样被编译成可执行 plan 的
- 请求是怎样按 shard/channel 被发到 QueryNode 的
- QueryNode 是怎样等到可读时间点、拿到可读 segment 视图并组织执行的
- worker 级 segment 执行结果又是怎样在 QueryNode 和 Proxy 两层被归并的

如果 Theme 7 没有串起来，你虽然知道:

- Proxy 是入口
- QueryCoord 是控制面
- QueryNode 是执行面

但你还是很难回答下面这些真正重要的问题:

- `guarantee timestamp` 到底在哪里生效？
- `plan` 是谁生成的？谁消费的？
- 为什么 QueryNode 既有 `Search/Query`，又有 `SearchSegments/QuerySegments`？
- 为什么 search 的收尾比 query 更复杂？

## 先给出一条总链路

可以先把 search/query 的主流程压缩成下面这张图:

```text
client
  -> Proxy PreExecute
     -> resolve collection/schema/meta
     -> validate request / partition / output fields
     -> build PlanNode via planparserv2
     -> resolve consistency / guarantee timestamp / mvcc context
  -> Proxy Execute
     -> lb.Execute(...)
     -> dispatch one request per shard/channel
  -> QueryNode Search/Query
     -> narrow to one channel
     -> hand off to shard delegator
  -> shardDelegator
     -> waitTSafe(guarantee ts)
     -> PinReadableSegments(...)
     -> split sealed/growing
     -> prune / organize subtasks
     -> execute worker SearchSegments / QuerySegments
  -> QueryNode leader reduce
     -> merge worker-local results for this shard/channel
  -> Proxy PostExecute
     -> collect all shard results
     -> search: reduce / rerank / requery / organize / highlight / order_by
     -> query: reduce retrieve results
  -> final response
```

Theme 7 最关键的一句话是:

> Milvus 的查询热路径，不是“Proxy 直接查 QueryNode 的某个全局大索引”，而是“Proxy 编译计划并按 shard 分发，QueryNode 再在当前可读 segment 视图上组织局部执行，最后两层归并结果”。

## 第 1 层: Proxy PreExecute 把用户请求变成内部查询任务

### Search 的 PreExecute 在做什么
`milvus/internal/proxy/task_search.go` 的 `PreExecute` 是 search 热路径的第一个核心入口。

它会先做这些事情:

- 解析 collection name，拿到 collection id
- 从 `globalMetaCache` 取 schema 和 collection info
- 校验 partition key mode、partition names、namespace、output fields
- 解析 `nq`、`ignoreGrowing`
- 计算 output field ids
- 调用 `initSearchRequest`

而 `initSearchRequest` 又会继续做:

- 调用 `tryGeneratePlan`
- 由 `planparserv2.CreateSearchPlanArgs(...)` 生成 `PlanNode`
- 解析 `queryInfo/topK/metricType/groupBy`
- 序列化 `SerializedExprPlan`
- 处理 placeholder vector 的类型转换
- 判断 `needRequery`

这里最重要的点有两个:

### 1. search 的 plan 在 Proxy 就已经编译好了
`tryGeneratePlan` 会选定 ANN field，然后调用:

- `planparserv2.CreateSearchPlanArgs`

这说明 QueryNode 并不是收到 DSL/expr 后再“现场理解业务语义”，而是直接消费 Proxy 已编译好的计划。

### 2. search 在入口阶段就决定后处理复杂度
`initSearchRequest` 会决定:

- 是否是 advanced search
- 是否要 `requery`
- 是否有 `functionScore`
- 是否有 `order_by`
- 是否需要 highlighter

这几个标志会直接决定 `PostExecute` 走哪条 pipeline。

### Query 的 PreExecute 在做什么
`milvus/internal/proxy/task_query.go` 的 `PreExecute` 是 retrieve/query 热路径的入口。

它和 search 一样会先做:

- collection/schema/meta 解析
- partition 与 namespace 校验
- `ignoreGrowing`、`limit/offset/groupBy` 等 query param 解析

但 query 更强调:

- `createPlanArgs`
- output fields / aggregates / group by 解析
- consistency / guarantee timestamp / mvcc timestamp 计算
- collection TTL / timeout timestamp 计算

`createPlanArgs` 会调用:

- `planparserv2.CreateRetrievePlanArgs(...)`

然后把:

- `Aggregates`
- `GroupByFieldIds`
- `OutputFieldsId`
- `DynamicFields`

写回到 `PlanNode` 和 `RetrieveRequest`。

### Search 和 Query 在入口阶段的本质区别
可以把两者的差异压缩成一句话:

- search 的核心是“ANN + filter + 后续可能 rerank/requery”
- query 的核心是“predicate retrieve + output shaping + reduce”

所以 search 的入口重点在:

- 选 ANN field
- 构建 `QueryInfo`
- 决定后处理 pipeline

而 query 的入口重点在:

- 构建 retrieve predicates
- 解析 aggregates/group by/output fields
- 决定最终 retrieve reducer 的行为

## 第 2 层: plan parser 把表达式编译成 PlanNode

Theme 7 一定要把 `plan parser` 单独拎出来，因为这是“概念到执行”的第一道边界。

### Retrieve plan
`milvus/internal/parser/planparserv2/plan_parser_v2.go` 的 `CreateRetrievePlanArgs` 会:

- 解析 expr
- 生成 `planpb.PlanNode`
- 把谓词写进 `QueryPlanNode.Predicates`
- 带上 `PlanOptions.ExprUseJsonStats`

这说明 query 并不是把字符串表达式直接扔到底层执行器，而是先变成标准的内部计划结构。

### Search plan
同一文件里的 `CreateSearchPlanArgs` 会在 retrieve plan 的基础上再绑定:

- vector field
- query field id
- vector type
- ANN query info

这意味着 search plan 本质上是:

> `predicate plan + vector search info`

所以 QueryNode 执行 search 时，拿到的不是“一个原始 DSL 字符串”，而是已经包含过滤条件和 ANN 参数的内部查询计划。

## 第 3 层: Proxy Execute 按 shard/channel 把任务发出去

### Search Execute
`task_search.go` 里的 `Execute` 会调用:

- `t.lb.Execute(...)`

并把:

- `CollectionID`
- `CollectionName`
- `Nq`
- `Exec: t.searchShard`

交给负载均衡与 shard client 层。

### Query Execute
`task_query.go` 里的 `Execute` 同样调用:

- `t.lb.Execute(...)`

并把:

- `Exec: t.queryShard`

作为 shard 级执行函数。

这一层的正确理解是:

> Proxy 不自己遍历 segment，它只负责把已经编译好的内部请求，按 shard/channel 路由到对应的 QueryNode shard leader。

### `searchShard` / `queryShard` 实际做什么
这两个函数都很像，核心动作是:

- clone 一份内部 request
- 设置 `TargetID = nodeID`
- 把请求收缩为“单 node + 单 channel”
- 调用 `qn.Search(...)` 或 `qn.Query(...)`
- 把返回的局部结果放进 `resultBuf`
- 更新 LB 的 cost metrics

如果遇到:

- RPC error
- `NotShardLeader`

它们会废弃 shard cache，让后续请求重新发现正确 leader。

这说明 Proxy 的分发是:

- 按 shard/channel 粒度
- 面向 QueryNode leader
- 具备 leader 失效恢复能力

## 第 4 层: QueryCoord 不在热 RPC 里，但它决定这条链能不能成立

Theme 6 已经讲过 QueryCoord 是控制平面。Theme 7 只需要把它放回动态链路里的正确位置:

> QueryCoord 通常不出现在每次 `Search` / `Query` 的同步 RPC 栈里，但 Proxy 的 shard 路由、QueryNode 的 segment 可读分布和 target 视图，都建立在它提前维护好的控制面状态之上。

换句话说，Theme 7 的热路径之所以能成立，前提是 QueryCoord 已经在后台完成了:

- target 维护
- distribution 维护
- shard leader / replica 组织
- segment load/reopen/update

所以 Theme 7 不该把 QueryCoord 画成“每个请求都在中央亲自调度”，更准确的说法是:

> QueryCoord 让系统提前变成一个“可服务的查询现场”，然后热路径只在这个现场里执行。

## 第 5 层: QueryNode service 入口先把请求收缩到单 channel

### Search 入口
`milvus/internal/querynodev2/services.go` 里的 `Search` 会检查:

- collection 是否已加载
- `DmlChannels` 数量是否正好为 1

然后把请求收缩为一个 channel request，调用:

- `node.searchChannel(ctx, channelReq, ch)`

### Query 入口
同一文件里的 `Query` 也会:

- 检查 collection 是否可用
- 保证一次请求只落到一个 channel
- 调用 `node.queryChannel(ctx, req, ch)`

### 为什么要求一个请求只对应一个 channel
因为 QueryNode 内部真正的执行组织单位不是“整个 collection”，而是:

> channel 对应的 shard 视图

这也是为什么 `delegators` 的 key 是 channel/shard，而不是 collection id。

## 第 6 层: shardDelegator 才是 QueryNode 内部真正的查询编排器

Theme 7 的核心，实际上就在 `milvus/internal/querynodev2/delegator/delegator.go`。

### Search 的 delegator 主流程
`ShardDelegator.Search` 做的事可以概括成:

1. 校验请求 channel 是否属于当前 delegator
2. 根据 consistency / iterator 等条件修正 `GuaranteeTimestamp`
3. `waitTSafe(...)`，等待本 shard 到达可读时间点
4. 设置或修正 `MvccTimestamp`
5. `distribution.PinReadableSegments(...)`
6. 拿到当前版本下的:
   - sealed segments
   - growing segments
   - sealed row count
   - distribution version
7. 根据配置决定是否 segment prune
8. `organizeSubTask(...)`
9. `executeSubTasks(...)`
10. 调 worker 执行 `SearchSegments`

其中最关键的三步是:

### 1. `waitTSafe` 决定“现在能不能读”
`waitTSafe` 不是一个普通等待动作，它实际上是把:

- consistency level
- guarantee timestamp
- streaming freshness

真正落到 shard 读取边界上的地方。

所以很多人说“Milvus 支持一致性级别”，真正的生效点并不是文档说明，而是这里。

### 2. `PinReadableSegments` 决定“现在该读哪些 segment”
`distribution.PinReadableSegments(...)` 返回的不是抽象概念，而是当前这个 shard 真正可读的:

- sealed
- growing

segment 集合，以及对应的版本号。

这一步把 Theme 6 里的 `target/distribution` 心智模型，真正转成了 Theme 7 里的执行输入。

### 3. `organizeSubTask` / `executeSubTasks` 决定“怎么并发执行”
有了 sealed/growing 之后，delegator 不会直接在一个大循环里把所有 segment 查完，而是会:

- 按 worker / segment 范围组织 subtasks
- 再用 `executeSubTasks` 分发给 worker

所以 delegator 的本质不是“再包一层函数”，而是:

> 把 shard 的可读视图变成一组可调度、可并发执行的 segment 子任务。

### Query 的 delegator 主流程
`ShardDelegator.Query` 和 search 很像，也会做:

- `waitTSafe`
- `PinReadableSegments`
- `IgnoreGrowing` 处理
- 可选 segment prune
- `organizeSubTask`
- `executeSubTasks`

差异在于执行函数变成:

- `worker.QuerySegments(...)`

因此可以说:

> Query 和 Search 在 QueryNode 内部共享同一套“按 shard 取可读 segment 视图并组织 subtasks”的骨架，只是在最终 segment 级执行算子上分叉。

## 第 7 层: worker 级 `SearchSegments/QuerySegments` 才真正落到 segment 任务

### SearchSegments
`milvus/internal/querynodev2/services.go` 里的 `SearchSegments` 是 worker 侧的 segment 执行入口。

它会:

- 校验 collection 已加载
- `Collection.Ref(...)`
- 创建 `tasks.NewSearchTask(...)`
- 交给 `node.scheduler.Add(task)`
- `task.Wait()`
- 返回 `task.SearchResult()`

### QuerySegments
`QuerySegments` 的结构也一样:

- `tasks.NewQueryTask(...)`
- `node.scheduler.Add(task)`
- `task.Wait()`
- 返回 `task.Result()`

这里要建立一个非常重要的认识:

> QueryNode 的真正 segment 执行，不是在 gRPC handler 里直接跑完的，而是进入本地 scheduler 和 task 体系，由它们在节点内部统一调度。

所以 QueryNode 的执行链还可以再压缩成:

```text
QueryNode Search/Query
  -> searchChannel/queryChannel
  -> shardDelegator Search/Query
  -> worker SearchSegments/QuerySegments
  -> node.scheduler
  -> SearchTask / QueryTask
  -> segment runtime
```

## 第 8 层: QueryNode 先在本 shard 内做一次 reduce

这一步特别容易被忽略。

### Search 的 shard 内 reduce
`milvus/internal/querynodev2/handlers.go` 里的 `searchChannel` 在 delegator 返回 worker results 之后，会调用:

- `segments.ReduceSearchOnQueryNode(...)`

这说明同一个 shard/channel 内部，如果 subtasks 分发到了多个 worker 或多个 segment 子集，QueryNode 会先做一次本地归并，再把一个 shard 结果回给 Proxy。

### Query 的 shard 内 reduce
`queryChannel` 则会创建:

- `segments.CreateInternalReducer(req, collection.Schema())`

然后:

- `reducer.Reduce(ctx, results)`

把多个 worker 的 retrieve results 合并成一个 channel 级返回值。

所以 Theme 7 里必须把结果归并分成两层看:

### 第 1 次 reduce
发生在 QueryNode 内部:

- 多个 segment/worker 子任务
  -> 一个 shard/channel 结果

### 第 2 次 reduce
发生在 Proxy:

- 多个 shard/channel 结果
  -> 一个最终 client response

## 第 9 层: Proxy PostExecute 做最终归并和结果整理

### Search 的 PostExecute 是 pipeline 驱动的
`task_search.go` 的 `PostExecute` 会:

- `collectSearchResults`
- 汇总 `channelsMvcc`、`storageCost`、`relatedDataSize`
- 构造 `newSearchPipeline(t)`
- 执行 `pipeline.Run(...)`
- `fillResult`
- 回填 output fields、collection name、pk field、iterator token、highlight、timestamp 等

这说明 search 的最终收尾不是一个简单的 `reduceResults(...)` 调用，而是一条可变 pipeline。

### 为什么 search 要用 pipeline
因为 search 的后处理分支太多，至少包括:

- 普通 reduce
- hybrid search reduce
- rerank
- requery
- organize
- highlight
- order_by

`milvus/internal/proxy/search_pipeline.go` 里甚至明确写出了某些组合路径，例如:

- common search with order_by:
  - `reduce -> requery -> organize -> order_by`

以及根据:

- `IsAdvanced`
- `needRequery`
- `functionScore`
- `orderByFields`
- `highlighter`

动态选择不同 pipeline。

所以 search 的完整心智模型应该是:

> QueryNode 负责算局部 ANN / filter，Proxy 再根据结果形态决定做 reduce、rerank、requery 和最终展示层组织。

### Query 的 PostExecute 更像“最终 retrieve reduce”
`task_query.go` 的 `PostExecute` 则相对直接:

- 从 `resultBuf` 收集各 shard 的 retrieve results
- 创建 reducer
- `reducer.Reduce(toReduceResults)`
- 校验 geometry 字段
- 回填 `OutputFields`

也就是说 query 的 Proxy 收尾核心是:

> 把多个 shard 的 retrieve 结果按 query 语义合并。

它没有 search 那种 rerank/requery/highlight 主导的复杂后处理链。

## 第 10 层: Search 和 Query 应该怎样放在一条统一心智模型里

到这里，可以把两条链压成一个统一模型:

### 共同骨架
1. Proxy 解析 collection/schema/meta
2. Proxy 编译 `PlanNode`
3. Proxy 按 shard/channel 分发
4. QueryNode 收缩到单 channel
5. shardDelegator 等待 `tSafe`
6. 获取当前可读 sealed/growing segment 视图
7. 组织 subtasks
8. worker 执行 segment tasks
9. QueryNode 先做 shard 内归并
10. Proxy 再做全局归并并返回

### search 比 query 多出来的部分
- ANN field 选择
- `QueryInfo` 与 topK/metric
- rerank
- requery
- highlight
- order_by

### query 比 search 更突出的部分
- aggregate / group by
- output shaping
- retrieve reducer 语义
- limit/offset/count/group 处理

## Theme 7 的正确心智模型

把上面全部压缩一下，Theme 7 最重要的是下面 6 句话:

### 1. 请求在 Proxy 就已经从“用户 API”变成了“内部计划 + 内部请求”

### 2. 查询不是直接打给整个 collection，而是按 shard/channel 分发

### 3. QueryNode 不是拿到请求就直接查，而是先通过 delegator 等到可读时间点并固定可读 segment 视图

### 4. QueryNode 内部先把 segment 查询组织成 subtasks，再交给 worker/task/scheduler 执行

### 5. 结果归并分两层: QueryNode 先做 shard 内 reduce，Proxy 再做全局 reduce

### 6. search 的最终收尾是 pipeline 化的，query 的最终收尾是 retrieve reducer 化的

## Theme 7 的源码目录

### 查询入口与请求编排
- `milvus/internal/proxy`

### 表达式与查询计划编译
- `milvus/internal/parser/planparserv2`

### QueryNode 服务入口
- `milvus/internal/querynodev2`

### QueryNode channel/shard 级处理
- `milvus/internal/querynodev2/handlers.go`
- `milvus/internal/querynodev2/delegator`

### QueryNode 本地 segment 执行与调度
- `milvus/internal/querynodev2/segments`
- `milvus/internal/querynodev2/tasks`
- `milvus/internal/querynodev2/schedulers`

## Theme 7 的关键文件

### Proxy 入口与收尾
- `milvus/internal/proxy/task_search.go`
- `milvus/internal/proxy/task_query.go`
- `milvus/internal/proxy/search_pipeline.go`

这几份文件回答:

- Search/Query 在 Proxy 里怎样做 `PreExecute/Execute/PostExecute`
- Search 为什么要走 pipeline 化后处理

### Plan 编译
- `milvus/internal/parser/planparserv2/plan_parser_v2.go`

这份文件回答:

- expr / dsl 怎样变成 `PlanNode`
- retrieve plan 和 search plan 有什么差异

### QueryNode 对外服务入口
- `milvus/internal/querynodev2/services.go`
- `milvus/internal/querynodev2/handlers.go`

这两份文件回答:

- QueryNode 怎样接住 Proxy 发来的 Search/Query
- 为什么会先收缩到单 channel，再进入 delegator

### QueryNode 内部 shard 编排
- `milvus/internal/querynodev2/delegator/delegator.go`

这份文件回答:

- `waitTSafe`
- `PinReadableSegments`
- `organizeSubTask`
- `executeSubTasks`

也就是 Theme 7 最关键的执行骨架。

### 本地 segment 执行支撑
- `milvus/internal/querynodev2/segments/manager.go`
- `milvus/internal/querynodev2/segments/segment_loader.go`

这两份文件回答:

- QueryNode 依赖什么运行时 segment/index 视图
- 为什么 delegator 能拿到 sealed/growing 的可执行现场

## 建议阅读顺序

### 第 1 轮: 先把 Proxy 三段式看清楚
1. `milvus/internal/proxy/task_search.go`
2. `milvus/internal/proxy/task_query.go`
3. `milvus/internal/proxy/search_pipeline.go`

这一轮的目标是先固定:

- `PreExecute -> Execute -> PostExecute`
- search 和 query 在入口与收尾上的差异

### 第 2 轮: 再看 plan 是怎么生成的
1. `milvus/internal/parser/planparserv2/plan_parser_v2.go`

这一轮的目标是搞清:

- 为什么 QueryNode 消费的是内部计划，而不是原始表达式

### 第 3 轮: 看 QueryNode 的服务入口和 channel 收缩
1. `milvus/internal/querynodev2/services.go`
2. `milvus/internal/querynodev2/handlers.go`

这一轮的目标是搞清:

- 为什么 QueryNode `Search/Query` 和 `SearchSegments/QuerySegments` 是两层入口
- 为什么一个热路径请求必须先收缩到单 channel

### 第 4 轮: 最后深读 delegator
1. `milvus/internal/querynodev2/delegator/delegator.go`

这一轮的目标是搞清:

- `waitTSafe`
- `PinReadableSegments`
- subtasks 组织
- worker 执行分发

如果这一轮读懂了，Theme 7 就算真正打通了。

### 第 5 轮: 反过来补 segment runtime 依赖
1. `milvus/internal/querynodev2/segments/manager.go`
2. `milvus/internal/querynodev2/segments/segment_loader.go`

这一轮的目标是把 Theme 5、Theme 6、Theme 7 串起来:

- Theme 5 讲“索引工件怎样承载”
- Theme 6 讲“谁负责查询”
- Theme 7 讲“请求怎样在这些角色和工件之间真正流动”

## 这一题学完后你应该能回答

1. search/query 在 Proxy 里分别做了哪些 `PreExecute/Execute/PostExecute` 动作？
2. `PlanNode` 是谁生成的，谁消费的？
3. 为什么 QueryNode 既有 `Search/Query`，又有 `SearchSegments/QuerySegments`？
4. `waitTSafe` 和 `PinReadableSegments` 在查询热路径里分别解决什么问题？
5. 为什么结果归并要分成 QueryNode 和 Proxy 两层？
6. 为什么 search 的收尾是 pipeline 化的，而 query 的收尾更像 retrieve reducer？
