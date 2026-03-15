import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase3_demo.src.build_demo import COLLECTION_NAME, DATA_PATH, DB_PATH
from phase3_demo.src.demo_data import load_documents
from phase3_demo.src.retrieval import keyword_search, normalize_results
from phase3_demo.src.vector_store import LightweightChineseEmbedder, connect_client, vector_search


def _format_section(title: str, query: str, results: list[dict]) -> str:
    lines = [title, f"Query: {query}"]
    if not results:
        lines.append("(no results)")
        return "\n".join(lines)

    for idx, row in enumerate(results, start=1):
        lines.append(
            f"{idx}. [{row['id']}] ({row['category']}/{row['source']}) "
            f"score={row['score']:.3f} {row['text']}"
        )
    return "\n".join(lines)


def build_demo_report(keyword_results, vector_results, filtered_results):
    sections = [
        _format_section("Keyword Search", "PostgreSQL", keyword_results),
        _format_section("Vector Search", "怎么搭建编程环境", vector_results),
        _format_section("Filtered Vector Search", "怎么做语义搜索", filtered_results),
    ]
    return "\n\n".join(sections)


def run_demo_queries():
    docs = load_documents(DATA_PATH)
    embedder = LightweightChineseEmbedder()
    client = connect_client(DB_PATH)
    try:
        keyword_results = keyword_search("PostgreSQL", docs, top_k=3)
        vector_results = normalize_results(
            vector_search(client, COLLECTION_NAME, embedder, "怎么搭建编程环境", top_k=3),
            search_type="vector",
        )
        filtered_results = normalize_results(
            vector_search(client, COLLECTION_NAME, embedder, "怎么做语义搜索", top_k=3, category="ai"),
            search_type="vector_filtered",
        )
    finally:
        client.close()

    return {
        "keyword_results": keyword_results,
        "vector_results": vector_results,
        "filtered_results": filtered_results,
    }


if __name__ == "__main__":
    payload = run_demo_queries()
    print(
        build_demo_report(
            keyword_results=payload["keyword_results"],
            vector_results=payload["vector_results"],
            filtered_results=payload["filtered_results"],
        )
    )
