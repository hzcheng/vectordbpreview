def keyword_search(query: str, docs: list[dict], top_k: int = 5):
    scored = []
    query_lower = query.lower()

    for doc in docs:
        score = doc["text"].lower().count(query_lower)
        if score > 0:
            scored.append({**doc, "score": float(score), "search_type": "keyword"})

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def normalize_results(rows: list[dict], search_type: str):
    return [{**row, "search_type": search_type} for row in rows]
