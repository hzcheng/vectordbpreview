# Learning Sequence Reorder Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder the remaining learning phases so the platform integration design lands first, then Milvus architecture and source study are used to validate and refine it.

**Architecture:** Keep the existing 48-hour structure, but split the old Phase 4 into a draft-and-revise loop around Milvus architecture study. Use the persistent planning files as the source of truth, and produce one focused platform draft before any deep source-code reading.

**Tech Stack:** Markdown planning files, Milvus official docs, local study notes, Phase 3 demo outputs

---

## File Structure Map

- Modify: `task_plan.md`
  - Replace the old linear `Phase 4 -> Phase 5 -> Phase 6` order with `Phase 4A -> Phase 5 -> Phase 4B -> Phase 6`.
- Modify: `findings.md`
  - Capture the rationale for the new sequence and the specific validation questions for Milvus study.
- Modify: `progress.md`
  - Record the sequence adjustment, current checkpoint, and next recommended action.
- Create: `docs/superpowers/specs/2026-03-15-learning-sequence-reorder-design.md`
  - Persist the approved reasoning behind the sequence change.
- Create: `docs/platform_integration_draft.md`
  - Store the future Phase 4A platform integration draft.
- Create: `docs/milvus_validation_notes.md`
  - Store targeted validation notes from Phase 5 against the Phase 4A draft.

## Chunk 1: Persist The Sequence Change

### Task 1: Write The Approved Sequence Decision To Disk

**Files:**
- Create: `docs/superpowers/specs/2026-03-15-learning-sequence-reorder-design.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Save the accepted design rationale**

Write a short spec that explains:
- why the old plan was questioned
- why full reordering is not recommended
- why the recommended structure is `Phase 4A -> Phase 5 -> Phase 4B -> Phase 6`

- [ ] **Step 2: Sync the findings file**

Add the new stable findings:
- platform design should come before deep source reading when fast solution-shaping is the priority
- Milvus architecture study is most useful when driven by concrete platform questions

- [ ] **Step 3: Sync the progress file**

Record:
- the user-approved sequence change
- the new checkpoint
- the next recommended action

- [ ] **Step 4: Verify planning files are consistent**

Run: `sed -n '1,220p' task_plan.md && sed -n '1,220p' progress.md`
Expected: both files point to `Phase 2 收尾 / Phase 4A 准备` or equivalent wording without contradiction.

## Chunk 2: Execute The Next Learning Segment

### Task 2: Close Phase 2 With A Compact Scenario Matrix

**Files:**
- Create: `docs/scenario_problem_solution_matrix.md`
- Modify: `task_plan.md`
- Modify: `progress.md`

- [ ] **Step 1: Draft the matrix**

Include rows for:
- RAG
- semantic search
- recommendation
- multimodal retrieval
- deduplication / clustering
- recall + rerank

- [ ] **Step 2: Mark the Phase 2 deliverable complete**

Update `task_plan.md` so the pending item under Phase 2 is checked off once the matrix exists.

- [ ] **Step 3: Record completion in the progress log**

Add the output path and the completion timestamp.

### Task 3: Produce The Platform Integration Draft (Phase 4A)

**Files:**
- Create: `docs/platform_integration_draft.md`
- Modify: `task_plan.md`
- Modify: `progress.md`

- [ ] **Step 1: Write the platform draft outline**

Sections:
- data objects
- vectorized units
- schema and primary keys
- metadata and filtering fields
- embedding generation timing
- update propagation
- retrieval path
- rerank boundary
- access control boundary

- [ ] **Step 2: Write the draft with explicit assumptions**

Every major section should include:
- current proposal
- why it is proposed
- what still needs Milvus validation

- [ ] **Step 3: Update the checkpoint**

Set the current checkpoint to a Phase 4A-complete state once the draft exists and the assumptions are written down.

## Chunk 3: Validate And Revise

### Task 4: Use Milvus Architecture Study To Validate The Draft (Phase 5)

**Files:**
- Create: `docs/milvus_validation_notes.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Read the architecture and data-processing docs with a question list**

Questions should be derived from the Phase 4A draft:
- online writes and indexing
- segment lifecycle
- compaction
- filter execution
- query fan-out
- cold/hot data handling

- [ ] **Step 2: Record pass/fail outcomes for each assumption**

Use a compact structure:
- assumption
- Milvus mechanism
- impact on platform draft

- [ ] **Step 3: Update findings and progress**

Capture which parts of the draft remain valid and which need revision.

### Task 5: Revise The Platform Draft (Phase 4B)

**Files:**
- Modify: `docs/platform_integration_draft.md`
- Modify: `task_plan.md`
- Modify: `progress.md`

- [ ] **Step 1: Revise the draft into v0.2**

Make the changes justified by `docs/milvus_validation_notes.md`.

- [ ] **Step 2: Mark the revised platform design milestone**

Update `task_plan.md` to show `Phase 4B` complete after the revision is finished.

- [ ] **Step 3: Prepare for focused source reading**

List the 3-5 remaining questions that require Phase 6 source-code study.

## Chunk 4: Focused Source Deep Dive

### Task 6: Restrict Phase 6 To Platform-Critical Questions

**Files:**
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Lock the source-reading scope**

Keep only questions that materially affect:
- update path design
- retrieval path design
- index lifecycle
- isolation or scaling boundaries

- [ ] **Step 2: Record concrete source-reading entry points**

Write down the exact modules, directories, or flows to inspect next.

- [ ] **Step 3: Confirm the handoff**

Run: `sed -n '1,220p' task_plan.md`
Expected: the plan clearly shows `Phase 4A -> Phase 5 -> Phase 4B -> Phase 6`.
