# Milvus Theme 2: 整体架构

## 这一题要解决什么问题
Theme 1 解决的是“Milvus 里有哪些核心名词”。Theme 2 要解决的是另一个问题:

> 这些名词在系统里是怎么被组织成一个真正运行的分布式架构的？

如果 Theme 1 记的是词汇表，Theme 2 就是在建立地图。你要开始知道:

- 请求先到哪里
- 谁负责元数据和全局协调
- 谁负责真正执行查询
- 谁负责真正处理写入
- WAL、对象存储、元数据存储在系统图里分别在哪里

## 一个先行结论
Milvus 不能被理解成“单机 ANN 库 + 一层 API”。更准确的理解是:

> Milvus 是一个分层的、存储和计算分离的向量数据库系统。访问层负责接请求，协调层负责全局元数据和调度，工作节点负责真正处理数据和查询，存储层负责 WAL、对象存储和元数据持久化。

## 架构分层

### 1. Access Layer
这一层最典型的角色是 `Proxy`。

它的职责不是“自己完成查询和写入”，而是:

- 接收客户端请求
- 做参数校验和基本编排
- 把请求转成内部任务
- 和协调层、工作节点协作
- 对结果做聚合或整理

你可以把它理解成 Milvus 的前门。

### 2. Coordinator Layer
这一层是“全局控制平面”。

主要角色包括:

- `RootCoord`
- `DataCoord`
- `QueryCoord`
- 在当前代码和部署形态里还能看到 `MixCoord`
- 与 streaming 相关的 `StreamingCoord`

它们共同解决的问题是:

- 元数据管理
- 节点会话与服务发现
- segment / channel / replica / target 的全局视图
- 调度和协调
- 把系统从“很多独立节点”组织成一个整体

### 3. Worker Layer
这一层是真正做事的运行节点。

主要角色包括:

- `DataNode`
- `QueryNode`
- `StreamingNode`

这些节点不负责整个系统的全局决策，但负责真正执行:

- 数据接收与组织
- segment 生命周期推进
- 查询与搜索
- WAL 相关处理
- 索引加载或相关运行时协作

### 4. Storage Layer
这一层不只是“磁盘”。

从当前文档和代码基线看，它至少包含三类承载:

- `WAL Storage`
- `Object Storage`
- `Meta Store`

三者的职责不同:

- WAL 负责写入顺序和异步处理入口
- Object Storage 负责持久化数据与索引工件
- Meta Store 负责 collection / segment / index / channel 等状态和位置

## 为什么要这样分层

### 原因 1: 请求入口和执行现场不是一回事
客户端把请求发给 Proxy，但真正执行查询的通常是 QueryNode，真正处理数据生命周期的是 DataNode。把这两类职责混在一起，会让系统既难扩展也难治理。

### 原因 2: 全局视图和局部执行必须分开
比如:

- “哪个 QueryNode 负责哪些 segments”
- “哪些 sealed segments 已经可以 handoff”
- “哪些 collection schema 已更新”

这些问题都需要协调层维护全局视图，而不是让每个工作节点自己猜。

### 原因 3: 持久化和计算需要分离
Milvus 当前强调 shared storage 和 storage/compute disaggregation，所以不能把它理解成“数据和索引始终固定在某个执行节点本地”。节点更多是在加载和服务，而不是独占所有持久化工件。

## 主要组件的最小职责边界

### Proxy
Proxy 是访问层入口。它接收查询、搜索、插入、DDL 等请求，然后把请求送进内部任务和下游组件。

最重要的直觉:

- Proxy 不是存储层
- Proxy 不是最终查询执行层
- Proxy 更像“请求编排与转发 + 部分前后处理”

### RootCoord
RootCoord 更偏“元数据与系统根协调者”。

从代码结构上看，它和以下事情高度相关:

- collection / database / schema 相关元数据
- time tick / tso / id 分配
- proxy watcher
- metastore

因此你可以把 RootCoord 先看成“系统根级控制面”。

### DataCoord
DataCoord 更偏“数据生命周期协调者”。

从 `internal/datacoord/server.go` 的字段就能看出来，它关心:

- segment manager
- flush
- compaction
- import
- index inspector
- DataNode session

所以 DataCoord 不等于 DataNode。它更像“数据处理流程的全局调度中心”。

### QueryCoord
QueryCoord 更偏“查询侧资源与分布协调者”。

从 `internal/querycoordv2/server.go` 可以看到，它关心:

- target manager
- distribution manager
- replicas
- resource observer
- task scheduler
- QueryNode session

所以 QueryCoord 的重点不是“自己跑 query”，而是“决定查询侧应该怎么组织和分发”。

### QueryNode
QueryNode 是查询工作节点。

从 `internal/querynodev2/server.go` 看，它内部直接组合了:

- `segments.Manager`
- `delegator`
- `pipeline`
- `scheduler`
- `chunkManager`

这说明 QueryNode 是真正靠近 query/search 执行现场的地方。

### DataNode
DataNode 是写路径与数据处理工作节点。

在 Theme 2 里先记住它的边界:

- 更接近写入、segment 生命周期和数据组织
- 和 DataCoord 协同，而不是取代 DataCoord

写入主流程会在 Theme 3 详细展开。

### StreamingNode / StreamingCoord
这一组组件和 WAL / streaming 路径强相关。

从 `internal/streamingnode/server/server.go` 可以看到，StreamingNode 内部直接初始化:

- `walManager`
- handler service
- manager service

所以它不是普通“附属服务”，而是当前架构里写入与流式路径的重要组成部分。

### MixCoord
在当前源码中还能看到 `MixCoord`，它反映了当前版本/部署形态里“多种 coordinator 组合运行”的方式。你在阅读时要把它理解为当前代码树里的实际启动组织方式，而不是简单套用旧文档里的单独组件图。

## Theme 2 的源码目录怎么对应架构分层

### 启动与角色组合层
- `milvus/cmd/roles`
- `milvus/cmd/components`

这一层回答的是:

- 哪些角色会被启动
- 这些角色如何被组合
- 组件生命周期如何统一管理

### 分布式服务包装层
- `milvus/internal/distributed/proxy`
- `milvus/internal/distributed/querynode`
- `milvus/internal/distributed/datanode`
- `milvus/internal/distributed/mixcoord`
- `milvus/internal/distributed/streamingnode`

这一层更像“服务封装与对外暴露层”。

### 核心运行组件层
- `milvus/internal/proxy`
- `milvus/internal/rootcoord`
- `milvus/internal/datacoord`
- `milvus/internal/querycoordv2`
- `milvus/internal/querynodev2`
- `milvus/internal/streamingnode`
- `milvus/internal/streamingcoord`

这一层才是架构理解的核心。

## Theme 2 的关键文件

### 启动总入口
- `milvus/cmd/roles/roles.go`

这是理解“Milvus 到底会起哪些角色”的第一入口。它把 Proxy、MixCoord、QueryNode、DataNode、StreamingNode 等角色的启动组合放在一起看。

### 组件包装入口
- `milvus/cmd/components/proxy.go`
- `milvus/cmd/components/mix_coord.go`
- `milvus/cmd/components/query_node.go`
- `milvus/cmd/components/data_node.go`
- `milvus/cmd/components/streaming_node.go`

这些文件把“角色名”和“具体 server 实现”连接起来。

### 访问层入口
- `milvus/internal/proxy/proxy.go`
- `milvus/internal/proxy/impl.go`
- `milvus/internal/proxy/task_search.go`
- `milvus/internal/proxy/task_query.go`
- `milvus/internal/proxy/task_insert.go`

这些文件帮助你理解 Proxy 是如何把外部请求转成内部任务的。

### 协调层入口
- `milvus/internal/rootcoord/root_coord.go`
- `milvus/internal/datacoord/server.go`
- `milvus/internal/querycoordv2/server.go`
- `milvus/internal/streamingcoord/server/server.go`

这些文件帮助你建立各 coordinator 的边界感。

### 工作节点入口
- `milvus/internal/querynodev2/server.go`
- `milvus/internal/datanode/services.go`
- `milvus/internal/streamingnode/server/server.go`

这些文件帮助你理解真正执行查询、写入和流式处理的节点长什么样。

## 建议阅读顺序

### 第 1 轮: 先看系统是怎么被“拼起来”的
1. `milvus/cmd/roles/roles.go`
2. `milvus/cmd/components/proxy.go`
3. `milvus/cmd/components/mix_coord.go`
4. `milvus/cmd/components/query_node.go`
5. `milvus/cmd/components/data_node.go`
6. `milvus/cmd/components/streaming_node.go`

目标: 先知道有哪些角色，以及角色是怎么启动的。

### 第 2 轮: 再看控制平面
1. `milvus/internal/rootcoord/root_coord.go`
2. `milvus/internal/datacoord/server.go`
3. `milvus/internal/querycoordv2/server.go`
4. `milvus/internal/streamingcoord/server/server.go`

目标: 建立“谁管元数据、谁管数据生命周期、谁管查询分发、谁管 streaming”的边界感。

### 第 3 轮: 再看执行平面
1. `milvus/internal/proxy/proxy.go`
2. `milvus/internal/querynodev2/server.go`
3. `milvus/internal/datanode/services.go`
4. `milvus/internal/streamingnode/server/server.go`

目标: 知道“请求入口”和“真正执行节点”如何衔接。

## 这一题学完后你应该能回答

1. 为什么 Milvus 不能被看成单机 ANN 库？
2. Proxy、RootCoord、DataCoord、QueryCoord、QueryNode、DataNode 各自解决什么问题？
3. 为什么协调层和工作节点必须分开？
4. 为什么当前 Milvus 要强调 storage/compute disaggregation？
5. `cmd/roles`、`cmd/components` 和 `internal/*` 三层在架构理解里各自扮演什么角色？

## 和下一题怎么衔接
Theme 2 解决的是“系统图长什么样”。Theme 3 会把这个静态架构图变成动态链路，回答:

- 一次 insert 是怎么从 Proxy 进入系统的
- WAL / channel / DataNode / DataCoord 是怎么接起来的
- growing segment 怎么出现
- flush / seal / handoff 是怎么串起来的

## 相关前置文档
- `docs/milvus_theme1_concepts.md`
- `docs/milvus_version_and_terms.md`
- `docs/milvus_storage_and_index_map.md`

