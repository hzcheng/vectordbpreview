# Milvus Theme 4: 向量数据和其他数据的组织格式

## 这一题要解决什么问题
Theme 3 讲的是“数据怎么写进来”。Theme 4 要解决的是另一个非常关键的问题:

> 一条数据进入 Milvus 之后，向量字段、标量字段、JSON 字段到底是按什么模型被组织起来的？

如果这一题不搞清楚，后面你在看索引、过滤、查询计划时，很容易把 Milvus 错看成“向量列外挂几列 metadata”的系统。实际上在当前源码里，更准确的理解是:

> Milvus 先用 `collection/schema/field` 定义逻辑实体模型，再把同一实体拆成按字段组织的数据列，由不同字段类型共同参与写入、存储、索引和查询。

## 先给出一个总模型

可以先把 Theme 4 压缩成下面这条链:

```text
collection
  -> schema
    -> fields
      -> primary key field
      -> vector field(s)
      -> scalar field(s)
      -> JSON field
      -> optional dynamic field($meta)
  -> row input on client side
  -> column-oriented field data inside write/storage path
  -> schema copy in metastore / query runtime
```

这条链的重点是两件事:

- 逻辑上，Milvus 以 collection/schema/field 建模
- 运行时，Milvus 以“按字段拆开的列数据”组织实际内容

## 第 1 层: Collection / Schema / Field 是逻辑骨架

### Collection 是实体边界
collection 是顶层逻辑容器。它界定的是一组实体的共同 schema、共同 shard/channel、共同索引和共同查询边界。

在 `milvus/client/entity/collection.go` 里，你能直接看到 collection 对外暴露的不只是名字，还包括:

- `Schema`
- `PhysicalChannels`
- `VirtualChannels`
- `ConsistencyLevel`
- `ShardNum`
- `Properties`

这说明 collection 不是单纯“一个表名”，而是逻辑模型和分布式运行边界的结合体。

### Schema 是字段合同
在 `milvus/client/entity/schema.go` 里，`Schema` 明确包含:

- `CollectionName`
- `Description`
- `AutoID`
- `Fields`
- `EnableDynamicField`
- `Functions`
- `ExternalSource`
- `ExternalSpec`

这说明 schema 的职责不是只保存字段列表，而是定义:

- collection 的名字和描述
- 是否自动生成主键
- 这批数据有哪些字段
- 是否允许动态字段
- 是否有函数输出字段或外部数据源信息

### Field 是真正的数据组织单位
在 `milvus/client/entity/field.go` 里，`Field` 是 Theme 4 的核心入口。它告诉你一个 field 不只是“名字 + 类型”，还包含:

- `PrimaryKey`
- `AutoID`
- `DataType`
- `TypeParams`
- `IndexParams`
- `IsDynamic`
- `IsPartitionKey`
- `IsClusteringKey`
- `ElementType`
- `Nullable`
- `ExternalField`

因此 field 的正确理解是:

> Field 既定义列的值类型，也定义这列在主键、分区、聚类、动态字段、数组元素类型等方面承担的系统语义。

## 第 2 层: 向量字段、标量字段、JSON 字段是并列的一等公民

### 向量字段
`client/entity/field.go` 里定义了多种 vector type，包括:

- `FloatVector`
- `BinaryVector`
- `Float16Vector`
- `BFloat16Vector`
- `SparseVector`
- `Int8Vector`

向量字段的核心特点是:

- 它们通常有 `dim` 等 type params
- 它们承担 ANN/search 的主要召回职责
- 一个 collection 可以有不止一个向量字段

所以 Milvus 的对象模型不是“一个对象只能有一个 embedding”。

### 标量字段
同一份 `FieldType` 定义里，也能看到标量类型包括:

- `Bool`
- `Int8/16/32/64`
- `Float/Double`
- `String/VarChar`
- `Array`
- `Timestamptz`

这些字段不负责相似度计算，但负责:

- 精确过滤
- 权限/租户/状态约束
- 排序与解释
- 生命周期和业务标签表达

### JSON 字段
`FieldTypeJSON` 说明 JSON 在 Milvus 里不是外部外挂结构，而是正式 field type。

它的作用是承载半结构化属性。Theme 4 要特别记住一点:

> JSON 字段属于 schema 的正式成员，不是 schema 之外的逃生口。

后面讲索引和查询时，你会看到 JSON 也会进入过滤和索引体系。

## 第 3 层: Dynamic Field 不是“没 schema”，而是“schema 内的 JSON 兜底列”

这部分最容易误解。

### EnableDynamicField 只是打开能力开关
在 `client/entity/schema.go` 里，schema 有 `EnableDynamicField`。这表示 collection 允许接收 schema 外的附加字段，但不等于“整个 collection 从此没有固定 schema”。

固定字段仍然存在，而且依然是主模型。

### RootCoord 会补一列真正的 dynamic field
在 `internal/rootcoord/create_collection_task.go` 里，`appendDynamicField` 会在创建 collection 时追加一个字段:

- 名字是动态元字段
- 类型是 `JSON`
- `IsDynamic = true`
- 默认值是 `{}` 

这说明 dynamic field 在系统内部不是抽象概念，而是一列真实存在的 JSON field。也就是说:

> “支持动态字段”在内部的真实落地方式，是在 schema 里加一列特殊 JSON 字段，用来收纳 schema 外的属性。

### 客户端会把剩余字段打包进 dynamic JSON 列
`milvus/client/row/data.go` 很关键。它把用户传入的 row struct 转成 column data 时，会做两件事:

- 已在 schema 中声明的字段，进入各自对应的列
- 没在 schema 中声明、但启用了 dynamic field 的字段，被收集并 `json.Marshal` 到一个 `ColumnJSONBytes`

`milvus/client/column/json.go` 又进一步表明，这个 JSON 列在发给服务端时会带上 `IsDynamic` 标记。

所以 dynamic field 的正确心智模型是:

```text
用户输入的一行数据
  -> 已声明字段: 各归各列
  -> 未声明字段: 汇总到一个动态 JSON 列
```

## 第 4 层: 客户端是“按行理解”，写入/存储侧是“按列组织”

这是 Theme 4 的核心转换。

### 客户端输入常常是 row-oriented
从使用者视角看，一条数据通常像这样:

```text
{
  id,
  text_vec,
  category,
  owner_id,
  extra_json
}
```

这是一行实体。

`milvus/client/row/schema.go` 和 `milvus/client/row/data.go` 说明:

- client 可以从 struct tag 推导 schema
- 每个字段被识别成对应的 `FieldType`
- 行数据最终会被重排成按列的 `column.Column`

### 写入/存储侧按 FieldID 组织列数据
`milvus/internal/storage/insert_data.go` 是 Theme 4 最重要的运行时入口之一。

`InsertData` 的核心结构是:

- `Data map[FieldID]FieldData`

这说明在真正进入写入和持久化链路后，Milvus 不是保存“一个 row struct 数组”，而是保存:

> 一个以 `FieldID` 为键、每个字段单独持有自己列数据的列式结构。

这也是为什么同一实体里的向量、标量、JSON 虽然逻辑上属于一条记录，但运行时会被拆成不同的列数据承载。

### 不同字段类型对应不同 FieldData 实现
同一个 `insert_data.go` 里，`NewFieldData` 会按 `schemapb.DataType` 创建不同实现，例如:

- `FloatVectorFieldData`
- `BinaryVectorFieldData`
- `SparseFloatVectorFieldData`
- `JSONFieldData`
- `ArrayFieldData`
- 各类 scalar field data

所以 Theme 4 最关键的一句总结是:

> Milvus 的“混合数据模型”在运行时并不是一块混合 blob，而是被拆成一组按字段类型分别存放的 FieldData 列。

## 第 5 层: 向量、标量、JSON 是怎样在同一实体里共存的

### 逻辑上共存
逻辑上，它们同属同一个 collection 的 schema，并共享:

- 同一个主键语义
- 同一条写入生命周期
- 同一个 segment 归属

### 物理上分列
物理组织上，它们在 `InsertData.Data` 里按 `FieldID -> FieldData` 分开保存。也就是说:

- 向量列不会和字符串列混在一个数组里
- JSON 列不会把所有字段替代掉
- 标量列依然是单独列

这种设计的工程价值很直接:

- 向量列可以走自己的索引和搜索路径
- 标量列可以走自己的过滤和统计路径
- JSON 列可以保留灵活性，但不破坏整体 schema 模型

## 第 6 层: Metastore 和 Query Runtime 会各自保留 schema 副本

Theme 4 不能只停在 client 层，因为 schema 不是一次性对象。

### Metastore 模型
在 `internal/metastore/model/field.go` 和 `internal/metastore/model/collection.go` 中，你能看到内部元数据模型把 schema 的关键语义继续保留下来:

- collection 里有 `Fields`
- collection 里有 `StructArrayFields`
- collection 里有 `VirtualChannelNames` / `PhysicalChannelNames`
- collection 里有 `EnableDynamicField`
- field 里保留 `IsDynamic` / `IsPartitionKey` / `IsClusteringKey` / `Nullable` / `ExternalField`

这说明 metastore 持有的不是一个“弱化版 schema”，而是能支撑后续生命周期、调度和执行的正式元数据对象。

### Query Runtime 模型
在 `internal/querynodev2/segments/collection.go` 中，QueryNode 的 collection manager 也会持有 `schemapb.CollectionSchema`，并支持 `UpdateSchema`。

这说明 schema 不是只在建表时用一次。它会被:

- 创建时生成
- 存入 metastore
- 下发到 query runtime
- 在 schema 变化时继续更新

因此 Theme 4 的另一个重要结论是:

> schema 是贯穿 client、control plane、query runtime 的长生命周期对象，而不是 DDL 完成后就消失的声明。

## 第 7 层: 特殊字段也属于数据组织的一部分

Theme 4 还要注意几类容易忽略的字段语义。

### Primary Key
主键字段是实体身份锚点。它不只是业务字段，也直接参与删除、去重、定位和后续查询返回。

### Partition Key / Clustering Key
`Field` 和 metastore model 里都保留了 `IsPartitionKey`、`IsClusteringKey`。这说明某些字段不只是“可过滤列”，还会影响数据如何被组织和后续如何被切分。

### Nullable / DefaultValue
字段是否允许空值、默认值是什么，也写进了 schema/field 模型里。这些不是纯客户端校验项，而是写入和导入路径要真正执行的约束。

### StructArrayFields
`client/entity/schema.go` 和 `internal/metastore/model/collection.go` 里都显式处理了 `StructArrayFields`。这说明 Milvus 在当前版本下已经不只是简单扁平列模型，还允许更复杂的结构化数组字段表达。

## Theme 4 的正确心智模型

把上面压缩一下，你应该把 Milvus 的数据组织理解成:

### 1. 先用 schema 定义实体
- collection 决定边界
- schema 决定字段合同
- field 决定每一列的系统语义

### 2. 再把一行实体拆成按字段组织的数据列
- client 侧输入看起来像 row
- 写入和存储侧实际更接近 column-oriented
- 每个字段通过 `FieldID -> FieldData` 承载

### 3. dynamic field 只是特殊 JSON 列
- 它不是取消 schema
- 它是对 schema 外属性的受控收纳

### 4. schema 会一路跟着数据走
- client 有 schema
- metastore 有 schema
- query runtime 也有 schema

## Theme 4 的源码目录

### 对外建模与 row/column 转换
- `milvus/client/entity`
- `milvus/client/row`
- `milvus/client/column`

### 系统内部 schema / collection 元数据
- `milvus/internal/metastore/model`
- `milvus/internal/rootcoord`

### 运行时数据组织与写入承载
- `milvus/internal/storage`
- `milvus/internal/datanode/importv2`

### 查询侧持有的 schema 副本
- `milvus/internal/querynodev2/segments`
- `milvus/internal/querycoordv2/meta`

## Theme 4 的关键文件

### 对外逻辑模型
- `milvus/client/entity/collection.go`
- `milvus/client/entity/schema.go`
- `milvus/client/entity/field.go`

这三份文件负责建立 collection/schema/field 的基础概念和类型系统。

### row -> column 转换
- `milvus/client/row/schema.go`
- `milvus/client/row/data.go`
- `milvus/client/column/json.go`

这三份文件回答:

- row struct 如何推导 schema
- 行数据如何拆成列
- dynamic field 如何打包为 JSON 列

### 内部元数据模型
- `milvus/internal/metastore/model/field.go`
- `milvus/internal/metastore/model/collection.go`
- `milvus/internal/rootcoord/create_collection_task.go`

这三份文件回答:

- schema 在内部 catalog 里如何表示
- dynamic field 如何在建 collection 时被真正补进 schema

### 运行时数据承载
- `milvus/internal/storage/insert_data.go`
- `milvus/internal/storage/data_codec.go`
- `milvus/internal/datanode/importv2/util.go`

这三份文件回答:

- 各字段如何以 `FieldID -> FieldData` 组织
- 写入后的列数据如何进入 codec / binlog 体系
- dynamic field 缺失时如何补齐为空 JSON

### 查询侧 schema 持有与更新
- `milvus/internal/querynodev2/segments/collection.go`
- `milvus/internal/querycoordv2/meta/collection_manager.go`

这两份文件回答:

- QueryNode 如何持有 collection schema
- schema 如何在查询侧被更新和同步

## 建议阅读顺序

### 第 1 轮: 先建立逻辑对象模型
1. `milvus/client/entity/collection.go`
2. `milvus/client/entity/schema.go`
3. `milvus/client/entity/field.go`

这一轮的目标是先搞清 collection/schema/field 各自表达什么。

### 第 2 轮: 再看 row 数据如何被拆成列
1. `milvus/client/row/schema.go`
2. `milvus/client/row/data.go`
3. `milvus/client/column/json.go`

这一轮的目标是建立“用户看见的是行，Milvus 内部更偏列”的转换直觉。

### 第 3 轮: 看 dynamic field 在系统里如何真实落地
1. `milvus/internal/rootcoord/create_collection_task.go`
2. `milvus/internal/datanode/importv2/util.go`

这一轮的目标是把 dynamic field 从抽象能力，落实为真实 JSON 列和导入/写入补齐逻辑。

### 第 4 轮: 看内部元数据和运行时如何继续持有 schema
1. `milvus/internal/metastore/model/field.go`
2. `milvus/internal/metastore/model/collection.go`
3. `milvus/internal/querycoordv2/meta/collection_manager.go`
4. `milvus/internal/querynodev2/segments/collection.go`

这一轮的目标是理解 schema 如何从 DDL 延续到 control plane 和 query runtime。

### 第 5 轮: 最后看真正的数据列承载
1. `milvus/internal/storage/insert_data.go`
2. `milvus/internal/storage/data_codec.go`

这一轮的目标是把“schema 模型”连接到“实际字段数据怎么存放”。

## 这一题学完后你应该能回答

1. Milvus 为什么不是“单向量列 + 外挂 metadata”的模型？
2. dynamic field 为什么本质上是一列特殊 JSON field，而不是取消 schema？
3. 为什么 client 侧看起来像 row，写入/存储侧却按 `FieldID -> FieldData` 组织？
4. schema 为什么要在 client、metastore、QueryNode 三处都保留？
