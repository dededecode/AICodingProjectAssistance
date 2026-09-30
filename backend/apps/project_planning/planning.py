"""AI 项目计划生成：基于需求文档、成员权重、上线时间拆分开发计划。"""
import logging
import re
import time

from django.utils import timezone
from services import llm

logger = logging.getLogger(__name__)


def _extract_plan_tasks_section(plan_content: str) -> str:
    """从计划正文中截取「任务拆分（按业务模块）」小节（到下一个 ## 章节为止）。"""
    if not plan_content:
        return ""
    m = re.search(r"(?i)##\s*二[、.\s]*任务拆分.*?(?=##\s*三|\Z)", plan_content, re.S)
    return m.group(0) if m else ""

SYSTEM_PROMPT = """你是一名资深的全栈 AI Coding 项目交付规划师。
团队采用 AI coding 方式进行全栈开发，成员可独立完成包含前端、后端、数据存储在内的完整业务功能，不需要按前后端分工。

【第一原则·按业务板块划分并固定负责人】
按业务板块（业务模块）拆分任务，不得把同一业务按端（如管理端/移动端/大屏）或按技术层拆开分配给不同成员；
一个业务板块只要分配给了某位成员，该板块涉及的各端、各功能及其前后端工作就全部由该成员一人负责到底，
不在多人之间拆分同一板块、不做中途转手。每个任务都必须归属到明确的业务板块。

任务分配必须严格遵循给定的【成员及其开发工作权重】：成员权重代表其应承担的开发工作量占比（如 0.3 表示承担约 30% 的开发工作量）。请按权重比例分配任务，权重高的成员分配更多/更重的任务，权重低的分配较少任务；同一业务模块尽量由同一成员负责，减少交接成本。

【成员能力描述】是重要参考：分配任务时应结合成员的【能力描述】（擅长技术栈、可承担职责等），把对应技术栈/职责的任务优先分配给擅长的成员；若某成员能力描述为空，则按权重均衡分配即可。

请根据提供的需求文档、计划名称、成员（含权重）与上线时间，生成一份可执行的项目开发计划（中文，markdown 格式），须包含：
## 一、整体策略与里程碑
按业务价值与依赖关系划分若干里程碑，每个里程碑给出计划起止日期。
## 二、任务拆分（按业务模块）
每个任务包含：序号、所属业务模块、任务名称、任务描述、预估难度（简单/中等/复杂）、预估工期（人日）、负责人（使用真实成员名）、计划起止日期、前置依赖。
拆分原则：按业务模块划分，任务按成员权重比例均衡分配，整体进度需在上线时间前完成并预留联调与测试缓冲。
## 三、成员负载概览
列出每个成员负责的任务、总人日与占比，体现与权重的匹配。
## 四、关键风险与说明
列出计划中的主要风险与假设（如 AI coding 的返工、需求变更、依赖第三方等）。

只输出 markdown 计划内容，不要输出其他解释。"""


def generate_plan(requirement, plan_name: str, start_date, launch_date, members, suggestion: str = "", current_content: str = "") -> str:
    """members: list of (username, weight, capability)。
    若传入 suggestion（修改意见），AI 会结合当前计划版本（current_content）与修改意见重新生成。"""
    today = timezone.localdate()
    member_lines = "、".join(
        f"{name}(权重{weight:.0%}{'；能力：' + capability if capability else ''})" for name, weight, capability in members
    )
    user_content = (
        f"需求文档名称：{requirement.title}\n"
        f"计划名称：{plan_name}\n"
        f"计划开始时间：{start_date}\n"
        f"计划上线时间：{launch_date}\n"
        f"今天日期：{today}\n"
        f"成员及权重：{member_lines}\n"
        f"需求文档内容（用于拆分任务）：\n\n{requirement.parsed_text[:12000]}"
    )
    system = SYSTEM_PROMPT
    if current_content:
        user_content += f"\n\n【当前计划版本】\n{current_content[:8000]}"
    if suggestion:
        user_content += f"\n\n【修改意见】\n{suggestion}"
        system = (
            SYSTEM_PROMPT
            + "\n\n【重新生成要求】请重点结合【修改意见】对【当前计划版本】进行调整后重新生成一份完整计划，保持原有章节结构；"
            "若修改意见与当前版本内容冲突，以修改意见为准，同时兼顾需求文档与成员权重。"
        )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    return llm.chat(messages, temperature=0.4)


def generate_plan_stream(
    requirement,
    plan_name: str,
    start_date,
    launch_date,
    members,
    partial_content: str = "",
    suggestion: str = "",
    current_content: str = "",
):
    """流式生成计划（逐块产出）。

    - partial_content 非空：把已生成（被中断）的内容拼入上下文，从末尾继续，不重复。
    - suggestion + current_content：按「修改意见」结合「当前计划版本」重新生成（用于计划重新生成）。
    - 二者可同时传入（重新生成过程中被中断后再继续）。
    """
    today = timezone.localdate()
    member_lines = "、".join(
        f"{name}(权重{weight:.0%}{'；能力：' + capability if capability else ''})" for name, weight, capability in members
    )
    user_content = (
        f"需求文档名称：{requirement.title}\n"
        f"计划名称：{plan_name}\n"
        f"计划开始时间：{start_date}\n"
        f"计划上线时间：{launch_date}\n"
        f"今天日期：{today}\n"
        f"成员及权重：{member_lines}\n"
        f"需求文档内容（用于拆分任务）：\n\n{requirement.parsed_text[:12000]}"
    )
    system = SYSTEM_PROMPT
    if current_content:
        user_content += f"\n\n【当前计划版本】\n{current_content[:8000]}"
    if suggestion:
        user_content += f"\n\n【修改意见】\n{suggestion}"
        system = (
            SYSTEM_PROMPT
            + "\n\n【重新生成要求】请重点结合【修改意见】对【当前计划版本】进行调整后重新生成一份完整计划，保持原有章节结构；"
            "若修改意见与当前版本内容冲突，以修改意见为准，同时兼顾需求文档与成员权重。"
        )
    if partial_content:
        user_content += (
            "\n\n【已生成内容（被中断）】以下是之前已生成但被中断的部分，"
            "请从该内容末尾继续完整生成剩余部分，不要重复已生成的内容，保持章节结构连贯，最终输出一份完整计划。\n\n"
            f"{partial_content[-8000:]}"
        )
        system += "\n\n（继续生成模式）请直接从上次中断处继续，输出完整计划；不得重复用户已提供的内容。"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    return llm.chat_stream(messages, temperature=0.4, max_tokens=8192)


TASKS_SYSTEM_PROMPT = """你是项目任务拆分器。请根据需求文档、成员名单（含权重）与计划周期，将开发工作拆分为一份【任务列表】，输出为结构化 JSON。

要求：
1. 严格输出以下 JSON 结构（不要输出其他内容）：
{"tasks": [{"title":"任务名","description":"任务描述","module":"所属业务模块","difficulty":"simple|medium|hard","estimated_days":数字,"assignee":"成员名","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","depends":"前置任务标题或空","ui_images":["关联UI图名称",...]}]}
2. assignee 必须是给定的成员名单之一，且任务分配比例需与成员权重匹配（权重高者任务多/重）。
3. 每个任务的 start_date/end_date 必须在计划开始与上线时间之间，且结束不早于开始。
4. 按业务模块拆分，覆盖需求文档的主要功能点，任务数量合理（一般 5-20 个）。
5. ui_images：从给定的【项目原型图/UI图清单】中选出与该任务模块/功能相关的图名称（优先页面 UI 图，业务流程图/时序图等有助于理解业务的图也可关联）；没有相关图时输出空数组 []；严禁输出清单之外的名称。
只输出 JSON，不要输出解释。"""


def _prototype_images_text(prototype_images: list) -> str:
    """把 [(图名, 类型)] 清单转成供 AI 引用的文本段。"""
    if not prototype_images:
        return ""
    lines = "\n".join(f"- {name}（{kind}）" for name, kind in prototype_images)
    return f"\n\n【项目原型图/UI图清单（共 {len(prototype_images)} 张，ui_images 字段只能从中引用）】\n{lines}"


def generate_tasks(requirement, plan_name: str, start_date, launch_date, members, plan_content: str = "", prototype_images: list | None = None) -> list:
    """生成结构化任务列表。members: list of (username, weight)。
    plan_content 传入项目计划正文，AI 将严格遵循其中的「任务拆分（按业务模块）」分配。
    prototype_images: [(图名, 类型)]，供任务关联 ui_images。"""
    logger.info("[生成任务] 开始调用 AI：plan=%s requirement=%s 成员=%s", plan_name, requirement.title, member_list := "、".join(f"{n}({w})" for n, w, *_ in members))
    today = timezone.localdate()
    member_lines = "、".join(f"{name}(权重{weight:.0%})" for name, weight in members)
    user_content = (
        f"需求文档名称：{requirement.title}\n"
        f"计划名称：{plan_name}\n"
        f"计划开始时间：{start_date}\n"
        f"计划上线时间：{launch_date}\n"
        f"今天日期：{today}\n"
        f"成员名单及权重：{member_lines}\n"
        f"需求文档内容（用于拆分任务）：\n\n{requirement.parsed_text[:12000]}"
    )
    system = TASKS_SYSTEM_PROMPT
    user_content += _prototype_images_text(prototype_images)
    tasks_section = _extract_plan_tasks_section(plan_content)
    if tasks_section:
        user_content += f"\n\n【项目计划·任务拆分（必须严格遵循，据此拆分任务并指派到人）】\n{tasks_section[:6000]}"
        system = (
            TASKS_SYSTEM_PROMPT
            + "\n\n【硬性要求】必须严格按照【项目计划·任务拆分】中列出的任务项、所属业务模块与负责人进行拆分与指派，"
            "负责人必须是成员名单中的真实成员，不得自行更改负责人、合并或遗漏任务；仅在计划确有遗漏时可补充，补充任务也按权重分配。"
        )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    t0 = time.time()
    result = llm.chat_json(messages, temperature=0.2)
    tasks = result.get("tasks") or []
    logger.info("[生成任务] AI 返回耗时 %.1fs，解析出任务 %s 条", time.time() - t0, len(tasks))
    return tasks


def generate_tasks_stream(requirement, plan_name: str, start_date, launch_date, members, plan_content: str = "", prototype_images: list | None = None):
    """流式生成任务原始 JSON（逐块产出），由视图在完成后统一解析落库。
    plan_content 传入项目计划正文，AI 将严格遵循其中的「任务拆分（按业务模块）」分配。
    prototype_images: [(图名, 类型)]，供任务关联 ui_images。"""
    logger.info("[生成任务] 开始流式调用 AI：plan=%s requirement=%s 成员=%s", plan_name, requirement.title, "、".join(f"{n}({w})" for n, w, *_ in members))
    today = timezone.localdate()
    member_lines = "、".join(f"{name}(权重{weight:.0%})" for name, weight in members)
    user_content = (
        f"需求文档名称：{requirement.title}\n"
        f"计划名称：{plan_name}\n"
        f"计划开始时间：{start_date}\n"
        f"计划上线时间：{launch_date}\n"
        f"今天日期：{today}\n"
        f"成员名单及权重：{member_lines}\n"
        f"需求文档内容（用于拆分任务）：\n\n{requirement.parsed_text[:12000]}"
    )
    system = TASKS_SYSTEM_PROMPT
    user_content += _prototype_images_text(prototype_images)
    tasks_section = _extract_plan_tasks_section(plan_content)
    if tasks_section:
        user_content += f"\n\n【项目计划·任务拆分（必须严格遵循，据此拆分任务并指派到人）】\n{tasks_section[:6000]}"
        system = (
            TASKS_SYSTEM_PROMPT
            + "\n\n【硬性要求】必须严格按照【项目计划·任务拆分】中列出的任务项、所属业务模块与负责人进行拆分与指派，"
            "负责人必须是成员名单中的真实成员，不得自行更改负责人、合并或遗漏任务；仅在计划确有遗漏时可补充，补充任务也按权重分配。"
        )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    return llm.chat_stream(messages, temperature=0.2, max_tokens=8192)
