# Milvus 7-Theme Learning Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce seven Milvus learning documents that teach the user from concepts to code, with each theme mapped to the local source tree at `/Projects/work/vectordbpreview/milvus`.

**Architecture:** Execute one theme at a time. For each theme, first study the relevant local source directories and existing notes, then write a standalone markdown document that explains the topic, lists the key local directories and files, and gives a recommended reading order. Sync `task_plan.md`, `findings.md`, and `progress.md` after each theme so interrupted sessions can resume safely.

**Tech Stack:** Markdown docs, local Milvus source tree, existing learning notes, persistent progress files

---

## File Structure Map

- Modify: `task_plan.md`
  - Track the active theme and mark each theme complete.
- Modify: `findings.md`
  - Capture stable conclusions, source-tree mappings, and reading-order decisions.
- Modify: `progress.md`
  - Record each completed theme and the next theme to execute.
- Create: `docs/milvus_theme1_concepts.md`
  - Theme 1 output for concepts and source entrypoints.
- Create: `docs/milvus_theme2_architecture.md`
  - Theme 2 output for architecture and component boundaries.
- Create: `docs/milvus_theme3_write_path.md`
  - Theme 3 output for write flow and write-path components.
- Create: `docs/milvus_theme4_data_organization.md`
  - Theme 4 output for vector/scalar/JSON organization.
- Create: `docs/milvus_theme5_index_organization.md`
  - Theme 5 output for index organization and segment lifecycle.
- Create: `docs/milvus_theme6_query_architecture.md`
  - Theme 6 output for query-side architecture.
- Create: `docs/milvus_theme7_query_flow.md`
  - Theme 7 output for end-to-end query flow.

## Chunk 1: Theme 1 Concepts

### Task 1: Produce Theme 1 Concepts Document

**Files:**
- Create: `docs/milvus_theme1_concepts.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Read the current baseline documents**

Run: `sed -n '1,220p' docs/milvus_version_and_terms.md && sed -n '1,220p' phase1_vectors_basics.md`
Expected: the current concept baseline and earlier vector basics are visible.

- [ ] **Step 2: Inspect the local source tree for concept anchor points**

Run: `find milvus/internal milvus/pkg milvus/client -maxdepth 2 -type d | sed -n '1,200p'`
Expected: see candidate directories such as `internal/proxy`, `internal/datanode`, `internal/querynodev2`, `internal/storage`, `pkg/proto`, `client/milvusclient`.

- [ ] **Step 3: Identify concrete file entrypoints**

Run: `rg -n "Collection|Segment|Search|Query|Insert|Flush|Index" milvus/internal milvus/pkg/proto milvus/client -g '*.go' | sed -n '1,200p'`
Expected: get a first-pass list of files worth citing in the concepts document.

- [ ] **Step 4: Write the Theme 1 document**

Document sections must include:
- what problem each concept solves
- the minimum concept set
- how concepts relate
- local source directories
- key files
- recommended reading order

- [ ] **Step 5: Sync persistent state**

Update:
- `task_plan.md` to mark Theme 1 complete and Theme 2 current
- `findings.md` with the stable concept-to-source mapping
- `progress.md` with a Theme 1 completion entry

## Chunk 2: Theme 2 Architecture

### Task 2: Produce Theme 2 Architecture Document

**Files:**
- Create: `docs/milvus_theme2_architecture.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Read the current architecture baseline**

Run: `sed -n '1,240p' docs/milvus_version_and_terms.md && sed -n '1,240p' docs/milvus_storage_and_index_map.md`
Expected: architecture terms and storage/query-serving boundaries are in context.

- [ ] **Step 2: Inspect architecture-related source directories**

Run: `find milvus/internal -maxdepth 2 -type d | rg 'proxy|coord|query|data|streaming|root'`
Expected: the major runtime directories are listed.

- [ ] **Step 3: Identify architecture entry files**

Run: `find milvus/cmd milvus/internal -maxdepth 3 -type f | rg 'role|server|service|component|coord|proxy' | sed -n '1,200p'`
Expected: get the files that help explain process startup and component boundaries.

- [ ] **Step 4: Write the Theme 2 document**

Document sections must include:
- access layer, coordinators, workers, storage boundary
- component responsibilities
- local source directories
- key files
- recommended reading order

- [ ] **Step 5: Sync persistent state**

Update:
- `task_plan.md` to mark Theme 2 complete and Theme 3 current
- `findings.md` with the stable architecture mapping
- `progress.md` with a Theme 2 completion entry

## Chunk 3: Theme 3 And Theme 4

### Task 3: Produce Theme 3 Write Path Document

**Files:**
- Create: `docs/milvus_theme3_write_path.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Inspect write-path directories**

Run: `find milvus/internal -maxdepth 2 -type d | rg 'proxy|datanode|datacoord|streaming|flush|storage'`
Expected: see the main write-path directories.

- [ ] **Step 2: Identify write-path files**

Run: `rg -n "Insert|Flush|Seal|Segment|Sync|Write" milvus/internal/proxy milvus/internal/datanode milvus/internal/datacoord milvus/internal/streamingnode milvus/internal/storage -g '*.go' | sed -n '1,220p'`
Expected: get candidate files for request entry, write processing, and sealing/flush behavior.

- [ ] **Step 3: Write the Theme 3 document**

Document sections must include:
- request entry
- WAL/message path
- growing to sealed transition
- local source directories
- key files
- recommended reading order

- [ ] **Step 4: Sync persistent state**

Update:
- `task_plan.md` to mark Theme 3 complete and Theme 4 current
- `findings.md` with write-path conclusions
- `progress.md` with a Theme 3 completion entry

### Task 4: Produce Theme 4 Data Organization Document

**Files:**
- Create: `docs/milvus_theme4_data_organization.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Read the current mixed-model baseline**

Run: `sed -n '1,260p' docs/milvus_mixed_data_model.md`
Expected: collection/schema/field baseline is visible.

- [ ] **Step 2: Inspect data-organization source directories**

Run: `find milvus/internal milvus/client milvus/pkg/proto -maxdepth 2 -type d | sed -n '1,200p'`
Expected: directories covering schema, storage, and client-side field definitions are visible.

- [ ] **Step 3: Identify data-organization files**

Run: `rg -n "Schema|Field|Collection|JSON|Vector|PrimaryKey" milvus/internal milvus/client milvus/pkg/proto -g '*.go' | sed -n '1,220p'`
Expected: find the files that define or manipulate schema and mixed fields.

- [ ] **Step 4: Write the Theme 4 document**

Document sections must include:
- collection/schema/field model
- vector/scalar/JSON organization
- local source directories
- key files
- recommended reading order

- [ ] **Step 5: Sync persistent state**

Update:
- `task_plan.md` to mark Theme 4 complete and Theme 5 current
- `findings.md` with stable data-organization conclusions
- `progress.md` with a Theme 4 completion entry

## Chunk 4: Theme 5, Theme 6, Theme 7

### Task 5: Produce Theme 5 Index Organization Document

**Files:**
- Create: `docs/milvus_theme5_index_organization.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Read the current storage/index baseline**

Run: `sed -n '1,260p' docs/milvus_storage_and_index_map.md`
Expected: index carriers and segment-lifecycle notes are visible.

- [ ] **Step 2: Inspect index-related source directories**

Run: `find milvus/internal -maxdepth 2 -type d | rg 'index|storage|compaction|query|data'`
Expected: directories related to index build and serving are visible.

- [ ] **Step 3: Identify index-related files**

Run: `rg -n "Index|Build|LoadIndex|PK|Delete|Compaction" milvus/internal milvus/client -g '*.go' | sed -n '1,240p'`
Expected: gather candidate files for vector indexes, scalar filtering aids, and PK-related helpers.

- [ ] **Step 4: Write the Theme 5 document**

Document sections must include:
- vector index organization
- scalar/inverted-style index role
- primary-key helpers
- local source directories
- key files
- recommended reading order

- [ ] **Step 5: Sync persistent state**

Update:
- `task_plan.md` to mark Theme 5 complete and Theme 6 current
- `findings.md` with stable index-organization conclusions
- `progress.md` with a Theme 5 completion entry

### Task 6: Produce Theme 6 Query Architecture Document

**Files:**
- Create: `docs/milvus_theme6_query_architecture.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Inspect query-side directories**

Run: `find milvus/internal -maxdepth 2 -type d | rg 'proxy|querycoord|querynode|streaming|rootcoord|datacoord'`
Expected: query-side actor directories are visible.

- [ ] **Step 2: Identify query-architecture files**

Run: `rg -n "Search|Query|Plan|Reduce|Load|Segment" milvus/internal/proxy milvus/internal/querycoordv2 milvus/internal/querynodev2 milvus/internal/rootcoord -g '*.go' | sed -n '1,240p'`
Expected: get files that anchor role boundaries and query coordination.

- [ ] **Step 3: Write the Theme 6 document**

Document sections must include:
- query-side roles
- component responsibilities
- local source directories
- key files
- recommended reading order

- [ ] **Step 4: Sync persistent state**

Update:
- `task_plan.md` to mark Theme 6 complete and Theme 7 current
- `findings.md` with query-architecture conclusions
- `progress.md` with a Theme 6 completion entry

### Task 7: Produce Theme 7 Query Flow Document

**Files:**
- Create: `docs/milvus_theme7_query_flow.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] **Step 1: Gather the final query-flow anchors**

Run: `rg -n "Search|Query|Retrieve|Reduce|Segment|Plan" milvus/internal/proxy milvus/internal/querycoordv2 milvus/internal/querynodev2 milvus/internal/parser milvus/pkg/proto -g '*.go' | sed -n '1,260p'`
Expected: get the main files needed to narrate the end-to-end query flow.

- [ ] **Step 2: Write the Theme 7 document**

Document sections must include:
- request entry
- planning
- routing
- segment execution
- merge/reduce
- local source directories
- key files
- recommended reading order

- [ ] **Step 3: Sync persistent state**

Update:
- `task_plan.md` to mark Theme 7 complete
- `findings.md` with end-to-end query-flow conclusions
- `progress.md` with a Theme 7 completion entry

- [ ] **Step 4: Verify final checkpoint consistency**

Run: `sed -n '1,220p' task_plan.md && sed -n '1,220p' progress.md`
Expected: the theme sequence is complete and the next step is open-ended review or deeper source reading.
