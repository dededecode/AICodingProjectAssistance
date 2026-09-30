"""Chroma 向量库封装：每个项目一个 collection，管理项目知识。"""
from django.conf import settings

_client = None


def get_client():
    global _client
    if _client is None:
        import chromadb  # 惰性导入，避免未安装时阻塞服务启动

        _client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    return _client


def _collection_name(project_id):
    return f"project_{project_id}"


def get_collection(project_id):
    client = get_client()
    return client.get_or_create_collection(name=_collection_name(project_id))


def add_knowledge(project_id, texts, metadatas=None, ids=None):
    """向项目知识库写入多个文本块。"""
    from .embedding import embed_texts

    if not texts:
        return
    col = get_collection(project_id)
    vecs = embed_texts(texts)
    if ids is None:
        ids = [f"{project_id}_{i}_{texts[i][:20]}" for i in range(len(texts))]
    if metadatas is None:
        metadatas = [{} for _ in texts]
    col.upsert(ids=ids, embeddings=vecs, documents=texts, metadatas=metadatas)


def search_knowledge(project_id, query, top_k=5):
    """语义检索项目知识。"""
    from .embedding import embed_query

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


def list_knowledge(project_id):
    """列出项目知识库中的全部文本块（含需求初始知识与开发新增知识）。"""
    col = get_collection(project_id)
    if col.count() == 0:
        return []
    got = col.get(include=["documents", "metadatas"])
    ids = got.get("ids") or []
    docs = got.get("documents") or []
    metas = got.get("metadatas") or []
    out = []
    for i, doc in enumerate(docs):
        out.append(
            {
                "id": ids[i] if i < len(ids) else str(i),
                "text": doc,
                "metadata": metas[i] if i < len(metas) else {},
            }
        )
    return out


def delete_project_knowledge(project_id):
    client = get_client()
    try:
        client.delete_collection(name=_collection_name(project_id))
    except Exception:
        pass


def delete_knowledge_by_metadata(project_id, where):
    """按元数据条件删除项目知识库中的向量（如按来源 type 删除）。"""
    col = get_collection(project_id)
    if col.count() == 0:
        return
    try:
        col.delete(where=where)
    except Exception:
        pass


def count_knowledge(project_id):
    col = get_collection(project_id)
    return col.count()
