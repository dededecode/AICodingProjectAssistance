"""LLM Wiki 编译层：把源文档编译为结构化、互联的 Wiki 页面。

对应 Karpathy LLM Wiki 模式中的 Schema 层：固定页面类型、命名规则、
双链与来源引用格式，保证多次编译风格一致、页面不分裂。
"""
import json

from services import llm

MAX_SOURCE_CHARS = 30000  # 超长源文档截断上限（超出部分不编译，编译结果会带 truncated 标记）
# 输出上限：优先请求更大的 max_tokens；模型不支持时自动回退（截断由 _extract_pages 兜底抢救）
MAX_TOKENS_PRIMARY = 32768
MAX_TOKENS_FALLBACK = 16384

SYSTEM_PROMPT = """你是知识编译器（LLM Wiki）。请把用户提供的【源文档】编译为若干结构化 Wiki 页面，用于构建可长期维护的项目知识库。

编译规则：
1. 每个页面是一个自包含的知识单元：标题唯一且语义清晰，读者不看原文也能理解该页内容。
2. 页面命名采用「页面类型-主题」格式，如：总览-项目全景、模块-用户管理、表-用户表、接口-登录、实体-订单、时间线-迭代计划、综合-技术选型对比。
3. page_type 只能是：overview（总览）、module（业务模块）、entity（实体/概念）、table（数据表）、api（接口）、timeline（时间线/里程碑）、synthesis（跨章节综合分析）。
4. content 为 Markdown，用小标题、要点、表格结构化组织；综合提炼而非照抄原文；关键结论保留原文依据，不要编造文档中没有的信息。
5. links 列出与该页相关的其它页面标题（尽量互联，形成知识网络）。
6. sources 列出该页依据的原文小节/章节名称。
7. 页面数量按内容规模决定（通常 6~20 页），优先覆盖：总览、核心业务模块、业务规则、关键数据表、重要接口、跨章节综合分析。
8. 若文档内容包含图片占位标记（如【图片:xxx】），原样保留在相关页面中。
9. 内容充实度：单页 content 应完整覆盖该主题的关键信息（规则、流程、字段、接口、约束等），一般不超过 1100 字；宁可减少页数也必须保证 JSON 完整闭合，绝不允许输出被截断。
10. JSON 格式要求：字符串值内的换行必须写成 \\n 转义符，禁止使用真实换行；引号、反斜杠必须转义；输出必须是合法 JSON。

输出 JSON：{"pages": [{"title": "...", "page_type": "...", "content": "...", "links": ["..."], "sources": ["..."]}]}
只输出 JSON，不要输出其它内容。"""


def _fix_raw_newlines(text):
    """把 JSON 字符串值内部的裸换行转义为 \\n（模型输出长 content 时容易偷懒写真实换行，导致整段 JSON 非法）。"""
    out = []
    in_str = False
    esc = False
    for ch in text:
        if esc:
            out.append(ch)
            esc = False
            continue
        if ch == "\\":
            out.append(ch)
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            continue
        if ch == "\n" and in_str:
            out.append("\\n")
            continue
        out.append(ch)
    return "".join(out)


def _extract_pages(text):
    """解析模型输出中的 pages 数组；输出被截断或格式非法时逐个抢救完整页面对象。

    返回 (pages, partial_output)：partial_output=True 表示输出未完整闭合/格式受损，
    仅保留了可解析的完整页面。
    """
    text = text.strip()
    # 宽松修复①：字符串内裸换行 → \\n（最常导致整段 JSON 非法的元凶）
    cleaned = _fix_raw_newlines(text)
    for candidate in (cleaned, text):
        try:
            result = llm.extract_json(candidate)
            return result.get("pages") or [], False
        except ValueError:
            continue
    # 宽松修复②：逐个解码完整的 page 对象（截断/局部损坏兜底）
    pages = []
    decoder = json.JSONDecoder()
    idx = 0
    while True:
        brace = cleaned.find("{", idx)
        if brace == -1:
            break
        try:
            obj, end = decoder.raw_decode(cleaned, brace)
            if isinstance(obj, dict) and obj.get("title"):
                pages.append(obj)
            idx = end
        except json.JSONDecodeError:
            idx = brace + 1
    return pages, True


def compile_wiki_pages(project_name: str, source_title: str, text: str, existing_titles=None):
    """编译为 Wiki 页面，返回 (pages, partial_output)。

    existing_titles：项目已有 Wiki 页面标题（其它来源编译所得），用于跨源关联——
    新页面会主动 link 已有页面；主题重叠时聚焦增量差异信息。
    """
    user = f"项目：{project_name}\n源文档：{source_title}\n\n【源文档内容】\n{text[:MAX_SOURCE_CHARS]}"
    titles = [str(t).strip() for t in (existing_titles or []) if str(t).strip()][:200]
    if titles:
        user += (
            "\n\n【项目已有 Wiki 页面标题】\n" + "\n".join(f"- {t}" for t in titles)
            + "\n\n关联要求：新页面的 links 应优先关联上述已有页面（标题须与列表完全一致，形成跨文档知识网络）；"
            "若本源文档的主题与某个已有页面高度重叠，新页面应聚焦本源文档新增/修订/差异的信息，"
            "并在 content 开头用一行说明与已有页面的关系（如：本文档补充「xxx」页面的勋章规则）。"
        )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
    try:
        out = llm.chat(messages, temperature=0.2, max_tokens=MAX_TOKENS_PRIMARY)
    except Exception as e:
        # 部分模型不接受超过自身上限的 max_tokens，回退到保守值重试
        if "max_tokens" in str(e).lower():
            out = llm.chat(messages, temperature=0.2, max_tokens=MAX_TOKENS_FALLBACK)
        else:
            raise
    return _extract_pages(out)
