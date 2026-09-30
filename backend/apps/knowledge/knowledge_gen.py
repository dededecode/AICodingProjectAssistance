"""AI 知识整理：把项目计划/任务/架构设计等整理成结构化知识条目。"""
from services import llm

PROMPTS = {
    "plan": "你是项目计划知识整理助手。请把以下【项目计划】整理成若干条结构化知识（每条含标题与内容），便于后续开发与检索，"
            "如：计划总览、里程碑/周期、成员分工、各阶段安排等。输出 JSON {\"items\":[{\"title\":\"...\",\"content\":\"...\"}]}。只输出 JSON。",
    "task": "你是任务清单知识整理助手。请把以下【开发任务】整理成若干条结构化知识（每条含标题与内容），"
            "按业务模块归类，含任务说明、负责人、工期、依赖关系等要点。输出 JSON {\"items\":[{\"title\":\"...\",\"content\":\"...\"}]}。只输出 JSON。",
    "architecture": "你是架构知识整理助手。请把以下【架构设计】整理成若干条结构化知识（每条含标题与内容），"
                    "如：总体架构与分层、技术选型（前端/后端/底座/数据库）、模块划分、关键设计、数据库表设计等。"
                    "输出 JSON {\"items\":[{\"title\":\"...\",\"content\":\"...\"}]}。只输出 JSON。",
    "operation": "你是运营知识整理助手。请把以下【项目运营记录】整理成若干条结构化知识（每条含标题与内容），"
                  "按类型（迭代需求/优化需求/业务变更/用户反馈）归类，含各条目的描述、优先级、状态、提出人，"
                  "并汇总运营指标（续期/续费/满意度等）。输出 JSON {\"items\":[{\"title\":\"...\",\"content\":\"...\"}]}。只输出 JSON。",
}


def organize_knowledge(kind: str, project_name: str, context: str) -> list:
    """整理为知识条目列表 [{title, content}]。"""
    system = PROMPTS.get(kind, PROMPTS["plan"])
    user = f"项目：{project_name}\n\n原始内容：\n{context[:15000]}"
    result = llm.chat_json(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
    )
    return result.get("items") or []
