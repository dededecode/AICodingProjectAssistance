"""一次性脚本：把已存在的默认「开发工作群」文案同步为最新默认提示词。

用法（在 backend 目录下执行）：
    python sync_default_workgroup.py

只更新仍保留旧版默认文案（含 test_case_generate 特征）的群，不覆盖用户自定义过的文案。
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.collaboration.models import WorkGroup  # noqa: E402
from apps.collaboration.views import (  # noqa: E402
    DEFAULT_DEV_TASK_PROMPT,
    DEFAULT_TEST_TASK_PROMPT,
    DEFAULT_WORKFLOW_DESC,
)

UPDATED = 0
for g in WorkGroup.objects.filter(name="开发工作群"):
    # 特征判断：开发提示词仍是旧版（要求开发生成测试用例/任务）
    if g.dev_task_prompt and "test_case_generate" in g.dev_task_prompt:
        g.workflow_desc = DEFAULT_WORKFLOW_DESC
        g.dev_task_prompt = DEFAULT_DEV_TASK_PROMPT
        g.test_task_prompt = DEFAULT_TEST_TASK_PROMPT
        g.save(update_fields=["workflow_desc", "dev_task_prompt", "test_task_prompt"])
        UPDATED += 1
        print(f"已同步群 #{g.id}（项目 {g.project.name}）文案")

print(f"完成：共同步 {UPDATED} 个默认开发工作群")
