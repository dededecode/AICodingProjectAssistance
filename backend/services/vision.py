"""多模态视觉服务：调用 OpenAI 兼容的多模态 LLM，将图片解析为文字描述。"""
import base64
import mimetypes

from .ai_config import get_vision_config


def describe_image(image_path: str, prompt: str) -> str:
    """将单张图片交给多模态 LLM，返回文字描述。"""
    from openai import OpenAI

    cfg = get_vision_config()
    if not cfg["api_key"]:
        raise RuntimeError("未配置多模态 LLM 的 API Key。请在「模型管理」中配置多模态模型。")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    mime = mimetypes.guess_type(image_path)[0] or "image/png"
    data_url = f"data:{mime};base64,{b64}"

    client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        max_tokens=2000,
    )
    return resp.choices[0].message.content or ""


def describe_images(image_paths, prompt: str) -> list:
    """批量解析多张图片（逐张调用）。"""
    return [describe_image(p, prompt) for p in image_paths]
