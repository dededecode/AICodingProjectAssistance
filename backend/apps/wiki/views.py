import json
import threading
import time
from datetime import timedelta

from django.db import connection
from django.db.models import Count, Max, Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.architecture.models import ArchitectureDesign
from apps.delivery.models import DeliveryDoc
from apps.project_planning.models import ProjectPlan
from apps.projects.models import Project
from apps.requirements.models import Requirement

from . import vector as wiki_vector
from .models import WikiCompileLog, WikiPage
from .serializers import WikiPageSerializer
from .wiki_gen import MAX_SOURCE_CHARS, compile_wiki_pages

SOURCE_TYPES = ("requirement", "architecture", "plan", "delivery")


def _sse(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _load_source(source_type, source_id):
    """读取单个源文档，返回 (标题, 正文, 来源时间) 或 None。"""
    if source_type == "requirement":
        r = Requirement.objects.filter(id=source_id).select_related("project").first()
        if not r:
            return None
        return r.title, r.parsed_text or "", r.created_at
    if source_type == "architecture":
        d = ArchitectureDesign.objects.filter(id=source_id).select_related("project").first()
        if not d:
            return None
        text = (
            f"前端技术栈：{d.frontend_stack}\n后端技术栈：{d.backend_stack}\n"
            f"框架底座：{d.get_base_framework_display()}\n数据库：{d.get_db_type_display()}\n\n"
            f"【架构概设文档】\n{d.design_doc}\n\n【数据库设计 SQL】\n{d.db_sql}"
        )
        return str(d), text, d.created_at
    if source_type == "plan":
        p = ProjectPlan.objects.filter(id=source_id).select_related("project").first()
        if not p:
            return None
        members = "、".join(f"{m.user.username}(权重{m.weight})" for m in p.members.select_related("user"))
        text = (
            f"计划名称：{p.name}\n周期：{p.start_date} ~ {p.launch_date}\n成员：{members}\n\n【计划内容】\n{p.plan_content}"
        )
        return p.name, text, p.created_at
    if source_type == "delivery":
        doc = DeliveryDoc.objects.filter(id=source_id).select_related("project").first()
        if not doc:
            return None
        title = doc.title + (f"（{doc.get_doc_type_display()}）" if doc.doc_type else "")
        return title, doc.content or "", doc.created_at
    return None


def _run_compile_worker(project_id, source_type, source_id, src_title, text, src_time, log_id, truncated, user_id):
    """后台线程执行编译：LLM 编译 → 覆盖式重建页面 → 向量化 → 更新编译日志。

    大文档同步编译会超过网关/前端超时，故异步执行；结果通过 compile-status 轮询获取。
    线程内无请求上下文，需恢复触发者身份，get_llm_config 才能取到该用户配置的大模型 Key。
    """
    from apps.accounts.models import User
    from services import current_user

    start = time.time()
    try:
        current_user.set_current_user(User.objects.filter(id=user_id).first())
        project = Project.objects.get(id=project_id)
        print(f"[wiki-compile] 开始 log_id={log_id} source={source_type}:{source_id} 输入={len(text)}字", flush=True)
        # 跨源关联：把项目已有页面标题提供给编译模型，新页面会主动 link 已有知识
        existing_titles = list(WikiPage.objects.filter(project=project).values_list("title", flat=True)[:200])
        pages, partial_output = compile_wiki_pages(project.name, src_title, text, existing_titles)
        print(
            f"[wiki-compile] LLM 编译完成 log_id={log_id} pages={len(pages)} partial={partial_output} "
            f"耗时={int(time.time() - start)}s",
            flush=True,
        )
        if not pages:
            # 模型未返回任何可用页面（输出格式损坏且抢救失败）→ 判失败而非静默成功
            raise RuntimeError("模型未返回可用的 Wiki 页面（输出格式损坏且未能抢救），请重试编译")

        # 协作式取消检查①：LLM 期间被取消 → 丢弃结果（旧页面尚未删除，无损）
        if not WikiCompileLog.objects.filter(id=log_id, status="running").exists():
            print(f"[wiki-compile] 已取消 log_id={log_id}（LLM 结果丢弃，旧页面保留）", flush=True)
            return

        # 覆盖式：删除该来源旧页面与旧向量
        WikiPage.objects.filter(project=project, source_type=source_type, source_id=source_id).delete()
        wiki_vector.delete_wiki_by_source(project_id, source_type, source_id)

        page_types = dict(WikiPage.PAGE_TYPE_CHOICES)
        created, texts, metas, vec_ids = [], [], [], []
        for pg in pages:
            ptitle = str(pg.get("title") or "").strip()[:300]
            content = str(pg.get("content") or "").strip()
            if not ptitle or not content:
                continue
            page_type = pg.get("page_type") if pg.get("page_type") in page_types else "synthesis"
            links = [str(x).strip() for x in (pg.get("links") or []) if str(x).strip()][:20]
            srcs = [str(x).strip() for x in (pg.get("sources") or []) if str(x).strip()][:20]
            page = WikiPage.objects.create(
                project=project, source_type=source_type, source_id=source_id, source_title=src_title,
                source_updated_at=src_time, page_type=page_type, title=ptitle, content=content,
                links=links, sources=srcs,
            )
            created.append(ptitle)
            texts.append(f"{ptitle}\n{content}")
            metas.append(
                {
                    "page_id": page.id,
                    "title": ptitle,
                    "page_type": page_type,
                    "source_type": source_type,
                    "source_id": int(source_id),
                    "source_key": f"{source_type}:{source_id}",
                }
            )
            vec_ids.append(f"page{page.id}")

        # 协作式取消检查②：向量化前被取消 → 清理刚写入的半成品页面
        if not WikiCompileLog.objects.filter(id=log_id, status="running").exists():
            WikiPage.objects.filter(project=project, source_type=source_type, source_id=source_id).delete()
            wiki_vector.delete_wiki_by_source(project_id, source_type, source_id)
            print(f"[wiki-compile] 已取消 log_id={log_id}（清理半成品页面）", flush=True)
            return

        if texts:
            try:
                wiki_vector.add_wiki_pages(project_id, texts, metas, vec_ids)
            except Exception as e:
                # 向量化失败整体回滚，避免“页面有记录但检索不到”的脏状态
                WikiPage.objects.filter(project=project, source_type=source_type, source_id=source_id).delete()
                raise RuntimeError(f"页面向量化失败：{e}") from e

        # 仅当仍是 running 时才落最终状态：已取消/已重置的任务不会被线程结果覆盖
        WikiCompileLog.objects.filter(id=log_id, status="running").update(
            status="success", page_count=len(created),
            duration_ms=int((time.time() - start) * 1000),
            meta={"truncated": truncated, "partial_output": partial_output, "titles": created[:20]},
        )
        print(f"[wiki-compile] 成功 log_id={log_id} 入库{len(created)}页 向量化完成 总耗时={int(time.time() - start)}s", flush=True)
    except Exception as e:
        print(f"[wiki-compile] 失败 log_id={log_id} error={str(e)[:300]}", flush=True)
        WikiCompileLog.objects.filter(id=log_id, status="running").update(
            status="failed", error=str(e)[:2000], duration_ms=int((time.time() - start) * 1000),
        )
    finally:
        from services import current_user

        current_user.clear_current_user()
        connection.close()  # 线程持有的 DB 连接用完即还，避免连接泄漏


class WikiPageViewSet(viewsets.ModelViewSet):
    """LLM Wiki：源文档编译为结构化知识页（独立 collection wiki_{project_id}），与知识库互不影响。"""

    queryset = WikiPage.objects.select_related("project", "compiled_by").all()
    serializer_class = WikiPageSerializer

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params
        if params.get("project_id"):
            qs = qs.filter(project_id=params["project_id"])
        if params.get("source_type"):
            qs = qs.filter(source_type=params["source_type"])
        if params.get("page_type"):
            qs = qs.filter(page_type=params["page_type"])
        keyword = (params.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
        return qs

    def list(self, request, *args, **kwargs):
        """列表必须指定 project_id，避免跨项目数据泄露（list 无对象级权限校验）。"""
        if not request.query_params.get("project_id"):
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """直接新增 Wiki 页面（外部 agent 经 MCP wiki_page_add 调用，不走平台 AI 编译）。

        创建后立即向量化进入 wiki collection，参与 Wiki 检索；links 传已有页面标题可实现双链关联。
        """
        project_id = request.data.get("project_id")
        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
        title = str(request.data.get("title") or "").strip()
        content = str(request.data.get("content") or "").strip()
        if not title or not content:
            return Response({"detail": "title 和 content 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        page_type = request.data.get("page_type") or "synthesis"
        if page_type not in dict(WikiPage.PAGE_TYPE_CHOICES):
            page_type = "synthesis"
        source_type = request.data.get("source_type") or "delivery"
        if source_type not in SOURCE_TYPES:
            return Response(
                {"detail": "source_type 只能是 requirement/architecture/plan/delivery"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        source_id = int(request.data.get("source_id") or 0)
        source_title = str(request.data.get("source_title") or "").strip()[:300]
        links = [str(x).strip() for x in (request.data.get("links") or []) if str(x).strip()][:20]
        sources = [str(x).strip() for x in (request.data.get("sources") or []) if str(x).strip()][:20]

        page = WikiPage.objects.create(
            project=project, source_type=source_type, source_id=source_id,
            source_title=source_title or title, page_type=page_type,
            title=title, content=content, links=links, sources=sources,
            compiled_by=request.user,
        )
        try:
            wiki_vector.add_wiki_pages(
                project.id,
                [f"{title}\n{content}"],
                [
                    {
                        "page_id": page.id,
                        "title": title,
                        "page_type": page_type,
                        "source_type": source_type,
                        "source_id": source_id,
                        "source_key": f"{source_type}:{source_id}",
                    }
                ],
                [f"page{page.id}"],
            )
        except Exception as e:
            page.delete()
            return Response({"detail": f"页面向量化失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)
        print(f"[wiki-add] 新增页面 page_id={page.id} title={title[:50]}", flush=True)
        return Response(
            WikiPageSerializer(page, context={"request": request}).data, status=status.HTTP_201_CREATED
        )

    def destroy(self, request, *args, **kwargs):
        """删除 Wiki 页面并同步清理其向量。"""
        page = self.get_object()
        wiki_vector.delete_wiki_page(page.project_id, page.id)
        self.perform_destroy(page)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="sources")
    def sources(self, request):
        """列出项目可编译的源文档（需求/架构/计划/交付）及编译状态（含过期标记）。"""
        project_id = request.query_params.get("project_id")
        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        raw = []
        for r in Requirement.objects.filter(project=project):
            raw.append(("requirement", r.id, r.title, bool((r.parsed_text or "").strip()), r.created_at))
        for d in ArchitectureDesign.objects.filter(project=project):
            raw.append(("architecture", d.id, str(d), bool((d.design_doc or "").strip() or (d.db_sql or "").strip()), d.created_at))
        for p in ProjectPlan.objects.filter(project=project):
            raw.append(("plan", p.id, p.name, bool((p.plan_content or "").strip()), p.created_at))
        for doc in DeliveryDoc.objects.filter(project=project):
            raw.append(("delivery", doc.id, doc.title, bool((doc.content or "").strip()), doc.created_at))

        compiled = {}
        stats = WikiPage.objects.filter(project=project).values("source_type", "source_id").annotate(
            n=Count("id"), last=Max("updated_at"), snap=Max("source_updated_at")
        )
        for s in stats:
            compiled[(s["source_type"], s["source_id"])] = s

        items = []
        for st, sid, title, has_content, updated in raw:
            s = compiled.get((st, sid))
            stale = bool(s) and (not s["snap"] or (updated and s["snap"] < updated))
            items.append(
                {
                    "source_type": st,
                    "source_id": sid,
                    "title": title,
                    "has_content": has_content,
                    "compiled": bool(s),
                    "page_count": s["n"] if s else 0,
                    "compiled_at": s["last"] if s else None,
                    "stale": stale,
                }
            )
        return Response({"items": items})

    @action(detail=False, methods=["post"], url_path="compile")
    def compile(self, request):
        """编译源文档为 Wiki 页面（异步：立即返回 log_id，后台线程执行，前端轮询 compile-status）。"""
        project_id = request.data.get("project_id")
        source_type = request.data.get("source_type")
        source_id = request.data.get("source_id")
        if source_type not in SOURCE_TYPES:
            return Response(
                {"detail": "source_type 只能是 requirement/architecture/plan/delivery"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        loaded = _load_source(source_type, source_id)
        if not loaded:
            return Response({"detail": "来源不存在"}, status=status.HTTP_404_NOT_FOUND)
        src_title, text, src_time = loaded
        if not text.strip():
            return Response({"detail": "该来源暂无内容可编译"}, status=status.HTTP_400_BAD_REQUEST)
        src_title = src_title[:300]  # 超长标题截断，避免超出字段长度（MySQL 严格模式会报错）
        truncated = len(text) > MAX_SOURCE_CHARS

        # 防重复编译：同来源已有进行中的任务则拒绝
        running = WikiCompileLog.objects.filter(
            project=project, source_type=source_type, source_id=source_id, status="running"
        ).first()
        if running:
            return Response(
                {"detail": "该来源正在编译中，请稍候", "log_id": running.id},
                status=status.HTTP_409_CONFLICT,
            )

        # 请求上下文里预校验 LLM Key（线程内无用户身份，问题要在这里暴露）
        from services.ai_config import get_llm_config

        if not (get_llm_config()["api_key"] or "").strip():
            return Response(
                {"detail": "LLM API Key 未配置：请在「模型管理」页面配置当前账号的大模型 Key"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log = WikiCompileLog.objects.create(
            project=project, source_type=source_type, source_id=int(source_id), source_title=src_title,
            status="running", operator=request.user,
        )
        threading.Thread(
            target=_run_compile_worker,
            args=(project.id, source_type, int(source_id), src_title, text, src_time, log.id, truncated, request.user.id),
            daemon=True,
        ).start()
        return Response({"log_id": log.id, "status": "running"})

    @action(detail=False, methods=["get"], url_path="compile-status")
    def compile_status(self, request):
        """轮询编译进度：返回项目最近编译日志；超过 15 分钟仍是 running 视为失败（进程重启等）。"""
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        stale_cut = timezone.now() - timedelta(minutes=15)
        WikiCompileLog.objects.filter(
            project_id=project_id, status="running", created_at__lt=stale_cut
        ).update(status="failed", error="编译超时或服务重启，请重试")
        logs = WikiCompileLog.objects.filter(project_id=project_id).order_by("-created_at")[:50]
        return Response(
            {
                "logs": [
                    {
                        "id": l.id,
                        "source_type": l.source_type,
                        "source_id": l.source_id,
                        "source_title": l.source_title,
                        "status": l.status,
                        "page_count": l.page_count,
                        "error": l.error,
                        "duration_ms": l.duration_ms,
                        "meta": l.meta or {},
                        "created_at": l.created_at,
                    }
                    for l in logs
                ]
            }
        )

    @action(detail=False, methods=["post"], url_path="compile-cancel")
    def compile_cancel(self, request):
        """取消进行中的编译任务：running 日志标记为失败。

        后台线程无法强杀，worker 会在 LLM 返回后/向量化前检查取消状态并自行中止，
        且最终状态更新带 running 条件，取消后不会被线程结果覆盖。
        """
        running = WikiCompileLog.objects.filter(
            project_id=request.data.get("project_id"),
            source_type=request.data.get("source_type"),
            source_id=request.data.get("source_id"),
            status="running",
        ).first()
        if not running:
            return Response({"detail": "该来源没有进行中的编译任务"}, status=status.HTTP_400_BAD_REQUEST)
        duration_ms = int((time.time() - running.created_at.timestamp()) * 1000)
        running.status = "failed"
        running.error = "已手动取消编译"
        running.duration_ms = duration_ms
        running.save(update_fields=["status", "error", "duration_ms"])
        print(f"[wiki-compile] 手动取消 log_id={running.id} source={running.source_type}:{running.source_id}", flush=True)
        return Response({"cancelled": running.id})

    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        """语义检索 Wiki 页面。"""
        project_id = request.data.get("project_id")
        query = (request.data.get("query") or "").strip()
        top_k = int(request.data.get("top_k") or 5)
        if not project_id or not query:
            return Response({"detail": "缺少 project_id 或 query"}, status=status.HTTP_400_BAD_REQUEST)
        results = wiki_vector.search_wiki(int(project_id), query, top_k=top_k)
        return Response({"results": results})

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        """清空项目 Wiki（页面 + 向量 collection），不影响知识库。仅管理员/负责人/项目经理。"""
        project_id = request.data.get("project_id")
        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        can_clear = (
            user.is_superuser
            or getattr(user, "role", None) == "admin"
            or project.owner_id == user.id
            or project.member_links.filter(user=user, role="manager").exists()
        )
        if not can_clear:
            return Response(
                {"detail": "仅管理员、项目负责人或项目经理可清空 Wiki"},
                status=status.HTTP_403_FORBIDDEN,
            )
        deleted_pages, _ = WikiPage.objects.filter(project=project).delete()
        wiki_vector.delete_wiki_collection(project.id)
        return Response({"cleared_pages": deleted_pages})

    # ---- Agentic 多轮检索参数 ----
    QA_TOP_K = 5             # 首轮向量检索条数
    QA_NEED_MAX = 3          # 最多补充页面数
    QA_SUPPLEMENT_CHARS = 2200  # 补充页正文截断上限
    QA_CATALOG_MAX = 80      # 规划时展示的页面目录上限

    def _qa_catalog(self, project_id):
        """Wiki 全部页面标题目录（供规划器挑选补充页）。"""
        rows = (
            WikiPage.objects.filter(project_id=project_id)
            .order_by("-updated_at")
            .values_list("title", flat=True)[: self.QA_CATALOG_MAX]
        )
        return "\n".join(f"- {t}" for t in rows) or "（空）"

    def _fetch_pages_by_titles(self, project_id, titles, exclude_ids):
        """按标题捞补充页：先精确匹配，再模糊兜底，去重限量。"""
        titles = [str(t).strip() for t in titles if str(t).strip()][: self.QA_NEED_MAX]
        if not titles:
            return []
        qs = WikiPage.objects.filter(project_id=project_id).exclude(id__in=list(exclude_ids))
        pages, seen = [], set(exclude_ids)
        for p in qs.filter(title__in=titles)[: self.QA_NEED_MAX]:
            if p.id not in seen:
                seen.add(p.id)
                pages.append(p)
        for t in titles:
            if len(pages) >= self.QA_NEED_MAX:
                break
            for p in qs.filter(title__icontains=t)[:2]:
                if p.id not in seen:
                    seen.add(p.id)
                    pages.append(p)
                    break
        return pages[: self.QA_NEED_MAX]

    def _qa_context(self, project_id, question):
        """Agentic 检索：向量命中 → 规划轮判断缺页 → 按目录/双链标题补充页面。

        返回 (context, refs)；refs 中补充页带 via_link=True。
        """
        from services import llm

        results = wiki_vector.search_wiki(int(project_id), question, top_k=self.QA_TOP_K)
        blocks, refs, given_ids = [], [], []
        for i, r in enumerate(results):
            meta = r.get("metadata") or {}
            blocks.append(f"[{i + 1}] {meta.get('title', '')}\n{r['text']}")
            if meta.get("page_id"):
                given_ids.append(meta["page_id"])
            refs.append(
                {
                    "page_id": meta.get("page_id"),
                    "title": meta.get("title", ""),
                    "page_type": meta.get("page_type", ""),
                    "distance": r.get("distance"),
                }
            )
        context = "\n\n".join(blocks) if blocks else "（Wiki 中暂无相关内容）"

        # 规划轮：判断已提供页面是否足以回答，不足则按标题补充（最多扩展 1 次）
        try:
            plan = llm.chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是检索规划器。根据【用户问题】判断已提供的 Wiki 页面内容是否足以回答。\n"
                            f"【已提供页面内容】\n{context}\n\n"
                            f"【Wiki 全部页面目录】\n{self._qa_catalog(project_id)}\n\n"
                            '足以回答 → 输出 {"need_pages": []}；'
                            '不足 → 从目录中挑选最相关且未提供的页面标题（最多3个），'
                            '输出 {"need_pages": ["标题", ...]}。\n只输出 JSON。'
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                max_tokens=200,
            )
        except Exception:
            plan = {}
        titles = [str(t) for t in (plan.get("need_pages") or []) if str(t).strip()]
        if titles:
            extra = self._fetch_pages_by_titles(project_id, titles, given_ids)
            if extra:
                supp = "\n\n".join(
                    f"[S{i + 1}] {p.title}\n{p.content[: self.QA_SUPPLEMENT_CHARS]}"
                    for i, p in enumerate(extra)
                )
                context = f"{context}\n\n【补充页面】\n{supp}"
                refs += [
                    {"page_id": p.id, "title": p.title, "page_type": p.page_type, "via_link": True}
                    for p in extra
                ]
        return context, refs

    def _qa_messages(self, project_id, question, history):
        """检索 Wiki 页面并组装问答消息（Agentic 补充检索 + 会话记忆）。"""
        context, refs = self._qa_context(project_id, question)
        system = (
            "你是项目 Wiki 知识问答助手。Wiki 页面由 LLM 从项目的需求/架构/计划/交付文档编译而成，"
            "请严格基于下面提供的【Wiki 页面内容】回答用户问题，答案要准确、条理清晰。"
            "如需查看原始文档细节，可提示用户查阅对应源文档。"
            "如果 Wiki 中没有相关信息，请明确说明“Wiki 中未找到相关内容”，不要编造。\n\n"
            f"【Wiki 页面内容】\n{context}"
        )
        messages = [{"role": "system", "content": system}]
        for h in (history or [])[-6:]:
            if h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": str(h.get("content", ""))})
        messages.append({"role": "user", "content": question})
        return messages, refs

    @action(detail=False, methods=["post"], url_path="qa")
    def qa(self, request):
        """Wiki 问答：检索 Wiki 页面 → AI 回答（支持会话记忆）。"""
        from services import llm

        project_id = request.data.get("project_id")
        question = (request.data.get("question") or "").strip()
        history = request.data.get("history") or []
        if not project_id or not question:
            return Response({"detail": "缺少 project_id 或 question"}, status=status.HTTP_400_BAD_REQUEST)

        messages, refs = self._qa_messages(project_id, question, history)
        try:
            answer = llm.chat(messages, temperature=0.3)
        except Exception as e:
            return Response({"detail": f"AI 回答失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"answer": answer, "refs": refs})

    @action(detail=False, methods=["post"], url_path="qa-stream")
    def qa_stream(self, request):
        """Wiki 问答（流式）：检索 Wiki 页面 → AI 流式回答。"""
        from services import llm

        project_id = request.data.get("project_id")
        question = (request.data.get("question") or "").strip()
        history = request.data.get("history") or []
        if not project_id or not question:
            return Response({"detail": "缺少 project_id 或 question"}, status=status.HTTP_400_BAD_REQUEST)

        messages, _ = self._qa_messages(project_id, question, history)

        def gen():
            try:
                yield _sse({"type": "start"})
                for piece in llm.chat_stream(messages, temperature=0.3, max_tokens=4096):
                    yield _sse({"type": "chunk", "content": piece})
                yield _sse({"type": "done"})
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})

        response = StreamingHttpResponse(gen(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
