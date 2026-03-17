# Milvus-First Research Replan Design

## Goal
将当前学习主线从“平台接入草图与后续对接”重排为“先研究 Milvus 本体如何解决向量场景问题”，使后续任何 RedDB 对接讨论都建立在稳定的底层心智模型之上。

## Trigger
- 用户新增了三个后续议题：
  - 向量、标量、JSON/BSON 等的混合存储格式
  - 倒排、向量、正排索引在 RedDB 中的存储方式
  - Milvus 计算层和 RedDB 对接移植的技术路线
- 但用户随后进一步收窄当前目标：
  - 暂时不要讨论 RedDB
  - 暂时不要讨论 RAG 平台
  - 先只研究 Milvus 自身对向量场景的解决方式

## Problem
原计划的主轴已经是：
- 先形成平台接入草图
- 再用 Milvus 机制去校正

这与当前目标冲突。用户现在不是要优先形成平台方案，而是要先理解：
- 向量数据如何被组织、存储和索引
- 混合字段如何在 Milvus 中表达
- 查询引擎和计算层如何工作

如果继续沿用原来的 `Phase 4A -> Phase 5 -> Phase 4B -> Phase 6` 结构，后续研究会持续被 `RAG 平台` 和 `RedDB 对接` 叙事牵引，无法形成纯粹的 Milvus 底层研究主线。

## Decision
当前主线切换为 `Milvus-first` 研究路线：

- 冻结 `RAG 平台接入草图`
- 冻结 `RedDB 对接/移植路线`
- 先只围绕 Milvus 本体建立底层技术逻辑

## What Gets Frozen

### Frozen Background 1: Notes RAG Platform Draft
- 已完成的 `Phase 4A notes RAG` spec 保留为背景材料
- 当前不再继续拆执行计划
- 当前不再作为学习主轴推进

### Frozen Background 2: RedDB Integration Discussion
- 当前不讨论 RedDB 的存储承载方式
- 当前不讨论 Milvus 计算层如何移植/对接到 RedDB
- 等用户拿到 RedDB 资料后，再新开一条独立讨论线

## New Mainline

### Phase A: Version Lock And Terminology Baseline
- 锁定当前研究所依据的 Milvus 版本与文档版本
- 建立统一术语表：
  - segment
  - growing / sealed
  - WAL
  - flush
  - handoff
  - compaction
  - shard / channel
  - Query Node / Data Node / Streaming Node / Proxy
  - query plan
- 目标：避免后续因版本漂移或术语误解导致阅读混乱

### Phase B: Data Model And Mixed Storage Format
- 研究 Milvus 如何表达：
  - vector fields
  - scalar fields
  - JSON fields
- 明确 collection / schema / field 在混合数据模型中的角色
- 暂不讨论 RedDB/BSON 的具体承载实现
- 目标：建立“Milvus 如何组织混合数据”的第一层模型

### Phase C: Storage Organization And Index Carriers
- 研究数据与索引在 Milvus 中如何被组织和承载
- 重点包括：
  - growing / sealed segment
  - WAL 与持久化关系
  - 对象存储中的数据文件与索引文件
  - 向量索引、标量/倒排类索引、主键查询辅助结构的承载方式
- 目标：形成“数据如何落地、索引如何挂接”的结构性认识

### Phase D: Query Engine And Compute Layer Workflow
- 研究 Milvus 查询引擎和计算层如何工作
- 重点包括：
  - 请求入口与路由
  - 查询计划
  - growing/sealed 数据查询
  - 多 segment / 多 shard 结果归并
  - 检索与过滤如何结合
- 目标：形成“从请求到结果”的完整执行链路

### Phase E: Abstract Lessons For Future Integration
- 这一步不是讨论 RedDB 方案
- 只抽象出未来做任何系统对接时一定要回答的问题：
  - 数据组织抽象
  - 索引承载抽象
  - 存储/计算边界
  - 查询执行抽象
- 目标：把 Milvus 研究成果沉淀成后续对接前的分析框架

## Recommended Deliverables
- 一份 Milvus 版本与术语基线笔记
- 一页 Milvus 混合数据模型说明
- 一张数据与索引承载关系图
- 一张查询执行时序图
- 一页“后续系统对接前必须回答的问题清单”

## Why This Order

### Option 1: 保留旧主线，只把 Milvus 研究插入现有阶段
优点：
- 改动最小

缺点：
- 主轴仍会被 RAG 平台与 RedDB 对接牵引
- 当前研究目标不够纯粹

### Option 2: 切换为纯 Milvus 本体研究主线
优点：
- 完全对齐用户最新优先级
- 先补足底层心智模型，再谈其他系统
- 后续对接讨论更不容易建立在错误抽象上

缺点：
- 需要主动冻结已有但未继续推进的平台方案

### Option 3: 同时推进 Milvus、RedDB、对接路线三条线
优点：
- 表面上覆盖更全面

缺点：
- 研究问题空间过大
- 容易每条线都停留在半懂状态

## Recommendation
采用 Option 2：先切到纯 Milvus 本体研究主线。

## Success Criteria
- 当前计划文件不再把 `RAG 平台` 或 `RedDB 对接` 作为近期主任务
- 后续研究围绕 Milvus 的：
  - 数据模型
  - 混合存储
  - 索引承载
  - 查询执行
  - 计算层工作流
- 形成的输出能够在未来支撑 RedDB 讨论，但当前不提前绑定任何 RedDB 假设

## One-Sentence Summary
当前主线重排为：先研究 Milvus 自身如何组织数据、构建索引、执行查询与承载计算层，再把这些结论留作未来 RedDB 对接讨论的前置基础。
