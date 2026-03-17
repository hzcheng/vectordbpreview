# Milvus Theme 3: 数据写入流程

## 这一题要解决什么问题
Theme 2 让你看到了 Milvus 的系统地图。Theme 3 要回答的是:

> 一次写入请求到底是怎么从客户端入口，变成 growing segment，再逐步进入 flush / sealed 生命周期的？

这题的关键不是死记函数名，而是建立一条稳定的动态链路。

## 先给出整条主链

在当前 `2.6.x` 本地代码树里，可以先把写入路径压缩成这条主链:

```text
client insert
  -> Proxy validates / enriches request
  -> rows are assigned to channels
  -> insert messages are repacked
  -> messages append to WAL / streaming path
  -> DataNode-side flowgraph consumes channel data
  -> writebuffer / syncmgr persist logs and checkpoints
  -> DataCoord tracks segment/channel lifecycle
  -> segment remains growing, then becomes flushable / sealed
```

这条链已经足够支撑你后面理解 segment、flush、sealed、handoff、compaction。

## 第 1 段: Proxy 如何处理写入请求

### Proxy 不负责直接写最终数据
Proxy 是写入的入口，但不是最终数据持久化者。它的职责更像:

- 校验 collection 和 schema
- 分配 row IDs / timestamps
- 处理 primary key、dynamic field、partition key
- 把行分配到 channel
- 把大请求拆成适合消息路径的 insert messages

### 从代码上看什么
`milvus/internal/proxy/task_insert.go` 里能直接看到这些动作:

- 获取 collection id / schema
- 分配 auto ID
- 生成 row timestamps
- 校验主键字段与输入字段
- 设置 channels

这说明写入在 Proxy 里首先不是“存数据”，而是“把请求变成合法、完整、可下发的内部写入任务”。

### 为什么要在 Proxy 做这些
因为后面的 DataNode / streaming path 更适合处理“已经结构化好的内部消息”，而不是直接处理各种客户端输入差异。

## 第 2 段: 行如何被分配到 channel

### channel 是写入并行化的关键
Milvus 不会把所有写入都塞进一个全局单通道里。写入会先根据 channel / shard 逻辑拆开。

这一步的意义是:

- 把 collection 的写入流分散
- 为后续 DataNode 侧按 channel 消费创造条件
- 让 segment 生命周期绑定到更具体的 channel 上

### 从代码上看什么
`milvus/internal/proxy/msg_pack.go` 里的 `genInsertMsgsByPartition` 很关键。它做了几件事:

- 基于 partition / channel 创建 insert message
- 把多行数据按阈值切包
- 给每个包设置 `CollectionID`、`PartitionID`、`ShardName`

这一步让“客户端的一次 insert”变成“内部可传播的多个 insert messages”。

## 第 3 段: 写入如何真正进入 WAL / streaming 路径

### 当前代码里 streaming path 是写入主入口之一
在当前代码基线下，`milvus/internal/proxy/task_insert_streaming.go` 很值得重点看。

这里能直接看到写入执行阶段的关键动作:

- 获取 vchannels
- 把 insert data repack 成 streaming messages
- 调用 `streaming.WAL().AppendMessages(...)`

这说明在当前路径里，Proxy 不是直接把数据写对象存储，也不是直接 RPC 给 DataNode 做“最终落盘”，而是先进入 WAL / streaming 抽象。

### 为什么 WAL 是关键
WAL 的作用不是“顺手记个日志”，而是:

- 成为写入顺序与可靠性的基础
- 把请求入口和后续异步处理解耦
- 为 channel-based 的下游消费提供统一入口

### 从代码上看什么
- `milvus/internal/proxy/task_insert_streaming.go`
- `milvus/internal/streamingnode/server/walmanager/manager.go`
- `milvus/internal/streamingnode/server/server.go`

这里最重要的直觉是:

> 写入先变成消息，再进入 WAL manager 管理的 channel 级写入路径。

## 第 4 段: DataNode 如何接住这条写入流

### DataNode 不是“直接接 HTTP/SDK insert”的地方
DataNode 更像写入流水线的工作节点。它负责:

- 消费 channel 上的数据
- 在 flowgraph 中处理 insert / delta / timetick
- 组织 writebuffer
- 驱动 sync manager 把数据变成持久化工件

### DataNode 的运行时核心
从 `milvus/internal/datanode/data_node.go` 看，DataNode 初始化时会挂上:

- `syncMgr`
- import / compaction / index 相关管理器
- chunk manager / storage factory

这说明 DataNode 的角色是“数据处理与持久化执行者”。

### 真正把 channel 跑起来的地方
`milvus/internal/flushcommon/pipeline/data_sync_service.go` 很重要。这个文件表明:

- DataSyncService 是按 vchannel 组织的
- 内部有 `TimeTickedFlowGraph`
- 它会为特定 collection / vchannel 服务
- 会初始化 metacache、加载 unflushed / flushed segment 状态
- 会把 msgdispatcher、syncMgr、chunkManager 接起来

这其实就是写路径运行时的主骨架。

你可以把它理解成:

> 每个写入 channel 背后，都有一条 DataSyncService 驱动的 flowgraph，在持续把消息流加工成 segment 相关状态和持久化工件。

## 第 5 段: flush 到底发生在哪里

### flush 不是“Proxy 调个 flush API 就完成”
flush 的本质是把 DataNode 侧已经接收和组织好的数据，推进成稳定的持久化对象和 checkpoint。

在当前代码树里，`flushcommon` 很关键:

- `milvus/internal/flushcommon/pipeline`
- `milvus/internal/flushcommon/writebuffer`
- `milvus/internal/flushcommon/syncmgr`
- `milvus/internal/flushcommon/metacache`

其中最关键的理解是:

- `writebuffer` 负责累积与组织写入中的数据
- `syncmgr` 负责把 sync task 推进成真正的持久化写出
- `metacache` 帮 flowgraph 维护 segment/channel 相关运行时状态

### sync manager 的作用
`milvus/internal/flushcommon/syncmgr/sync_manager.go` 表明 sync manager 是专门负责提交 sync task 的。它就是“从运行时缓冲到持久化对象”的关键桥梁。

因此 flush 的工程含义更接近:

> channel 上的运行时数据经过 flowgraph 和 sync manager，被同步成 segment 相关的持久化日志/工件，并把 checkpoint 往前推进。

## 第 6 段: DataCoord 在写路径里扮演什么角色

### DataCoord 不是执行者，而是生命周期协调者
DataCoord 负责的是全局视角下的数据组织:

- segment 分配
- growing / sealed 的状态推进
- flushable segments 判断
- channel 维度的管理
- compaction / index / snapshot 等后续生命周期动作

### 从代码上看什么
`milvus/internal/datacoord/segment_manager.go` 是 Theme 3 的核心入口之一。

它直接暴露的职责包括:

- `AllocSegment`
- `AllocNewGrowingSegment`
- `SealAllSegments`
- `GetFlushableSegments`
- `ExpireAllocations`

这说明 DataCoord 更像“全局 segment 生命周期管理器”。

`milvus/internal/datacoord/channel.go` 则说明 channel 在 DataCoord 里也是一等概念，而不是简单字符串。

### 为什么 DataCoord 必须存在
因为单个 DataNode 只能看到自己处理的局部流，而系统必须有一个组件统一回答这些问题:

- 哪些 segment 还在 growing
- 哪些 segment 已经可以 seal
- 哪些 segment 已经 flushable
- 哪些 channel 属于哪个 collection

这正是 DataCoord 的职责。

## 写入主流程的正确心智模型

把上面的所有细节压缩一下，可以得到一个更稳定的理解:

### 1. Proxy 负责把客户端写入变成内部合法消息
- 校验 schema
- 分配 row IDs / timestamps
- 按 partition / channel 切分

### 2. WAL / streaming path 负责承接写入流
- append message
- 保证后续异步处理入口

### 3. DataNode 负责把消息流变成可持久化的数据状态
- 按 vchannel 建 flowgraph
- 用 metacache / writebuffer / syncmgr 处理数据

### 4. DataCoord 负责全局 segment 生命周期
- 分配 growing segment
- 判断 seal / flushable
- 维护 channel / segment / metadata

## Theme 3 的源码目录

### 写入入口
- `milvus/internal/proxy`

### WAL / streaming 路径
- `milvus/internal/streamingnode`
- `milvus/internal/streamingcoord`

### 数据处理与 flush 运行时
- `milvus/internal/datanode`
- `milvus/internal/flushcommon/pipeline`
- `milvus/internal/flushcommon/writebuffer`
- `milvus/internal/flushcommon/syncmgr`
- `milvus/internal/flushcommon/metacache`

### 全局生命周期协调
- `milvus/internal/datacoord`

## Theme 3 的关键文件

### Proxy 入口
- `milvus/internal/proxy/task_insert.go`
- `milvus/internal/proxy/task_insert_streaming.go`
- `milvus/internal/proxy/msg_pack.go`

### WAL / streaming 入口
- `milvus/internal/streamingnode/server/server.go`
- `milvus/internal/streamingnode/server/walmanager/manager.go`

### DataNode / flowgraph / flush
- `milvus/internal/datanode/data_node.go`
- `milvus/internal/datanode/services.go`
- `milvus/internal/flushcommon/pipeline/data_sync_service.go`
- `milvus/internal/flushcommon/syncmgr/sync_manager.go`

### DataCoord / segment 生命周期
- `milvus/internal/datacoord/server.go`
- `milvus/internal/datacoord/segment_manager.go`
- `milvus/internal/datacoord/channel.go`

## 建议阅读顺序

### 第 1 轮: 先看写入是怎么从 Proxy 出发的
1. `milvus/internal/proxy/task_insert.go`
2. `milvus/internal/proxy/msg_pack.go`
3. `milvus/internal/proxy/task_insert_streaming.go`

目标: 理解客户端 insert 如何被校验、补全、切包和按 channel 分发。

### 第 2 轮: 再看 WAL / streaming 接口层
1. `milvus/internal/streamingnode/server/server.go`
2. `milvus/internal/streamingnode/server/walmanager/manager.go`

目标: 理解写入为什么先进入 WAL 抽象，而不是直接落对象存储。

### 第 3 轮: 再看 DataNode 侧如何真正处理这条流
1. `milvus/internal/datanode/data_node.go`
2. `milvus/internal/flushcommon/pipeline/data_sync_service.go`
3. `milvus/internal/flushcommon/syncmgr/sync_manager.go`
4. `milvus/internal/datanode/services.go`

目标: 理解 vchannel flowgraph、writebuffer、sync task、持久化推进之间的关系。

### 第 4 轮: 最后看 DataCoord 如何维护全局生命周期
1. `milvus/internal/datacoord/server.go`
2. `milvus/internal/datacoord/segment_manager.go`
3. `milvus/internal/datacoord/channel.go`

目标: 理解为什么 growing / seal / flushable 必须由全局协调组件统一管理。

## 这一题学完后你应该能回答

1. 为什么 Proxy 不是最终写入执行者？
2. 为什么写入要先变成 channel 上的消息？
3. DataNode 的 flowgraph 在写路径里到底起什么作用？
4. flush 和 sealed 分别对应链路里的哪个阶段？
5. 为什么 DataCoord 必须维护 segment 生命周期，而不能只靠 DataNode 自己决定？

## 和下一题怎么衔接
Theme 3 讲的是“写入怎么流动”。Theme 4 会回答另一件事:

- 这些被写进去的数据，在 collection/schema/field 层面到底是怎么组织的
- 向量字段、标量字段、JSON 字段在逻辑模型里如何共存

也就是从“动态写入路径”切到“静态数据组织模型”。

## 相关前置文档
- `docs/milvus_theme1_concepts.md`
- `docs/milvus_theme2_architecture.md`
- `docs/milvus_storage_and_index_map.md`

