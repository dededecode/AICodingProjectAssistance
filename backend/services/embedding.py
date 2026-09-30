"""Embedding 服务：本地 sentence-transformers 或远程 OpenAI 兼容 embedding 端点。"""
from django.conf import settings

from .ai_config import get_embedding_config

# 本地模型懒加载（首次调用加载，进程内缓存）
_model = None


def _cfg():
    return get_embedding_config()


def _get_local_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_cfg()["model"])
    return _model


def _remote_embed(texts):
    from openai import OpenAI

    from .ai_config import get_embedding_api_key

    cfg = _cfg()
    api_key, account = get_embedding_api_key()
    if not api_key:
        raise RuntimeError("未配置 API Key，远程 embedding 无法使用。")
    client = OpenAI(base_url=cfg["remote_base_url"], api_key=api_key)

    # 部分兼容端点单次输入数量有限（如 10 条），分批处理
    batch_size = int(getattr(settings, "EMBEDDING_BATCH_SIZE", 8) or 8)
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=cfg["remote_model"], input=batch)
        resp.data.sort(key=lambda d: d.index)
        results.extend(d.embedding for d in resp.data)
    _log_call(account)
    return results


def _log_call(account):
    """记录一次远程 embedding 调用（时间 + 调用账号）。日志失败不影响主流程。"""
    try:
        from apps.ai_config.models import EmbeddingCallLog

        EmbeddingCallLog.objects.create(username=account)
    except Exception:
        pass


def embed_texts(texts):
    """输入文本列表，返回向量列表。"""
    if not texts:
        return []
    if _cfg()["mode"] == "remote":
        return _remote_embed(texts)
    model = _get_local_model()
    vecs = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def embed_query(text):
    """单条查询向量（local 模式下给 bge 加查询前缀提升召回）。"""
    if _cfg()["mode"] == "remote":
        return _remote_embed([text])[0]
    model = _get_local_model()
    query_text = f"为这个句子生成表示以用于检索相关文章：{text}"
    vec = model.encode([query_text], normalize_embeddings=True)[0]
    return vec.tolist()
