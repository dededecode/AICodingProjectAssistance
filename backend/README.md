# 后端说明（Django）

AICodingProjectAssistance（AICoding项目辅助、管理系统）后端。

> 安装、启动、模型配置、MCP 接入与 Docker 部署等通用步骤见根目录 [README.md](../README.md)；本文件只讲后端自身的结构、配置项与开发约定。

## 目录结构

```text
backend/
├── config/          # settings.py / urls.py / wsgi.py / asgi.py
├── apps/            # 业务应用（见下表）
├── services/        # 跨应用服务：llm / embedding / vector_store / document_parser / ai_config / vision / db_crypto
├── manage.py
├── requirements.txt         # 含本地 embedding（sentence-transformers）
├── requirements.noembed.txt # 轻量版：不含 torch，适合远程 embedding 部署
├── rsa_keys/                # 登录 RSA 密钥对（首启自动生成，已 gitignore）
├── db.sqlite3               # 业务库（migrate 后生成，已 gitignore）
├── chroma/ media/           # 向量库与上传文件（运行时生成，已 gitignore）
└── sync_default_workgroup.py # 一次性脚本：同步默认工作群文案
```

## 应用划分

| 应用 | 职责 |
|---|---|
| `accounts` | 用户与角色、JWT 登录、RSA 加密传输、图形验证码、MCP Token |
| `projects` | 项目与项目成员 |
| `requirements` | 需求文档、AI 完整度检测、原型图 / UI 图 |
| `project_planning` | 项目计划、计划成员权重、开发任务 |
| `architecture` | 架构概设文档与数据库设计 SQL |
| `knowledge` | 知识库（传统 RAG，Chroma `project_{id}`）|
| `wiki` | LLM Wiki 知识页编译与 Agentic 问答（Chroma `wiki_{project_id}`）|
| `collaboration` | 工时登记、周总结、工作群（人 + Agent 消息总线）|
| `testing` | 测试用例、测试任务派单、缺陷 |
| `delivery` | 交付文档（架构/测试/部署/其它）|
| `ai_config` | LLM / Embedding 配置、调用日志 |
| `rbac` | 权限组与资源码（菜单码 + 接口码联动，白名单制）|
| `operation` | 运营记录与运营指标 |

## 环境变量

除标注外都有默认值，本地开发通常无需设置。

| 变量 | 默认 | 说明 |
|---|---|---|
| `DJANGO_SECRET_KEY` | 开发占位值 | 生产必改；`DEBUG=0` 时使用默认值会拒绝启动 |
| `DJANGO_DEBUG` | `1` | `0` 为生产模式（同时开启生产安全自检）|
| `DJANGO_ALLOWED_HOSTS` | `*` | 逗号分隔 |
| `DB_PATH` | `backend/db.sqlite3` | 业务库路径 |
| `MEDIA_ROOT` | `backend/media` | 上传文件目录 |
| `CHROMA_DIR` | `backend/chroma` | 向量库目录 |
| `STATIC_ROOT` | `backend/staticfiles` | `collectstatic` 输出目录 |
| `RSA_KEYS_DIR` | `backend/rsa_keys` | 登录 RSA 密钥对目录（首启自动生成）|
| `PLATFORM_SERVICE_TOKEN` | `local-mcp-service-token` | 服务令牌（免登录调用接口）；`DEBUG=0` 时用默认值会拒绝启动 |
| `PLATFORM_DB_SECRET` | 从 `DJANGO_SECRET_KEY` 派生 | 库内 API Key 加密主密钥，**一经使用不可更换** |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | DeepSeek 相关默认值 | OpenAI 兼容协议 |
| `VISION_BASE_URL` / `VISION_API_KEY` / `VISION_MODEL` | 回退到 LLM 配置 | 多模态（图文文档图片解析）|
| `EMBEDDING_MODE` | `local` | `local`（sentence-transformers）或 `remote`（OpenAI 兼容端点）|
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 本地 embedding 模型 |
| `LLM_EMBEDDING_BASE_URL` / `LLM_EMBEDDING_MODEL` | 回退到 LLM | 远程 embedding 端点与模型 |
| `EMBEDDING_BATCH_SIZE` | `8` | 远程 embedding 单次条数 |

> 「模型管理」页面的配置**优先于**上述环境变量，环境变量仅作兜底。

## 管理命令

```bash
python manage.py seed_demo            # 生成合成演示数据（--reset 清空重建）
python manage.py seed_demo --reset
python manage.py encrypt_api_keys     # 加密库中已存的明文 API Key
python manage.py migrate
python manage.py collectstatic --noinput
```

## 开发约定

- **数据库迁移**：仓库已包含全部迁移，首次只需 `migrate`；**新增/修改模型后**才需要 `makemigrations`。迁移文件是数据库结构的唯一事实来源，同时承载数据修正（`RunPython`），不要删除。
- **权限**：接口默认走 `IsProjectMemberOrAdmin` + RBAC 资源码白名单（[`apps/rbac/api_map.py`](apps/rbac/api_map.py)）。新增接口时要同步在该文件的 `MAP` 中登记资源码，否则会走"未映射兜底放行"。
- **AI 调用**：统一走 `services/llm.py`、`services/embedding.py`，不要在视图里直接调 SDK。
- **Mock / 演示数据**：演示数据一律由 `seed_demo` 用代码合成，不得提交含真实个人信息的数据库或上传文件。
- **敏感文件**：`rsa_keys/`、`db.sqlite3`、`chroma/`、`media/`、`*_config.json`、`data_initial/` 均已在 `.gitignore` / `.dockerignore` 中排除。

## 常见问题

- **接口 403**：该接口的资源码未授予你的权限组，到「权限组管理」勾选对应菜单码；单独调试可临时用服务令牌（映射为管理员账号）。
- **本地 Embedding 超时**：多为 HuggingFace 不可达，设置 `HF_ENDPOINT=https://hf-mirror.com` 或改用 ModelScope。
- **向量库损坏**：多进程并发写 Chroma（sqlite + hnsw）会导致损坏，容器部署请保持 `GUNICORN_WORKERS=1`。
