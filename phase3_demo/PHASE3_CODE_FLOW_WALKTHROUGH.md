# Phase 3 Code Flow Walkthrough

这份文档整理了我们刚才一步一步走过的 Phase 3 代码流程。目标不是一次性讲完所有细节，而是帮你建立一个稳定的心智模型：

1. 整个 Demo 从哪里开始
2. 建库阶段做了什么
3. 每一步在代码里对应哪里

后面如果你继续往下读 `search_demo.py`，可以直接接着这份文档往后走。

---

## Step 1: 先看整体入口

Phase 3 的 Demo，真正的入口只有两个：

- `phase3_demo/src/build_demo.py`
- `phase3_demo/src/search_demo.py`

你可以把它理解成两个阶段：

1. `build_demo.py`
   - 作用是建库
   - 把本地文本数据读进来，转成向量，再写入 Milvus Lite

2. `search_demo.py`
   - 作用是查询
   - 跑三种检索：
     - 关键词检索
     - 向量检索
     - 带过滤条件的向量检索

所以整个 Phase 3 的最粗主线就是：

```text
先 build
再 search
```

README 里的命令顺序也是这个逻辑：

```bash
python3 phase3_demo/src/build_demo.py
python3 phase3_demo/src/search_demo.py
```

---

## Step 2: `build_demo.py` 在做什么

核心入口在：

- `phase3_demo/src/build_demo.py`
- 函数：`build_demo()`

这个函数只做了 4 件事：

1. 读入文档
2. 初始化一个 embedder
3. 连接 Milvus Lite
4. 重建 collection 并把文档写进去

你可以先记住这个顺序：

```text
文本数据
-> embedder 准备好
-> 连上 Milvus Lite
-> 创建/重建 collection
-> 插入文档
```

它的本质不是“搜索”，而是“准备一个可搜索的向量库”。

---

## Step 3: `load_documents()` 读进来的是什么

`build_demo.py` 的第一步是调用：

- `phase3_demo/src/demo_data.py`
- 函数：`load_documents(path)`

这个函数做的事情非常简单：

```python
json.load(handle)
```

也就是：

- 打开 `phase3_demo/data/sample_docs.json`
- 把 JSON 文件读成 Python 列表
- 返回给 `build_demo()`

返回值可以理解成：

```python
docs = [
    {
        "id": "...",
        "text": "...",
        "category": "...",
        "source": "..."
    },
    ...
]
```

样本记录最关键的 4 个字段是：

- `id`
- `text`
- `category`
- `source`

它们分别代表：

- `id`：文档唯一标识
- `text`：真正做检索的文本
- `category`：类别，例如 `python`、`database`、`ai`
- `source`：来源，例如 `tutorial`、`guide`、`note`

这一步的意义是：

```text
把磁盘上的 JSON 文本文件
变成 Python 内存里的文档列表
```

这时候还没有向量，也还没有 Milvus 检索。

---

## Step 4: `LightweightChineseEmbedder` 是什么

`build_demo.py` 的第二步会创建：

- `phase3_demo/src/vector_store.py`
- 类：`LightweightChineseEmbedder`

先不要把它理解成大模型。

它只是一个“本地轻量文本编码器”，作用是：

```text
把一段中文文本 -> 转成一个数字向量
```

为什么需要它？

因为 Milvus 不能直接拿自然语言句子做近邻搜索，它搜索的是向量。
所以写入 Milvus 之前，必须先把每条 `text` 变成向量。

这个 embedder 的核心思路不是深度学习，而是“概念命中”。

它内部预先定义了一组概念，例如：

- 开发环境
- 虚拟环境
- python
- database
- 向量检索
- 语义检索
- rag
- 过滤
- 数据管道
- 数据治理

每个概念还对应一组同义词或相关词。

例如：

- `开发环境` 对应：
  - `开发环境`
  - `编程环境`
  - `环境配置`

这意味着：

- “怎么搭建编程环境”
- “如何配置开发环境”

会命中同一个语义概念组，因此生成的向量更接近。

所以这个类的目标不是“真正理解语言”，而是：

```text
用一组固定概念，把文本投影到一个小的语义特征空间里
```

---

## Step 5: `encode_text()` 怎么把文本变成向量

真正把文本编码成向量的函数是：

- `phase3_demo/src/vector_store.py`
- 函数：`encode_text(text)`

它可以拆成 4 个动作。

### 5.1 文本归一化

先做标准化处理：

- 转成小写
- 压缩空白字符

目的是让后面的匹配更稳定。

### 5.2 统计每个概念组的命中情况

函数会遍历 `_concepts` 里的每一组同义词，然后问：

```text
当前文本里，这组词命中了多少次？
```

所以到这一步时，向量可以粗略理解成：

```text
[
  开发环境命中次数,
  虚拟环境命中次数,
  python 命中次数,
  database 命中次数,
  向量检索命中次数,
  ...
]
```

### 5.3 如果一个概念都没命中，才启用 fallback

为了避免完全未知文本变成全零向量，代码里还有一层 fallback。

但它的规则是：

- 如果概念特征已经命中，就不用 fallback
- 只有“所有概念都没命中”时，才加一层很弱的兜底特征

这样做是为了避免 fallback 压过真正的语义特征。

### 5.4 最后做归一化

函数最后会把向量做 L2 归一化。

你现在不用记数学细节，只要记住：

```text
归一化后，更适合按方向相似度比较
```

所以 `encode_text()` 的整体作用可以概括成：

```text
文本
-> 统计它命中了哪些语义概念
-> 必要时加一点兜底特征
-> 归一化
-> 得到向量
```

这就是本 Demo 里的 embedding 过程。

---

## Step 6: 怎么连接 Milvus Lite

`build_demo.py` 的下一步会调用：

- `phase3_demo/src/vector_store.py`
- 函数：`connect_client(db_path)`

这个函数做的事情很少：

1. 确保 `phase3_demo/demo.db` 所在目录存在
2. 返回 `MilvusClient(db_path)`

这意味着：

- 它不是在连远程 Milvus 服务
- 它是在连本地文件型 Milvus Lite 数据库

所以你可以把这一步理解成：

```text
打开本地的 Milvus Lite 数据库文件
```

---

## Step 7: 怎么创建 collection

连接完数据库后，`build_demo.py` 会调用：

- `phase3_demo/src/vector_store.py`
- 函数：`recreate_collection(client, collection_name, dimension)`

这个函数的作用是定义“这张向量表长什么样”。

它会先检查：

- 如果 collection 已经存在，就先删掉

这样每次重新跑 `build_demo.py`，都能得到一个干净结果。

然后它开始定义 schema，核心字段包括：

- `id`
- `text`
- `category`
- `source`
- `vector`

最关键的一点是：

```text
Milvus 里不只是存 vector
也一起存 text/category/source 这些标量字段
```

否则你后面搜索到了一个向量，也不知道它对应哪条文本。

接着它会给 `vector` 字段配置索引参数：

- `metric_type="COSINE"`
- `index_type="AUTOINDEX"`

这一步的本质是：

```text
告诉 Milvus：
以后我要按向量相似度来搜，请把 vector 字段按向量检索方式组织好
```

最后调用 `create_collection(...)`，collection 才真正创建完成。

此时你可以把状态理解成：

```text
本地 demo.db 已打开
-> collection schema 已定义
-> 向量索引方式已指定
-> 但里面还没有插入任何文档
```

---

## Step 8: `insert_documents()` 怎么把数据写进去

最后一步是：

- `phase3_demo/src/vector_store.py`
- 函数：`insert_documents(client, collection_name, docs, embedder)`

它可以拆成 3 个动作。

### 8.1 先把所有文档编码成向量

函数会调用：

- `encode_documents(docs)`

也就是：

```text
对 docs 里的每一条文档
-> 取出 text
-> 调用 encode_text()
-> 得到一组向量
```

所以这一步后，你可以想成：

```python
docs = [doc1, doc2, doc3, ...]
vectors = [vec1, vec2, vec3, ...]
```

它们是一一对应的。

### 8.2 把文档字段和向量拼成插入行

函数会调用：

- `build_insert_rows(docs, vectors)`

原来你手里有两份东西：

1. 原始文档
   - `id`
   - `text`
   - `category`
   - `source`

2. 生成出来的向量
   - `vector`

这个函数会把两部分拼成 Milvus 可接受的完整记录：

```python
{
    "id": ...,
    "text": ...,
    "category": ...,
    "source": ...,
    "vector": ...
}
```

也就是：

```text
把文本世界的数据
变成向量数据库能接受的结构
```

### 8.3 真正写入 Milvus

最后调用：

- `client.insert(...)`
- `client.flush(...)`

它们的含义是：

- `insert(...)`：把记录写进 collection
- `flush(...)`：把写入刷到存储层，确保数据可用

所以整个写入流程可以压缩成：

```text
docs
-> vectors
-> rows
-> insert
-> flush
```

---

## Step 9: 到这里，建库流程就完成了

建库线完整走完以后，数据库里已经有：

- `id`
- `text`
- `category`
- `source`
- `vector`

也就是说，Phase 3 在这一刻已经从：

```text
原始 JSON 文本
```

变成了：

```text
可被向量搜索的 Milvus Lite collection
```

你现在可以把整个建库过程记成这一条主线：

```text
sample_docs.json
-> load_documents()
-> embedder.encode_documents()
-> build_insert_rows()
-> Milvus insert + flush
```

到这里为止，我们完成的是“建库线”。

下一步如果继续看代码，就该进入“查询线”：

- `search_demo.py`
- 为什么它会跑出三段结果
- 关键词检索和向量检索分别怎么走

---

## Step 10: 查询线的总入口

查询入口在：

- `phase3_demo/src/search_demo.py`
- 函数：`run_demo_queries()`

这个函数不是只跑一种搜索，而是一次性组织 3 类查询：

1. `keyword_results`
   - 关键词检索
   - 查询词：`PostgreSQL`

2. `vector_results`
   - 向量检索
   - 查询词：`怎么搭建编程环境`

3. `filtered_results`
   - 带过滤条件的向量检索
   - 查询词：`怎么做语义搜索`
   - 过滤条件：`category="ai"`

所以你可以先把查询线理解成：

```text
search_demo.py
-> 连续跑三种不同风格的查询
-> 最后把三组结果一起返回
```

这三条线分别想证明：

- 关键词检索适合精确术语命中
- 向量检索适合语义相近匹配
- 向量检索 + metadata filter 适合业务受限召回

---

## Step 11: 关键词检索怎么工作

在 `search_demo.py` 里，关键词检索这一行是：

- `keyword_search("PostgreSQL", docs, top_k=3)`

真正实现是在：

- `phase3_demo/src/retrieval.py`
- 函数：`keyword_search(query, docs, top_k=5)`

它的逻辑非常简单，可以拆成 4 步：

### 11.1 先把查询词转成小写

这样后面的匹配更稳定。

### 11.2 遍历每一条文档

它会对 `docs` 里的每一条记录检查：

```text
这条文档的 text 里有没有出现 query？
```

### 11.3 用出现次数当分数

代码本质上是在做：

```python
score = doc["text"].lower().count(query_lower)
```

也就是：

- 没出现，分数就是 0
- 出现 1 次，分数就是 1
- 出现更多次，分数更高

如果分数大于 0，就把这条文档收进结果里，并补上：

- `score`
- `search_type = "keyword"`

### 11.4 排序并截断

最后会：

- 按分数倒序排序
- 取前 `top_k` 条

所以关键词检索线可以记成：

```text
原始 docs
-> 看 text 里有没有 query
-> 用出现次数打分
-> 排序
-> 返回前 3 条
```

这一条线完全没有经过 Milvus，也没有用向量。
它只是一个对照组，用来展示“精确词面命中”时关键词检索的直接性。

---

## Step 12: 向量检索怎么工作

在 `search_demo.py` 里，普通向量检索这一段是：

- `vector_search(client, COLLECTION_NAME, embedder, "怎么搭建编程环境", top_k=3)`

真正实现是在：

- `phase3_demo/src/vector_store.py`
- 函数：`vector_search(...)`

它和关键词检索的根本区别是：

```text
它不直接看 text 里有没有某个词
而是先把 query 变成向量，再去 Milvus 里做近邻搜索
```

先看它的大流程：

### 12.1 先把查询文本编码成向量

函数第一步是：

```text
query text
-> embedder.encode_text(query)
-> query_vector
```

这是必要步骤，因为 Milvus 搜索的是向量，不是自然语言句子。

### 12.2 组装过滤条件

在普通向量检索这条线里，没有传 `category`，所以过滤表达式是空的。

也就是说：

- 只按向量相似度搜
- 没有额外 metadata 约束

### 12.3 调用 Milvus 做搜索

核心动作是：

```text
拿 query_vector
去 collection 的 vector 字段里
找 top_k 个最相近的向量
并把对应记录的 id/text/category/source 一起拿回来
```

所以普通向量检索线可以记成：

```text
自然语言问题
-> 编码成 query_vector
-> 到 Milvus 的 vector 字段里做近邻搜索
-> 返回最相似的几条文档
```

这和关键词检索最大的不同就在于：

- 关键词检索比较字面词
- 向量检索比较 query 向量和 document 向量在向量空间里的相似度

---

## Step 13: 为什么 Milvus 返回结果还要再整理一遍

`vector_search()` 调完 Milvus 以后，还做了一层结果整理。

原因是：

- Milvus 返回的是它自己的原始 hit 结构
- 这和关键词检索返回的 Python dict 结构不一样

所以代码后面会：

1. 取出命中的 hits
2. 遍历每个 hit
3. 提取其中关心的字段
4. 转成统一结果结构

最终每条结果都会被整理成：

```python
{
    "id": ...,
    "text": ...,
    "category": ...,
    "source": ...,
    "score": ...
}
```

这一步的本质是：

```text
把 Milvus 原始结果
翻译成业务侧更好用的统一结构
```

这样后面才能和关键词检索结果一起格式化、展示和比较。

所以普通向量检索的完整链路是：

```text
query text
-> encode_text(query)
-> Milvus search(vector field)
-> raw hits
-> 统一结果结构
```

---

## Step 14: 带过滤条件的向量检索怎么工作

在 `search_demo.py` 里，第三条查询线是：

- `vector_search(client, COLLECTION_NAME, embedder, "怎么做语义搜索", top_k=3, category="ai")`

这一条和普通向量检索很像，还是调用同一个 `vector_search(...)`。

区别在于这次多传了：

- `category="ai"`

这个参数会被转换成过滤表达式：

```text
category == "ai"
```

然后传给 Milvus 的 `filter` 参数。

所以这条线的真正含义不是“另一种搜索算法”，而是：

```text
还是向量搜索
但额外加了一个标量过滤条件
```

你可以把它理解成：

```text
先问：哪些文档和 query 在语义上接近？
再问：这些候选里，哪些 category 是 ai？
```

这就是为什么 Phase 3 里不只是存 `vector`，也一起存：

- `category`
- `source`
- `text`

因为没有这些标量字段，就做不了这种 metadata filter。

这条查询线最接近真实系统的工作方式，也就是：

```text
向量召回 + metadata filter
```

---

## Step 15: 为什么最终会打印成三段输出

终端里你看到的三段结果，不是 Milvus 直接打印出来的，而是由两个函数格式化得到的：

- `_format_section(...)`
- `build_demo_report(...)`

### 15.1 `_format_section(...)` 在做什么

这个函数负责把“一组结果”格式化成一段可读文本。

它会输出：

- 标题，例如 `Keyword Search`
- Query
- 每条结果的：
  - 排名
  - `id`
  - `category/source`
  - `score`
  - `text`

所以它的本质是：

```text
把结构化结果列表
变成人能直接看的报告文本
```

### 15.2 `build_demo_report(...)` 在做什么

这个函数会固定拼出三段：

1. `Keyword Search`
2. `Vector Search`
3. `Filtered Vector Search`

然后把它们拼成一个完整的大字符串返回。

所以最终终端输出的形成过程是：

```text
三组已经整理好的结果
-> 分别格式化成三段文本
-> 拼成完整报告
-> print 到终端
```

---

## Step 16: 查询线的完整闭环

到这里，查询线可以完整写成：

```text
run_demo_queries()
-> 跑三类查询
   -> keyword_search()
   -> vector_search()
   -> vector_search() + category filter
-> 得到三组结构化结果
-> build_demo_report()
-> 生成三段文本
-> print 到终端
```

---

## Step 17: 用一句人话总结整个 Phase 3

如果你以后要自己复述 Phase 3，我建议用下面这段话：

```text
Phase 3 做的是一个最小语义检索 Demo。

它先从本地 JSON 文件读取一批中文技术文本，
每条文本都带有 id、text、category、source。

然后用一个本地轻量 embedder，
把每条 text 转成向量。

接着把原始字段和对应向量一起写进 Milvus Lite，
在本地建立一个可搜索的 collection。

查询时，它同时跑三条线：

第一条是关键词检索，
直接在原始文本里做词面匹配，
用来展示精确术语命中的效果。

第二条是向量检索，
先把用户问题转成向量，
再去 Milvus 里找最接近的文档向量，
用来展示语义相近检索。

第三条是带 metadata filter 的向量检索，
也就是在向量搜索的基础上，
再加上 category 这样的标量约束，
用来展示真实业务里常见的“语义召回 + 过滤”组合。

最后程序把三组结果整理成统一格式，
打印成三段输出，
让你能直接比较：
关键词检索、向量检索、以及带过滤的向量检索分别擅长什么。
```

如果你想再压缩成一句话版本，那就是：

```text
Phase 3 就是在本地用 Milvus Lite 跑通“文本 -> 向量 -> 入库 -> 检索 -> 过滤 -> 输出对比”的完整最小链路。
```
