# Phase 3 Milvus Lite Demo Design

## Goal
构建一个最小可运行的中文语义检索 Demo，使用 `Python + Milvus Lite` 展示从文本数据准备、embedding、向量入库，到 `keyword search`、`vector search`、`metadata filter` 对比的完整链路。

## Scope
- 数据规模控制在 `100-300` 条短文本。
- 使用本地文件型 Milvus Lite，避免容器和分布式环境噪音。
- 使用轻量多语言 embedding 模型，优先保证中文文本和查询可用。
- 提供统一输出格式，便于直接对比关键词检索与向量检索结果。
- 交付物为可运行脚本、样本数据、README、示例结果，不做 Web UI。

## Non-Goals
- 不做真实生产级数据集和召回评测。
- 不做复杂中文分词、倒排索引优化或 reranker 集成。
- 不引入完整 Milvus Standalone 或集群部署。
- 不在 Phase 3 做 embedding 模型优劣评测。

## Approach Options

### Option 1: Python + Milvus Lite + Local Sample Data
优点：
- 环境最轻，最快跑通完整链路。
- 学习重点集中在检索流程本身，而不是部署问题。
- 适合当前 48 小时计划中的“快速建立直觉”目标。

缺点：
- 与生产部署存在距离。
- 样本规模较小，无法体现真正的大规模 ANN 调优问题。

### Option 2: Python + Local Milvus Standalone
优点：
- 更接近正式部署和后续架构阅读。
- 后面衔接组件职责时更自然。

缺点：
- 容器、依赖、服务编排会显著增加 Phase 3 的环境成本。

### Option 3: Pure In-Memory Vector Search Script
优点：
- 依赖最少，实验最简单。

缺点：
- 偏离本阶段目标，无法帮助理解 Milvus 的实际使用方式。

## Decision
采用 Option 1：`Python + Milvus Lite + Local Sample Data`。

原因：
- 它最符合 Phase 3 的学习目标，即先获得“向量检索到底在做什么”的清晰直觉。
- 它保留了真实向量数据库的使用体验，但去掉了容器和集群环境噪音。

## Demo Design

### Dataset
- 使用一份本地中文样本文本集，主题覆盖：
  - Python 开发
  - 数据库
  - 数据工程
  - AI 应用
- 每条样本记录至少包含：
  - `id`
  - `text`
  - `category`
  - `source`

数据集设计目标：
- 能构造“字面不同但语义接近”的样本，用于展示向量检索优势。
- 能构造“术语完全一致”的样本，用于展示关键词检索优势。
- 能构造可被 `category` 或 `source` 过滤的样本，用于展示 metadata filter。

### Data Flow
1. 从本地 `JSON` 文件加载样本数据。
2. 对每条 `text` 生成 embedding。
3. 在 Milvus Lite 中创建 collection 并写入：
   - `id`
   - `text`
   - `category`
   - `source`
   - `vector`
4. 对查询文本同时执行两条路径：
   - `keyword search`：简单词面包含或匹配计分
   - `vector search`：查询 embedding 后在 Milvus Lite 中执行相似检索
5. 可选叠加 metadata filter，例如 `category == "database"`。
6. 将两种检索结果整理成统一输出格式，便于对比。

### Query Scenarios
至少保留三类演示查询：
1. 同义表达查询
   - 目标：体现 `vector search` 能召回字面不同但语义接近的文本。
2. 精确术语查询
   - 目标：体现 `keyword search` 在词面精确命中时更直接。
3. 带 metadata filter 的查询
   - 目标：体现向量召回和标量过滤组合的价值。

## File Structure
- `phase3_demo/README.md`
  - 说明依赖、安装、运行方法和如何理解结果。
- `phase3_demo/data/sample_docs.json`
  - 小规模样本数据集。
- `phase3_demo/src/build_demo.py`
  - 负责加载数据、生成 embedding、创建 collection、写入 Milvus Lite。
- `phase3_demo/src/search_demo.py`
  - 负责关键词检索、向量检索、metadata filter 检索和结果展示。
- `phase3_demo/tests/`
  - 放最小自动化测试。
- `phase3_demo/results/`
  - 保存一份示例输出，供后续复盘和学习笔记引用。

## Dependencies
- `Python 3.10+`
- `pymilvus`
- `sentence-transformers`
- `pytest`

依赖选择原则：
- Phase 3 以“理解链路”为主，不做复杂基础设施选型。
- embedding 模型先选轻量多语言模型，优先可用性和运行成本。

## Testing Strategy
先做最小 TDD 闭环，再逐步扩展：

1. 数据加载测试
   - 样本数据能被正确读取并映射为预期字段结构。
2. 关键词检索测试
   - 在精确术语查询中能命中包含对应术语的文本。
3. 结果格式测试
   - 检索结果统一包含 `id/text/category/source/score` 等核心字段。
4. 向量检索测试
   - 关注“语义相近样本进入前几名”而不是分数绝对值或固定排序。

测试边界：
- 不把断言写成“模型输出完全固定顺序”。
- 重点验证检索链路和结果结构是否符合预期。

## Success Criteria
- 可以用一条命令完成数据构建和查询演示。
- 同一查询下，能看到 `keyword search` 和 `vector search` 返回不同结果。
- 至少有一个例子清楚体现向量检索对同义表达的优势。
- 至少有一个例子清楚体现关键词检索对精确术语的优势。
- 至少有一个例子清楚体现 metadata filter 的作用。
- README 足够清晰，未来会话可以在几分钟内重新跑起 Demo。

## Risks And Mitigations
- 风险：中文 embedding 效果不稳定。
  - 缓解：优先选择轻量多语言模型，并手工设计样本与查询，避免任务过难。
- 风险：Milvus Lite 或模型依赖安装较慢。
  - 缓解：将实现拆成独立脚本和测试，先完成数据和接口骨架，再跑依赖验证。
- 风险：关键词检索过于简陋导致对比失真。
  - 缓解：明确其目标只是提供词面对照基线，不作为生产检索方案。

## Open Questions
- 轻量 embedding 模型的最终名称在实现前再确认，以本机依赖可获取性为准。
- 样本主题先覆盖四类技术文本；如果中文语义区分不够明显，再补充少量对比样本。
