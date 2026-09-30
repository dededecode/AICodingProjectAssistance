"""图文需求文档中图片的 AI 取名：按「端-模块名-功能名-用途」规则。"""
import logging

from services import llm

logger = logging.getLogger(__name__)

SYSTEM = """你是需求文档管理员。给定一份需求文档内容，其中【图片:xxx】(路径) 标记代表文档中按顺序插入的图片，请为每张图片取名。

取名规则：端-模块名-功能名-用途
- 端：Web端/App端/H5端/管理端/小程序端等（依据图片上下文判断，无法判断时用"系统"）
- 模块名/功能名：依据图片前后的章节标题与描述文字
- 用途只能是以下四类之一：
  1. UI图：页面设计图/界面效果图（描述具体页面长什么样）
  2. 原型图：页面原型/线框图
  3. 业务流程图：流程图、时序图、数据流程图、架构图等非页面图，用于帮助理解业务流程/逻辑
  4. 其它：从上下文无法判断图片类型时（既看不出是页面图也看不出是流程图），归类为"其它"，不要臆断为 UI图或原型图

要求：
- 名称简洁准确，不超过 40 个字符，不含非法字符 \\ / : * ? " < > | 与换行
- 同一功能多张同类图时用途段加序号区分，如：Web端-订单管理-订单列表-UI图2
- 必须为每张图片都给出名称，index 与图片顺序一一对应（从 1 开始）

严格输出 JSON（不要输出其他内容）：
{"images": [{"index": 1, "name": "Web端-订单管理-订单列表-UI图", "purpose": "UI图"}]}"""


# 图片较多时一次让模型输出全部命名结果，容易超出 max_tokens 被截断导致 JSON 解析失败：
# 因此分批取名（每批最多 10 张），单批失败只跳过本批、不影响其它批，成功结果尽量保留。
_BATCH_SIZE = 10
_MAX_TOKENS = 8192


def name_document_images(doc_text: str, images: list, max_text: int = 60000) -> list:
    """让 AI 为文档中的图片取名。

    参数：
        doc_text: 含【图片:xxx】标记的文档全文
        images: parse_docx_rich 返回的图片信息列表（文档顺序）
    返回：
        [{"index": 1, "name": "...", "purpose": "..."}]（index 从 1 开始，与文档顺序一一对应）
        分批处理：某批解析失败会重试一次，仍失败则该批跳过（调用方对缺失图回退默认名）。
    """
    out = []
    for start in range(0, len(images), _BATCH_SIZE):
        batch = images[start : start + _BATCH_SIZE]
        first, last = start + 1, start + len(batch)
        listing = "\n".join(
            f"- 第 {g} 张：{info.get('marker', '')}" for g, info in enumerate(batch, start=first)
        )
        user = (
            f"文档内容（含图片标记）：\n\n{doc_text[:max_text]}\n\n"
            f"文档中共 {len(images)} 张图片，本次请为其中第 {first}~{last} 张取名"
            f"（{first} 到 {last}，按文档顺序编号如下）：\n{listing}"
        )
        items = []
        for attempt in (1, 2):
            try:
                result = llm.chat_json(
                    [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                    temperature=0.2,
                    max_tokens=_MAX_TOKENS,
                )
                items = result.get("images") or []
                break
            except Exception as e:
                logger.warning("[图片取名] 第 %s~%s 张 AI 取名失败（第 %s 次重试）：%s", first, last, attempt, e)
        for it in items:
            try:
                idx = int(it.get("index"))
            except (ValueError, TypeError):
                continue
            # 只收本批范围的结果，防止模型序号错乱污染其它批
            if not (first <= idx <= last):
                continue
            out.append(
                {
                    "index": idx,
                    "name": str(it.get("name") or "").strip(),
                    "purpose": str(it.get("purpose") or "").strip(),
                }
            )
    return out
