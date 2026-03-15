from phase3_demo.src.retrieval import keyword_search, normalize_results


def test_keyword_search_prefers_exact_term_matches():
    docs = [
        {
            "id": "db-1",
            "text": "PostgreSQL 支持事务和索引",
            "category": "database",
            "source": "guide",
        },
        {
            "id": "ai-1",
            "text": "向量数据库用于语义检索",
            "category": "ai",
            "source": "guide",
        },
    ]
    results = keyword_search("PostgreSQL", docs, top_k=1)
    assert results[0]["id"] == "db-1"


def test_keyword_results_include_standard_fields():
    docs = [
        {
            "id": "py-1",
            "text": "Python 教程",
            "category": "python",
            "source": "note",
        }
    ]
    result = keyword_search("Python", docs, top_k=1)[0]
    assert set(result) >= {"id", "text", "category", "source", "score", "search_type"}


def test_normalize_results_preserves_search_type_and_fields():
    raw = [
        {
            "id": "ai-1",
            "text": "向量数据库",
            "category": "ai",
            "source": "guide",
            "score": 0.88,
        }
    ]
    normalized = normalize_results(raw, search_type="vector")
    assert normalized[0]["search_type"] == "vector"
    assert normalized[0]["id"] == "ai-1"
