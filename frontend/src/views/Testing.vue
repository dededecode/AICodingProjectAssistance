<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">测试管理</h3>
      </div>

      <el-tabs v-model="tab" style="margin-top: 12px" @tab-change="load">
        <!-- 用例 -->
        <el-tab-pane label="测试用例" name="case">
          <div class="filter-bar">
            <el-input v-model="caseFilter.module" placeholder="按模块筛选" clearable style="width: 160px" @keyup.enter="applyCaseQuery" />
            <el-select v-model="caseFilter.priority" placeholder="优先级" clearable style="width: 120px">
              <el-option label="低" value="low" /><el-option label="中" value="medium" /><el-option label="高" value="high" />
            </el-select>
            <el-button type="primary" @click="applyCaseQuery">查询</el-button>
            <el-button @click="resetCaseQuery">重置</el-button>
            <div style="flex: 1"></div>
            <el-button type="success" size="small" @click="openAiGen">AI 生成用例</el-button>
            <el-button type="primary" size="small" :disabled="!selectedCases.length" @click="openBatchDispatch">批量派单({{ selectedCases.length }})</el-button>
            <el-button type="primary" size="small" @click="openCase()">新增用例</el-button>
          </div>

          <el-table :data="pagedCases" v-loading="loading" stripe style="margin-top: 12px" @selection-change="(r) => (selectedCases = r)">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="name" label="用例名称" min-width="150" />
            <el-table-column prop="module" label="模块" width="110" />
            <el-table-column label="优先级" width="80">
              <template #default="{ row }">
                <el-tag :type="priType(row.priority)" size="small">{{ priLabel(row.priority) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
            <el-table-column prop="expected_result" label="预期结果" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="190">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="openCase(row)">编辑</el-button>
                <el-button size="small" type="warning" text @click="openDispatch(row)">派单</el-button>
                <el-button size="small" type="danger" text @click="removeCase(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrap">
            <el-pagination background layout="total, prev, pager, next, sizes" :total="cases.length" v-model:current-page="casePage" v-model:page-size="casePageSize" :page-sizes="[10, 20, 50]" />
          </div>
        </el-tab-pane>

        <!-- 任务 -->
        <el-tab-pane label="测试任务" name="task">
          <div class="stat-cards">
            <div class="s-card"><div class="n">{{ stat.total_cases ?? 0 }}</div><div class="l">用例总数</div></div>
            <div class="s-card"><div class="n">{{ stat.total_tasks ?? 0 }}</div><div class="l">任务总数</div></div>
            <div class="s-card"><div class="n" :style="{ color: passColor(stat.pass_rate) }">{{ stat.pass_rate ?? 0 }}%</div><div class="l">通过率</div></div>
            <div class="s-card" v-for="(v, k) in stat.by_status || {}" :key="k">
              <div class="n">{{ v }}</div><div class="l">{{ statusLabel(k) }}</div>
            </div>
          </div>

          <div class="filter-bar">
            <el-select v-model="taskFilter.assignee" placeholder="执行人" clearable filterable style="width: 140px">
              <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
            </el-select>
            <el-select v-model="taskFilter.status" placeholder="状态" clearable style="width: 120px">
              <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-input v-model="taskFilter.module" placeholder="按模块筛选" clearable style="width: 160px" @keyup.enter="applyTaskQuery" />
            <el-button type="primary" @click="applyTaskQuery">查询</el-button>
            <el-button @click="resetTaskQuery">重置</el-button>
            <div style="flex: 1"></div>
            <el-button type="success" size="small" :loading="exporting" @click="exportExcel">导出 Excel</el-button>
            <el-button type="success" size="small" :loading="reportLoading" @click="genReport">生成测试报告</el-button>
          </div>

          <el-table :data="pagedTasks" v-loading="loading" stripe style="margin-top: 12px">
            <el-table-column prop="test_case_name" label="用例" min-width="150" />
            <el-table-column prop="test_case_module" label="模块" width="100" />
            <el-table-column prop="assignee_name" label="执行人" width="110" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-select v-model="row.status" size="small" @change="(v) => updateStatus(row, v)">
                  <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="结果/说明" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ row.result || "-" }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="showTaskDetail(row)">详情</el-button>
                <el-button size="small" type="warning" text :disabled="!['failed', 'blocked'].includes(row.status)" @click="toBug(row)">转缺陷</el-button>
                <el-button size="small" type="danger" text @click="removeTask(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrap">
            <el-pagination background layout="total, prev, pager, next, sizes" :total="tasks.length" v-model:current-page="taskPage" v-model:page-size="taskPageSize" :page-sizes="[10, 20, 50]" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新增/编辑用例 -->
    <el-dialog v-model="caseVisible" :title="editingCase ? '编辑测试用例' : '新增测试用例'" width="520px">
      <el-form :model="caseForm" label-width="90px">
        <el-form-item label="用例名称"><el-input v-model="caseForm.name" /></el-form-item>
        <el-form-item label="所属模块"><el-input v-model="caseForm.module" placeholder="如：登录" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="caseForm.priority" style="width: 100%">
            <el-option label="低" value="low" /><el-option label="中" value="medium" /><el-option label="高" value="high" />
          </el-select>
        </el-form-item>
        <el-form-item label="用例描述"><el-input v-model="caseForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="预期结果"><el-input v-model="caseForm.expected_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="caseVisible = false">取消</el-button>
        <el-button type="primary" @click="addCase">保存</el-button>
      </template>
    </el-dialog>

    <!-- 派单 -->
    <el-dialog v-model="dispatchVisible" :title="batchMode ? '批量派单' : '测试派单'" width="420px">
      <el-form label-width="80px">
        <el-form-item label="用例">
          <el-input v-if="!batchMode" :model-value="dispatchCase?.name" disabled />
          <span v-else>已选 {{ selectedCases.length }} 条用例</span>
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="dispatchForm.assignee_id" filterable placeholder="选择执行人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dispatchVisible = false">取消</el-button>
        <el-button type="primary" @click="doDispatch">派单</el-button>
      </template>
    </el-dialog>

    <!-- AI 生成用例 -->
    <el-dialog v-model="aiVisible" title="AI 生成测试用例" width="760px" top="4vh">
      <el-form :model="aiForm" label-width="90px">
        <el-form-item label="生成依据">
          <el-radio-group v-model="aiForm.source">
            <el-radio value="requirement">需求文档</el-radio>
            <el-radio value="task">开发任务</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="aiForm.source === 'task'" label="开发任务">
          <el-select v-model="aiForm.task_ids" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择任务（可多选）" style="width: 100%">
            <el-option v-for="t in devTasks" :key="t.id" :label="t.title" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="参考需求">
          <el-select v-model="aiForm.requirement_id" clearable filterable placeholder="选择需求文档（默认最新）" style="width: 100%">
            <el-option v-for="r in requirements" :key="r.id" :label="`${r.title}${r.is_confirmed ? '（已入库）' : ''}`" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块"><el-input v-model="aiForm.module" placeholder="留空自动划分" /></el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="aiLoading" @click="doAiGen">生成</el-button>
        </el-form-item>
      </el-form>

      <el-table v-if="aiCases.length" :data="pagedAiCases" size="small" stripe @selection-change="(r) => (aiSelected = r)">
        <el-table-column type="selection" width="40" />
        <el-table-column prop="name" label="用例名称" min-width="150" />
        <el-table-column prop="module" label="模块" width="100" />
        <el-table-column prop="priority" label="优先级" width="70" />
        <el-table-column prop="expected_result" label="预期结果" min-width="140" show-overflow-tooltip />
      </el-table>
      <div v-if="aiCases.length" class="pagination-wrap" style="margin-top: 8px">
        <el-pagination background layout="total, prev, pager, next, sizes" :total="aiCases.length" v-model:current-page="aiPage" v-model:page-size="aiPageSize" :page-sizes="[10, 20, 50]" />
      </div>
      <template #footer>
        <el-button @click="aiVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="!aiSelected.length" @click="createAiCases">创建所选({{ aiSelected.length }})</el-button>
      </template>
    </el-dialog>

    <!-- 测试任务详情 -->
    <el-dialog v-model="taskDetailVisible" title="测试任务详情" width="600px">
      <template v-if="taskDetail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用例">{{ taskDetail.test_case_name }}</el-descriptions-item>
          <el-descriptions-item label="模块">{{ taskDetail.test_case_module || "未分组" }}</el-descriptions-item>
          <el-descriptions-item label="执行人">{{ taskDetail.assignee_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusType(taskDetail.status)">{{ statusLabel(taskDetail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ taskDetail.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ taskDetail.updated_at }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-sec">
          <div class="detail-title">结果/说明</div>
          <el-input v-model="taskDetail.result" type="textarea" :rows="3" placeholder="填写测试结果/说明" />
        </div>
      </template>
      <template #footer>
        <el-button @click="taskDetailVisible = false">关闭</el-button>
        <el-button type="primary" @click="saveTaskDetail">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listUsers } from "../api/projects";
import { useProjectStore } from "../stores/project";
import { listRequirements } from "../api/requirements";
import { listTasks } from "../api/tasks";
import { bugFromTestTask } from "../api/bugs";
import { batchDispatchTestTask, createTestCase, deleteTestCase, deleteTestTask, dispatchTestTask, exportTestTasks, generateTestCases, generateTestReport, listTestCases, listTestTasks, testStatistics, updateTestCase, updateTestTask } from "../api/testing";

const tab = ref("case");
const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const loading = ref(false);
const cases = ref([]);
const tasks = ref([]);
const users = ref([]);
const selectedCases = ref([]);
const stat = ref({});
const batchMode = ref(false);

const caseVisible = ref(false);
const editingCase = ref(null);
const dispatchVisible = ref(false);
const dispatchCase = ref(null);
const caseForm = reactive({ project_id: null, name: "", module: "", priority: "medium", description: "", expected_result: "" });
const dispatchForm = reactive({ test_case_id: null, assignee_id: null });
const caseFilter = reactive({ module: "", priority: "" });
const taskFilter = reactive({ assignee: "", status: "", module: "" });
const aiVisible = ref(false);
const aiLoading = ref(false);
const aiCases = ref([]);
const aiSelected = ref([]);
const devTasks = ref([]);
const requirements = ref([]);
const reportLoading = ref(false);
const exporting = ref(false);
const aiForm = reactive({ source: "requirement", module: "", task_ids: [], requirement_id: null });

// 分页状态：用例 / 任务 / AI 生成用例各自独立
const casePage = ref(1);
const casePageSize = ref(10);
const taskPage = ref(1);
const taskPageSize = ref(10);
const aiPage = ref(1);
const aiPageSize = ref(10);

const pagedCases = computed(() => {
  const start = (casePage.value - 1) * casePageSize.value;
  return cases.value.slice(start, start + casePageSize.value);
});
const pagedTasks = computed(() => {
  const start = (taskPage.value - 1) * taskPageSize.value;
  return tasks.value.slice(start, start + taskPageSize.value);
});
const pagedAiCases = computed(() => {
  const start = (aiPage.value - 1) * aiPageSize.value;
  return aiCases.value.slice(start, start + aiPageSize.value);
});

const statusOpts = [
  { value: "pending", label: "待执行" },
  { value: "executing", label: "执行中" },
  { value: "passed", label: "通过" },
  { value: "failed", label: "失败" },
  { value: "blocked", label: "阻塞" },
  { value: "retest", label: "待复测" },
  { value: "closed", label: "已关闭" },
];

async function loadProjects() {
  await projectStore.ensureLoaded();
  const u = await listUsers("");
  users.value = u.data;
}

async function load() {
  loading.value = true;
  try {
    if (tab.value === "case") {
      const res = await listTestCases({ project_id: projectId.value || undefined, module: caseFilter.module || undefined, priority: caseFilter.priority || undefined });
      cases.value = res.data;
      casePage.value = 1;
    } else {
      const params = { project_id: projectId.value || undefined };
      if (taskFilter.assignee) params.assignee = taskFilter.assignee;
      if (taskFilter.status) params.status = taskFilter.status;
      if (taskFilter.module) params.module = taskFilter.module;
      const [t, s] = await Promise.all([listTestTasks(params), testStatistics(projectId.value)]);
      tasks.value = t.data;
      stat.value = s.data;
      taskPage.value = 1;
    }
  } finally {
    loading.value = false;
  }
}

// 用例 / 任务 查询与重置
function applyCaseQuery() {
  load();
}
function resetCaseQuery() {
  caseFilter.module = "";
  caseFilter.priority = "";
  load();
}
function applyTaskQuery() {
  load();
}
function resetTaskQuery() {
  taskFilter.assignee = "";
  taskFilter.status = "";
  taskFilter.module = "";
  load();
}

function openCase(row) {
  editingCase.value = row || null;
  if (row) {
    caseForm.name = row.name; caseForm.module = row.module; caseForm.priority = row.priority;
    caseForm.description = row.description; caseForm.expected_result = row.expected_result;
    caseForm.project_id = row.project;
  } else {
    caseForm.name = ""; caseForm.module = ""; caseForm.priority = "medium"; caseForm.description = ""; caseForm.expected_result = "";
    caseForm.project_id = projectId.value;
    if (!caseForm.project_id) return ElMessage.warning("请先选择项目");
  }
  caseVisible.value = true;
}

async function addCase() {
  if (!caseForm.name.trim()) return ElMessage.warning("请输入用例名称");
  if (editingCase.value) {
    await updateTestCase(editingCase.value.id, {
      name: caseForm.name, module: caseForm.module, priority: caseForm.priority,
      description: caseForm.description, expected_result: caseForm.expected_result,
    });
    ElMessage.success("已更新");
  } else {
    await createTestCase({
      project: caseForm.project_id, name: caseForm.name, module: caseForm.module,
      priority: caseForm.priority, description: caseForm.description, expected_result: caseForm.expected_result,
    });
    ElMessage.success("用例已创建");
  }
  caseVisible.value = false;
  load();
}

async function removeCase(row) {
  try {
    await ElMessageBox.confirm(`确定删除用例「${row.name}」？`, "删除用例", { type: "warning" });
  } catch {
    return;
  }
  await deleteTestCase(row.id);
  ElMessage.success("已删除");
  load();
}

function openDispatch(row) {
  batchMode.value = false;
  dispatchCase.value = row;
  dispatchForm.test_case_id = row.id;
  dispatchForm.assignee_id = null;
  dispatchVisible.value = true;
}

function openBatchDispatch() {
  batchMode.value = true;
  dispatchForm.test_case_id = null;
  dispatchForm.assignee_id = null;
  dispatchVisible.value = true;
}

async function doDispatch() {
  if (!dispatchForm.assignee_id) return ElMessage.warning("请选择执行人");
  if (batchMode.value) {
    await batchDispatchTestTask({ test_case_ids: selectedCases.value.map((c) => c.id), assignee_id: dispatchForm.assignee_id });
  } else {
    await dispatchTestTask(dispatchForm);
  }
  ElMessage.success("派单成功");
  dispatchVisible.value = false;
  selectedCases.value = [];
  load();
}

async function updateStatus(row, status) {
  await updateTestTask(row.id, { status });
  ElMessage.success("状态已更新");
  load();
}

// 测试任务详情（含结果编辑）
const taskDetailVisible = ref(false);
const taskDetail = ref(null);
function showTaskDetail(row) {
  taskDetail.value = { ...row };
  taskDetailVisible.value = true;
}
async function saveTaskDetail() {
  await updateTestTask(taskDetail.value.id, { result: taskDetail.value.result });
  ElMessage.success("结果已保存");
  taskDetailVisible.value = false;
  load();
}
async function removeTask(row) {
  try {
    await ElMessageBox.confirm("确定删除该测试任务？", "删除任务", { type: "warning" });
  } catch {
    return;
  }
  await deleteTestTask(row.id);
  ElMessage.success("已删除");
  load();
}

// 失败/阻塞的测试任务转缺陷
async function toBug(row) {
  try {
    const { data } = await bugFromTestTask({ test_task_id: row.id });
    ElMessage.success(`已创建缺陷「${data.title}」，可到「缺陷管理」查看`);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "转缺陷失败");
  }
}

// AI 生成用例
async function openAiGen() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  aiForm.source = "requirement";
  aiForm.module = "";
  aiForm.task_ids = [];
  aiCases.value = [];
  aiSelected.value = [];
  try {
    const { data } = await listRequirements(projectId.value);
    requirements.value = data;
    aiForm.requirement_id = data.length ? data[0].id : null; // 默认最新
  } catch {
    /* 忽略 */
  }
  const { data } = await listTasks({ project_id: projectId.value });
  devTasks.value = data;
  aiVisible.value = true;
}

async function doAiGen() {
  if (aiForm.source === "task" && !aiForm.task_ids.length) return ElMessage.warning("请选择至少一个开发任务");
  aiLoading.value = true;
  aiCases.value = [];
  aiSelected.value = [];
  try {
    const { data } = await generateTestCases({
      project_id: projectId.value,
      source: aiForm.source,
      module: aiForm.module,
      task_ids: aiForm.task_ids,
      requirement_id: aiForm.requirement_id,
    });
    aiCases.value = data.cases || [];
    aiPage.value = 1;
    if (!aiCases.value.length) ElMessage.info("未生成到用例，可尝试调整依据");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "生成失败");
  } finally {
    aiLoading.value = false;
  }
}

async function createAiCases() {
  for (const c of aiSelected.value) {
    await createTestCase({
      project: projectId.value,
      name: c.name,
      module: c.module || aiForm.module,
      priority: c.priority || "medium",
      description: c.description || "",
      expected_result: c.expected_result || "",
    });
  }
  ElMessage.success(`已创建 ${aiSelected.value.length} 条用例`);
  aiVisible.value = false;
  load();
}

// 生成测试报告（写入交付文档，通过率达标推进项目到交付）
async function genReport() {
  if (!projectId.value) return ElMessage.warning("请选择项目");
  reportLoading.value = true;
  try {
    const { data } = await generateTestReport({ project_id: projectId.value });
    ElMessage.success(`测试报告已生成（通过率 ${data.pass_rate}%）`);
    if (data.advanced) ElMessage.success("通过率达标，项目已推进到「项目交付」");
    await ElMessageBox.alert(
      `测试报告已保存到「交付文档」。\n\n通过率：${data.pass_rate}%\n任务数：${data.total_tasks}\n${data.advanced ? "项目已推进到「项目交付」" : "项目状态未变更"}`,
      "测试报告已生成",
      { type: "success", confirmButtonText: "好的" }
    );
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "报告生成失败");
  } finally {
    reportLoading.value = false;
  }
}

// 导出测试任务 Excel
async function exportExcel() {
  if (!projectId.value) return ElMessage.warning("请选择项目");
  exporting.value = true;
  try {
    const params = { project_id: projectId.value };
    if (taskFilter.assignee) params.assignee = taskFilter.assignee;
    if (taskFilter.status) params.status = taskFilter.status;
    if (taskFilter.module) params.module = taskFilter.module;
    const res = await exportTestTasks(params);
    const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `测试任务_${projectId.value}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

function priType(p) {
  return { low: "info", medium: "warning", high: "danger" }[p] || "info";
}
function priLabel(p) {
  return { low: "低", medium: "中", high: "高" }[p] || p;
}
function statusLabel(k) {
  return { pending: "待执行", executing: "执行中", passed: "通过", failed: "失败", blocked: "阻塞", retest: "待复测", closed: "已关闭" }[k] || k;
}
function statusType(k) {
  return { pending: "info", executing: "primary", passed: "success", failed: "danger", blocked: "warning", retest: "warning", closed: "info" }[k] || "info";
}
function passColor(r) {
  return r >= 80 ? "#34d399" : r >= 50 ? "#f59e0b" : "#f87171";
}

// 初始加载完成前，忽略全局项目切换（避免与首次加载重复请求）
let projectReady = false;
watch(projectId, () => {
  if (projectReady) load();
});

onMounted(async () => {
  await loadProjects();
  await nextTick();
  projectReady = true;
  load();
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
  gap: 8px;
  align-items: center;
  margin-top: 12px;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.detail-sec {
  margin-top: 14px;
}
.detail-sec .detail-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}
.detail-sec .detail-content {
  white-space: pre-wrap;
  word-break: break-word;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 13px;
  color: #334155;
  max-height: 320px;
  overflow-y: auto;
}
.stat-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin: 12px 0;
}
.stat-cards .s-card {
  flex: 1;
  min-width: 100px;
  text-align: center;
  background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
  border-radius: 10px;
  padding: 12px 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.stat-cards .s-card .n { font-size: 24px; font-weight: 800; color: #0ea5e9; }
.stat-cards .s-card .l { color: #64748b; font-size: 12px; margin-top: 2px; }
</style>
