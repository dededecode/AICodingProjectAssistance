"""AI 测试：生成测试用例、生成测试报告。"""
import json

from services import llm

CASES_SYSTEM = """你是资深测试工程师。请根据提供的【需求文档】【架构设计】【计划任务拆分】等多来源内容，生成一份贴合实际实现的【测试用例列表】，输出为 JSON。

严格输出以下结构（不要输出其他内容）：
{"cases": [{"name":"用例名称","module":"所属模块","description":"测试步骤/场景描述","priority":"low|medium|high","expected_result":"预期结果"}]}

要求：
- 用例应贴合【计划任务拆分】中的任务与【架构设计】中的模块划分、关键设计与表结构，使测试场景覆盖真实实现。
- 覆盖需求文档的主要功能点，含正常场景、边界、异常场景。
- 用例数量合理（一般 5-15 条）。
- module 优先使用任务/架构中的业务模块名；若给定模块名则统一使用该模块。
- 若包含【本次重点生成用例的目标任务】，则以该任务为中心生成用例。
只输出 JSON。"""


def generate_test_cases(context: str, module: str = "") -> list:
    """生成测试用例列表。context 为需求/架构/任务等多来源拼接内容。"""
    user = f"指定模块：{module or '（按内容自动划分）'}\n\n需求/任务内容：\n{context[:60000]}"
    result = llm.chat_json(
        [{"role": "system", "content": CASES_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.3,
    )
    return result.get("cases") or []


REPORT_SYSTEM = """你是测试负责人。请根据项目的测试统计数据与失败/阻塞用例清单，撰写一份【测试报告】（中文 markdown），须包含：
## 一、测试概述
## 二、测试统计
用表格展示用例数、任务数、通过率、各状态数量、优先级分布。
## 三、缺陷分析
列出失败/阻塞用例及原因，分析共性。
## 四、结论与建议
给出是否可交付/上线的结论与后续建议。
只输出报告内容，不要输出其他解释。"""


def generate_report(project_name: str, stats: dict, failed_items: list) -> str:
    user = (
        f"项目：{project_name}\n"
        f"测试统计：{json.dumps(stats, ensure_ascii=False)}\n"
        f"失败/阻塞用例：{json.dumps(failed_items, ensure_ascii=False)}"
    )
    return llm.chat(
        [{"role": "system", "content": REPORT_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.4,
    )
