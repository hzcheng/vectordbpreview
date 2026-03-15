from phase3_demo.src.search_demo import build_demo_report


def test_build_demo_report_returns_all_three_sections():
    report = build_demo_report(
        keyword_results=[
            {
                "id": "db-1",
                "text": "PostgreSQL",
                "category": "database",
                "source": "guide",
                "score": 1.0,
                "search_type": "keyword",
            }
        ],
        vector_results=[
            {
                "id": "ai-1",
                "text": "语义检索",
                "category": "ai",
                "source": "guide",
                "score": 0.9,
                "search_type": "vector",
            }
        ],
        filtered_results=[
            {
                "id": "ai-2",
                "text": "RAG 召回",
                "category": "ai",
                "source": "tutorial",
                "score": 0.8,
                "search_type": "vector_filtered",
            }
        ],
    )
    lowered = report.lower()
    assert "keyword search" in lowered
    assert "vector search" in lowered
    assert "filtered vector search" in lowered
