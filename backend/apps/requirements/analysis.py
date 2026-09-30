"""AI 需求完整度分析：基于需求要素清单（含权重）打分并给出缺失意见。"""
from services import llm as llm_svc

# 需求要素及权重（权重用于加权计算整体得分）
REQUIREMENT_ELEMENTS = [
    {"name": "背景与目标", "weight": 0.10},
    {"name": "功能需求", "weight": 0.25},
    {"name": "非功能需求（性能/安全/可用性）", "weight": 0.10},
    {"name": "用户角色与权限", "weight": 0.20},
    {"name": "业务规则与边界", "weight": 0.20},
    {"name": "验收标准", "weight": 0.05},
    {"name": "风险与依赖", "weight": 0.05},
    {"name": "技术约束", "weight": 0.05},
]

_ELEMENTS_DESC = "、".join(e["name"] for e in REQUIREMENT_ELEMENTS)
_WEIGHT_HINT = "、".join(f"{e['name']}(权重{int(e['weight']*100)}%)" for e in REQUIREMENT_ELEMENTS)


def _weight_of(name: str) -> float:
    for e in REQUIREMENT_ELEMENTS:
        if e["name"] == name:
            return e["weight"]
    return 0.0


def _weighted_score(elements) -> int:
    """按权重计算整体得分（elements 未提供整体分时的兜底）。"""
    total_w = 0.0
    acc = 0.0
    for e in elements:
        w = _weight_of(e.get("name", ""))
        if w > 0:
            total_w += w
            acc += w * e.get("score", 0)
    if total_w <= 0:
        # 权重未知则退化为平均分
        scores = [e.get("score", 0) for e in elements]
        return int(sum(scores) / len(scores)) if scores else 0
    return int(round(acc / total_w))


SYSTEM_PROMPT = f"""一位你是资深的需求分析师。请对给定的项目需求文档进行完整度检测，并评估内容质量。

请严格按以下 JSON 结构输出，不要输出其他内容：
{{
  "overall_score": 0-100 的整数,
  "verdict": "passed" 或 "needs_revision",
  "elements": [
    {{"name": "需求要素名", "present": true/false, "score": 0-100, "comment": "简要说明"}}
  ],
  "quality": {{
    "clarity": 0-100,
    "understandability": 0-100,
    "logic": 0-100,
    "comment": "内容质量总评与说明"
  }},
  "missing": ["缺失或不足的要素/要点列表"],
  "suggestions": ["具体改进建议列表"]
}}

打分要求：
1. 请依据以下要素清单逐项判断文档是否覆盖（完整度）：{_ELEMENTS_DESC}。
2. 其中【{_WEIGHT_HINT}】三项在完整度中权重最高，是评审重点，请重点检验其完整度与细节；若这三项缺失或含糊，完整度得分应显著拉低。
3. 【内容质量】评估（除完整性外同样重要），逐项打分：
   - quality.clarity：需求是否阐述清楚、无歧义、描述具体（而非泛泛而谈）。
   - quality.understandability：开发团队能否据此直接理解业务并开始实现（是否说清输入、处理逻辑、输出/交互）。
   - quality.logic：条理是否清晰、前后是否一致、有无自相矛盾或跳跃。
4. overall_score = 完整度加权分 × 0.7 + 质量平均分（clarity/understandability/logic 均值）× 0.3。
5. verdict 规则：overall_score >= 70 判定为 "passed"，否则为 "needs_revision"。
6. present=false、score 偏低或质量项偏低的，务必在 missing 或 suggestions 中给出具体、可执行的改进建议。"""


def analyze_requirement(parsed_text: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"项目需求文档内容如下：\n\n{parsed_text[:10000]}"},
    ]
    result = llm_svc.chat_json(messages)
    # 规范化字段
    result.setdefault("elements", [])
    result.setdefault("missing", [])
    result.setdefault("suggestions", [])
    q = result.get("quality") or {}
    result["quality"] = {
        "clarity": int(q.get("clarity", 0) or 0),
        "understandability": int(q.get("understandability", 0) or 0),
        "logic": int(q.get("logic", 0) or 0),
        "comment": q.get("comment", "") or "",
    }
    if "overall_score" not in result:
        # 兜底：完整度(0.7) + 质量平均分(0.3) 加权
        comp = _weighted_score(result["elements"])
        qs = [result["quality"][k] for k in ("clarity", "understandability", "logic")]
        qs = [v for v in qs if v]
        qavg = sum(qs) / len(qs) if qs else comp
        result["overall_score"] = int(round(comp * 0.7 + qavg * 0.3))
    if "verdict" not in result:
        result["verdict"] = "passed" if result["overall_score"] >= 70 else "needs_revision"
    return result
