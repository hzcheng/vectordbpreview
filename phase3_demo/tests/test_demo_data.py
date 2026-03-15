from phase3_demo.src.demo_data import load_documents


def test_load_documents_returns_structured_records():
    docs = load_documents("phase3_demo/data/sample_docs.json")
    assert len(docs) >= 100
    first = docs[0]
    assert set(first) >= {"id", "text", "category", "source"}
