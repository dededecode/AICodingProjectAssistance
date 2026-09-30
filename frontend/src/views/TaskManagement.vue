<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">任务管理</h3>
        <div>
          <el-button type="success" :disabled="!projectId" :loading="ingesting" @click="ingest">知识入库</el-button>
          <el-button type="warning" :disabled="!projectId" @click="openGenerate">AI 生成任务</el-button>
          <el-button type="primary" :disabled="!projectId" @click="openCreate">新增任务</el-button>
        </div>
      </div>

      <div class="filter-bar" v-if="projectId">
        <el-input
          v-model="keyword"
          placeholder="按任务名称/模块搜索"
          clearable
          style="width: 240px"
          @keyup.enter="page = 1"
          @clear="page = 1"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="assigneeFilter" placeholder="按负责人筛选" clearable filterable style="width: 180px" @change="onFilter">
          <el-option v-for="m in members" :key="m.id" :label="m.username" :value="m.id" />
        </el-select>
        <div style="flex: 1"></div>
        <el-button type="success" :loading="exporting" @click="exportExcel">导出 Excel</el-button>
      </div>

      <el-table
        :data="pagedTasks"
        v-loading="loading"
        stripe
        style="margin-top: 12px"
        :default-sort="{ prop: 'start_date', order: 'ascending' }"
        @sort-change="onSortChange"
      >
        <el-table-column prop="id" label="ID" width="80" sortable="custom" />
        <el-table-column prop="title" label="任务名称" min-width="160" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="module" label="业务模块" width="110" show-overflow-tooltip sortable="custom" />
        <el-table-column label="关联UI图" min-width="170">
          <template #default="{ row }">
            <template v-if="row.ui_images && row.ui_images.length">
              <el-tag v-for="n in row.ui_images" :key="n" size="small" type="info" style="margin: 2px 4px 2px 0">{{ n }}</el-tag>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="plan_name" label="所属计划" width="120" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="difficulty" label="难度" width="80" sortable="custom">
          <template #default="{ row }">
            <el-tag :type="diffType(row.difficulty)" size="small">{{ row.difficulty_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="estimated_days" label="工期(人日)" width="90" sortable="custom" />
        <el-table-column prop="assignee_name" label="负责人" width="100" sortable="custom" />
        <el-table-column prop="start_date" label="计划起止" width="180" sortable="custom">
          <template #default="{ row }">{{ row.start_date || "-" }} ~ {{ row.end_date || "-" }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" sortable="custom">
          <template #default="{ row }">
            <el-select v-model="row.status" size="small" @change="(v) => updateStatus(row, v)">
              <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" text @click="removeTask(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="tasks.length" style="display: flex; justify-content: flex-end; margin-top: 12px">
        <el-pagination
          v-model:current-page="page"
          background
          layout="total, sizes, prev, pager, next"
          :total="filteredTasks.length"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>

    <!-- 新增任务 -->
    <el-dialog v-model="createVisible" title="新增任务" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="所属计划">
          <el-select v-model="form.plan" clearable placeholder="选择计划（可空）" style="width: 100%">
            <el-option v-for="p in plans" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务名称"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="业务模块"><el-input v-model="form.module" /></el-form-item>
        <el-form-item label="难度">
          <el-select v-model="form.difficulty" style="width: 100%">
            <el-option label="简单" value="simple" /><el-option label="中等" value="medium" /><el-option label="复杂" value="hard" />
          </el-select>
        </el-form-item>
        <el-form-item label="工期(人日)"><el-input-number v-model="form.estimated_days" :min="0" :step="0.5" /></el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.assignee" clearable filterable placeholder="选择负责人" style="width: 100%">
            <el-option v-for="m in members" :key="m.id" :label="m.username" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划起止">
          <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="~" start-placeholder="开始" end-placeholder="完成" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑任务 -->
    <el-dialog v-model="editVisible" title="编辑任务" width="560px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="所属计划">
          <el-select v-model="editForm.plan" clearable placeholder="选择计划（可空）" style="width: 100%">
            <el-option v-for="p in plans" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务名称"><el-input v-model="editForm.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="editForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="业务模块"><el-input v-model="editForm.module" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="难度">
              <el-select v-model="editForm.difficulty" style="width: 100%">
                <el-option label="简单" value="simple" /><el-option label="中等" value="medium" /><el-option label="复杂" value="hard" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工期(人日)"><el-input-number v-model="editForm.estimated_days" :min="0" :step="0.5" style="width: 100%" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="负责人">
          <el-select v-model="editForm.assignee" clearable filterable placeholder="选择负责人" style="width: 100%">
            <el-option v-for="m in members" :key="m.id" :label="m.username" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划起止">
          <el-date-picker v-model="editDateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="~" start-placeholder="开始" end-placeholder="完成" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="前置依赖"><el-input v-model="editForm.depends" placeholder="前置任务标题（可空）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doEdit">保存修改</el-button>
      </template>
    </el-dialog>

    <!-- AI 生成任务 -->
    <el-dialog v-model="genVisible" title="AI 生成任务" width="680px" top="5vh">
      <template v-if="!genContent && !genStreaming">
        <el-alert
          type="info"
          :closable="false"
          title="AI 将依据所选计划（成员权重、计划周期）与需求文档生成结构化任务，并自动关联项目原型图/UI图；生成后将覆盖该计划原有任务。"
          style="margin-bottom: 12px"
        />
        <el-form label-width="90px">
          <el-form-item label="选择计划">
            <el-select v-model="genPlanId" filterable placeholder="选择项目计划" style="width: 100%">
              <el-option v-for="p in plans" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <template v-if="genPlan">
            <el-form-item label="需求文档"><span>{{ genPlan.requirement_title || "（计划未关联需求文档）" }}</span></el-form-item>
            <el-form-item label="计划周期"><span>{{ genPlan.start_date }} ~ {{ genPlan.launch_date }}</span></el-form-item>
            <el-form-item label="成员权重">
              <span>{{ (genPlan.members || []).map((m) => `${m.username}(${Math.round(m.weight * 100)}%)`).join("、") || "暂无成员" }}</span>
            </el-form-item>
          </template>
        </el-form>
      </template>
      <template v-else>
        <el-alert type="info" :closable="false" title="AI 正在流式生成结构化任务（输出 JSON），生成完成后自动写入并覆盖该计划原有任务…" style="margin-bottom: 12px" />
        <div v-loading="genStreaming" style="min-height: 120px">
          <el-input v-model="genContent" type="textarea" :rows="16" readonly placeholder="生成中…" />
        </div>
      </template>
      <template #footer>
        <el-button :disabled="genStreaming" @click="genVisible = false">取消</el-button>
        <el-button v-if="!genContent" type="primary" :disabled="!genPlanId" :loading="genStreaming" @click="startGenerateTasks">开始生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { useProjectStore } from "../stores/project";
import { listProjectPlans } from "../api/projectPlanning";
import { createTask, deleteTask, exportTasks, listTasks, updateTask } from "../api/tasks";
import { ingestKnowledge } from "../api/knowledge";

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const selectedProject = ref(null);
const tasks = ref([]);
const plans = ref([]);
const loading = ref(false);
const page = ref(1);
const pageSize = ref(10);
const createVisible = ref(false);
const creating = ref(false);
const ingesting = ref(false);
const exporting = ref(false);
const assigneeFilter = ref(null);
const keyword = ref("");
const dateRange = ref([]);
const editVisible = ref(false);
const saving = ref(false);
const editDateRange = ref([]);
const editForm = reactive({
  id: null,
  plan: null,
  title: "",
  description: "",
  module: "",
  difficulty: "medium",
  estimated_days: 1,
  assignee: null,
  status: "pending",
  depends: "",
});

const form = reactive({
  project: null,
  plan: null,
  title: "",
  description: "",
  module: "",
  difficulty: "medium",
  estimated_days: 1,
  assignee: null,
});

const statusOpts = [
  { value: "pending", label: "待执行" },
  { value: "executing", label: "执行中" },
  { value: "done", label: "已完成" },
  { value: "blocked", label: "阻塞" },
];

const members = computed(() => selectedProject.value?.members || []);

// 前端 keyword 过滤（按任务名称 / 模块模糊匹配）
const filteredTasks = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return tasks.value;
  return tasks.value.filter((t) => (t.title || "").toLowerCase().includes(kw) || (t.module || "").toLowerCase().includes(kw));
});

// 排序：默认按「计划开始时间」正序，空值排最后
const sortKey = ref("start_date");
const sortOrder = ref("asc");

const _DIFF_ORDER = { simple: 1, medium: 2, hard: 3 };
const _STATUS_ORDER = { pending: 1, executing: 2, done: 3, blocked: 4 };

function sortValue(t, key) {
  if (key === "difficulty") return _DIFF_ORDER[t.difficulty] || 2;
  if (key === "status") return _STATUS_ORDER[t.status] || 9;
  if (key === "id" || key === "estimated_days") return Number(t[key] || 0);
  return t[key];
}

const sortedTasks = computed(() => {
  const key = sortKey.value;
  const dir = sortOrder.value === "asc" ? 1 : -1;
  return [...filteredTasks.value].sort((a, b) => {
    const va = sortValue(a, key);
    const vb = sortValue(b, key);
    const ea = va === null || va === undefined || va === "";
    const eb = vb === null || vb === undefined || vb === "";
    if (ea && eb) return 0;
    if (ea) return 1; // 空值沉底
    if (eb) return -1;
    let cmp;
    if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
    else cmp = String(va).localeCompare(String(vb), "zh");
    return cmp * dir;
  });
});

function onSortChange({ prop, order }) {
  if (!order) {
    // 取消排序时回到默认：开始时间正序
    sortKey.value = "start_date";
    sortOrder.value = "asc";
  } else {
    sortKey.value = prop || "start_date";
    sortOrder.value = order === "ascending" ? "asc" : "desc";
  }
  page.value = 1;
}

// 前端分页：在排序后的全量数据上切片
const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return sortedTasks.value.slice(start, start + pageSize.value);
});

function onFilter() {
  page.value = 1;
  load();
}

function onSizeChange(size) {
  pageSize.value = size;
  page.value = 1;
}

const genVisible = ref(false);
const genPlanId = ref(null);
const genStreaming = ref(false);
const genContent = ref("");
const genPlan = computed(() => plans.value.find((p) => p.id === genPlanId.value) || null);

function openGenerate() {
  genPlanId.value = plans.value.length ? plans.value[0].id : null;
  genContent.value = "";
  genStreaming.value = false;
  genVisible.value = true;
}

async function startGenerateTasks() {
  if (!genPlanId.value) return;
  genContent.value = "";
  genStreaming.value = true;
  const token = localStorage.getItem("access_token");
  try {
    const res = await fetch(`/api/project-plans/${genPlanId.value}/generate-tasks-stream/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: "{}",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "生成失败");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    let created = null;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          let evt;
          try {
            evt = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (evt.type === "chunk") genContent.value += evt.content;
          else if (evt.type === "error") throw new Error(evt.message || "生成失败");
          else if (evt.type === "done") created = evt.created;
        }
      }
    }
    if (created != null) {
      ElMessage.success(`任务生成完成，共 ${created} 条`);
      genVisible.value = false;
      load();
    }
  } catch (e) {
    ElMessage.error(e.message || "任务生成失败");
  } finally {
    genStreaming.value = false;
  }
}

async function loadProjects() {
  await projectStore.ensureLoaded();
  onProjectChange();
}

async function onProjectChange() {
  selectedProject.value = projects.value.find((p) => p.id === projectId.value) || null;
  assigneeFilter.value = null;
  load();
  if (projectId.value) {
    const { data } = await listProjectPlans(projectId.value);
    plans.value = data;
  } else {
    plans.value = [];
  }
}

async function load() {
  if (!projectId.value) {
    tasks.value = [];
    return;
  }
  loading.value = true;
  try {
    const params = { project_id: projectId.value };
    if (assigneeFilter.value) params.assignee = assigneeFilter.value;
    const { data } = await listTasks(params);
    tasks.value = data;
    // 当前页被删空时自动回退到最后一页
    const maxPage = Math.max(1, Math.ceil(tasks.value.length / pageSize.value));
    if (page.value > maxPage) page.value = maxPage;
  } finally {
    loading.value = false;
  }
}

async function exportExcel() {
  if (!projectId.value) return ElMessage.warning("请选择项目");
  exporting.value = true;
  try {
    const params = { project_id: projectId.value };
    if (assigneeFilter.value) params.assignee = assigneeFilter.value;
    const res = await exportTasks(params);
    const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `任务_${projectId.value}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

function openCreate() {
  form.project = projectId.value;
  form.plan = null;
  form.title = "";
  form.description = "";
  form.module = "";
  form.difficulty = "medium";
  form.estimated_days = 1;
  form.assignee = null;
  dateRange.value = [];
  createVisible.value = true;
}

async function doCreate() {
  if (!form.title.trim()) return ElMessage.warning("请输入任务名称");
  creating.value = true;
  try {
    await createTask({
      project: form.project,
      plan: form.plan,
      title: form.title,
      description: form.description,
      module: form.module,
      difficulty: form.difficulty,
      estimated_days: form.estimated_days,
      assignee: form.assignee,
      start_date: dateRange.value?.[0] || null,
      end_date: dateRange.value?.[1] || null,
      status: "pending",
    });
    ElMessage.success("任务已创建");
    createVisible.value = false;
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "创建失败");
  } finally {
    creating.value = false;
  }
}

function openEdit(row) {
  editForm.id = row.id;
  editForm.plan = row.plan || null;
  editForm.title = row.title;
  editForm.description = row.description || "";
  editForm.module = row.module || "";
  editForm.difficulty = row.difficulty || "medium";
  editForm.estimated_days = row.estimated_days ?? 1;
  editForm.assignee = row.assignee || null;
  editForm.status = row.status || "pending";
  editForm.depends = row.depends || "";
  editDateRange.value = row.start_date && row.end_date ? [row.start_date, row.end_date] : [];
  editVisible.value = true;
}

async function doEdit() {
  if (!editForm.title.trim()) return ElMessage.warning("请输入任务名称");
  saving.value = true;
  try {
    await updateTask(editForm.id, {
      plan: editForm.plan,
      title: editForm.title,
      description: editForm.description,
      module: editForm.module,
      difficulty: editForm.difficulty,
      estimated_days: editForm.estimated_days,
      assignee: editForm.assignee,
      start_date: editDateRange.value?.[0] || null,
      end_date: editDateRange.value?.[1] || null,
      status: editForm.status,
      depends: editForm.depends,
    });
    ElMessage.success("任务已更新");
    editVisible.value = false;
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function updateStatus(row, status) {
  try {
    await updateTask(row.id, { status });
    ElMessage.success("状态已更新");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "更新失败");
  }
}

async function removeTask(row) {
  try {
    await ElMessageBox.confirm(`确定删除任务「${row.title}」？`, "删除任务", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteTask(row.id);
    ElMessage.success("任务已删除");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

function diffType(d) {
  return { simple: "success", medium: "warning", hard: "danger" }[d] || "info";
}

async function ingest() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  ingesting.value = true;
  try {
    const { data } = await ingestKnowledge({ project_id: projectId.value, kind: "task" });
    ElMessage.success(`已入库 ${data.created ?? 0} 条知识${data.overwritten ? `（覆盖旧知识 ${data.overwritten} 条）` : ""}`);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "知识入库失败");
  } finally {
    ingesting.value = false;
  }
}

// 初始加载完成前，忽略全局项目切换（避免与首次加载重复请求）
let projectReady = false;
watch(projectId, () => {
  if (projectReady) onProjectChange();
});

onMounted(async () => {
  await loadProjects();
  await nextTick();
  projectReady = true;
});
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
</style>
