import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase3_demo.src.demo_data import load_documents
from phase3_demo.src.vector_store import (
    LightweightChineseEmbedder,
    connect_client,
    insert_documents,
    recreate_collection,
)


DATA_PATH = "phase3_demo/data/sample_docs.json"
DB_PATH = "phase3_demo/demo.db"
COLLECTION_NAME = "phase3_demo_docs"


def build_demo():
    docs = load_documents(DATA_PATH)
    embedder = LightweightChineseEmbedder()
    client = connect_client(DB_PATH)
    try:
        recreate_collection(client, COLLECTION_NAME, embedder.dimension)
        insert_documents(client, COLLECTION_NAME, docs, embedder)
    finally:
        client.close()
    return {"db_path": DB_PATH, "collection_name": COLLECTION_NAME, "document_count": len(docs)}


if __name__ == "__main__":
    summary = build_demo()
    print(
        f"Built {summary['collection_name']} in {summary['db_path']} "
        f"with {summary['document_count']} documents."
    )
