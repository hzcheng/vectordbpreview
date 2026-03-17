# Milvus Mixed Data Model

## Purpose
这份文档回答一个核心问题: 在 Milvus 里，向量字段、标量字段和 JSON 字段是如何共同构成一个可检索对象模型的。

## One-Sentence Model
可以把 Milvus 的 collection 看成“以向量检索为中心、但允许附带结构化过滤条件和半结构化元数据”的表模型，而不是“只能存一列向量”的专用索引文件。

## Core Concepts

### Collection
collection 是顶层逻辑容器，作用接近数据库里的表。它定义一组统一 schema，并承载该组数据的写入、索引和查询边界。

### Schema
schema 描述 collection 中有哪些字段、每个字段是什么类型、哪些字段承担主键、哪些字段是向量字段、哪些字段负责结构化过滤。

### Field
field 是 schema 的基本列定义。Milvus 的 field 不只包含向量列，也包含主键、时间、分类、标签、文本元数据、JSON 元数据等非向量列。

## Field Categories

### Primary Key Field
主键字段承担实体身份。它不负责相似度计算，但它让“这个向量命中了谁”可以被稳定追踪，也为删除、更新重建和精确定位提供锚点。

### Vector Field
向量字段承载 embedding。它是 ANN/search 的核心输入。一个对象可以只有一个向量字段，也可以在同一 collection 中定义多个向量字段，用来表达不同视角的向量表示。

### Scalar Field
标量字段承载结构化条件，例如:
- `category`
- `source`
- `owner_id`
- `status`
- `created_at`

这些字段的价值不在“语义相似”，而在过滤、排序、租户隔离、业务裁剪和结果解释。

### JSON Field
JSON 字段承载半结构化元数据。它适合“字段集合不稳定、扩展速度快、但仍需要按键过滤或提取”的场景。JSON 不是替代 schema 的万能兜底，而是避免把所有弱结构属性都提前展开成大量固定列。

## Logical Data Shape

一个面向检索的对象通常长成这样:

```text
entity
  -> primary key
  -> one or more vector fields
  -> stable scalar fields
  -> optional JSON metadata
```

这说明 Milvus 的逻辑对象并不是“向量本体 + 外挂 metadata”，而是“同一实体的多类字段共同存在，其中向量字段负责召回，其他字段负责约束和解释”。

## How Vector Search And Filtering Coexist

### Search Path
向量字段负责把候选集先召回出来。

### Filter Path
标量字段和 JSON 字段负责缩小候选范围，或者在召回后继续应用业务约束。

### Combined Semantics
真正的业务查询通常不是“只做 ANN”，而是:
- 在某个向量字段上做 search
- 带一个或多个 scalar predicate
- 可能再带 JSON 条件
- 最终返回实体主键和若干解释性字段

因此，Milvus 的混合模型本质上是“向量召回 + 结构化约束”联合执行，而不是先把向量和业务字段拆成两个彼此无关的系统。

## Design Implications

### Multiple Vector Fields Are First-Class
如果一个实体需要多个语义视角，例如标题向量和正文向量，并不一定要拆成两个完全独立系统；Milvus 的 schema 层就允许一个 collection 拥有多个向量字段。

### Scalar Fields Should Stay Stable
高频参与过滤、权限、分组、生命周期控制的字段，更适合建成显式 scalar field，而不是全部塞进 JSON。

### JSON Is For Controlled Flexibility
JSON 适合承载长尾元数据、弱结构标签或还没稳定下来的属性。凡是将来必须高频过滤、跨团队约定、需要严格类型约束的字段，仍应优先显式建模。

### Dynamic Expansion Needs Discipline
Milvus 支持在 collection 创建后继续加字段，也支持动态字段能力，但这不等于可以放弃 schema 设计。对检索系统来说，主键、向量字段和高频过滤字段仍然必须尽早稳定。

## Practical Mental Model

如果用一句更工程化的话来概括:

> collection 是实体边界，schema 是字段合同，vector field 负责召回，scalar/JSON field 负责过滤与解释。

这个模型对后续 Phase C/D 很重要，因为后面要回答的是:
- 这些字段在 segment 中如何落盘
- 各类索引分别由谁承载
- 过滤在执行链路里的位置在哪里

## Stable Conclusions
- Milvus 不是“只能存向量”的单列系统，而是支持向量、标量和 JSON 共同组成一个检索对象。
- collection/schema/field 是混合数据模型的主骨架，后续索引和执行链路都依赖这个逻辑边界。
- 向量搜索和标量/JSON 过滤不是两个分离阶段的偶然拼接，而是 Milvus 设计里天然需要联合考虑的能力。
- JSON 字段适合补足半结构化元数据，但不能替代所有显式字段设计。

## Open Questions For Phase C/D
- scalar field 和 JSON field 的物理承载在 segment 中如何组织?
- growing segment 和 sealed segment 在过滤执行能力上是否存在能力或代价差异?
- 各类索引是附着在同一 segment 生命周期上，还是按字段类型走不同构建路径?

## Sources
- https://milvus.io/docs/schema.md
- https://milvus.io/docs/add-fields-to-an-existing-collection.md
- https://milvus.io/docs/use-json-fields.md
- https://milvus.io/docs/architecture_overview.md

