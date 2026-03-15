# Phase 3 Demo: Milvus Lite Semantic Search

这个目录包含一个最小可运行的 Phase 3 学习 Demo，用来演示：
- 小规模中文文本数据准备
- 向量入库到 Milvus Lite
- `keyword search` 与 `vector search` 的对比
- `metadata filter` 对召回范围的约束

## What This Demo Uses

- `pymilvus`
- `milvus-lite`
- 一个本地轻量 embedder

这里没有下载大模型 embedding，而是用了本地轻量向量编码逻辑。这样做的目的不是追求最强语义效果，而是先稳定演示 Milvus Lite 的建库、写入、搜索和过滤链路。

如果后面你要把它升级成更真实的检索实验，可以把 `phase3_demo/src/vector_store.py` 里的 `LightweightChineseEmbedder` 替换成正式 embedding 模型。

## Install

```bash
python3 -m pip install -r phase3_demo/requirements.txt
```

## Build The Demo Database

```bash
python3 phase3_demo/src/build_demo.py
```

预期结果：
- 在 `phase3_demo/demo.db` 创建或重建本地 Milvus Lite 数据库
- 创建 `phase3_demo_docs` collection
- 把 `phase3_demo/data/sample_docs.json` 中的样本数据写入库中

## Run The Demo Queries

```bash
python3 phase3_demo/src/search_demo.py
```

输出会包含三个部分：

1. `Keyword Search`
   - 用 `PostgreSQL` 这样的精确术语查询
   - 目的是展示关键词搜索在精确词面命中时的直接性

2. `Vector Search`
   - 用 `怎么搭建编程环境` 这样的自然语言问题查询
   - 目的是展示向量检索可以把“搭建编程环境”和“配置开发环境”这类表达拉近

3. `Filtered Vector Search`
   - 用 `怎么做语义搜索` 加上 `category=ai`
   - 目的是展示向量召回和 metadata filter 的组合效果

## Files

- `data/sample_docs.json`
  - 133 条中文样本文本
- `src/demo_data.py`
  - 数据加载
- `src/retrieval.py`
  - 关键词检索与结果标准化
- `src/vector_store.py`
  - 轻量 embedder、Milvus Lite connection、collection build、vector search
- `src/build_demo.py`
  - 建库脚本
- `src/search_demo.py`
  - 查询脚本
- `results/sample_run.md`
  - 一次实际运行输出的摘要

## Notes

- 这是学习用 Demo，不是生产级检索系统。
- 这里的 `keyword search` 只是非常简单的词面基线，不代表正式搜索实现。
- 这里的本地轻量 embedder 只用于稳定演示流程；后续如果你要做 Phase 4 或真实业务实验，应替换成正式 embedding 模型。
