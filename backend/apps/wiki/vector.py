"""Wiki 向量库封装：独立 collection（wiki_{project_id}），与知识库向量（project_{id}）物理隔离。

写入/检索/删除只作用于 wiki collection，完全不影响现有知识库的向量检索。
"""
from django.conf import settings

_client = None


def get_client():
    global _client
    if _client is None:
        import chromadb  # 惰性导入，避免未安装时阻塞服务启动

        _client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    return _client


def _collection_name(project_id):
    return f"wiki_{project_id}"


def get_collection(project_id):
    return get_client().get_or_create_collection(name=_collection_name(project_id))


def add_wiki_pages(project_id, texts, metadatas=None, ids=None):
    """写入多个 Wiki 页面向量。"""
    if not texts:
        return
    from services.embedding import embed_texts

    col = get_collection(project_id)
    vecs = embed_texts(texts)
    if ids is None:
        ids = [f"wiki_{i}_{texts[i][:20]}" for i in range(len(texts))]
    if metadatas is None:
        metadatas = [{} for _ in texts]
    col.upsert(ids=ids, embeddings=vecs, documents=texts, metadatas=metadatas)


def search_wiki(project_id, query, top_k=5):
    """语义检索 Wiki 页面。"""
    from services.embedding import embed_query

    col = get_collection(project_id)
    if col.count() == 0:
        return []
    vec = embed_query(query)
    result = col.query(query_embeddings=[vec], n_results=min(top_k, col.count()))
    out = []
    for i, doc in enumerate(result["documents"][0]):
        out.append(
            {
                "text": doc,
                "distance": result["distances"][0][i],
                "metadata": (result["metadatas"][0][i] or {}),
            }
        )
    return out


def delete_wiki_by_source(project_id, source_type, source_id):
    """按来源删除该来源的全部 Wiki 向量（覆盖式重编译前清理）。"""
    col = get_collection(project_id)
    if col.count() == 0:
        return
    try:
        col.delete(where={"source_key": f"{source_type}:{source_id}"})
    except Exception:
        pass


def delete_wiki_page(project_id, page_id):
    """删除单个页面的向量。"""
    col = get_collection(project_id)
    try:
        col.delete(ids=[f"page{page_id}"])
    except Exception:
        pass


def delete_wiki_collection(project_id):
    """删除整个 wiki collection（清空 Wiki 用）。"""
    client = get_client()
    try:
        client.delete_collection(name=_collection_name(project_id))
    except Exception:
        pass


def count_wiki(project_id):
    return get_collection(project_id).count()
