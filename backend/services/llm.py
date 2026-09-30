"""LLM 服务：OpenAI 兼容协议，用于需求分析、文档生成等。"""
import json
import re

from django.conf import settings

from .ai_config import get_llm_config


def _client():
    from openai import OpenAI

    cfg = get_llm_config()
    if not cfg["api_key"]:
        raise RuntimeError(
            "LLM_API_KEY 未配置。请在「模型管理」页面配置，或设置环境变量 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。"
        )
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])


def current_model():
    return get_llm_config()["model"]


def chat(messages, temperature: float = 0.3, max_tokens: int = 4096) -> str:
    """发送对话，返回纯文本。"""
    client = _client()
    cfg = get_llm_config()
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def chat_stream(messages, temperature: float = 0.3, max_tokens: int = 8192):
    """发送对话并流式返回文本片段（迭代器，逐 token）。"""
    client = _client()
    cfg = get_llm_config()
    stream = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def chat_json(messages, temperature: float = 0.2, max_tokens: int = 4096) -> dict:
    """发送对话并要求返回 JSON 对象。解析失败时兜底尝试从文本中抽取。"""
    text = chat(messages, temperature=temperature, max_tokens=max_tokens)
    return extract_json(text)


def extract_json(text: str) -> dict:
    """从模型输出中解析 JSON（去掉 markdown 围栏，尝试匹配第一个 JSON 对象）。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"模型返回内容无法解析为 JSON：{text[:500]}")
