"""AI 架构设计生成：架构概设文档 + 数据库设计 SQL。"""
from services import llm

BASE_LABELS = {
    "": "无（自研）",
    "ruoyi-vue-plus": "Ruoyi-Vue-Plus（5.x）",
    "smart-admin": "Smart-Admin",
}
DB_LABELS = {"mysql": "MySQL", "postgresql": "PostgreSQL"}

# 各框架底座的能力介绍（AI 对话/专家评审时拼入上下文，帮助 AI 基于底座能力评估设计）
BASE_CAPABILITIES = {
    "ruoyi-vue-plus": """RuoYi-Vue-Plus（5.x）是一套基于 Spring Boot 的企业级快速开发脚手架，核心能力如下：
【技术架构】前端采用 Vue3 + TypeScript + ElementPlus 重写；后端采用插件化 + 扩展包形式，结构解耦、易于扩展，代码遵循 Alibaba 规范；Web 容器采用基于 Netty 的高性能 Jetty。
【权限与认证】采用 Sa-Token + Jwt，低耦合、高扩展，支持登录校验、角色校验、权限校验、二级认证、HttpBasic 校验等注解，并支持 AND/OR、权限 OR 角色等复杂表达式；三方登录采用 JustAuth，支持微信、钉钉等数十种认证。
【数据与 ORM】原生支持 MySQL、Oracle、PostgreSQL、SQLServer 且支持异构切换；ORM 采用 Mybatis-Plus，几乎全对象化操作，含分页、乐观锁等插件；连接池采用 HikariCP；主键采用雪花 ID；内置 SQL 监控、数据权限（无感过滤）、数据脱敏（身份证/手机号等）、数据加解密（BASE64/AES/RSA/SM2/SM4 等）、接口传输加密（动态 AES+RSA）、数据翻译、多数据源（dynamic-datasource，支持事务回滚）。
【缓存与分布式】支持 Redis >= 6，采用 Redisson 客户端，支持分布式限流、分布式队列、分布式锁（Lock4j）、分布式幂等；缓存注解基于 Spring-Cache 扩展（过期时间、最大空闲时间等）；WebSocket 与 SSE 推送均扩展了 Token 鉴权与分布式会话同步；分布式任务调度采用 SnailJob（分片、重试、DAG 任务流）。
【文件与集成】文件存储采用 Minio/RustFS 分布式存储，云存储支持 AWS S3 协议（七牛、阿里、腾讯）；短信采用 sms4j，邮件采用 mail-api；接口文档采用 SpringDoc/javadoc 零注解；Excel 采用 EasyExcel 扩展；工作流采用 WarmFlow（会签、或签、加减签等）；工具集采用 Hutool、Lombok。
【运维与监控】采用 SpringBoot-Admin 服务监控、Apache SkyWalking 链路追踪、Docker 编排一键部署；支持国际化、代码生成器（多数据源一键生成 CRUD 代码与页面）。
【内置业务功能】客户端管理（支持短信登录、密码登录等动态授权方式，动态控制 token 时效）；用户、部门、岗位、菜单、角色（数据范围权限）、字典、参数管理；通知公告、操作日志、登录日志、文件管理、在线用户管理（监控与强制踢出）、定时任务（报表/任务/日志/执行器管理）、代码生成、系统接口（自动生成 API 文档）、服务监控（集群 CPU/内存/磁盘/堆栈/在线日志）、缓存监控、功能使用案例。""",
}


def base_capability_text(base_framework) -> str:
    """返回所选框架底座的能力介绍（供 AI 评估/对话上下文拼接），未选用或无资料时返回空串。"""
    text = BASE_CAPABILITIES.get(base_framework, "")
    if not text:
        return ""
    label = BASE_LABELS.get(base_framework, base_framework or "无（自研）")
    return f"【框架底座能力介绍】已选用底座【{label}】：\n{text}"

_DOC_SYSTEM = """你是一名资深系统架构师。请根据需求文档和选定的技术栈，输出一份【架构概设文档】（中文，markdown 格式），须包含：
## 一、总体架构
描述系统整体架构与层次结构。
## 二、技术选型
明确前端、后端、数据库、框架底座（若有）及理由。
## 三、模块划分与职责
结合需求文档的业务模块，说明各模块功能与职责。
## 四、系统分层与关键设计
说明分层（如 Controller/Service/Mapper）、核心业务流程、权限/认证、缓存/异步等关键设计。
## 五、部署与运行
简要说明部署方式与运行环境。
只输出架构概设文档，不要输出其他解释。"""


def _doc_user(requirement, frontend_stack, backend_stack, base_framework, db_type, constraints="", extra=""):
    base_label = BASE_LABELS.get(base_framework, base_framework or "无（自研）")
    db_label = DB_LABELS.get(db_type, db_type)
    parts = [
        f"需求文档名称：{requirement.title}",
        f"前端技术栈：{frontend_stack}",
        f"后端技术栈：{backend_stack}",
        f"框架底座：{base_label}",
        f"数据库：{db_label}",
    ]
    if constraints and constraints.strip():
        parts.append(f"约束/规则：\n{constraints.strip()}")
    if extra and extra.strip():
        parts.append(f"其它补充：\n{extra.strip()}")
    parts.append(f"需求文档内容：\n\n{requirement.parsed_text[:12000]}")
    return "\n".join(parts)


def generate_arch_doc(requirement, frontend_stack, backend_stack, base_framework, db_type, constraints="", extra="") -> str:
    return llm.chat(
        [{"role": "system", "content": _DOC_SYSTEM}, {"role": "user", "content": _doc_user(requirement, frontend_stack, backend_stack, base_framework, db_type, constraints, extra)}],
        temperature=0.4,
    )


def generate_doc_stream(requirement, frontend_stack, backend_stack, base_framework, db_type, constraints="", extra=""):
    """流式生成架构概设文档。"""
    return llm.chat_stream(
        [{"role": "system", "content": _DOC_SYSTEM}, {"role": "user", "content": _doc_user(requirement, frontend_stack, backend_stack, base_framework, db_type, constraints, extra)}],
        temperature=0.4,
    )


def _sql_system(db_type, base_framework):
    base_label = BASE_LABELS.get(base_framework, base_framework or "无（自研）")
    db_label = DB_LABELS.get(db_type, db_type)
    if base_framework:
        base_instruction = (
            f"已选用框架底座【{base_label}】，该底座已自带用户、角色、权限、部门、租户等基础表，"
            "因此【不要生成用户管理、角色权限、部门、租户等基础表】，只需生成业务相关的表。"
        )
    else:
        base_instruction = (
            "未选用框架底座（自研），因此除业务相关表外，还需自行包含用户、角色、权限等基础表。"
        )
    return f"""你是资深数据库设计师。请根据需求文档，为【{db_label}】数据库生成建表 SQL（DDL）。
{base_instruction}
要求：
- 使用 {db_label} 语法（字段类型、注释、索引等符合该库规范）。
- 每张业务表包含主键 id；常用查询字段建索引；业务表带 created_at/updated_at/created_by 字段。
- 表名与字段使用小写+下划线。
- 只输出 SQL，不要输出解释；SQL 用 ```sql 代码块包裹。"""


def _sql_user(requirement, constraints="", extra=""):
    parts = [f"需求文档名称：{requirement.title}"]
    if constraints and constraints.strip():
        parts.append(f"约束/规则：\n{constraints.strip()}")
    if extra and extra.strip():
        parts.append(f"其它补充：\n{extra.strip()}")
    parts.append(f"需求文档内容：\n\n{requirement.parsed_text[:12000]}")
    return "\n".join(parts)


def generate_db_sql(requirement, db_type, base_framework, constraints="", extra="") -> str:
    return llm.chat(
        [{"role": "system", "content": _sql_system(db_type, base_framework)}, {"role": "user", "content": _sql_user(requirement, constraints, extra)}],
        temperature=0.2,
    )


def generate_sql_stream(requirement, db_type, base_framework, constraints="", extra=""):
    """流式生成数据库 SQL。"""
    return llm.chat_stream(
        [{"role": "system", "content": _sql_system(db_type, base_framework)}, {"role": "user", "content": _sql_user(requirement, constraints, extra)}],
        temperature=0.2,
    )


def modify_design(requirement_text, design_doc, db_sql, prompt, target) -> str:
    """根据用户要求，结合需求 + 当前架构概设 + 当前 SQL，AI 修改后返回完整内容。target: design_doc | sql"""
    if target == "sql":
        system = (
            "你是资深数据库设计师。请根据用户的修改要求，结合需求文档、当前架构概设文档与当前 SQL，"
            "输出【修改后完整】的数据库 SQL。保持与当前库类型一致；SQL 应与架构设计保持一致；只输出 SQL（用 ```sql 代码块包裹），不要解释。"
        )
        label = "当前数据库 SQL"
    else:
        system = (
            "你是资深系统架构师。请根据用户的修改要求，结合需求文档、当前架构概设文档与当前 SQL，"
            "输出【修改后完整】的架构概设文档。保持 markdown 格式；只输出文档，不要解释。"
        )
        label = "当前架构概设文档"

    user = (
        f"需求文档内容：\n\n{requirement_text[:12000]}\n\n"
        f"当前架构概设文档：\n{design_doc}\n\n"
        f"当前数据库 SQL：\n{db_sql}\n\n"
        f"本次修改目标：{label}\n"
        f"用户的修改要求：\n{prompt}"
    )
    return llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0.3)
