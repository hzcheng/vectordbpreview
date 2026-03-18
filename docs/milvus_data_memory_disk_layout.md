# Milvus 数据在内存与硬盘上的组织方式

## 这份文档想回答什么

你已经知道：

- 用户写入时常常是“按行”输入
- Milvus 内部会把数据重排成“按列”组织

这份文档继续往下回答两个问题：

1. **在内存里，这些列到底长什么样？**
2. **落到硬盘/对象存储后，这些列又是怎么组织的？**

为了避免混淆，先给出一个最重要的结论：

> 在 Milvus 里，“segment”更像一个生命周期容器；真正的数据组织，取决于你是在看写入侧内存、查询侧内存，还是持久化后的日志/文件。

---

## 一张总图：从用户行数据到内部列数据

```text
用户侧
  Row-oriented records
    ↓
Client 侧重排
  row -> columns
    ↓
写入侧内存（DataNode / flush path）
  InsertData:
    map[fieldID]FieldData
    ↓
segment 生命周期
  growing segment
    ↓ flush / seal
持久化
  insert binlogs / statslogs / deltalogs
  或 packed parquet + manifest
    ↓
查询侧内存（QueryNode）
  LocalSegment(Go metadata wrapper)
    + segcore CSegment(actual query-time data/index holder)
```

---

## 先用一个简单例子

假设 collection schema 是：

```text
id          Int64          主键
embedding   FloatVector(4) 向量字段
color       VarChar        标量字段
price       Int64          标量字段
attrs       JSON           JSON 字段
```

用户写入 3 行：

```text
row1 = {id: 101, embedding: [0.1, 0.2, 0.3, 0.4], color: "red",   price: 10, attrs: {"brand":"A","vip":true}}
row2 = {id: 102, embedding: [0.5, 0.6, 0.7, 0.8], color: "blue",  price: 20, attrs: {"brand":"B","vip":false}}
row3 = {id: 103, embedding: [0.9, 1.0, 1.1, 1.2], color: "green", price: 30, attrs: {"brand":"A","vip":true}}
```

用户脑子里常常是“3 行对象”，但 Milvus 写入链路更接近：

```text
id        -> [101, 102, 103]
embedding -> [0.1,0.2,0.3,0.4,  0.5,0.6,0.7,0.8,  0.9,1.0,1.1,1.2]
color     -> ["red", "blue", "green"]
price     -> [10, 20, 30]
attrs     -> ["{\"brand\":\"A\",\"vip\":true}",
              "{\"brand\":\"B\",\"vip\":false}",
              "{\"brand\":\"A\",\"vip\":true}"]
```

也就是说：

- 逻辑上它们仍然属于同一批实体
- 物理上已经被拆成多列

---

## 第一层：写入侧内存到底长什么样

### 1.1 顶层结构：`InsertData`

在 `milvus/internal/storage/insert_data.go:32`，写入侧核心结构是：

```text
InsertData
  Data map[FieldID]FieldData
```

这表示：

- 一批数据进入内部后，不再是 `[]Row`
- 而是 `fieldID -> 该字段整列数据`

可以把它想成：

```text
InsertData
├── field 0   -> row_id
├── field 1   -> timestamp
├── field 100 -> id
├── field 101 -> embedding
├── field 102 -> color
├── field 103 -> price
└── field 104 -> attrs
```

其中系统字段通常包括：

- `row_id`
- `timestamp`

所以每个 segment 的内部列集合，通常不只包含你定义的业务列，也包含系统列。

### 1.2 每种字段在内存里的具体形态

Milvus 在 `milvus/internal/storage/insert_data.go:407` 之后，按类型定义了不同的 `FieldData`：

| 用户看到的类型 | 写入侧内存中的典型结构 | 直观理解 |
|---|---|---|
| `Bool` | `[]bool` | 一列布尔值 |
| `Int64` | `[]int64` | 一列 64 位整数 |
| `VarChar/String` | `[]string` | 一列字符串 |
| `JSON` | `[][]byte` | 一列 JSON 字节串 |
| `FloatVector(dim)` | `[]float32` + `Dim` | 一块连续 float 数组 |
| `BinaryVector(dim)` | `[]byte` + `Dim` | 一块连续二进制向量缓冲区 |
| `SparseFloatVector` | `schemapb.SparseFloatArray` | 稀疏向量专用结构 |

### 1.3 一个非常关键的细节：向量列是“拍平”的

以 `FloatVector(4)` 为例，3 行数据不会在内存里保存成：

```text
[[0.1,0.2,0.3,0.4],
 [0.5,0.6,0.7,0.8],
 [0.9,1.0,1.1,1.2]]
```

而更接近：

```text
Data = []float32{
  0.1, 0.2, 0.3, 0.4,
  0.5, 0.6, 0.7, 0.8,
  0.9, 1.0, 1.1, 1.2,
}
Dim = 4
```

第 `i` 行向量的位置可理解为：

```text
start = i * Dim
end   = start + Dim
```

这比“每行一个小数组”更接近底层批量处理和序列化需求。

### 1.4 Nullable 字段怎么表示

Milvus 的很多 `FieldData` 都带：

```text
ValidData []bool
Nullable  bool
```

也就是说，它不是单独用一个特殊值表示 null，而是：

- `Data` 保存真实值缓冲区
- `ValidData` 记录每一行是否有效

对 nullable vector，代码里还有：

```text
L2PMapping LogicalToPhysicalMapping
```

可以把它理解成：

- 逻辑第 7 行可能是 null
- 但物理向量缓冲区只存了非 null 向量
- 所以需要一层“逻辑行 -> 物理偏移”的映射

这点很重要，因为它解释了“为什么 nullable vector 不能只靠 `[]float32` 本身表达完整语义”。

---

## 第二层：segment 里到底装了什么

这里最容易误解。

很多人会以为：

> segment = 一个 Go struct，里面直接有各列数组

这对写入侧临时结构来说只对一半；对查询侧则不准确。

### 2.1 写入侧看：segment 更像“列数据批次 + 生命周期状态”

在写入链路里，一批数据先以 `InsertData` 形式存在，然后被归入某个 growing segment。

可以先这样理解：

```text
Growing Segment
├── field 0   -> row_id column
├── field 1   -> timestamp column
├── field 100 -> id column
├── field 101 -> embedding column
├── field 102 -> color column
├── field 103 -> price column
└── field 104 -> attrs column
```

这个阶段的关键点是：

- 每列仍然按字段分开
- 同一“行”的跨列对应关系，靠相同 offset 维持
- row 0 的各列值，实际是“各列的第 0 个位置”

### 2.2 查询侧看：`LocalSegment` 不是“字段数组本体”，而是 segment wrapper

在 `milvus/internal/querynodev2/segments/segment.go:290`，QueryNode 里的 `LocalSegment` 更像一个包装层：

```text
LocalSegment
├── baseSegment
├── ptr / csegment          -> 指向 segcore C++ segment
├── bloomFilterSet          -> 主键过滤辅助结构
├── fields                  -> field 对应的 binlog 信息
├── fieldIndexes            -> 已加载/可加载索引信息
├── fieldJSONStats          -> JSON stats
├── memSize / rowNum cache  -> 缓存指标
└── bm25Stats               -> 文本/BM25 统计
```

这说明 QueryNode 上的 segment 有两层：

1. **Go 层 wrapper**：保存 metadata、索引信息、过滤辅助结构、缓存指标
2. **segcore C++ segment**：真正承载查询执行所需数据与索引

所以如果你问“segment 在查询内存里是什么形状”，更准确的回答是：

> Go 层看到的是一个 segment 句柄和若干元数据；真正的字段列、索引、执行态结构主要在 segcore 那层。

### 2.3 growing 和 sealed 的差别

可以先建立这个心智模型：

```text
Growing Segment
- 更接近“可继续写入的实时缓冲 + 可查询”
- 还没完成稳定落盘/封存

Sealed Segment
- 更接近“已稳定冻结的数据块”
- 更适合构建和加载正式索引
```

不要把这个差别理解成“行存 vs 列存”的差别。

**二者都遵循按字段组织的思路**，差别主要在：

- 生命周期状态
- 是否继续接受写入
- 是否已经完成 flush / seal / index build

---

## 第三层：落盘之后怎么组织

### 3.1 旧直觉不要带偏：不是“整个 segment 一次性写成一个大文件”

Milvus 持久化时，并不是把一个 segment 直接 dump 成一个“单体 row file”。

更接近：

```text
segment
  -> per-field insert logs
  -> stats logs
  -> delta logs
  -> index files
```

也就是说，segment 是逻辑单元；磁盘上通常是多类工件。

### 3.2 Storage V1：按 field 写 insert binlog

在 `milvus/internal/storage/data_codec.go:223`，`InsertCodec.Serialize` 的逻辑非常直接：

- 从 schema 拿到所有 field
- **对每个 field 单独创建一个 binlog writer**
- 把该 field 的整列 payload 写进 binlog

因此 V1 的基本形态可以画成：

```text
Segment 5001
├── insert_log / coll / part / seg / field_id / file...
│   ├── field=id
│   ├── field=embedding
│   ├── field=color
│   ├── field=price
│   └── field=attrs
├── stats_log / coll / part / seg / field_id / file...
└── delta_log / coll / part / seg / file...
```

在 `milvus/internal/storage/binlog_util.go:11` 里也能看到路径规则注释：

```text
[log_type]/collID/partID/segID/fieldID/fileName
```

对 insert/stats log 来说，它本质上就是：

- 先按 segment 分
- 再按 field 分
- 每个 field 再对应一个或多个日志文件

### 3.3 具体到上面的例子，落盘长什么样

我们的例子在 V1 持久化后，可以近似想成：

```text
Segment 5001
├── insert_log/.../5001/100/id.binlog
│     [101,102,103]
├── insert_log/.../5001/101/embedding.binlog
│     [0.1,0.2,0.3,0.4, 0.5,0.6,0.7,0.8, 0.9,1.0,1.1,1.2]
├── insert_log/.../5001/102/color.binlog
│     ["red","blue","green"]
├── insert_log/.../5001/103/price.binlog
│     [10,20,30]
├── insert_log/.../5001/104/attrs.binlog
│     ["{\"brand\":\"A\",\"vip\":true}", ...]
├── stats_log/.../5001/100/...
└── delta_log/.../5001/...
```

所以：

- **同一行不会以“对象”形式连续存放在磁盘**
- 同一 segment 内，不同字段通常是分开的

### 3.4 stats log / delta log 分别是什么

可以先记住最小模型：

- `insert log`：真正的字段数据
- `stats log`：主键统计、bloom filter/min-max 一类辅助统计
- `delta log`：删除记录，核心是“哪个主键在什么时间被删”

所以删除并不是简单“回写覆盖原 insert 文件”，而是以独立 delta 工件表示。

---

## 第四层：新版本持久化为什么又看到 parquet / manifest

### 4.1 代码里已经明确区分了 3 代存储版本

在 `milvus/internal/storage/rw.go:35`：

```text
StorageV1 = legacy binlog
StorageV2 = packed writer binlog format(parquet)
StorageV3 = loon manifest format
```

这说明当前源码里，持久化并不只有一种形态。

### 4.2 V2 / V3 的核心变化：仍然是列式，但开始“打包”和“加 manifest”

可以先把新格式理解成：

```text
segment
  -> column groups
  -> packed parquet files
  -> manifest path
```

也就是说：

- 本质仍是列式组织
- 但不一定再是“每个字段一个独立旧式 binlog 文件”的直观形态
- 可以把多个列按 column group 打包
- 再通过 manifest 记录这个 segment 对应哪些文件/碎片

### 4.3 新版更像这样

```text
Segment 5001
├── manifest
│   ├── column group A -> pk + timestamp + price
│   ├── column group B -> embedding
│   ├── column group C -> attrs / json stats
│   └── delta logs / fragments metadata
└── parquet / packed files
    ├── group_A_000.parquet
    ├── group_B_000.parquet
    ├── group_C_000.parquet
    └── ...
```

所以新版不要再想成“segment = 一个文件”，而更像：

> segment = manifest 管理下的一组列式文件/碎片

---

## 第五层：你真正该建立的 4 个视角

为了以后看源码不乱，我建议把“数据组织”固定成下面 4 个视角。

### 视角 A：逻辑模型

```text
collection
  -> schema
    -> fields
```

这是“数据是什么”。

### 视角 B：写入侧内存模型

```text
InsertData
  -> map[fieldID]FieldData
```

这是“数据刚进系统、准备 flush 之前怎么放”。

### 视角 C：查询侧 segment 模型

```text
LocalSegment
  -> Go metadata
  + segcore CSegment
```

这是“查询节点拿什么执行 search/query”。

### 视角 D：持久化模型

```text
segment
  -> insert logs / stats logs / delta logs / index files
  or
  -> packed parquet + manifest
```

这是“数据最终怎么落到对象存储/硬盘上”。

---

## 一张最实用的对照表

| 关心的问题 | 正确答案 |
|---|---|
| 用户写入是一行一行吗？ | 对，用户视角通常是 row-oriented |
| 内部还是按行存吗？ | 不是，写入/持久化主线是按列组织 |
| segment 里是不是直接放 `[]Row`？ | 不是，至少主线理解不该这么想 |
| 向量在内存里是什么样？ | 常见是拍平成连续数组，再配 `Dim` |
| JSON 在内存里是什么样？ | 常见是 `[][]byte`，每行一段 JSON bytes |
| nullable 怎么处理？ | `Data` + `ValidData`，向量还可能有逻辑到物理映射 |
| 落盘是不是一个 segment 一个文件？ | 不是，通常是 segment 关联多类日志/文件工件 |
| 新版 parquet/manifest 是不是变回行存？ | 不是，仍然是列式，只是组织粒度和封装方式升级了 |

---

## 你可以用一句话记住它

> Milvus 不是把“行对象”直接塞进 segment；它先把一批行拆成按字段组织的列，再把这些列挂到 segment 生命周期上，最后以日志文件或 packed/manifest 形式持久化。

---

## 如果你下一步还想继续

最自然的两个深挖方向是：

1. **专盯 `InsertData -> Serialize -> binlog`**：把每种字段如何写成 payload 看透
2. **专盯 `LocalSegment -> segcore -> LoadIndex/LoadDeltaLogs`**：把 QueryNode 内存态 segment 看透

对应入口：

- `milvus/internal/storage/insert_data.go:32`
- `milvus/internal/storage/data_codec.go:223`
- `milvus/internal/querynodev2/segments/segment.go:290`
- `milvus/internal/querynodev2/segments/segment_loader.go:67`
