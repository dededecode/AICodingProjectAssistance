"""生成一套合成的演示数据（不含任何真实个人信息，可安全随开源仓库分发）。

用法（在 backend 目录下执行）：
    python manage.py seed_demo            # 首次生成
    python manage.py seed_demo --reset    # 清空演示数据后重建

设计要点：
  * 全部数据由本命令用代码合成，不含真实姓名、手机号、邮箱、密钥；
  * 不调用任何 AI 接口、不联网，离线可用；
  * 图片由标准库绘制为示意图（无 EXIF / 作者信息）；
  * 以 `demo_` 前缀用户名 +「演示项目」前缀项目名作为标记，便于 --reset 精确清理。
"""
import struct
import zlib
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.architecture.models import ArchitectureDesign
from apps.collaboration.models import (
    WeeklySummary,
    WorkGroup,
    WorkGroupMember,
    WorkGroupMessage,
    WorkLog,
)
from apps.collaboration.views import (
    DEFAULT_DEV_TASK_PROMPT,
    DEFAULT_TEST_TASK_PROMPT,
    DEFAULT_WORKFLOW_DESC,
)
from apps.delivery.models import DeliveryDoc
from apps.knowledge.models import KnowledgeItem
from apps.operation.models import OperationItem, OperationMetric
from apps.project_planning.models import PlanTask, ProjectPlan, ProjectPlanMember
from apps.projects.models import Project, ProjectMember
from apps.rbac.api_map import MAP as RBAC_API_MAP
from apps.rbac.models import RoleResource
from apps.requirements.models import PrototypeImage, Requirement
from apps.testing.models import Bug, TestCase, TestTask
from apps.wiki.models import WikiCompileLog, WikiPage

User = get_user_model()

DEMO_PASSWORD = "demo12345"
PROJECT_NAME = "演示项目 · 客户工单管理系统"
DEMO_USERS = [
    # (username, 姓名, 角色, 能力描述)
    ("demo_admin", "演示管理员", "admin", "负责平台配置、权限组与模型管理。"),
    ("demo_manager", "演示项目经理", "manager", "负责需求确认、计划排期、派单与验收；熟悉工单类业务。"),
    ("demo_dev1", "演示开发甲", "developer", "后端方向：Django/DRF、数据库设计、接口开发。"),
    ("demo_dev2", "演示开发乙", "developer", "前端方向：Vue3、Element Plus、图表可视化。"),
    ("demo_tester", "演示测试", "tester", "功能与接口测试，负责用例设计、执行与缺陷跟踪。"),
    ("demo_guest", "演示访客", "guest", "只读浏览演示数据。"),
]
PROJECT_MEMBERS = [
    # (username, 项目内角色)
    ("demo_manager", "manager"),
    ("demo_dev1", "developer"),
    ("demo_dev2", "developer"),
    ("demo_tester", "tester"),
    ("demo_guest", "guest"),
]

IMG_LIST = "Web-工单管理-工单列表"
IMG_DETAIL = "Web-工单管理-工单详情"

# ── 演示权限组 ──
# 后端 apps/rbac/api_map.py 把几乎所有业务接口映射到资源码，非 admin 用户必须在权限组里
# 被勾选对应码才放行（否则登录后除首页/项目列表外全是 403）。
# 这里使用独立的「演示-」组，而非 rbac 迁移创建的内置角色组（admin/manager/...），
# 这样 --reset 能干净移除演示授权，不会破坏使用者自己配置的 RBAC。
DEMO_GROUP_PREFIX = "演示-"
# 真正参与后端鉴权的资源码：直接从 api_map 取，避免与后端映射漂移
_API_CODES = sorted({code for _prefix, code in RBAC_API_MAP})
# 仅用于前端菜单渲染、不在 api_map 的码。其中 menu:bugs 是缺陷管理页的菜单码，
# 但 /api/bugs 实际归 menu:testing，所以两者都要给。
_UI_ONLY_CODES = ["menu:dashboard", "menu:overview", "menu:project-manage", "menu:bugs"]
ALL_MENU_CODES = _API_CODES + _UI_ONLY_CODES
ALL_BTN_CODES = [
    "btn:user-create", "btn:user-edit", "btn:user-delete", "btn:user-reset-pwd",
    "btn:user-token-regen", "btn:user-active", "btn:user-group", "btn:weekly-delete",
    "btn:role-create", "btn:role-delete", "btn:role-save", "btn:project-delete",
    "btn:project-status", "btn:project-invite", "btn:project-remove-member",
    "btn:kb-delete", "btn:model-embedding", "btn:workgroup-dismiss",
    "btn:workgroup-delete", "btn:workgroup-message",
]
_WORK_MENUS = [
    "menu:dashboard", "menu:overview", "menu:project-manage", "menu:projects",
    "menu:prototype-images", "menu:project-planning", "menu:tasks", "menu:architecture",
    "menu:testing", "menu:bugs", "menu:collaboration", "menu:work-groups",
    "menu:knowledge", "menu:llm-wiki", "menu:delivery-docs",
]
_ROLE_TO_GROUP = {
    "admin": "管理员",
    "manager": "项目经理",
    "developer": "开发",
    "tester": "测试",
    "guest": "访客",
}
DEMO_GROUPS = {
    "管理员": ALL_MENU_CODES + ALL_BTN_CODES,
    "项目经理": ALL_MENU_CODES + ALL_BTN_CODES,
    "开发": _WORK_MENUS,
    "测试": [
        "menu:dashboard", "menu:overview", "menu:project-manage", "menu:projects",
        "menu:prototype-images", "menu:tasks", "menu:testing", "menu:bugs",
        "menu:collaboration", "menu:work-groups", "menu:knowledge", "menu:llm-wiki",
        "menu:delivery-docs",
    ],
    "访客": ["menu:dashboard", "menu:overview", "menu:projects"],
}


def _month_str(base_date, months_back):
    """返回 base_date 往前推 months_back 个月的 YYYY-MM。"""
    year, month = base_date.year, base_date.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


# ────────────────────── 合成图片（纯标准库，无第三方依赖） ──────────────────────

def _png(width, height, blocks):
    """把若干矩形画成一张 RGB PNG。blocks: [(x, y, w, h, (r, g, b)), ...]"""
    bg = (247, 249, 251)
    canvas = [[bg] * width for _ in range(height)]
    for x, y, w, h, color in blocks:
        for yy in range(max(0, y), min(height, y + h)):
            row = canvas[yy]
            for xx in range(max(0, x), min(width, x + w)):
                row[xx] = color

    raw = bytearray()
    for row in canvas:
        raw.append(0)  # 每行的 filter type
        for r, g, b in row:
            raw += bytes((r, g, b))

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _mock_screen(kind):
    """生成一张界面示意图：kind 为 list / detail / mobile / flow。"""
    primary = (64, 108, 214)
    border = (222, 227, 234)
    text = (170, 178, 190)
    panel = (255, 255, 255)

    if kind == "mobile":
        width, height = 380, 640
        b = [
            (0, 0, width, height, (238, 242, 247)),
            (102, 20, 176, 620, panel),
            (102, 20, 176, 56, primary),
        ]
        for i in range(5):
            b.append((122, 100 + i * 96, 136, 72, (241, 244, 248)))
            b.append((122, 100 + i * 96, 136, 8, border))
        return _png(width, height, b)

    width, height = 900, 560
    if kind == "detail":
        b = [
            (0, 0, width, height, (238, 242, 247)),
            (0, 0, width, 56, primary),
            (0, 56, 220, height - 56, panel),
            (220, 56, 1, height - 56, border),
        ]
        for i in range(7):
            b.append((250, 90 + i * 60, 110, 14, text))
            b.append((380, 86 + i * 60, 460, 30, (245, 247, 250)))
        return _png(width, height, b)

    if kind == "flow":
        b = [(0, 0, width, height, (238, 242, 247)), (0, 0, width, 56, primary)]
        for i, x in enumerate(range(70, 780, 180)):
            b.append((x, 230, 130, 80, panel))
            b.append((x, 230, 130, 5, primary))
            if i < 3:
                b.append((x + 130, 266, 50, 6, border))
        return _png(width, height, b)

    # list
    b = [
        (0, 0, width, height, (238, 242, 247)),
        (0, 0, width, 56, primary),
        (0, 56, 200, height - 56, panel),
        (200, 56, 1, height - 56, border),
        (230, 88, 640, 44, panel),
    ]
    for i in range(6):
        b.append((24, 96 + i * 46, 152, 14, text))
    for i in range(7):
        b.append((230, 152 + i * 52, 640, 40, panel))
        b.append((246, 166 + i * 52, 150, 12, text))
        b.append((470, 166 + i * 52, 120, 12, text))
        b.append((680, 164 + i * 52, 70, 16, (226, 232, 240)))
    return _png(width, height, b)


# ────────────────────────── 参考文案（全部为合成内容） ──────────────────────────

REQUIREMENT_TEXT = """# 客户工单管理系统 · 需求说明（演示数据）

## 1. 背景与目标
演示企业目前通过电话与表格登记工单，存在漏单、重复派单、进度不可见等问题。
本系统目标是建立统一工单入口，实现登记 → 派单 → 处理 → 回访 → 归档的全流程线上化，
并让管理人员实时掌握工单量与处理时长。

## 2. 用户角色与权限
- 座席：登记工单、查看本人创建工单。
- 主管：派单、改派、查看本组全部工单与统计。
- 工程师：处理被指派工单、填写处理记录。
- 管理员：用户与角色维护、基础数据维护。
- 访客：只读查看统计看板。

## 3. 功能需求
3.1 工单登记：客户信息、问题描述、紧急程度、来源渠道、附件。
3.2 工单派单：按技能组与负载自动推荐，支持手动改派并留痕。
3.3 工单流转：待派单 → 处理中 → 待回访 → 已归档，状态变更需记录操作人与时间。
3.4 处理记录：工程师填写处理过程、耗时、结果，可追加多条。
3.5 统计报表：按日/周/月统计工单量、平均处理时长、超时率，支持导出 Excel。

## 4. 业务规则与边界
- 紧急工单须在 30 分钟内派单，否则升级提醒主管。
- 工单归档后不可修改，仅可追加备注。
- 同一客户同一问题 24 小时内重复登记时提示合并。
- 单条工单附件上限 20MB，最多 10 个。

## 5. 非功能需求（性能/安全/可用性）
- 列表查询响应时间 P95 小于 800ms。
- 登录参数需加密传输，操作日志留存不少于 180 天。
- 服务可用性不低于 99.5%，异常时给出明确提示。

## 6. 验收标准
- 全流程可完整走通，状态流转与权限控制符合第 3、4 节描述。
- 统计报表数值与明细数据一致，导出文件可正常打开。
- 每个功能模块提供可勾选的验收清单并逐项确认。

## 7. 风险与依赖
- 需要客户方提供组织架构与技能组基础数据。
- 短信通知依赖第三方通道，需提前申请模板。

## 8. 技术约束
- 后端采用 Django + DRF，数据库 MySQL 8。
- 前端采用 Vue3 + Element Plus，需兼容主流 Chromium 内核浏览器。
"""

PLAN_CONTENT = """# 客户工单管理系统 · 项目计划（演示数据）

## 一、目标与范围
按需求说明实现工单登记、派单、流转、处理记录与统计报表五大模块。

## 二、里程碑
| 阶段 | 内容 | 预计完成 |
|------|------|---------|
| M1 | 基础框架、登录与权限 | 第 1 周 |
| M2 | 工单登记/派单/流转 | 第 2-3 周 |
| M3 | 处理记录与消息通知 | 第 3 周 |
| M4 | 统计报表与导出 | 第 4 周 |
| M5 | 联调、测试与验收 | 第 5 周 |

## 三、人力与分工
- 演示开发甲（40%）：后端接口、数据库设计、报表统计。
- 演示开发乙（40%）：前端页面、交互与图表。
- 演示项目经理（20%）：需求澄清、进度跟踪、验收。

## 四、风险与应对
- 第三方短信通道审批延迟 → 先用站内信兜底，通道就绪后切换。
- 报表口径存在歧义 → 第 2 周与客户确认口径并书面固化。
"""

ARCH_DOC = """# 客户工单管理系统 · 架构概设（演示数据）

## 1. 总体架构
浏览器（Vue3 SPA）→ Nginx → Django + DRF（Gunicorn）→ MySQL 8；
异步通知通过站内信表 + 定时任务实现。

## 2. 分层设计
- 接入层：Nginx 负责静态资源与 /api 反向代理。
- 应用层：按领域拆分 apps（工单、用户与权限、统计、通知）。
- 数据层：MySQL 8 主从，工单表按创建时间分区。

## 3. 关键设计
- 工单状态机集中在服务层，禁止在视图内直接改状态。
- 状态变更写操作流水表，保证可追溯。
- 统计查询走预聚合日表，避免明细表全表扫描。

## 4. 安全设计
- 登录参数 RSA 加密传输，口令 PBKDF2 存储。
- 接口按项目维度做数据隔离，越权返回 403。
"""

ARCH_SQL = """-- 客户工单管理系统 · 数据库设计（演示数据）
CREATE TABLE `ticket` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `ticket_no` VARCHAR(32) NOT NULL COMMENT '工单编号',
  `title` VARCHAR(200) NOT NULL COMMENT '标题',
  `description` TEXT COMMENT '问题描述',
  `urgency` VARCHAR(16) NOT NULL DEFAULT 'normal' COMMENT '紧急程度',
  `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '状态',
  `assignee_id` BIGINT DEFAULT NULL COMMENT '处理人',
  `created_by` BIGINT NOT NULL COMMENT '登记人',
  `created_at` DATETIME NOT NULL,
  `archived_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ticket_no` (`ticket_no`),
  KEY `idx_status_created` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单主表';

CREATE TABLE `ticket_flow` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `ticket_id` BIGINT NOT NULL,
  `from_status` VARCHAR(16) DEFAULT NULL,
  `to_status` VARCHAR(16) NOT NULL,
  `operator_id` BIGINT NOT NULL,
  `remark` VARCHAR(500) DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ticket` (`ticket_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单流转流水';
"""


class Command(BaseCommand):
    help = "生成合成的演示数据（无真实个人信息，可安全分发）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="先清空已有演示数据（demo_ 用户与演示项目）再重建",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        if Project.objects.filter(name=PROJECT_NAME).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"已存在「{PROJECT_NAME}」，未做任何改动。如需重建请加 --reset"
                )
            )
            return

        today = timezone.localdate()
        users = self._create_users()
        self._create_rbac(users)
        project = self._create_project(users)
        self._create_images(project, users)
        requirement = self._create_requirement(project)
        plan = self._create_plan(project, users, requirement, today)
        tasks = self._create_tasks(project, plan, users, today)
        self._create_architecture(project, users)
        _cases, test_tasks = self._create_testing(project, users)
        self._create_bugs(project, users, tasks, test_tasks)
        self._create_worklogs(project, users, tasks, today)
        self._create_workgroup(project, users, tasks)
        self._create_knowledge_and_wiki(project, users, requirement, plan)
        self._create_delivery(project, users)
        self._create_operation(project, users, today)
        self._done()

    # ── 清理 ──
    def _reset(self):
        demo_users = User.objects.filter(username__startswith="demo_")
        projects = (
            Project.objects.filter(name=PROJECT_NAME)
            | Project.objects.filter(owner__in=demo_users)
        ).distinct()
        # 先删磁盘上的图片：FileField 默认不随记录删除，否则重复 seed 会残留孤儿文件
        # 并因同名文件被自动改名而产生 _xxxxxx 副本
        for img in PrototypeImage.objects.filter(project__in=projects):
            img.image.delete(save=False)
        # 必须"先项目、后用户"：Project.owner 是 PROTECT，顺序反了删不掉
        count = projects.count()
        projects.delete()
        demo_users.delete()
        self.stdout.write(self.style.WARNING(f"已清理 {count} 个演示项目及其关联数据"))
        # 演示权限组（独立于内置角色组，删除它不影响使用者自己的 RBAC 配置）
        Group.objects.filter(name__startswith=DEMO_GROUP_PREFIX).delete()
        self.stdout.write(self.style.WARNING("已清理演示权限组"))

    # ── 用户 ──
    def _create_users(self):
        users = {}
        for username, name, role, capability in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"name": name, "role": role, "capability": capability},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
            users[username] = user
        return users

    # ── 权限组（不给资源码的话，非 admin 用户登录后几乎全是 403）──
    def _create_rbac(self, users):
        groups = {}
        for suffix, codes in DEMO_GROUPS.items():
            group, _created = Group.objects.get_or_create(name=DEMO_GROUP_PREFIX + suffix)
            for code in codes:
                RoleResource.objects.get_or_create(
                    group=group,
                    code=code,
                    defaults={"resource_type": "btn" if code.startswith("btn:") else "menu"},
                )
            groups[suffix] = group
        for username, _name, role, _cap in DEMO_USERS:
            suffix = _ROLE_TO_GROUP.get(role)
            if suffix and suffix in groups:
                users[username].groups.add(groups[suffix])

    # ── 项目 ──
    def _create_project(self, users):
        project = Project.objects.create(
            name=PROJECT_NAME,
            description="演示用项目：客户工单的登记、派单、流转与统计。全部数据由 seed_demo 合成。",
            owner=users["demo_manager"],
            status="developing",
        )
        for username, role in PROJECT_MEMBERS:
            ProjectMember.objects.create(project=project, user=users[username], role=role)
        return project

    # ── 原型图 / UI 图 ──
    def _create_images(self, project, users):
        specs = [
            (IMG_LIST, "ui", "list"),
            (IMG_DETAIL, "ui", "detail"),
            ("手机端-工单管理-我的工单", "prototype", "mobile"),
            ("系统-工单流转-核心流程", "flow", "flow"),
        ]
        for name, kind, screen in specs:
            # 幂等：同名文件先删掉，避免被存储层自动改名成 xxx_ab12cd.png
            rel = f"prototypes/{name}.png"
            if default_storage.exists(rel):
                default_storage.delete(rel)
            img = PrototypeImage(
                project=project, name=name, kind=kind, uploader=users["demo_manager"]
            )
            img.image.save(f"{name}.png", ContentFile(_mock_screen(screen)), save=True)

    # ── 需求文档 ──
    def _create_requirement(self, project):
        elements = [
            ("背景与目标", 90, "目标明确，给出了现状问题与期望结果。"),
            ("功能需求", 88, "五大功能模块描述完整，含字段与状态流转。"),
            ("非功能需求（性能/安全/可用性）", 82, "给出了响应时间与可用性指标，安全要求可再细化。"),
            ("用户角色与权限", 92, "角色划分清晰，权限边界明确。"),
            ("业务规则与边界", 86, "含超时升级、归档限制、重复合并等规则。"),
            ("验收标准", 78, "标准可验证，建议补充每条功能的验收清单。"),
            ("风险与依赖", 74, "识别了外部依赖，缺少应对预案的时间点。"),
            ("技术约束", 80, "技术栈与浏览器兼容范围已明确。"),
        ]
        return Requirement.objects.create(
            project=project,
            title="客户工单管理系统 · 需求说明书",
            file_path="",
            parsed_text=REQUIREMENT_TEXT,
            analysis_result={
                "overall_score": 86,
                "verdict": "passed",
                "elements": [
                    {"name": n, "present": True, "score": s, "comment": c}
                    for n, s, c in elements
                ],
                "quality": {
                    "clarity": 88,
                    "understandability": 86,
                    "logic": 90,
                    "comment": "结构清晰、条目可执行；建议补充验收清单与超时升级的时间点定义。",
                },
                "missing": ["部分功能的验收清单", "外部依赖延迟时的应对预案时间点"],
                "suggestions": [
                    "为每条功能需求补充可勾选的验收清单。",
                    "为短信通道审批延迟补充明确的兜底切换时间点。",
                ],
            },
            is_confirmed=True,
        )

    # ── 项目计划 ──
    def _create_plan(self, project, users, requirement, today):
        plan = ProjectPlan.objects.create(
            project=project,
            name="客户工单管理系统 · 实施计划",
            requirement=requirement,
            planned_members=3,
            start_date=today - timedelta(days=21),
            launch_date=today + timedelta(days=14),
            plan_content=PLAN_CONTENT,
            created_by=users["demo_manager"],
        )
        for username, weight in [
            ("demo_dev1", 0.4),
            ("demo_dev2", 0.4),
            ("demo_manager", 0.2),
        ]:
            ProjectPlanMember.objects.create(plan=plan, user=users[username], weight=weight)
        return plan

    # ── 开发任务 ──
    def _create_tasks(self, project, plan, users, today):
        specs = [
            # (标题, 模块, 难度, 人日, 负责人, 状态, 关联图, 前置依赖, 起始偏移)
            ("登录与图形验证码", "用户与权限", "simple", 2, "demo_dev2", "done", [], "", -21),
            ("用户与角色管理", "用户与权限", "medium", 3, "demo_dev1", "done", [], "登录与图形验证码", -19),
            ("工单列表与多条件筛选", "工单管理", "medium", 3, "demo_dev2", "done", [IMG_LIST], "用户与角色管理", -16),
            ("工单创建与派单", "工单管理", "medium", 3, "demo_dev1", "done", [IMG_LIST], "工单列表与多条件筛选", -13),
            ("工单详情与状态流转", "工单管理", "hard", 4, "demo_dev1", "executing", [IMG_DETAIL], "工单创建与派单", -9),
            ("工单统计报表与图表", "统计报表", "hard", 4, "demo_dev2", "executing", [], "工单详情与状态流转", -6),
            ("消息通知（站内信与邮件）", "消息通知", "medium", 3, "demo_dev1", "pending", [], "工单详情与状态流转", 0),
            ("统计报表导出 Excel", "统计报表", "simple", 2, "demo_dev2", "pending", [IMG_LIST], "工单统计报表与图表", 3),
        ]
        tasks = []
        for i, (title, module, diff, days, who, status, imgs, dep, off) in enumerate(specs):
            tasks.append(
                PlanTask.objects.create(
                    plan=plan,
                    project=project,
                    title=title,
                    description=f"按需求文档与架构设计实现「{title}」，并完成自测。",
                    module=module,
                    difficulty=diff,
                    estimated_days=days,
                    assignee=users[who],
                    status=status,
                    start_date=today + timedelta(days=off),
                    end_date=today + timedelta(days=off + int(days) + 1),
                    depends=dep,
                    ui_images=imgs,
                    sort_order=i,
                )
            )
        return tasks

    # ── 架构设计 ──
    def _create_architecture(self, project, users):
        ArchitectureDesign.objects.create(
            project=project,
            frontend_stack="Vue3 + TypeScript + Element Plus",
            backend_stack="Django 5 + Django REST Framework",
            base_framework="",
            db_type="mysql",
            design_doc=ARCH_DOC,
            db_sql=ARCH_SQL,
            created_by=users["demo_manager"],
        )

    # ── 测试用例与测试任务 ──
    def _create_testing(self, project, users):
        specs = [
            ("工单列表按状态筛选", "工单管理", "high", "列表仅展示所选状态的工单，总数与筛选条件一致。", "passed"),
            ("登记工单必填校验", "工单管理", "high", "缺少标题或问题描述时阻止提交并给出字段级提示。", "passed"),
            ("工单状态流转留痕", "工单管理", "high", "每次状态变更写入流转记录，含操作人与时间。", "failed"),
            ("越权访问他人工单", "用户与权限", "high", "非本人且非主管身份查询他人工单返回 403。", "passed"),
            ("报表数值与明细一致", "统计报表", "medium", "按日统计的工单量等于明细条数。", "executing"),
            ("导出 Excel 内容校验", "统计报表", "low", "导出文件可打开且字段与页面一致。", "pending"),
        ]
        results = {
            "passed": "实际结果与预期一致，用例通过。",
            "failed": "状态变更后未写入流转记录，复现 3/3。",
            "executing": "已执行部分场景，待补充边界数据后回归。",
            "pending": "尚未开始执行。",
        }
        cases, test_tasks = [], []
        for name, module, priority, expected, tt_status in specs:
            case = TestCase.objects.create(
                project=project,
                module=module,
                name=name,
                description="前置条件：已登录具备相应权限的账号。步骤：按用例名称执行对应操作并观察结果。",
                priority=priority,
                expected_result=expected,
                created_by=users["demo_tester"],
            )
            cases.append(case)
            test_tasks.append(
                TestTask.objects.create(
                    test_case=case,
                    assignee=users["demo_tester"],
                    status=tt_status,
                    result=results[tt_status],
                )
            )
        return cases, test_tasks

    # ── 缺陷 ──
    def _create_bugs(self, project, users, tasks, test_tasks):
        failed_task = next((t for t in test_tasks if t.status == "failed"), None)
        flow_task = next((t for t in tasks if "状态流转" in t.title), None)
        list_task = next((t for t in tasks if "列表" in t.title), None)
        Bug.objects.create(
            project=project,
            title="工单状态变更后未生成流转记录",
            description=(
                "复现步骤：\n"
                "1. 以主管身份打开工单详情；\n"
                "2. 将状态由「处理中」改为「待回访」；\n"
                "3. 查看流转记录页签。\n\n"
                "期望：新增一条含操作人与时间的流转记录。\n实际：记录为空。"
            ),
            module="工单管理",
            severity="high",
            status="processing",
            assignee=users["demo_dev1"],
            related_test_task=failed_task,
            related_task=flow_task,
            reporter=users["demo_tester"],
        )
        Bug.objects.create(
            project=project,
            title="工单列表筛选后分页未重置到第一页",
            description=(
                "复现步骤：\n"
                "1. 进入工单列表并翻到第 3 页；\n"
                "2. 修改状态筛选条件。\n\n"
                "期望：回到第 1 页。\n实际：仍停留在第 3 页，偶发空白列表。"
            ),
            module="工单管理",
            severity="medium",
            status="fixed",
            assignee=users["demo_dev2"],
            related_task=list_task,
            reporter=users["demo_tester"],
        )
        Bug.objects.create(
            project=project,
            title="统计报表跨月日期区间数值偏移一天",
            description=(
                "复现步骤：\n"
                "1. 选择跨越月末的日期区间；\n"
                "2. 查看按日统计图。\n\n"
                "期望：各日数值与明细一致。\n实际：月末一天数据被计入次月首日。"
            ),
            module="统计报表",
            severity="medium",
            status="retest",
            assignee=users["demo_dev2"],
            reporter=users["demo_tester"],
        )

    # ── 工时与周总结 ──
    def _create_worklogs(self, project, users, tasks, today):
        rows = [
            ("demo_dev1", 6, "实现工单创建接口与派单逻辑", [3]),
            ("demo_dev2", 5, "完成工单列表页面与筛选交互", [2]),
            ("demo_dev1", 7, "工单详情与状态流转服务层改造", [4]),
            ("demo_dev2", 4, "统计报表图表联调", [5]),
            ("demo_tester", 6, "执行工单模块用例并提交缺陷", []),
            ("demo_manager", 2, "需求口径确认与进度同步", []),
        ]
        total = len(rows)
        for i, (who, hours, desc, idxs) in enumerate(rows):
            log = WorkLog.objects.create(
                project=project,
                user=users[who],
                date=today - timedelta(days=total - i),
                hours=Decimal(str(hours)),
                description=desc,
            )
            linked = [tasks[j] for j in idxs if j < len(tasks)]
            if linked:
                log.tasks.set(linked)

        week_start = today - timedelta(days=today.weekday())
        WeeklySummary.objects.create(
            project=project,
            user=users["demo_dev1"],
            week_start=week_start,
            content=(
                "## 本周完成\n- 工单创建与派单接口联调完成。\n- 状态流转服务层重构，补充流转留痕。\n\n"
                "## 下周计划\n- 修复流转记录缺失缺陷。\n- 开始消息通知模块。"
            ),
        )
        WeeklySummary.objects.create(
            project=project,
            user=users["demo_dev2"],
            week_start=week_start,
            content=(
                "## 本周完成\n- 工单列表与筛选交互完成。\n- 统计报表图表接入。\n\n"
                "## 下周计划\n- 报表导出 Excel。\n- 回归分页缺陷。"
            ),
        )

    # ── 工作群 ──
    def _create_workgroup(self, project, users, tasks):
        group = WorkGroup.objects.create(
            project=project,
            name="开发工作群",
            workflow_desc=DEFAULT_WORKFLOW_DESC,
            dev_task_prompt=DEFAULT_DEV_TASK_PROMPT,
            test_task_prompt=DEFAULT_TEST_TASK_PROMPT,
            created_by=users["demo_manager"],
        )
        for username, _role in PROJECT_MEMBERS:
            WorkGroupMember.objects.create(group=group, user=users[username])
        done_titles = "、".join(t.title for t in tasks if t.status == "done") or "基础模块"
        messages = [
            ("demo_manager", f"本轮已发布开发任务：{done_titles}。请开发同学按任务提示词开始。"),
            ("demo_dev2", "我已完成【工单列表与多条件筛选】模块功能，请测试人员基于相关任务和测试用例，开始测试该部分。"),
            ("demo_tester", "测试完成，通过 3 条、失败 1 条。缺陷清单：工单状态变更后未生成流转记录。请开发人员修复缺陷。"),
            ("demo_dev1", "已定位到状态流转未写流水表，正在修复，预计今日提测。"),
        ]
        for sender, content in messages:
            WorkGroupMessage.objects.create(group=group, sender=users[sender], content=content)

    # ── 知识库与 Wiki ──
    def _create_knowledge_and_wiki(self, project, users, requirement, plan):
        items = [
            "工单紧急程度分三级：普通、紧急、特急；特急需 30 分钟内派单，超时自动升级提醒主管。",
            "工单归档后不可修改任何字段，只能追加备注；如需更正须新建关联工单。",
            "统计报表口径：工单量按登记时间统计，平均处理时长按「派单时间 → 归档时间」计算。",
        ]
        for text in items:
            KnowledgeItem.objects.create(
                project=project, content=text, source="manual", created_by=users["demo_manager"]
            )

        pages = [
            (
                "总览-客户工单管理系统",
                "overview",
                "# 系统总览\n\n覆盖工单登记、派单、流转、处理记录与统计报表五大模块，"
                "面向座席、主管、工程师与管理员四类角色。\n\n## 关键约束\n"
                "- 特急工单 30 分钟内必须派单。\n- 归档后不可修改，仅可追加备注。",
                ["模块-工单管理"],
            ),
            (
                "模块-工单管理",
                "module",
                "# 工单管理\n\n## 职责\n负责工单的登记、派单、状态流转与流转留痕。\n\n"
                "## 状态机\n待派单 → 处理中 → 待回访 → 已归档\n\n"
                "## 关键规则\n每次状态变更必须写入流转流水，含操作人与时间戳。",
                ["总览-客户工单管理系统", "模块-统计报表"],
            ),
            (
                "模块-统计报表",
                "module",
                "# 统计报表\n\n## 指标\n工单量、平均处理时长、超时率。\n\n"
                "## 实现要点\n走预聚合日表，避免明细表全表扫描；导出 Excel 字段与页面保持一致。",
                ["模块-工单管理"],
            ),
        ]
        for title, page_type, content, links in pages:
            WikiPage.objects.create(
                project=project,
                source_type="requirement",
                source_id=requirement.id,
                source_title=requirement.title,
                source_updated_at=requirement.created_at,
                page_type=page_type,
                title=title,
                content=content,
                links=links,
                sources=[
                    {"type": "requirement", "id": requirement.id, "title": requirement.title}
                ],
                compiled_by=users["demo_manager"],
            )
        WikiCompileLog.objects.create(
            project=project,
            source_type="plan",
            source_id=plan.id,
            source_title=plan.name,
            status="success",
            page_count=3,
            duration_ms=4200,
            meta={"demo": True},
            operator=users["demo_manager"],
        )

    # ── 交付文档 ──
    def _create_delivery(self, project, users):
        DeliveryDoc.objects.create(
            project=project,
            title="客户工单管理系统 · 部署说明",
            doc_type="deployment",
            content=(
                "# 部署说明\n\n## 环境要求\n- Docker 与 Compose 插件\n- 2 核 4G 以上\n\n"
                "## 步骤\n```bash\ncd deploy\ndocker compose up -d --build\n```\n\n"
                "## 验证\n浏览器访问服务器地址，使用演示账号登录后确认工单列表可见。"
            ),
            source="manual",
            created_by=users["demo_manager"],
        )
        DeliveryDoc.objects.create(
            project=project,
            title="客户工单管理系统 · 测试报告",
            doc_type="testing",
            content=(
                "# 测试报告\n\n## 范围\n工单管理、用户与权限、统计报表三个模块。\n\n"
                "## 结果\n共执行 6 条用例，通过 4 条、失败 1 条、执行中 1 条，登记缺陷 3 个。\n\n"
                "## 结论\n主干流程可用，遗留缺陷不影响验收，建议修复后回归。"
            ),
            source="manual",
            created_by=users["demo_tester"],
        )

    # ── 运营 ──
    def _create_operation(self, project, users, today):
        rows = [
            ("iteration", "新增工单批量导出", "业务方希望按筛选条件一次性导出，避免逐页复制。", "high", "scheduled"),
            ("optimization", "缩短工单列表首屏加载时间", "列表首屏约 1.6s，目标压到 800ms 以内。", "medium", "accepted"),
            ("feedback", "希望手机端支持工单处理", "现场工程师反馈手机端只能查看不能处理。", "medium", "evaluating"),
            ("change", "统计口径调整为按派单时间", "客户确认工单量统计口径由登记时间改为派单时间。", "high", "online"),
        ]
        for category, title, content, priority, status in rows:
            OperationItem.objects.create(
                project=project,
                category=category,
                title=title,
                content=content,
                priority=priority,
                status=status,
                requestor="客户方（演示）",
                created_by=users["demo_manager"],
            )

        for i in range(3):
            month = _month_str(today, i)
            OperationMetric.objects.create(
                project=project, month=month, indicator="active_users",
                value=120 - i * 15, note="演示数据",
            )
            OperationMetric.objects.create(
                project=project, month=month, indicator="satisfaction",
                value=round(4.5 - i * 0.2, 1), note="演示数据（5 分制）",
            )

    # ── 收尾提示 ──
    def _done(self):
        self.stdout.write(
            self.style.SUCCESS("\n演示数据生成完成（全部为合成数据，不含任何真实个人信息）\n")
        )
        self.stdout.write("演示账号（密码统一为 %s）：" % DEMO_PASSWORD)
        for username, name, role, _cap in DEMO_USERS:
            self.stdout.write(f"  {username:<14} {name:<12} 角色={role}")
        self.stdout.write(
            "\n权限说明（不是报错，是 RBAC 权限组在正常生效）：\n"
            "  demo_admin / demo_manager 可见全部模块；\n"
            "  demo_dev1  无「运营管理」；\n"
            "  demo_tester 无「项目计划 / 架构设计 / 运营管理」；\n"
            "  demo_guest 只读（仅首页、项目概览、需求分析）。\n"
            "  演示权限组：演示-管理员 / 演示-项目经理 / 演示-开发 / 演示-测试 / 演示-访客，\n"
            "  可在「权限组管理」页查看与调整。\n"
        )
        self.stdout.write(
            "\n下一步：\n"
            "  1. 启动后端与前端，用 demo_manager 登录即可看到完整项目数据；\n"
            "  2. AI 相关功能（需求分析、生成计划/架构/用例）需在「模型管理」里配置你自己的 API Key；\n"
            "  3. 想清空重来：python manage.py seed_demo --reset\n"
        )
