from phase3_demo.src.vector_store import (
    LightweightChineseEmbedder,
    build_insert_rows,
    dot_similarity,
)


def test_build_insert_rows_keeps_scalar_fields_and_vectors():
    docs = [{"id": "x1", "text": "向量检索", "category": "ai", "source": "note"}]
    vectors = [[0.1, 0.2, 0.3]]
    rows = build_insert_rows(docs, vectors)
    assert rows[0]["id"] == "x1"
    assert rows[0]["category"] == "ai"
    assert rows[0]["vector"] == [0.1, 0.2, 0.3]


def test_lightweight_embedder_brings_synonyms_closer_than_unrelated_text():
    embedder = LightweightChineseEmbedder()
    query = embedder.encode_text("怎么搭建编程环境")
    similar = embedder.encode_text("如何配置开发环境")
    unrelated = embedder.encode_text("PostgreSQL 支持事务和索引")
    assert dot_similarity(query, similar) > dot_similarity(query, unrelated)


def test_lightweight_embedder_prefers_environment_doc_over_unrelated_batch_doc():
    embedder = LightweightChineseEmbedder()
    query = embedder.encode_text("怎么搭建编程环境")
    similar = embedder.encode_text("配置开发环境时，先创建虚拟环境再安装依赖会更稳妥。")
    unrelated = embedder.encode_text("批处理任务要关注幂等性，否则重复调度会产生脏数据。")
    assert dot_similarity(query, similar) > dot_similarity(query, unrelated)


def test_lightweight_embedder_prefers_environment_doc_over_repeated_batch_example():
    embedder = LightweightChineseEmbedder()
    query = embedder.encode_text("怎么搭建编程环境")
    similar = embedder.encode_text("配置开发环境时，先创建虚拟环境再安装依赖会更稳妥。")
    unrelated = embedder.encode_text("批处理任务要关注幂等性，否则重复调度会产生脏数据。 示例编号 3。")
    assert dot_similarity(query, similar) > dot_similarity(query, unrelated)
