# Milvus-First Research Replan Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current post-Phase-3 learning track with a Milvus-first research sequence focused on storage format, index organization, query execution, and compute-layer mechanics.

**Architecture:** Freeze the existing RAG-platform and RedDB-integration threads as background context, then execute a linear Milvus research track. Each phase produces a compact output artifact that becomes input for the next phase.

**Tech Stack:** Markdown planning files, Milvus official docs, local notes, architecture diagrams, Milvus source tree references where needed

---

## File Structure Map

- Modify: `task_plan.md`
  - Replace the remaining platform-first phases with Milvus-focused research phases.
- Modify: `findings.md`
  - Capture the new scope, the frozen threads, and the Milvus-specific research questions.
- Modify: `progress.md`
  - Record the replanning event and the new current checkpoint.
- Create: `docs/superpowers/specs/2026-03-16-milvus-first-research-replan-design.md`
  - Persist the approved reasoning behind the replan.
- Create: `docs/milvus_version_and_terms.md`
  - Phase A output for version lock and terminology baseline.
- Create: `docs/milvus_mixed_data_model.md`
  - Phase B output for vector/scalar/JSON storage model.
- Create: `docs/milvus_storage_and_index_map.md`
  - Phase C output for storage organization and index carriers.
- Create: `docs/milvus_query_engine_workflow.md`
  - Phase D output for query engine and compute-layer workflow.
- Create: `docs/milvus_future_integration_questions.md`
  - Phase E output for future system-integration abstraction.

## Chunk 1: Replan The Current Track

### Task 1: Freeze The Old Threads And Persist The New Mainline

**Files:**
- Create: `docs/superpowers/specs/2026-03-16-milvus-first-research-replan-design.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Save the replan rationale**

Write down:
- why the old `RAG platform + Milvus validation` mainline no longer matches the current goal
- which threads are frozen
- what the new Milvus-first research phases are

- [ ] **Step 2: Update the task plan**

Replace the remaining active phases with:
- Phase A: version lock and terminology
- Phase B: mixed data model
- Phase C: storage and index organization
- Phase D: query engine and compute layer
- Phase E: future integration abstractions

- [ ] **Step 3: Update findings and progress**

Record:
- RedDB is out of scope for now
- RAG platform is background only for now
- the new immediate focus is Milvus storage model plus compute-layer mechanics

- [ ] **Step 4: Verify checkpoint consistency**

Run: `sed -n '1,220p' task_plan.md && sed -n '1,220p' progress.md`
Expected: both files point to `Milvus-first` research as the current mainline.

## Chunk 2: Build The Milvus Research Baseline

### Task 2: Produce Phase A Output

**Files:**
- Create: `docs/milvus_version_and_terms.md`
- Modify: `progress.md`

- [ ] **Step 1: Lock the research baseline**

Record:
- Milvus version branch under study
- doc version under study
- which terminology list is mandatory for later phases

- [ ] **Step 2: Create the glossary**

Include at least:
- segment
- growing / sealed
- WAL
- flush
- handoff
- compaction
- shard / channel
- query plan

- [ ] **Step 3: Sync progress**

Update the checkpoint once the version/term baseline is complete.

### Task 3: Produce Phase B Output

**Files:**
- Create: `docs/milvus_mixed_data_model.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Explain the schema model**

Cover:
- collection
- field
- vector field
- scalar field
- JSON field

- [ ] **Step 2: Explain mixed storage implications**

Clarify how vector search and scalar/JSON filtering coexist in the logical model.

- [ ] **Step 3: Sync findings and progress**

Capture the stable conclusions and unresolved questions.

## Chunk 3: Deepen Into Storage And Query Execution

### Task 4: Produce Phase C Output

**Files:**
- Create: `docs/milvus_storage_and_index_map.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Map data organization**

Cover:
- WAL
- growing segments
- sealed segments
- persisted data and index artifacts

- [ ] **Step 2: Map index carriers**

Cover:
- vector indexes
- scalar/inverted-style indexes
- primary-key lookup aids

- [ ] **Step 3: Sync findings and progress**

Record what is understood and what still needs validation.

### Task 5: Produce Phase D Output

**Files:**
- Create: `docs/milvus_query_engine_workflow.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Trace the query path**

Explain:
- request entry
- planning
- routing
- segment-level execution
- result merge/reduce

- [ ] **Step 2: Explain compute-layer responsibilities**

Clarify the roles of the main runtime components involved in search/query.

- [ ] **Step 3: Sync findings and progress**

Update the current checkpoint when the workflow note is complete.

## Chunk 4: Prepare For Future Integration Work

### Task 6: Produce Phase E Output

**Files:**
- Create: `docs/milvus_future_integration_questions.md`
- Modify: `task_plan.md`
- Modify: `progress.md`

- [ ] **Step 1: Extract the future-facing abstractions**

Summarize:
- data organization boundary
- index boundary
- storage/compute boundary
- query execution boundary

- [ ] **Step 2: Write the future question list**

The list should be suitable for later RedDB discussions without baking in RedDB assumptions now.

- [ ] **Step 3: Confirm the handoff**

Run: `sed -n '1,220p' task_plan.md`
Expected: the task plan clearly shows a Milvus-first track with the future integration discussion deferred.
