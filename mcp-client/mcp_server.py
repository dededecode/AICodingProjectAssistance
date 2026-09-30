"""AICodingProjectAssistance MCP 服务端（纯 stdio 实现，不依赖 mcp 包）。

通过 MCP（Model Context Protocol, stdio + JSON-RPC 2.0）向 AI 客户端暴露平台能力：
- 知识库上传 / 检索
- 交付文档上传
- 架构设计查询
- 数据库 SQL 查询

所有操作都基于【项目】，项目 id 在 MCP 服务端配置（可被每个工具的参数覆盖）。

配置（环境变量或同目录 mcp_server_config.json，优先级：环境变量 > 配置文件 > 默认）：
- PLATFORM_API_URL      平台地址，默认 http://127.0.0.1:8000
- PLATFORM_API_TOKEN    用户的 MCP Token（在平台的「用户管理」中查看/生成），
                        平台按此 Token 识别操作者身份，并校验其是否为目标项目成员（管理员除外）
- PLATFORM_PROJECT_ID   默认项目 id（MCP 服务端配置时填上）

运行：python mcp_server.py （stdin/stdout 通信，供 MCP 客户端以 stdio 方式连接）
依赖：httpx   ->  pip install httpx
"""
import json
import os
import sys

# httpx 改为惰性导入：确保 tools/list 等无需 httpx 的能力在缺少依赖时也能工作，
# 避免不同客户端环境下启动即崩溃（transport closed）。

# ── 中文参数修复 ──
def _repair_unicode(s):
    """修复 Windows 管道/工具桥把 UTF-8 字节经 surrogateescape 转成 \\udcXX 导致的中文损坏。

    还原规则：U+DC80~U+DCFF 视为对应字节 0x80~0xFF，重组为 UTF-8 后解码。
    正常文本不会出现该代理项区间，因此可安全还原。
    """
    if not s:
        return s
    out = bytearray()
    for ch in s:
        o = ord(ch)
        if 0xDC80 <= o <= 0xDCFF:
            out.append(o & 0xFF)
        else:
            out.extend(ch.encode("utf-8"))
    return out.decode("utf-8", "replace")


def _fix(obj):
    """递归修复参数中的中文损坏。"""
    if isinstance(obj, str):
        return _repair_unicode(obj)
    if isinstance(obj, dict):
        return {k: _fix(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fix(x) for x in obj]
    return obj

# ── 配置 ──
_config = {}
_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server_config.json")
if os.path.exists(_cfg_path):
    try:
        with open(_cfg_path, "r", encoding="utf-8") as f:
            _config = json.load(f) or {}
    except Exception:
        _config = {}


def _get(key, default):
    return os.getenv(key) or _config.get(key) or default


BASE_URL = _get("PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = _get("PLATFORM_API_TOKEN", "local-mcp-service-token")
DEFAULT_PROJECT_ID = _get("PLATFORM_PROJECT_ID", "1")

PROTOCOL_VERSION = "2025-03-26"
SERVER_NAME = "ai-platform"
SERVER_VERSION = "1.0.0"


def _headers():
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    return headers


def _project(project_id):
    return int(project_id or DEFAULT_PROJECT_ID)


def _text_page(text, page, page_size):
    """长文本按字符数分页。返回 (content, meta)。
    长文档一次返回会被 agent 截断，故正文类工具统一用本函数分页（默认每页 1000 字符）。"""
    size = max(1, int(page_size or 1000))
    if size > 20000:
        size = 20000
    total = len(text or "")
    total_pages = max(1, (total + size - 1) // size)
    page = max(1, int(page or 1))
    if page > total_pages:
        page = total_pages
    start = (page - 1) * size
    content = (text or "")[start:start + size]
    meta = {
        "total_chars": total,
        "page": page,
        "page_size": size,
        "total_pages": total_pages,
        "has_more": page < total_pages,
    }
    return content, meta


# ── 平台调用 ──
def _post(path, payload, timeout=120):
    import httpx

    try:
        r = httpx.post(f"{BASE_URL}{path}", json=_fix(payload), headers=_headers(), timeout=timeout)
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}
    try:
        data = r.json()
    except Exception:
        data = r.text
    if r.status_code in (200, 201):
        return {"ok": True, "status": r.status_code, "data": data}
    detail = data.get("detail") if isinstance(data, dict) else data
    return {"ok": False, "status": r.status_code, "error": detail or r.text}


def _get(path, params=None):
    import httpx

    try:
        r = httpx.get(f"{BASE_URL}{path}", params=_fix(params) if params else params, headers=_headers(), timeout=60)
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}
    try:
        data = r.json()
    except Exception:
        data = r.text
    if r.status_code == 200:
        return {"ok": True, "status": r.status_code, "data": data}
    detail = data.get("detail") if isinstance(data, dict) else data
    return {"ok": False, "status": r.status_code, "error": detail or r.text}


def _patch(path, payload):
    import httpx

    try:
        r = httpx.patch(f"{BASE_URL}{path}", json=_fix(payload), headers=_headers(), timeout=120)
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}
    try:
        data = r.json()
    except Exception:
        data = r.text
    if r.status_code in (200, 201):
        return {"ok": True, "status": r.status_code, "data": data}
    detail = data.get("detail") if isinstance(data, dict) else data
    return {"ok": False, "status": r.status_code, "error": detail or r.text}


def _delete(path):
    import httpx

    try:
        r = httpx.delete(f"{BASE_URL}{path}", headers=_headers(), timeout=60)
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}
    if r.status_code == 204:
        return {"ok": True, "status": 204, "data": None}
    try:
        data = r.json()
    except Exception:
        data = r.text
    detail = data.get("detail") if isinstance(data, dict) else data
    return {"ok": False, "status": r.status_code, "error": detail or r.text}


# ── 工具实现 ──
def tool_knowledge_add(args):
    pid = _project(args.get("project_id"))
    return _post("/api/knowledge/add/", {"project_id": pid, "text": args.get("text", ""), "title": args.get("title", "")})


def tool_knowledge_delete(args):
    """删除一条知识（同步清理向量，避免脏数据/重复影响检索）。"""
    return _delete(f"/api/knowledge/{int(args['item_id'])}/")


def tool_knowledge_search(args):
    pid = _project(args.get("project_id"))
    return _post("/api/knowledge/search/", {"project_id": pid, "query": args.get("query", ""), "top_k": int(args.get("top_k", 5))})


def tool_delivery_doc_upload(args):
    pid = _project(args.get("project_id"))
    return _post(
        "/api/delivery-docs/upload/",
        {"project_id": pid, "title": args.get("title", ""), "type": args.get("doc_type", ""), "content": args.get("content", "")},
    )


def tool_architecture_query(args):
    """查询指定项目的架构设计列表（概要：不含正文全文，避免长文截断）。
    需要查看某一版的架构概设文档或数据库 SQL 正文时，用 architecture_content_query 按 id 分页拉取。"""
    pid = _project(args.get("project_id"))
    res = _get("/api/architecture/", {"project_id": pid})
    if not res.get("ok"):
        return res
    items = []
    for d in (res.get("data") or []):
        doc = d.get("design_doc") or ""
        sql = d.get("db_sql") or ""
        items.append(
            {
                "id": d.get("id"),
                "project": d.get("project_name"),
                "frontend_stack": d.get("frontend_stack"),
                "backend_stack": d.get("backend_stack"),
                "base_framework": d.get("base_framework_display"),
                "db_type": d.get("db_type_display"),
                "design_doc_chars": len(doc),
                "db_sql_chars": len(sql),
                "creator": d.get("creator"),
                "created_at": d.get("created_at"),
            }
        )
    return {"ok": True, "status": 200, "data": items}


def tool_architecture_content_query(args):
    """按架构设计 id 分页读取正文：part=design_doc(架构概设文档，默认) 或 db_sql(数据库 SQL)。
    默认第 1 页、每页 1000 字符；请按返回 total_pages 依次传 page 拼接完整正文。"""
    pid = _project(args.get("project_id"))
    arch_id = int(args.get("architecture_id"))
    part = (args.get("part") or "design_doc").strip()
    if part not in ("design_doc", "db_sql"):
        return {"ok": False, "status": 0, "error": "part 只能是 design_doc 或 db_sql"}
    # 项目内定位该架构记录，避免跨项目取数
    res = _get("/api/architecture/", {"project_id": pid})
    if not res.get("ok"):
        return res
    hit = next((d for d in (res.get("data") or []) if d.get("id") == arch_id), None)
    if hit is None:
        return {"ok": False, "status": 0, "error": f"项目 {pid} 下不存在架构设计 id={arch_id}"}
    text = hit.get(part) or ""
    content, meta = _text_page(text, args.get("page"), args.get("page_size"))
    return {
        "ok": True,
        "status": 200,
        "data": {
            "id": arch_id,
            "project": hit.get("project_name"),
            "part": part,
            "label": "架构概设文档" if part == "design_doc" else "数据库 SQL",
            **meta,
            "content": content,
        },
    }


def tool_sql_query(args):
    """查询指定项目各架构版本的数据库设计 SQL 概要（不含全文，避免长文截断）。
    需要某版完整 SQL 时用 architecture_content_query(architecture_id, part=db_sql) 分页拉取。"""
    pid = _project(args.get("project_id"))
    res = _get("/api/architecture/", {"project_id": pid})
    if not res.get("ok"):
        return res
    items = [
        {
            "id": d.get("id"),
            "project": d.get("project_name"),
            "db_type": d.get("db_type_display"),
            "sql_chars": len(d.get("db_sql") or ""),
        }
        for d in (res.get("data") or [])
    ]
    return {"ok": True, "status": 200, "data": items}


def _latest_architecture(pid):
    """取项目最新一条架构设计记录；无记录时返回错误结果。"""
    res = _get("/api/architecture/", {"project_id": pid})
    if not res["ok"]:
        return None, res
    items = res["data"] if isinstance(res["data"], list) else []
    if not items:
        return None, {"ok": False, "status": res.get("status", 200), "error": "该项目暂无架构设计，无法修改"}
    return items[0], None


def tool_architecture_update(args):
    """覆盖修改项目最新架构设计文档。"""
    pid = _project(args.get("project_id"))
    design, err = _latest_architecture(pid)
    if err:
        return err
    content = (args.get("content") or "").strip()
    if not content:
        return {"ok": False, "status": 400, "error": "content 不能为空（将完整覆盖架构设计文档，请提供完整内容）"}
    return _patch(f"/api/architecture/{design['id']}/", {"design_doc": content})


def tool_sql_update(args):
    """覆盖修改项目最新数据库设计 SQL。"""
    pid = _project(args.get("project_id"))
    design, err = _latest_architecture(pid)
    if err:
        return err
    content = (args.get("content") or "").strip()
    if not content:
        return {"ok": False, "status": 400, "error": "content 不能为空（将完整覆盖数据库设计 SQL，请提供完整内容）"}
    payload = {"db_sql": content}
    if args.get("db_type"):
        payload["db_type"] = args["db_type"]
    return _patch(f"/api/architecture/{design['id']}/", payload)


def _resolve_workgroup(args):
    """定位工作群：group_id 优先，否则取项目最新创建的工作群。返回 (group, err)。"""
    pid = _project(args.get("project_id"))
    gid = args.get("group_id")
    if gid:
        try:
            res = _get(f"/api/work-groups/{int(gid)}/")
        except (ValueError, TypeError):
            return None, {"ok": False, "status": 400, "error": "group_id 格式错误"}
        return (res, None) if res["ok"] else (None, res)
    res = _get("/api/work-groups/", {"project_id": pid})
    if not res["ok"]:
        return None, res
    items = res["data"] if isinstance(res["data"], list) else []
    if not items:
        return None, {"ok": False, "status": res.get("status", 200), "error": "该项目暂无工作群"}
    return items[0], None


def tool_workgroup_message_query(args):
    """获取工作群最新消息（正序返回），用于 agent 读取群内通知/总结等。"""
    group, err = _resolve_workgroup(args)
    if err:
        return err
    try:
        limit = int(args.get("limit") or 20)
    except (ValueError, TypeError):
        limit = 20
    res = _get(f"/api/work-groups/{group['id']}/messages/", {"limit": limit})
    if not res["ok"]:
        return res
    return {"ok": True, "status": 200, "data": {"group_id": group["id"], "group_name": group["name"], "messages": res["data"]}}


def tool_workgroup_message_send(args):
    """向工作群发送消息，用于 agent 在群内输出总结/回复（如开发完成通知测试）。"""
    group, err = _resolve_workgroup(args)
    if err:
        return err
    content = (args.get("content") or "").strip()
    if not content:
        return {"ok": False, "status": 400, "error": "content 不能为空"}
    payload = {"content": content, "group": group["id"]}
    sender_username = (args.get("sender_username") or "").strip()
    if sender_username:
        member = next((m for m in group.get("members", []) if m.get("username") == sender_username), None)
        if not member:
            return {"ok": False, "status": 400, "error": f"用户 {sender_username} 不是该群成员，无法以该身份发言"}
        payload["sender_id"] = member["user"]
    return _post(f"/api/work-groups/{group['id']}/send-message/", payload)


def tool_task_create(args):
    """新增一条开发任务。title 必填；project_id 缺省用服务端配置项目。"""
    payload = {"project": _project(args.get("project_id"))}
    title = (args.get("title") or "").strip()
    if not title:
        return {"ok": False, "status": 0, "error": "缺少 title（任务名称）"}
    payload["title"] = title[:300]
    for k in ("description", "module", "depends"):
        if args.get(k) is not None:
            payload[k] = str(args.get(k) or "")
    if args.get("difficulty"):
        payload["difficulty"] = args["difficulty"]
    if args.get("status"):
        payload["status"] = args["status"]
    if args.get("estimated_days") is not None:
        try:
            payload["estimated_days"] = float(args["estimated_days"])
        except (TypeError, ValueError):
            return {"ok": False, "status": 0, "error": "estimated_days 必须是数字（人日）"}
    assignee = args.get("assignee")
    if assignee is not None and str(assignee) != "":
        try:
            payload["assignee"] = int(assignee)
        except (TypeError, ValueError):
            return {"ok": False, "status": 0, "error": "assignee 必须是项目成员的用户 id"}
    plan = args.get("plan")
    if plan is not None and str(plan) != "":
        try:
            payload["plan"] = int(plan)
        except (TypeError, ValueError):
            return {"ok": False, "status": 0, "error": "plan 必须是项目计划 id"}
    for k in ("start_date", "end_date"):
        v = (args.get(k) or "").strip()
        if v:
            payload[k] = v
    if args.get("ui_images") is not None:
        ui = args.get("ui_images")
        if not isinstance(ui, list) or not all(isinstance(x, str) for x in ui):
            return {"ok": False, "status": 0, "error": "ui_images 必须是字符串数组"}
        payload["ui_images"] = ui
    return _post("/api/plan-tasks/", payload)


def tool_task_query(args):
    """查询指定用户/项目的任务列表。"""
    params = {"project_id": _project(args.get("project_id"))}
    if args.get("user_id"):
        params["assignee"] = args["user_id"]
    if args.get("status"):
        params["status"] = args["status"]
    return _get("/api/plan-tasks/", params)


def tool_task_update(args):
    """修改任务：状态/标题/描述/模块/难度/工期/负责人/计划起止/前置依赖/所属计划/关联UI图。
    按需传入字段，传了哪个改哪个；至少传一个。assignee 用项目成员的用户 id。"""
    tid = int(args["task_id"])
    payload = {}
    if args.get("title") is not None:
        payload["title"] = str(args.get("title") or "").strip()
    if args.get("description") is not None:
        payload["description"] = str(args.get("description") or "")
    if args.get("module") is not None:
        payload["module"] = str(args.get("module") or "").strip()
    if args.get("difficulty"):
        payload["difficulty"] = args["difficulty"]
    if args.get("status"):
        payload["status"] = args["status"]
    if args.get("depends") is not None:
        payload["depends"] = str(args.get("depends") or "")
    if args.get("estimated_days") is not None:
        try:
            payload["estimated_days"] = float(args["estimated_days"])
        except (TypeError, ValueError):
            return {"ok": False, "status": 0, "error": "estimated_days 必须是数字（人日）"}
    assignee = args.get("assignee")
    if assignee is not None and str(assignee) != "":
        try:
            payload["assignee"] = int(assignee)
        except (TypeError, ValueError):
            return {"ok": False, "status": 0, "error": "assignee 必须是项目成员的用户 id"}
    for k in ("start_date", "end_date"):
        v = (args.get(k) or "").strip()
        if v:
            payload[k] = v
    plan = args.get("plan")
    if plan is not None and str(plan) != "":
        try:
            payload["plan"] = int(plan)
        except (TypeError, ValueError):
            return {"ok": False, "status": 0, "error": "plan 必须是项目计划 id"}
    if args.get("ui_images") is not None:
        ui = args.get("ui_images")
        if not isinstance(ui, list) or not all(isinstance(x, str) for x in ui):
            return {"ok": False, "status": 0, "error": "ui_images 必须是字符串数组"}
        payload["ui_images"] = ui
    if not payload:
        return {"ok": False, "status": 0, "error": "请至少提供要修改的一个字段"}
    return _patch(f"/api/plan-tasks/{tid}/", payload)


def tool_worklog_submit(args):
    """提交工时登记。date 缺省为今天；user_id 可选（管理员可代录）。"""
    pid = _project(args.get("project_id"))
    payload = {
        "project": pid,
        "hours": float(args.get("hours", 0)),
        "date": args.get("date") or "",
        "description": args.get("description", ""),
        "tasks": args.get("task_ids", []),
    }
    if args.get("user_id"):
        payload["user_id"] = args["user_id"]
    return _post("/api/work-logs/", payload)


def tool_worklog_query(args):
    """查询工时登记，可按项目/日期范围/成员筛选。"""
    params = {"project_id": _project(args.get("project_id"))}
    for k in ("start", "end", "user_id"):
        if args.get(k):
            params[k] = args[k]
    return _get("/api/work-logs/", params)


def tool_worklog_update(args):
    """修改工时登记（只能改自己的；管理员可改任意）。"""
    payload = {}
    for k in ("date", "hours", "description"):
        if args.get(k) is not None:
            payload[k] = args[k]
    if args.get("task_ids") is not None:
        payload["tasks"] = args["task_ids"]
    if not payload:
        return {"ok": False, "status": 0, "error": "没有可更新的字段"}
    return _patch(f"/api/work-logs/{int(args['worklog_id'])}/", payload)


def tool_worklog_delete(args):
    """删除工时登记（只能删自己的；管理员可删任意）。"""
    return _delete(f"/api/work-logs/{int(args['worklog_id'])}/")


def tool_test_case_query(args):
    """查询测试用例列表，可按模块、优先级过滤。"""
    params = {"project_id": _project(args.get("project_id"))}
    if args.get("module"):
        params["module"] = args["module"]
    if args.get("priority"):
        params["priority"] = args["priority"]
    return _get("/api/test-cases/", params)


def tool_test_case_add(args):
    """新增测试用例。"""
    pid = _project(args.get("project_id"))
    return _post(
        "/api/test-cases/",
        {
            "project": pid,
            "name": args.get("name", ""),
            "module": args.get("module", ""),
            "description": args.get("description", ""),
            "priority": args.get("priority", "medium"),
            "expected_result": args.get("expected_result", ""),
        },
    )


def tool_test_task_query(args):
    """查询测试任务列表，可按执行人、状态过滤。"""
    params = {"project_id": _project(args.get("project_id"))}
    if args.get("assignee"):
        params["assignee"] = args["assignee"]
    if args.get("status"):
        params["status"] = args["status"]
    return _get("/api/test-tasks/", params)


def tool_test_task_dispatch(args):
    """测试派单：将用例指派给执行人。"""
    return _post("/api/test-tasks/dispatch/", {"test_case_id": int(args["test_case_id"]), "assignee_id": int(args["assignee_id"])})


def tool_test_task_reassign(args):
    """测试任务改派：将已存在的测试任务转派给另一个执行人。"""
    return _patch(f"/api/test-tasks/{int(args['test_task_id'])}/", {"assignee": int(args["assignee_id"])})


def tool_test_task_update(args):
    """更新测试任务状态/结果/执行人。status: pending|executing|passed|failed|blocked|retest|closed；传 assignee_id 可改派。"""
    payload = {}
    if args.get("status"):
        payload["status"] = args["status"]
    if args.get("result"):
        payload["result"] = args["result"]
    if args.get("assignee_id"):
        payload["assignee"] = int(args["assignee_id"])
    return _patch(f"/api/test-tasks/{int(args['test_task_id'])}/", payload)


def tool_test_statistics(args):
    """测试统计：用例/任务规模、通过率、状态与优先级分布。"""
    return _get("/api/test-tasks/statistics/", {"project_id": _project(args.get("project_id"))})


def tool_test_case_generate(args):
    """AI 生成测试用例（依据需求文档或开发任务）。"""
    pid = _project(args.get("project_id"))
    payload = {"project_id": pid, "source": args.get("source", "requirement"), "module": args.get("module", "")}
    if args.get("task_id"):
        payload["task_id"] = args["task_id"]
    return _post("/api/test-cases/generate/", payload)


def tool_test_report(args):
    """生成测试报告并写入交付文档；通过率>=90%且处于开发中时推进项目到「项目交付」。"""
    return _post("/api/test-tasks/report/", {"project_id": _project(args.get("project_id"))})


def tool_bug_query(args):
    """查询缺陷列表，可按状态、严重程度、处理人过滤。"""
    params = {"project_id": _project(args.get("project_id"))}
    if args.get("status"):
        params["status"] = args["status"]
    if args.get("severity"):
        params["severity"] = args["severity"]
    if args.get("assignee"):
        params["assignee"] = args["assignee"]
    return _get("/api/bugs/", params)


def tool_bug_create(args):
    """新增缺陷。"""
    pid = _project(args.get("project_id"))
    payload = {
        "project": pid,
        "title": args.get("title", ""),
        "description": args.get("description", ""),
        "module": args.get("module", ""),
        "severity": args.get("severity", "medium"),
    }
    if args.get("assignee"):
        payload["assignee"] = args["assignee"]
    if args.get("related_task"):
        payload["related_task"] = args["related_task"]
    return _post("/api/bugs/", payload)


def tool_bug_update(args):
    """更新缺陷状态/处理人/严重程度/模块等。"""
    payload = {}
    for k in ("title", "description", "module", "severity", "status", "assignee", "related_task"):
        if args.get(k):
            payload[k] = args[k]
    return _patch(f"/api/bugs/{int(args['bug_id'])}/", payload)


def tool_bug_from_test_task(args):
    """从失败/阻塞的测试任务一键转缺陷。"""
    return _post("/api/bugs/from-test-task/", {"test_task_id": int(args["test_task_id"]), "severity": args.get("severity", "medium")})


def tool_bug_statistics(args):
    """缺陷统计：总数/未关闭/按状态与严重程度分布。"""
    return _get("/api/bugs/statistics/", {"project_id": _project(args.get("project_id"))})


def tool_requirement_query(args):
    """查询需求文档列表（标题/状态/完整度，不含正文）。"""
    res = _get("/api/requirements/", {"project_id": _project(args.get("project_id"))})
    if res.get("ok") and isinstance(res.get("data"), list):
        items = []
        for r in res["data"]:
            analysis = r.get("analysis_result") or {}
            items.append(
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "is_confirmed": r.get("is_confirmed"),
                    "verdict": analysis.get("verdict"),
                    "overall_score": analysis.get("overall_score"),
                    "created_at": r.get("created_at"),
                }
            )
        res["data"] = items
    return res


def tool_requirement_content_query(args):
    """按文档名称分页查询需求文档正文。长文档请按返回 total_pages 依次传 page=2,3,… 拼接完整正文，
    不要期望一次取全（单次返回会被截断）。"""
    name = (args.get("name") or "").strip()
    if not name:
        return {"ok": False, "status": 0, "error": "缺少 name（需求文档名称/标题）"}
    res = _get("/api/requirements/", {"project_id": _project(args.get("project_id"))})
    if not res.get("ok"):
        return res
    items = res["data"] if isinstance(res.get("data"), list) else []
    matches = [r for r in items if (r.get("title") or "") == name] or [r for r in items if name in (r.get("title") or "")]
    if not matches:
        return {"ok": False, "status": 0, "error": f"未找到名为「{name}」的需求文档"}
    r = matches[0]
    content, meta = _text_page(r.get("parsed_text") or "", args.get("page"), args.get("page_size"))
    return {"ok": True, "status": 200, "data": {"id": r.get("id"), "title": r.get("title"), **meta, "content": content}}


def tool_wiki_page_query(args):
    """查询项目 Wiki 页面列表（概要：id/标题/类型/来源/关联数/字符数，不含正文）。
    Wiki 是 LLM 从需求/架构/计划/交付文档编译出的结构化知识页，与知识库（knowledge_search）互相独立；
    需查看页面正文时用 wiki_page_content_query 按 id 分页拉取。"""
    params = {"project_id": _project(args.get("project_id"))}
    for k in ("source_type", "page_type", "keyword"):
        if args.get(k):
            params[k] = args[k]
    res = _get("/api/wiki/", params)
    if res.get("ok") and isinstance(res.get("data"), list):
        items = []
        for p in res["data"]:
            items.append(
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "page_type": p.get("page_type"),
                    "source_type": p.get("source_type"),
                    "source_title": p.get("source_title"),
                    "links_count": len(p.get("links") or []),
                    "content_chars": len(p.get("content") or ""),
                    "updated_at": p.get("updated_at"),
                }
            )
        res["data"] = items
    return res


def tool_wiki_page_content_query(args):
    """按页面 id 分页查询 Wiki 页面正文。长内容请按返回 total_pages 依次传 page=2,3,… 拼接，
    不要期望一次取全（单次返回会被截断）。"""
    if not args.get("page_id"):
        return {"ok": False, "status": 0, "error": "缺少 page_id（Wiki 页面 id，可用 wiki_page_query 查询）"}
    res = _get(f"/api/wiki/{int(args['page_id'])}/")
    if not res.get("ok"):
        return res
    p = res.get("data") or {}
    content, meta = _text_page(p.get("content") or "", args.get("page"), args.get("page_size"))
    return {
        "ok": True,
        "status": 200,
        "data": {
            "id": p.get("id"),
            "title": p.get("title"),
            "page_type": p.get("page_type"),
            "source_type": p.get("source_type"),
            "source_title": p.get("source_title"),
            "links": p.get("links") or [],
            "sources": p.get("sources") or [],
            **meta,
            "content": content,
        },
    }


def tool_wiki_compile_source(args):
    """触发 Wiki 编译并等待（最多约 2 分钟）。把源文档（需求/架构/计划/交付）编译为结构化 Wiki 知识页，
    编译时会把项目已有 Wiki 页面标题提供给模型，新页面会主动关联已有知识（跨文档知识网络）。
    返回 running 时用 wiki_compile_status 继续查询。source_id 可先用 requirement_query /
    architecture_query / project_plan_query 等工具查询获取。"""
    import time

    source_type = args.get("source_type")
    if source_type not in ("requirement", "architecture", "plan", "delivery"):
        return {"ok": False, "status": 0, "error": "source_type 只能是 requirement/architecture/plan/delivery"}
    if not args.get("source_id"):
        return {"ok": False, "status": 0, "error": "缺少 source_id（可先用 requirement_query 等工具查询文档 id）"}
    project_id = _project(args.get("project_id"))
    payload = {"project_id": project_id, "source_type": source_type, "source_id": int(args["source_id"])}
    res = _post("/api/wiki/compile/", payload)
    if res.get("status") == 409:
        return {
            "ok": True,
            "status": 200,
            "data": {"status": "running", "detail": res.get("error"), "hint": "该来源已有编译任务在执行，可用 wiki_compile_status 查询进度"},
        }
    if not res.get("ok"):
        return res
    log_id = (res.get("data") or {}).get("log_id")
    if not log_id:
        return res
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(5)
        st = _get("/api/wiki/compile-status/", {"project_id": project_id})
        if not st.get("ok"):
            continue
        for log in (st.get("data") or {}).get("logs", []):
            if log.get("id") == log_id and log.get("status") != "running":
                return {
                    "ok": True,
                    "status": 200,
                    "data": {
                        "log_id": log_id,
                        "status": log.get("status"),
                        "page_count": log.get("page_count"),
                        "error": log.get("error"),
                        "meta": log.get("meta") or {},
                        "duration_ms": log.get("duration_ms"),
                        "hint": "用 wiki_page_query 查看生成的页面，wiki_page_content_query 读取正文",
                    },
                }
    return {
        "ok": True,
        "status": 200,
        "data": {"log_id": log_id, "status": "running", "hint": "编译仍在进行（大文档可能 3~10 分钟），请用 wiki_compile_status 继续查询"},
    }


def tool_wiki_compile_status(args):
    """查询项目 Wiki 编译任务进度（最近 50 条：状态/页面数/错误/耗时）。编译为异步后台任务，
    wiki_compile_source 返回 running 时用它轮询；status=failed 时 error 字段含原因。"""
    res = _get("/api/wiki/compile-status/", {"project_id": _project(args.get("project_id"))})
    if res.get("ok"):
        logs = (res.get("data") or {}).get("logs", [])
        keys = ("id", "source_type", "source_id", "source_title", "status", "page_count", "error", "duration_ms", "created_at")
        res["data"] = {"logs": [{k: l.get(k) for k in keys} for l in logs]}
    return res


def tool_wiki_page_add(args):
    """直接新增 Wiki 页面（外部 agent 调用，不走平台 AI 编译）：标题+正文立即入库并向量化，
    新增后即参与 Wiki 检索与问答。links 传项目已有页面标题可实现双链关联（标题须与已有页面完全一致）。"""
    project_id = _project(args.get("project_id"))
    title = str(args.get("title") or "").strip()
    content = str(args.get("content") or "").strip()
    if not title or not content:
        return {"ok": False, "status": 0, "error": "缺少 title 或 content"}
    page_type = args.get("page_type")
    if page_type not in ("overview", "module", "entity", "table", "api", "timeline", "synthesis"):
        page_type = "synthesis"
    payload = {"project_id": project_id, "title": title, "content": content, "page_type": page_type}
    if args.get("links"):
        payload["links"] = args["links"]
    if args.get("source_title"):
        payload["source_title"] = args["source_title"]
    res = _post("/api/wiki/", payload)
    if res.get("ok"):
        p = res.get("data") or {}
        res["data"] = {
            "id": p.get("id"),
            "title": p.get("title"),
            "page_type": p.get("page_type"),
            "links": p.get("links") or [],
            "content_chars": len(p.get("content") or ""),
            "updated_at": p.get("updated_at"),
            "hint": "用 wiki_page_query 确认页面已入列，wiki_page_content_query 读取正文",
        }
    return res


def tool_operation_item_query(args):
    """查询运营记录，可按类型、状态过滤。"""
    params = {"project_id": _project(args.get("project_id"))}
    if args.get("category"):
        params["category"] = args["category"]
    if args.get("status"):
        params["status"] = args["status"]
    return _get("/api/operation-items/", params)


def tool_operation_item_create(args):
    """新增运营记录（迭代需求/优化需求/业务变更/用户反馈）。"""
    pid = _project(args.get("project_id"))
    payload = {
        "project": pid,
        "category": args.get("category", "iteration"),
        "title": args.get("title", ""),
        "content": args.get("content", ""),
        "priority": args.get("priority", "medium"),
        "status": args.get("status", "evaluating"),
        "requestor": args.get("requestor", ""),
    }
    return _post("/api/operation-items/", payload)


def tool_operation_item_update(args):
    """更新运营记录状态等。"""
    payload = {}
    for k in ("title", "content", "category", "priority", "status", "requestor"):
        if args.get(k):
            payload[k] = args[k]
    return _patch(f"/api/operation-items/{int(args['operation_item_id'])}/", payload)


def tool_operation_metric_query(args):
    """查询运营指标（按月，如续期/续费、满意度）。"""
    params = {"project_id": _project(args.get("project_id"))}
    if args.get("month"):
        params["month"] = args["month"]
    return _get("/api/operation-metrics/", params)


def tool_operation_metric_create(args):
    """登记运营指标（续期/续费、满意度、活跃用户等）。"""
    pid = _project(args.get("project_id"))
    return _post(
        "/api/operation-metrics/",
        {
            "project": pid,
            "month": args.get("month", ""),
            "indicator": args.get("indicator", "custom"),
            "value": float(args.get("value", 0)),
            "note": args.get("note", ""),
        },
    )


def tool_operation_statistics(args):
    """运营记录统计：按类型与状态分布。"""
    return _get("/api/operation-items/statistics/", {"project_id": _project(args.get("project_id"))})


# ── 原型图 / UI 图 ──
def tool_prototype_image_query(args):
    """查询指定项目的原型图/UI 图列表（可按名称/类型筛选，服务端分页，此处分页拉取全量）。"""
    params = {"project_id": _project(args.get("project_id")), "page_size": 100}
    if args.get("kind"):
        params["kind"] = args["kind"]
    name = (args.get("name") or "").strip()
    if name:
        params["name"] = name
    items, page = [], 1
    while True:
        params["page"] = page
        res = _get("/api/prototype-images/", params)
        if not res.get("ok"):
            return res
        data = res["data"]
        if isinstance(data, list):
            # 兼容未分页响应
            items.extend(data)
            break
        results = data.get("results") or []
        items.extend(results)
        count = data.get("count") or len(items)
        if not results or data.get("next") is None or len(items) >= count:
            break
        page += 1
    mapped = [
        {
            "id": d.get("id"),
            "name": d.get("name"),
            "kind": d.get("kind"),
            "kind_display": d.get("kind_display"),
            "url": d.get("image"),
            "uploader": d.get("uploader_name"),
            "created_at": d.get("created_at"),
        }
        for d in items
    ]
    return {"ok": True, "status": 200, "data": mapped}


def tool_prototype_image_upload(args):
    """上传一张原型图/UI 图到指定项目。AI agent 无法直接传二进制文件，请提供可访问的图片 URL。"""
    pid = _project(args.get("project_id"))
    payload = {
        "project": pid,
        "name": args.get("name", ""),
        "kind": args.get("kind", "prototype"),
        "image_url": args.get("image_url", ""),
    }
    return _post("/api/prototype-images/", payload)


def tool_prototype_image_download(args):
    """下载指定原型图/UI 图的原始字节（base64 编码返回，供 AI agent 读取图片内容）。"""
    import base64 as _b64
    import urllib.parse as _up

    img_id = int(args["image_id"])
    try:
        import httpx

        r = httpx.get(f"{BASE_URL}/api/prototype-images/{img_id}/download/", headers=_headers(), timeout=60)
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}
    if r.status_code != 200:
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            pass
        return {"ok": False, "status": r.status_code, "error": detail or r.text[:200]}
    ctype = r.headers.get("Content-Type", "")

    def _cd_name(cd):
        """解析 Content-Disposition，支持 RFC 5987 filename*=UTF-8'' 与普通 filename=""。"""
        for part in (cd or "").split(";"):
            part = part.strip()
            if part.lower().startswith("filename*="):
                try:
                    val = part.split("=", 1)[1]
                    charset, _, encoded = val.split("'", 2)
                    return _up.unquote(encoded, encoding=charset or "utf-8")
                except Exception:
                    pass
            if part.lower().startswith("filename="):
                return _up.unquote(part.split("=", 1)[1].strip("'\""))
        return ""

    name = _cd_name(r.headers.get("Content-Disposition", ""))
    if not name:
        # 兜底：从列表接口取图片元数据的 URL 文件名
        try:
            meta = _get(f"/api/prototype-images/{img_id}/")
            url = (meta.get("data") or {}).get("image") or ""
            name = _up.unquote(url.split("/")[-1].split("?")[0]) or "image"
        except Exception:
            name = "image"
    return {
        "ok": True,
        "status": 200,
        "data": {
            "image_id": img_id,
            "filename": name,
            "content_type": ctype,
            "size": len(r.content),
            "base64": _b64.b64encode(r.content).decode("ascii"),
        },
    }


# ── 项目成员画像 ──
def tool_member_profile_query(args):
    """查询项目成员画像（项目内角色、能力描述 capability、加入时间、承担任务统计）。
    用于 AI 为成员分配开发权重/派单前了解成员；仅项目负责人/项目经理(manager)/管理员可查，普通成员 403。"""
    pid = _project(args.get("project_id"))
    res = _get(f"/api/projects/{pid}/member-profiles/")
    if not res.get("ok"):
        return res
    return {"ok": True, "status": 200, "data": res.get("data") or []}


def tool_project_plan_update(args):
    """修改（覆盖）一份已有项目计划的内容/名称/日期（不调用服务端 AI）。"""
    plan_id = int(args["plan_id"])
    content = (args.get("plan_content") or "").strip()
    if not content:
        return {"ok": False, "status": 0, "error": "缺少 plan_content（完整计划正文 markdown）"}
    payload = {"plan_content": content}
    for k in ("name", "start_date", "launch_date"):
        v = (args.get(k) or "").strip()
        if v:
            payload[k] = v
    return _patch(f"/api/project-plans/{plan_id}/", payload)


def tool_project_plan_tasks_submit(args):
    """直接提交一份已生成好的任务 JSON 到项目计划并保存（覆盖该计划原有任务，不调用服务端 AI）。
    返回 {"imported": 导入条数, "plan": 计划概要}。"""
    plan_id = int(args["plan_id"])
    tasks = args.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return {"ok": False, "status": 0, "error": "tasks 不能为空，需为任务对象数组"}
    return _post(f"/api/project-plans/{plan_id}/tasks-import/", {"tasks": tasks})


# ── 项目计划 / 任务生成 ──
def _parse_members(members):
    """把 MCP 参数 members 解析为 [{user_id, weight}]；格式错误返回 None。"""
    try:
        return [
            {"user_id": int(m.get("user_id")), "weight": float(m.get("weight"))}
            for m in members
            if m and m.get("user_id") is not None
        ]
    except (TypeError, ValueError):
        return None


def tool_project_plan_query(args):
    """查询指定项目的项目计划列表（概要：不含正文全文，避免长文截断）。
    需要某计划完整正文时用 project_plan_content_query 按 id/名称分页拉取。"""
    res = _get("/api/project-plans/", {"project_id": _project(args.get("project_id"))})
    if not res.get("ok"):
        return res
    items = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "project": p.get("project_name"),
            "requirement_title": p.get("requirement_title"),
            "start_date": p.get("start_date"),
            "launch_date": p.get("launch_date"),
            "plan_content_chars": len(p.get("plan_content") or ""),
            "members": p.get("members") or [],
            "task_count": p.get("task_count") or 0,
            "creator": p.get("creator"),
            "created_at": p.get("created_at"),
        }
        for p in (res.get("data") or [])
    ]
    return {"ok": True, "status": 200, "data": items}


def tool_project_plan_content_query(args):
    """按计划 id 或名称分页查询单份项目计划正文（默认第 1 页、每页 1000 字符）。
    长计划请按返回 total_pages 依次传 page 拼接完整正文。plan_id 与 name 至少给一个（都给了以 plan_id 为准）。"""
    plan_id = (args.get("plan_id") or "").strip()
    name = (args.get("name") or "").strip()
    if plan_id:
        res = _get(f"/api/project-plans/{int(plan_id)}/")
        if not res.get("ok"):
            return res
        p = res.get("data")
    else:
        if not name:
            return {"ok": False, "status": 0, "error": "缺少 plan_id 或 name"}
        res = _get("/api/project-plans/", {"project_id": _project(args.get("project_id"))})
        if not res.get("ok"):
            return res
        items = res.get("data") or []
        matches = [x for x in items if (x.get("name") or "") == name] or [x for x in items if name in (x.get("name") or "")]
        if not matches:
            return {"ok": False, "status": 0, "error": f"未找到名为「{name}」的项目计划"}
        p = matches[0]
    content, meta = _text_page(p.get("plan_content") or "", args.get("page"), args.get("page_size"))
    return {
        "ok": True,
        "status": 200,
        "data": {
            "id": p.get("id"),
            "name": p.get("name"),
            "project": p.get("project_name"),
            "requirement_title": p.get("requirement_title"),
            "task_count": p.get("task_count") or 0,
            **meta,
            "content": content,
        },
    }


def tool_project_plan_create(args):
    """直接上传一份已生成好的项目计划正文并保存为新计划（不调用服务端 AI 生成，秒回）。
    适用：你在自己的 agent 里已生成完整计划 markdown，仅需入库。
    前置：项目需求需已确认、members 须为项目成员、调用者须为项目成员或管理员。"""
    plan_content = (args.get("plan_content") or "").strip()
    if not plan_content:
        return {"ok": False, "status": 0, "error": "缺少 plan_content（完整计划正文 markdown）"}
    member_payload = _parse_members(args.get("members") or [])
    if member_payload is None:
        return {"ok": False, "status": 0, "error": "members 格式错误：需 [{user_id, weight}]"}
    payload = {
        "project_id": _project(args.get("project_id")),
        "requirement_id": int(args.get("requirement_id")),
        "name": (args.get("name") or "").strip(),
        "start_date": args.get("start_date") or "",
        "launch_date": args.get("launch_date") or "",
        "members": member_payload,
        "plan_content": plan_content,
    }
    if not payload["name"] or not payload["start_date"] or not payload["launch_date"] or not member_payload:
        return {"ok": False, "status": 0, "error": "缺少必填参数（name/start_date/launch_date/members）"}
    # 后端 generate 端点识别到 plan_content 会直接落库、跳过 AI 生成
    return _post("/api/project-plans/generate/", payload)


def tool_architecture_upload(args):
    """直接上传一份已生成好的架构设计并保存为项目架构记录（架构概设文档 + 数据库 SQL，不调用服务端 AI）。
    适用：你在自己的 agent 里已完成架构设计，仅需入库。前置：项目需处于「架构设计」阶段
    （需求已确认且有项目计划）；调用者须为项目成员或管理员。"""
    payload = {
        # 后端 ArchitectureDesignSerializer 使用外键字段名 project（非 project_id）
        "project": _project(args.get("project_id")),
        "frontend_stack": (args.get("frontend_stack") or "").strip(),
        "backend_stack": (args.get("backend_stack") or "").strip(),
        "base_framework": (args.get("base_framework") or "").strip(),
        "db_type": (args.get("db_type") or "mysql").strip(),
        "design_doc": args.get("design_doc") or "",
        "db_sql": args.get("db_sql") or "",
    }
    if not payload["frontend_stack"] or not payload["backend_stack"]:
        return {"ok": False, "status": 0, "error": "缺少必填参数（frontend_stack/backend_stack）"}
    if not payload["design_doc"] and not payload["db_sql"]:
        return {"ok": False, "status": 0, "error": "design_doc 与 db_sql 至少提供一项"}
    if payload["base_framework"] not in ("", "ruoyi-vue-plus", "smart-admin"):
        return {"ok": False, "status": 0, "error": "base_framework 只能是 空/ruoyi-vue-plus/smart-admin"}
    if payload["db_type"] not in ("mysql", "postgresql"):
        return {"ok": False, "status": 0, "error": "db_type 只能是 mysql 或 postgresql"}
    return _post("/api/architecture/", payload)


# ── 工具元数据（供 tools/list） ──
def _json_schema(props, required):
    return {"type": "object", "properties": props, "required": required}


PROJECT_PROP = {"type": "string", "description": "项目 id（缺省用服务端配置）"}

TOOLS = [
    {
        "name": "knowledge_add",
        "description": "向指定项目的知识库新增一条知识",
        "inputSchema": _json_schema(
            {"text": {"type": "string", "description": "知识内容"}, "title": {"type": "string", "description": "标题（可空）"}, "project_id": PROJECT_PROP},
            ["text"],
        ),
    },
    {
        "name": "knowledge_delete",
        "description": "删除一条知识（同步清理向量，避免脏数据/重复影响检索）",
        "inputSchema": _json_schema(
            {"item_id": {"type": "string", "description": "知识条目 id"}, "project_id": PROJECT_PROP},
            ["item_id"],
        ),
    },
    {
        "name": "knowledge_search",
        "description": "在指定项目的知识库中进行语义检索",
        "inputSchema": _json_schema(
            {"query": {"type": "string", "description": "检索内容"}, "top_k": {"type": "integer", "description": "返回条数"}, "project_id": PROJECT_PROP},
            ["query"],
        ),
    },
    {
        "name": "delivery_doc_upload",
        "description": "上传交付文档（内容形式，如详细设计/操作说明书）到指定项目",
        "inputSchema": _json_schema(
            {
                "title": {"type": "string"},
                "content": {"type": "string", "description": "文档内容"},
                "doc_type": {"type": "string", "description": "文档类型：architecture(架构设计文档)/testing(测试文档)/deployment(部署文档)/other(其它)，可空，默认按内容识别归一"},
                "project_id": PROJECT_PROP,
            },
            ["title", "content"],
        ),
    },
    {
        "name": "requirement_query",
        "description": "查询项目需求文档列表（标题/状态/完整度，不含正文）",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "requirement_content_query",
        "description": "按文档名称分页查询需求文档正文：每次返回约 1000 字符（page_size 可调）。返回含 total_pages/has_more，正文长时请循环 page=1..total_pages 拼接，勿期望一次取全",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "name": {"type": "string", "description": "需求文档名称/标题"},
                "page": {"type": "integer", "description": "页码，从 1 开始（默认 1）"},
                "page_size": {"type": "integer", "description": "每页字符数（默认 1000，最大 20000）"},
            },
            ["name"],
        ),
    },
    {
        "name": "wiki_page_query",
        "description": "查询项目 Wiki 页面列表（概要：id/标题/类型/来源，不含正文）。Wiki 是 LLM 从需求/架构/计划/交付文档编译出的结构化知识页，与知识库互相独立",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "source_type": {"type": "string", "description": "按来源过滤：requirement|architecture|plan|delivery"},
                "page_type": {"type": "string", "description": "按页面类型过滤：overview|module|entity|table|api|timeline|synthesis"},
                "keyword": {"type": "string", "description": "标题/内容关键词"},
            },
            [],
        ),
    },
    {
        "name": "wiki_page_content_query",
        "description": "按页面 id 分页查询 Wiki 页面正文：每次返回约 1000 字符（page_size 可调）。返回含 total_pages/has_more，正文长时请循环 page=1..total_pages 拼接",
        "inputSchema": _json_schema(
            {
                "page_id": {"type": "string", "description": "Wiki 页面 id（wiki_page_query 可查）"},
                "page": {"type": "integer", "description": "页码，从 1 开始（默认 1）"},
                "page_size": {"type": "integer", "description": "每页字符数（默认 1000，最大 20000）"},
            },
            ["page_id"],
        ),
    },
    {
        "name": "wiki_compile_source",
        "description": "把项目源文档（需求/架构/计划/交付）编译为 Wiki 知识页：LLM 生成结构化、互联、可溯源的知识页并向量化（与知识库检索互相独立）。编译时注入项目已有 Wiki 页面标题，新页面会主动关联已有知识。本工具最多等待约 2 分钟，仍在编译时返回 running，用 wiki_compile_status 继续查询",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "source_type": {"type": "string", "description": "源文档类型：requirement|architecture|plan|delivery"},
                "source_id": {"type": "string", "description": "源文档 id，可先用 requirement_query / architecture_query / project_plan_query 等查询"},
            },
            ["source_type", "source_id"],
        ),
    },
    {
        "name": "wiki_compile_status",
        "description": "查询项目 Wiki 编译任务进度（最近 50 条：状态/页面数/错误/耗时）。编译为异步后台任务，wiki_compile_source 返回 running 时用它轮询；status=failed 时 error 字段含原因",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "wiki_page_add",
        "description": "直接新增 Wiki 页面（外部 agent 调用，不走平台 AI 编译）：标题+正文立即入库并向量化，新增后即参与 Wiki 检索与问答。links 传项目已有页面标题可实现双链关联",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "title": {"type": "string", "description": "页面标题（建议用「类型-主题」格式，如 模块-勋章系统）"},
                "content": {"type": "string", "description": "页面正文（Markdown）"},
                "page_type": {"type": "string", "description": "页面类型：overview|module|entity|table|api|timeline|synthesis（默认 synthesis）"},
                "links": {"type": "array", "items": {"type": "string"}, "description": "关联的已有页面标题（双链，须与已有页面标题完全一致）"},
                "source_title": {"type": "string", "description": "来源说明（可选）"},
            },
            ["title", "content"],
        ),
    },
    {
        "name": "architecture_query",
        "description": "查询指定项目的架构设计列表（概要：id/技术栈/底座/数据库/文档与SQL字符数，不含正文全文）。需查看正文请用 architecture_content_query 按 id 分页拉取",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "architecture_content_query",
        "description": "按架构设计 id 分页读取正文（part=design_doc 架构概设文档 / db_sql 数据库 SQL）。每次约 1000 字符，长文请循环 page=1..total_pages 拼接。architecture_id 来自 architecture_query",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "architecture_id": {"type": "integer", "description": "架构设计 id（architecture_query 返回）"},
                "part": {"type": "string", "description": "design_doc(默认)|db_sql"},
                "page": {"type": "integer", "description": "页码，从 1 开始（默认 1）"},
                "page_size": {"type": "integer", "description": "每页字符数（默认 1000，最大 20000）"},
            },
            ["architecture_id"],
        ),
    },
    {
        "name": "sql_query",
        "description": "查询指定项目各架构版本的数据库设计 SQL 概要（id/数据库类型/SQL字符数，不含全文）。完整 SQL 用 architecture_content_query(architecture_id, part=db_sql) 分页拉取",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "architecture_update",
        "description": "覆盖修改项目最新的架构设计文档（design_doc）。content 必须是完整的文档内容(markdown)，将整体覆盖原文档",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "content": {"type": "string", "description": "完整的架构设计文档内容(markdown)"}},
            ["content"],
        ),
    },
    {
        "name": "sql_update",
        "description": "覆盖修改项目最新的数据库设计 SQL。content 必须是完整的 SQL 内容，将整体覆盖；可选 db_type 指定数据库类型",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "content": {"type": "string", "description": "完整的数据库设计 SQL，将整体覆盖"},
                "db_type": {"type": "string", "description": "可选，mysql|postgresql"},
            },
            ["content"],
        ),
    },
    {
        "name": "workgroup_message_query",
        "description": "获取工作群最新消息（按时间正序返回）。不传 group_id 时取项目最新创建的工作群。用于 agent 读取群内通知、任务指派、开发/测试总结等",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "group_id": {"type": "string", "description": "工作群 id（缺省取项目最新创建的群）"},
                "limit": {"type": "string", "description": "获取条数，默认 20"},
            },
            [],
        ),
    },
    {
        "name": "workgroup_message_send",
        "description": "向工作群发送消息。不传 group_id 时取项目最新创建的工作群；sender_username 须为群成员，缺省以当前用户身份发送。agent 开发完成后应在群内输出总结（如：我已完成xx模块功能，并生成测试用例和任务，请测试人员开始测试）",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "group_id": {"type": "string", "description": "工作群 id（缺省取项目最新创建的群）"},
                "content": {"type": "string", "description": "消息内容"},
                "sender_username": {"type": "string", "description": "以哪个群成员身份发言（用户名），缺省当前用户"},
            },
            ["content"],
        ),
    },
    {
        "name": "task_create",
        "description": "新增一条开发任务：title 必填；project_id 缺省用服务端配置项目；plan/assignee(项目成员用户id)/module/difficulty(simple|medium|hard)/estimated_days/status/start_date/end_date/depends/ui_images 可选。权限与平台一致（登录用户，通常为项目成员/管理员）",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "title": {"type": "string", "description": "任务名称（必填）"},
                "description": {"type": "string", "description": "任务描述"},
                "module": {"type": "string", "description": "所属业务模块"},
                "difficulty": {"type": "string", "description": "simple|medium|hard（默认 medium）"},
                "status": {"type": "string", "description": "pending|executing|done|blocked（默认 pending）"},
                "estimated_days": {"type": "number", "description": "预估工期（人日）"},
                "assignee": {"type": "integer", "description": "负责人：项目成员的用户 id（可空）"},
                "plan": {"type": "integer", "description": "所属项目计划 id（可空）"},
                "start_date": {"type": "string", "description": "计划开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "计划完成日期 YYYY-MM-DD"},
                "depends": {"type": "string", "description": "前置依赖任务标题或空"},
                "ui_images": {"type": "array", "items": {"type": "string"}, "description": "关联的原型图/UI图名称数组"},
            },
            ["title"],
        ),
    },
    {
        "name": "task_query",
        "description": "查询任务列表，可按项目、负责人(user_id)、状态过滤。返回含 ui_images（任务关联的原型图/UI图名称列表，可用 prototype_image_download 按名称拉取图片辅助开发）",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "user_id": {"type": "string", "description": "负责人用户 id"}, "status": {"type": "string", "description": "pending|executing|done|blocked"}},
            [],
        ),
    },
    {
        "name": "task_update",
        "description": "修改任务（按需传字段，传哪个改哪个；至少传一个）。可改：title 标题、description 描述、module 业务模块、difficulty 难度(simple|medium|hard)、status 状态(pending|executing|done|blocked)、estimated_days 工期人日、assignee 负责人(项目成员用户 id)、start_date/end_date 计划起止(YYYY-MM-DD)、depends 前置依赖、plan 所属计划 id、ui_images 关联UI图名称数组。任务修改权限与平台一致（项目成员/管理员）",
        "inputSchema": _json_schema(
            {
                "task_id": {"type": "string", "description": "任务 id"},
                "title": {"type": "string", "description": "任务名称"},
                "description": {"type": "string", "description": "任务描述"},
                "module": {"type": "string", "description": "所属业务模块"},
                "difficulty": {"type": "string", "description": "simple|medium|hard"},
                "status": {"type": "string", "description": "pending|executing|done|blocked"},
                "estimated_days": {"type": "number", "description": "预估工期（人日）"},
                "assignee": {"type": "integer", "description": "负责人：项目成员的用户 id"},
                "start_date": {"type": "string", "description": "计划开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "计划完成日期 YYYY-MM-DD"},
                "depends": {"type": "string", "description": "前置依赖任务标题或空"},
                "plan": {"type": "integer", "description": "所属项目计划 id（可迁移到其它计划）"},
                "ui_images": {"type": "array", "items": {"type": "string"}, "description": "关联的原型图/UI图名称数组（整体覆盖）"},
            },
            ["task_id"],
        ),
    },
    {
        "name": "worklog_submit",
        "description": "提交工时登记。date 缺省为今天；user_id 可选（管理员可代录）",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "hours": {"type": "number", "description": "工时(小时)"},
                "date": {"type": "string", "description": "日期 YYYY-MM-DD，缺省今天"},
                "description": {"type": "string", "description": "工作内容"},
                "task_ids": {"type": "array", "items": {"type": "integer"}, "description": "关联任务 id 列表"},
                "user_id": {"type": "string", "description": "登记的用户 id（管理员可代录）"},
            },
            ["hours"],
        ),
    },
    {
        "name": "worklog_query",
        "description": "查询工时登记，可按项目/日期范围/成员筛选",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "start": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "user_id": {"type": "string", "description": "成员 id"},
            },
            [],
        ),
    },
    {
        "name": "worklog_update",
        "description": "修改工时登记（只能改自己的；管理员可改任意）",
        "inputSchema": _json_schema(
            {
                "worklog_id": {"type": "string"},
                "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
                "hours": {"type": "number", "description": "工时(小时)"},
                "description": {"type": "string", "description": "工作内容"},
                "task_ids": {"type": "array", "items": {"type": "integer"}, "description": "关联任务 id 列表"},
            },
            ["worklog_id"],
        ),
    },
    {
        "name": "worklog_delete",
        "description": "删除工时登记（只能删自己的；管理员可删任意）",
        "inputSchema": _json_schema({"worklog_id": {"type": "string"}}, ["worklog_id"]),
    },
    {
        "name": "test_case_query",
        "description": "查询测试用例列表，可按模块、优先级过滤",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "module": {"type": "string"}, "priority": {"type": "string", "description": "low|medium|high"}},
            [],
        ),
    },
    {
        "name": "test_case_add",
        "description": "新增测试用例",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "name": {"type": "string", "description": "用例名称"},
                "module": {"type": "string", "description": "所属模块"},
                "description": {"type": "string"},
                "priority": {"type": "string", "description": "low|medium|high"},
                "expected_result": {"type": "string", "description": "预期结果"},
            },
            ["name"],
        ),
    },
    {
        "name": "test_task_query",
        "description": "查询测试任务列表，可按执行人、状态过滤",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "assignee": {"type": "string", "description": "执行人用户 id"}, "status": {"type": "string", "description": "pending|executing|passed|failed|blocked|retest|closed"}},
            [],
        ),
    },
    {
        "name": "test_task_dispatch",
        "description": "测试派单：将用例指派给执行人",
        "inputSchema": _json_schema(
            {"test_case_id": {"type": "string", "description": "用例 id"}, "assignee_id": {"type": "string", "description": "执行人用户 id"}},
            ["test_case_id", "assignee_id"],
        ),
    },
    {
        "name": "test_task_reassign",
        "description": "测试任务改派：将已存在的测试任务转派给另一个执行人",
        "inputSchema": _json_schema(
            {"test_task_id": {"type": "string", "description": "测试任务 id"}, "assignee_id": {"type": "string", "description": "新执行人用户 id"}},
            ["test_task_id", "assignee_id"],
        ),
    },
    {
        "name": "test_task_update",
        "description": "更新测试任务状态/结果/执行人",
        "inputSchema": _json_schema(
            {
                "test_task_id": {"type": "string", "description": "测试任务 id"},
                "status": {"type": "string", "description": "pending|executing|passed|failed|blocked|retest|closed"},
                "result": {"type": "string", "description": "测试结果/说明"},
                "assignee_id": {"type": "string", "description": "改派到新执行人用户 id"},
            },
            ["test_task_id"],
        ),
    },
    {
        "name": "test_statistics",
        "description": "测试统计：用例/任务规模、通过率、状态与优先级分布",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "test_case_generate",
        "description": "AI 生成测试用例（依据需求文档或开发任务），返回待确认的用例列表",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "source": {"type": "string", "description": "requirement|task"}, "module": {"type": "string"}, "task_id": {"type": "string", "description": "source=task 时的开发任务 id"}},
            [],
        ),
    },
    {
        "name": "test_report",
        "description": "生成测试报告并写入交付文档；通过率>=90%且处于开发中时推进项目到「项目交付」",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "bug_query",
        "description": "查询缺陷列表，可按状态、严重程度、处理人过滤",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "status": {"type": "string", "description": "new|processing|fixed|retest|closed"}, "severity": {"type": "string", "description": "low|medium|high|critical"}, "assignee": {"type": "string", "description": "处理人用户 id"}},
            [],
        ),
    },
    {
        "name": "bug_create",
        "description": "提交缺陷（可含业务模块、关联开发任务）",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "title": {"type": "string"}, "description": {"type": "string"}, "module": {"type": "string", "description": "业务模块"}, "severity": {"type": "string", "description": "low|medium|high|critical"}, "assignee": {"type": "string", "description": "处理人用户 id"}, "related_task": {"type": "string", "description": "关联开发任务 id"}},
            ["title"],
        ),
    },
    {
        "name": "bug_update",
        "description": "更新缺陷状态/处理人/严重程度等",
        "inputSchema": _json_schema(
            {"bug_id": {"type": "string"}, "status": {"type": "string", "description": "new|processing|fixed|retest|closed"}, "severity": {"type": "string"}, "assignee": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}},
            ["bug_id"],
        ),
    },
    {
        "name": "bug_from_test_task",
        "description": "从失败/阻塞的测试任务一键转缺陷",
        "inputSchema": _json_schema({"test_task_id": {"type": "string"}, "severity": {"type": "string", "description": "low|medium|high|critical"}}, ["test_task_id"]),
    },
    {
        "name": "bug_statistics",
        "description": "缺陷统计：总数/未关闭/按状态与严重程度分布",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "operation_item_query",
        "description": "查询运营记录，可按类型、状态过滤",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "category": {"type": "string", "description": "iteration|optimization|change|feedback"}, "status": {"type": "string", "description": "evaluating|accepted|scheduled|online|closed"}},
            [],
        ),
    },
    {
        "name": "operation_item_create",
        "description": "新增运营记录（迭代需求/优化需求/业务变更/用户反馈）",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "category": {"type": "string", "description": "iteration|optimization|change|feedback"}, "title": {"type": "string"}, "content": {"type": "string"}, "priority": {"type": "string", "description": "low|medium|high"}, "status": {"type": "string"}, "requestor": {"type": "string", "description": "提出人"}},
            ["title"],
        ),
    },
    {
        "name": "operation_item_update",
        "description": "更新运营记录（状态等）",
        "inputSchema": _json_schema(
            {"operation_item_id": {"type": "string"}, "status": {"type": "string", "description": "evaluating|accepted|scheduled|online|closed"}, "title": {"type": "string"}, "content": {"type": "string"}, "priority": {"type": "string"}, "category": {"type": "string"}, "requestor": {"type": "string"}},
            ["operation_item_id"],
        ),
    },
    {
        "name": "operation_metric_query",
        "description": "查询运营指标（按月，如续期/续费、满意度、活跃用户）",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP, "month": {"type": "string", "description": "YYYY-MM"}}, []),
    },
    {
        "name": "operation_metric_create",
        "description": "登记运营指标（续期/续费、满意度、活跃用户等）",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP, "month": {"type": "string", "description": "YYYY-MM"}, "indicator": {"type": "string", "description": "renewal|satisfaction|active_users|custom"}, "value": {"type": "number"}, "note": {"type": "string"}},
            ["month", "value"],
        ),
    },
    {
        "name": "operation_statistics",
        "description": "运营记录统计：按类型与状态分布",
        "inputSchema": _json_schema({"project_id": PROJECT_PROP}, []),
    },
    {
        "name": "prototype_image_query",
        "description": "查询指定项目的原型图/UI 图结构化列表（含 id、名称、类型、URL），可按名称模糊搜索（name 不传返回全量），kind 可选。开发/测试前可先按模块名搜索确认相关图，再用 image_id 下载",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "kind": {"type": "string", "description": "prototype(原型图)|ui(UI图)|flow(业务流程图)|other(其它)，可空"},
                "name": {"type": "string", "description": "按图名称模糊搜索（可空，如：订单列表）"},
            },
            [],
        ),
    },
    {
        "name": "prototype_image_upload",
        "description": "上传一张原型图/UI 图到指定项目。图片需提供可访问的 URL（AI agent 无法直接传二进制）。图名称在项目内唯一，建议按「端-模块-功能」命名",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "name": {"type": "string", "description": "图名称，建议格式：端-模块-功能，如 Web-登录-验证码"},
                "kind": {"type": "string", "description": "prototype(原型图)|ui(UI图)|flow(业务流程图)|other(其它)"},
                "image_url": {"type": "string", "description": "图片可访问的 http(s) URL"},
            },
            ["name", "image_url"],
        ),
    },
    {
        "name": "prototype_image_download",
        "description": "下载指定原型图/UI 图的原始字节（base64 编码返回，含文件名/类型/大小），供 AI agent 读取图片内容",
        "inputSchema": _json_schema(
            {"image_id": {"type": "string", "description": "图片 id"}},
            ["image_id"],
        ),
    },
    {
        "name": "architecture_upload",
        "description": "直接上传一份已生成好的架构设计并保存为项目架构记录（架构概设文档 + 数据库 SQL，不调用服务端 AI 生成）。适用：你在自己的 agent 里已完成架构设计、仅需入库。前置：项目需处于「架构设计」阶段（需求已确认且有项目计划）；调用者需为该项目成员或管理员。如需覆盖已有架构记录，可用 architecture_update / sql_update 工具",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "frontend_stack": {"type": "string", "description": "前端技术栈，如：Vue3 + TypeScript + Element Plus"},
                "backend_stack": {"type": "string", "description": "后端技术栈，如：Spring Boot 3 + MyBatis-Plus"},
                "base_framework": {"type": "string", "description": "框架底座（可空）：留空=无(自研)、ruoyi-vue-plus=Ruoyi-Vue-Plus(5.x)、smart-admin=Smart-Admin"},
                "db_type": {"type": "string", "description": "数据库类型：mysql(默认) 或 postgresql"},
                "design_doc": {"type": "string", "description": "架构概设文档正文（markdown），直接保存，不触发服务端 AI"},
                "db_sql": {"type": "string", "description": "数据库设计 SQL 全文，直接保存，不触发服务端 AI（可空；与 design_doc 至少填一项）"},
            },
            ["frontend_stack", "backend_stack"],
        ),
    },
    {
        "name": "project_plan_query",
        "description": "查询指定项目的项目计划列表（概要：名称/周期/正文字符数/成员/任务数，不含正文全文）。完整正文用 project_plan_content_query 分页拉取。调用者需为该项目成员或管理员",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP},
            [],
        ),
    },
    {
        "name": "project_plan_content_query",
        "description": "按计划 id 或名称分页读取单份计划正文：每次约 1000 字符（page_size 可调），长文请循环 page=1..total_pages 拼接。plan_id 与 name 至少给一个（都给了以 plan_id 为准；按 name 时精确优先、其次模糊）。调用者需为该项目成员或管理员",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "plan_id": {"type": "integer", "description": "项目计划 id（可空，与 name 二选一）"},
                "name": {"type": "string", "description": "项目计划名称（可空，与 plan_id 二选一）"},
                "page": {"type": "integer", "description": "页码，从 1 开始（默认 1）"},
                "page_size": {"type": "integer", "description": "每页字符数（默认 1000，最大 20000）"},
            },
            [],
        ),
    },
    {
        "name": "project_plan_create",
        "description": "直接上传一份已生成好的项目计划正文并保存为新计划（不调用服务端 AI 生成）。适用：你在自己的 agent 里已写好完整计划 markdown、仅需入库。前置：项目需求需已确认、members 须为项目成员、调用者须为项目成员或管理员",
        "inputSchema": _json_schema(
            {
                "project_id": PROJECT_PROP,
                "requirement_id": {"type": "integer", "description": "需求文档 id（用 requirement_query 查询）"},
                "name": {"type": "string", "description": "计划名称"},
                "start_date": {"type": "string", "description": "计划开始日期 YYYY-MM-DD（不早于今天）"},
                "launch_date": {"type": "string", "description": "计划上线日期 YYYY-MM-DD（不早于开始日期）"},
                "members": {
                    "type": "array",
                    "description": "参与开发的成员 user_id 与开发权重，权重和应约为 1",
                    "items": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "integer", "description": "项目成员的用户 id"},
                            "weight": {"type": "number", "description": "该成员开发权重 0-1，如 0.5"},
                        },
                        "required": ["user_id", "weight"],
                    },
                },
                "plan_content": {"type": "string", "description": "完整计划正文（markdown），将直接保存，不触发服务端 AI"},
            },
            ["requirement_id", "name", "start_date", "launch_date", "members", "plan_content"],
        ),
    },
    {
        "name": "member_profile_query",
        "description": "查询指定项目的成员画像列表：每位成员的用户 id/姓名/项目内角色/能力描述(capability)/加入时间/承担任务统计（总任务、待办、执行中、已完成、阻塞、预计人日）。用于 AI 生成计划分配开发权重或派单前评估成员。仅项目负责人、项目经理(项目内角色 manager)或管理员可查；普通成员调用会返回 403。建议传 project_id 以避免用错项目",
        "inputSchema": _json_schema(
            {"project_id": PROJECT_PROP},
            [],
        ),
    },
    {
        "name": "project_plan_update",
        "description": "修改（覆盖）一份已有项目计划的内容：必传 plan_content 全文整体覆盖，可选更新 name/start_date/launch_date。不调用服务端 AI。调用者需为该计划所属项目成员或管理员",
        "inputSchema": _json_schema(
            {
                "plan_id": {"type": "integer", "description": "项目计划 id（project_plan_query 查询）"},
                "plan_content": {"type": "string", "description": "新的完整计划正文（markdown），整体覆盖原正文"},
                "name": {"type": "string", "description": "计划名称（可空，仅需改名时传）"},
                "start_date": {"type": "string", "description": "计划开始日期 YYYY-MM-DD（可空）"},
                "launch_date": {"type": "string", "description": "计划上线日期 YYYY-MM-DD（可空）"},
            },
            ["plan_id", "plan_content"],
        ),
    },
    {
        "name": "project_plan_tasks_submit",
        "description": "直接提交一份已生成好的任务 JSON 到项目计划并保存（覆盖该计划原有任务，不调用服务端 AI）。任务项：title 必填，module 业务模块，difficulty simple|medium|hard，estimated_days 人日，assignee 负责人（计划成员的 username，须在该计划成员名单内），start_date/end_date YYYY-MM-DD，depends 前置任务，ui_images 关联图名数组。返回 {imported, plan}",
        "inputSchema": _json_schema(
            {
                "plan_id": {"type": "integer", "description": "项目计划 id（project_plan_query 查询）"},
                "tasks": {
                    "type": "array",
                    "description": "任务对象数组",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "任务名称（必填）"},
                            "description": {"type": "string", "description": "任务描述"},
                            "module": {"type": "string", "description": "所属业务模块"},
                            "difficulty": {"type": "string", "description": "simple|medium|hard"},
                            "estimated_days": {"type": "number", "description": "预估工期（人日）"},
                            "assignee": {"type": "string", "description": "负责人（计划成员的 username，必须在该计划成员内）"},
                            "start_date": {"type": "string", "description": "计划开始日期 YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "计划完成日期 YYYY-MM-DD"},
                            "depends": {"type": "string", "description": "前置依赖任务标题或空"},
                            "ui_images": {"type": "array", "items": {"type": "string"}, "description": "关联的原型图/UI图名称（须在项目图库中存在，否则被忽略）"},
                        },
                        "required": ["title"],
                    },
                },
            },
            ["plan_id", "tasks"],
        ),
    },
]

TOOL_IMPL = {
    "knowledge_add": tool_knowledge_add,
    "knowledge_delete": tool_knowledge_delete,
    "knowledge_search": tool_knowledge_search,
    "delivery_doc_upload": tool_delivery_doc_upload,
    "requirement_query": tool_requirement_query,
    "requirement_content_query": tool_requirement_content_query,
    "wiki_page_query": tool_wiki_page_query,
    "wiki_page_content_query": tool_wiki_page_content_query,
    "wiki_compile_source": tool_wiki_compile_source,
    "wiki_compile_status": tool_wiki_compile_status,
    "wiki_page_add": tool_wiki_page_add,
    "architecture_query": tool_architecture_query,
    "architecture_content_query": tool_architecture_content_query,
    "sql_query": tool_sql_query,
    "architecture_update": tool_architecture_update,
    "sql_update": tool_sql_update,
    "workgroup_message_query": tool_workgroup_message_query,
    "workgroup_message_send": tool_workgroup_message_send,
    "task_create": tool_task_create,
    "task_query": tool_task_query,
    "task_update": tool_task_update,
    "worklog_submit": tool_worklog_submit,
    "worklog_query": tool_worklog_query,
    "worklog_update": tool_worklog_update,
    "worklog_delete": tool_worklog_delete,
    "test_case_query": tool_test_case_query,
    "test_case_add": tool_test_case_add,
    "test_case_generate": tool_test_case_generate,
    "test_task_query": tool_test_task_query,
    "test_task_dispatch": tool_test_task_dispatch,
    "test_task_reassign": tool_test_task_reassign,
    "test_task_update": tool_test_task_update,
    "test_statistics": tool_test_statistics,
    "test_report": tool_test_report,
    "bug_query": tool_bug_query,
    "bug_create": tool_bug_create,
    "bug_update": tool_bug_update,
    "bug_from_test_task": tool_bug_from_test_task,
    "bug_statistics": tool_bug_statistics,
    "operation_item_query": tool_operation_item_query,
    "operation_item_create": tool_operation_item_create,
    "operation_item_update": tool_operation_item_update,
    "operation_metric_query": tool_operation_metric_query,
    "operation_metric_create": tool_operation_metric_create,
    "operation_statistics": tool_operation_statistics,
    "prototype_image_query": tool_prototype_image_query,
    "prototype_image_upload": tool_prototype_image_upload,
    "prototype_image_download": tool_prototype_image_download,
    "architecture_upload": tool_architecture_upload,
    "project_plan_query": tool_project_plan_query,
    "project_plan_content_query": tool_project_plan_content_query,
    "project_plan_create": tool_project_plan_create,
    "member_profile_query": tool_member_profile_query,
    "project_plan_update": tool_project_plan_update,
    "project_plan_tasks_submit": tool_project_plan_tasks_submit,
}


# ── MCP stdio JSON-RPC 处理 ──
def _write(msg):
    """以 UTF-8 字节写一行 JSON 到 stdout（避免 Windows 下 gbk 编码导致崩溃）。"""
    line = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()


def _result(msg_id, result):
    _write({"jsonrpc": "2.0", "id": msg_id, "result": result})


def _error(msg_id, code, message):
    _write({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def handle(message):
    if not isinstance(message, dict):
        return
    msg_id = message.get("id")
    method = message.get("method")

    # 通知类：不回响应
    if isinstance(method, str) and method.startswith("notifications/"):
        return

    if method == "initialize":
        _result(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    elif method == "ping":
        _result(msg_id, {})
    elif method == "tools/list":
        _result(msg_id, {"tools": TOOLS})
    elif method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        impl = TOOL_IMPL.get(name)
        if not impl:
            _error(msg_id, -32601, f"未知工具: {name}")
            return
        try:
            result = impl(args)
            text = json.dumps(result, ensure_ascii=False)
        except Exception as e:
            text = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        _result(msg_id, {"content": [{"type": "text", "text": text}], "isError": False})
    else:
        _error(msg_id, -32601, f"未知方法: {method}")


def main():
    # 强制以 UTF-8 读取 stdin（JSON-RPC 按 UTF-8 协议传输）。
    # 不强制时 Windows 下会按 GBK 解码，导致中文在入库前就变成乱码（如“涓氬姟”）。
    if hasattr(sys.stdin, "reconfigure"):
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="strict")
        except Exception:
            pass
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                handle(message)
            except Exception as e:
                if isinstance(message, dict) and "id" in message:
                    _error(message["id"], -32603, str(e))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # 致命错误写 stderr，便于客户端日志排查（不会污染 stdout 协议流）
        sys.stderr.write(f"[mcp_server] fatal: {e}\n")
        sys.stderr.flush()


if __name__ == "__main__":
    main()
