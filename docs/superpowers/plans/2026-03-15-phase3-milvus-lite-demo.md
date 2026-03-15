# Phase 3 Milvus Lite Demo Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Chinese semantic-search demo with `Python + Milvus Lite` that compares `keyword search`, `vector search`, and `metadata filter` on the same sample dataset.

**Architecture:** Keep the implementation small and file-based. Use reusable Python modules for data loading, retrieval logic, and Milvus Lite integration, with thin CLI entry points for indexing and querying. Favor deterministic dataset and output structure so tests can focus on behavior instead of unstable model scores.

**Tech Stack:** Python 3.10+, `pytest`, `pymilvus`, `sentence-transformers`, JSON sample data, Milvus Lite local database file

---

## File Structure Map

- Create: `phase3_demo/requirements.txt`
  - Pins the minimal Python dependencies for the demo.
- Create: `phase3_demo/README.md`
  - Explains install, indexing, query commands, and expected learning takeaways.
- Create: `phase3_demo/data/sample_docs.json`
  - Stores the curated Chinese sample dataset.
- Create: `phase3_demo/src/demo_data.py`
  - Loads and validates sample records from JSON.
- Create: `phase3_demo/src/retrieval.py`
  - Implements keyword search and output formatting helpers.
- Create: `phase3_demo/src/vector_store.py`
  - Owns embedding generation, Milvus Lite connection, collection management, indexing, and vector search.
- Create: `phase3_demo/src/build_demo.py`
  - CLI entry point to build/rebuild the local Milvus Lite demo collection.
- Create: `phase3_demo/src/search_demo.py`
  - CLI entry point to run keyword, vector, and filter search scenarios.
- Create: `phase3_demo/tests/test_demo_data.py`
  - Covers dataset loading and validation.
- Create: `phase3_demo/tests/test_retrieval.py`
  - Covers keyword search behavior and result formatting.
- Create: `phase3_demo/tests/test_vector_store.py`
  - Covers vector-store interfaces with fake embedder stubs and lightweight Milvus Lite integration.
- Create: `phase3_demo/results/sample_run.md`
  - Stores a representative run output after implementation.
- Modify: `task_plan.md`
  - Sync Phase 3 execution status after implementation milestones.
- Modify: `progress.md`
  - Record plan creation, implementation progress, and verification evidence.
- Modify: `findings.md`
  - Record concrete Phase 3 implementation findings if they affect later Milvus learning.

## Chunk 1: Data And Retrieval Baseline

### Task 1: Curate The Sample Dataset And Loader

**Files:**
- Create: `phase3_demo/data/sample_docs.json`
- Create: `phase3_demo/src/demo_data.py`
- Test: `phase3_demo/tests/test_demo_data.py`

- [ ] **Step 1: Write the failing dataset-loading test**

```python
from phase3_demo.src.demo_data import load_documents


def test_load_documents_returns_structured_records():
    docs = load_documents("phase3_demo/data/sample_docs.json")
    assert len(docs) >= 100
    first = docs[0]
    assert set(first) >= {"id", "text", "category", "source"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest phase3_demo/tests/test_demo_data.py::test_load_documents_returns_structured_records -v`
Expected: FAIL because `phase3_demo.src.demo_data` or `load_documents` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
import json


def load_documents(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        docs = json.load(fh)
    return docs
```

Also create `sample_docs.json` with at least 100 records using stable keys:

```json
{
  "id": "py-001",
  "text": "Python 虚拟环境可以隔离项目依赖，避免不同项目的包版本冲突。",
  "category": "python",
  "source": "tutorial"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest phase3_demo/tests/test_demo_data.py::test_load_documents_returns_structured_records -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add phase3_demo/data/sample_docs.json phase3_demo/src/demo_data.py phase3_demo/tests/test_demo_data.py
git commit -m "feat: add phase3 demo dataset loader"
```

### Task 2: Implement Keyword Search And Result Formatting

**Files:**
- Create: `phase3_demo/src/retrieval.py`
- Test: `phase3_demo/tests/test_retrieval.py`

- [ ] **Step 1: Write the failing keyword-search test**

```python
from phase3_demo.src.retrieval import keyword_search


def test_keyword_search_prefers_exact_term_matches():
    docs = [
        {"id": "db-1", "text": "PostgreSQL 支持事务和索引", "category": "database", "source": "guide"},
        {"id": "ai-1", "text": "向量数据库用于语义检索", "category": "ai", "source": "guide"},
    ]
    results = keyword_search("PostgreSQL", docs, top_k=1)
    assert results[0]["id"] == "db-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest phase3_demo/tests/test_retrieval.py::test_keyword_search_prefers_exact_term_matches -v`
Expected: FAIL because `keyword_search` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
def keyword_search(query: str, docs: list[dict], top_k: int = 5):
    scored = []
    query_lower = query.lower()
    for doc in docs:
        score = doc["text"].lower().count(query_lower)
        if score > 0:
            scored.append({**doc, "score": float(score), "search_type": "keyword"})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
```

Add a second test for output formatting:

```python
def test_keyword_results_include_standard_fields():
    docs = [{"id": "py-1", "text": "Python 教程", "category": "python", "source": "note"}]
    result = keyword_search("Python", docs, top_k=1)[0]
    assert set(result) >= {"id", "text", "category", "source", "score", "search_type"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest phase3_demo/tests/test_retrieval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add phase3_demo/src/retrieval.py phase3_demo/tests/test_retrieval.py
git commit -m "feat: add keyword retrieval baseline"
```

## Chunk 2: Vector Search Pipeline

### Task 3: Add Vector Store Abstractions And Build Command

**Files:**
- Create: `phase3_demo/requirements.txt`
- Create: `phase3_demo/src/vector_store.py`
- Create: `phase3_demo/src/build_demo.py`
- Test: `phase3_demo/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing unit test for indexing payloads**

```python
from phase3_demo.src.vector_store import build_insert_rows


def test_build_insert_rows_keeps_scalar_fields_and_vectors():
    docs = [{"id": "x1", "text": "向量检索", "category": "ai", "source": "note"}]
    vectors = [[0.1, 0.2, 0.3]]
    rows = build_insert_rows(docs, vectors)
    assert rows[0]["id"] == "x1"
    assert rows[0]["category"] == "ai"
    assert rows[0]["vector"] == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest phase3_demo/tests/test_vector_store.py::test_build_insert_rows_keeps_scalar_fields_and_vectors -v`
Expected: FAIL because `vector_store.py` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
def build_insert_rows(docs: list[dict], vectors: list[list[float]]):
    rows = []
    for doc, vector in zip(docs, vectors, strict=True):
        rows.append(
            {
                "id": doc["id"],
                "text": doc["text"],
                "category": doc["category"],
                "source": doc["source"],
                "vector": vector,
            }
        )
    return rows
```

Then add thin production functions for:
- loading a sentence-transformers model lazily
- creating a local Milvus Lite connection at `phase3_demo/demo.db`
- creating/recreating a collection with scalar fields plus a float-vector field
- inserting rows generated by `build_insert_rows`

Set `phase3_demo/requirements.txt` to:

```txt
pymilvus
sentence-transformers
pytest
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `pytest phase3_demo/tests/test_vector_store.py -v`
Expected: PASS for pure-Python helper tests before integration tests are added.

- [ ] **Step 5: Commit**

```bash
git add phase3_demo/requirements.txt phase3_demo/src/vector_store.py phase3_demo/src/build_demo.py phase3_demo/tests/test_vector_store.py
git commit -m "feat: add vector store build pipeline"
```

### Task 4: Add Search CLI For Vector And Filtered Queries

**Files:**
- Create: `phase3_demo/src/search_demo.py`
- Modify: `phase3_demo/src/retrieval.py`
- Modify: `phase3_demo/src/vector_store.py`
- Test: `phase3_demo/tests/test_vector_store.py`
- Test: `phase3_demo/tests/test_retrieval.py`

- [ ] **Step 1: Write the failing result-normalization test**

```python
from phase3_demo.src.retrieval import normalize_results


def test_normalize_results_preserves_search_type_and_fields():
    raw = [{"id": "ai-1", "text": "向量数据库", "category": "ai", "source": "guide", "score": 0.88}]
    normalized = normalize_results(raw, search_type="vector")
    assert normalized[0]["search_type"] == "vector"
    assert normalized[0]["id"] == "ai-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest phase3_demo/tests/test_retrieval.py::test_normalize_results_preserves_search_type_and_fields -v`
Expected: FAIL because `normalize_results` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
def normalize_results(rows: list[dict], search_type: str):
    return [{**row, "search_type": search_type} for row in rows]
```

Then add:
- `vector_search(query, top_k, category=None)` in `vector_store.py`
- `run_demo_queries()` in `search_demo.py`
- support for at least these cases:
  - synonym-style vector query
  - exact technical term keyword query
  - vector query with `category` filter

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `pytest phase3_demo/tests/test_retrieval.py phase3_demo/tests/test_vector_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add phase3_demo/src/search_demo.py phase3_demo/src/retrieval.py phase3_demo/src/vector_store.py phase3_demo/tests/test_retrieval.py phase3_demo/tests/test_vector_store.py
git commit -m "feat: add vector and filtered demo queries"
```

## Chunk 3: End-To-End Demo, Docs, And Verification

### Task 5: Wire End-To-End Commands And Capture Sample Output

**Files:**
- Modify: `phase3_demo/src/build_demo.py`
- Modify: `phase3_demo/src/search_demo.py`
- Create: `phase3_demo/results/sample_run.md`
- Test: `phase3_demo/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing smoke test**

```python
from phase3_demo.src.search_demo import build_demo_report


def test_build_demo_report_returns_all_three_sections():
    report = build_demo_report(
        keyword_results=[{"id": "db-1", "text": "PostgreSQL", "category": "database", "source": "guide", "score": 1.0}],
        vector_results=[{"id": "ai-1", "text": "语义检索", "category": "ai", "source": "guide", "score": 0.9}],
        filtered_results=[{"id": "ai-2", "text": "RAG 召回", "category": "ai", "source": "tutorial", "score": 0.8}],
    )
    assert "keyword search" in report.lower()
    assert "vector search" in report.lower()
    assert "filtered vector search" in report.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest phase3_demo/tests/test_vector_store.py::test_build_demo_report_returns_all_three_sections -v`
Expected: FAIL because `build_demo_report` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
def build_demo_report(keyword_results, vector_results, filtered_results):
    return "\n\n".join(
        [
            "Keyword Search\n" + repr(keyword_results),
            "Vector Search\n" + repr(vector_results),
            "Filtered Vector Search\n" + repr(filtered_results),
        ]
    )
```

Then make the CLI commands usable:
- `python3 phase3_demo/src/build_demo.py`
- `python3 phase3_demo/src/search_demo.py`

Save one representative output to `phase3_demo/results/sample_run.md`.

- [ ] **Step 4: Run the smoke test and the end-to-end commands**

Run: `pytest phase3_demo/tests/test_vector_store.py -v`
Expected: PASS

Run: `python3 phase3_demo/src/build_demo.py`
Expected: Creates or rebuilds the local Milvus Lite collection without tracebacks.

Run: `python3 phase3_demo/src/search_demo.py`
Expected: Prints keyword, vector, and filtered vector sections with meaningful differences.

- [ ] **Step 5: Commit**

```bash
git add phase3_demo/src/build_demo.py phase3_demo/src/search_demo.py phase3_demo/results/sample_run.md phase3_demo/tests/test_vector_store.py
git commit -m "feat: add end-to-end phase3 demo flow"
```

### Task 6: Write README And Sync Learning Progress

**Files:**
- Create: `phase3_demo/README.md`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `findings.md`

- [ ] **Step 1: Write the failing documentation checklist**

Create a manual checklist in `progress.md` for:
- installation instructions present
- build command present
- search command present
- explanation of keyword vs vector vs filter differences present

- [ ] **Step 2: Run the manual verification**

Run: `rg -n "install|build_demo.py|search_demo.py|keyword|vector|filter" phase3_demo/README.md`
Expected: FAIL before the README exists.

- [ ] **Step 3: Write the minimal implementation**

README must include:
- setup command:

```bash
python3 -m pip install -r phase3_demo/requirements.txt
```

- build command:

```bash
python3 phase3_demo/src/build_demo.py
```

- query command:

```bash
python3 phase3_demo/src/search_demo.py
```

- a short explanation of what each query demonstrates
- a note that this is a learning demo rather than a production retrieval stack

Also update planning files to:
- mark Phase 3 checklist items as completed once verified
- record dependency or model-selection findings that matter for later Milvus study

- [ ] **Step 4: Run documentation verification**

Run: `rg -n "install|build_demo.py|search_demo.py|keyword|vector|filter" phase3_demo/README.md`
Expected: Matches all key sections

- [ ] **Step 5: Commit**

```bash
git add phase3_demo/README.md task_plan.md progress.md findings.md
git commit -m "docs: document phase3 demo usage"
```

## Final Verification Checklist

- [ ] Run all demo tests:

```bash
pytest phase3_demo/tests -v
```

Expected: All tests pass.

- [ ] Run the build command:

```bash
python3 phase3_demo/src/build_demo.py
```

Expected: Milvus Lite database file is built successfully.

- [ ] Run the search command:

```bash
python3 phase3_demo/src/search_demo.py
```

Expected: Console output clearly shows differences between keyword search, vector search, and filtered vector search.

- [ ] Update `progress.md` with the exact verification commands and outcomes.
- [ ] Update `task_plan.md` to mark completed Phase 3 checklist items.
