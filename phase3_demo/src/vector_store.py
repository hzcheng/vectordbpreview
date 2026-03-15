import math
import re
from pathlib import Path

from pymilvus import DataType, MilvusClient


class LightweightChineseEmbedder:
    def __init__(self):
        self._concepts = [
            ("开发环境", ("开发环境", "编程环境", "环境配置")),
            ("虚拟环境", ("虚拟环境", "venv", "依赖隔离")),
            ("python", ("python", "pytest", "脚本", "自动化")),
            ("database", ("数据库", "postgresql", "mysql", "事务", "索引")),
            ("向量检索", ("向量检索", "向量搜索", "向量数据库")),
            ("语义检索", ("语义检索", "语义搜索", "语义匹配")),
            ("rag", ("rag", "检索增强生成", "召回上下文")),
            ("过滤", ("过滤", "filter", "metadata")),
            ("数据管道", ("数据管道", "etl", "抽取", "加载")),
            ("数据治理", ("数据治理", "元数据", "血缘", "质量校验")),
        ]
        self.dimension = len(self._concepts) + 4

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    def encode_text(self, text: str) -> list[float]:
        normalized = self._normalize(text)
        vector = []
        for _, synonyms in self._concepts:
            score = sum(normalized.count(token.lower()) for token in synonyms)
            vector.append(float(score))

        # Only use fallback buckets when no concept feature matched at all.
        hash_buckets = [0.0, 0.0, 0.0, 0.0]
        if not any(vector):
            for token in normalized:
                hash_buckets[ord(token) % len(hash_buckets)] += 0.05
        vector.extend(hash_buckets)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return [0.0] * self.dimension
        return [value / norm for value in vector]

    def encode_documents(self, docs: list[dict]) -> list[list[float]]:
        return [self.encode_text(doc["text"]) for doc in docs]


def dot_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


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


def connect_client(db_path: str = "phase3_demo/demo.db") -> MilvusClient:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return MilvusClient(db_path)


def recreate_collection(
    client: MilvusClient,
    collection_name: str,
    dimension: int,
):
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)

    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=2048)
    schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=128)
    schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=128)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)

    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(field_name="vector", metric_type="COSINE", index_type="AUTOINDEX")

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )


def insert_documents(
    client: MilvusClient,
    collection_name: str,
    docs: list[dict],
    embedder: LightweightChineseEmbedder,
):
    vectors = embedder.encode_documents(docs)
    rows = build_insert_rows(docs, vectors)
    client.insert(collection_name=collection_name, data=rows)
    client.flush(collection_name)


def vector_search(
    client: MilvusClient,
    collection_name: str,
    embedder: LightweightChineseEmbedder,
    query: str,
    top_k: int = 5,
    category: str | None = None,
):
    query_vector = embedder.encode_text(query)
    filter_expr = ""
    if category:
        filter_expr = f'category == "{category}"'

    raw_results = client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=top_k,
        filter=filter_expr,
        output_fields=["id", "text", "category", "source"],
        anns_field="vector",
    )
    hits = raw_results[0] if raw_results else []
    normalized = []
    for hit in hits:
        entity = hit.get("entity", {})
        normalized.append(
            {
                "id": entity.get("id", hit.get("id")),
                "text": entity.get("text", ""),
                "category": entity.get("category", ""),
                "source": entity.get("source", ""),
                "score": float(hit.get("distance", 0.0)),
            }
        )
    return normalized
