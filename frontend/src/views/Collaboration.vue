<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">工时登记</h3>
      </div>

      <el-tabs v-model="tab" style="margin-top: 12px" @tab-change="load">
        <!-- 工时 -->
        <el-tab-pane label="工时登记" name="worklog">
          <el-form :inline="true" :model="logForm" class="log-form">
            <el-form-item label="日期"><el-date-picker v-model="logForm.date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="工时(h)"><el-input-number v-model="logForm.hours" :min="0.5" :max="24" :step="0.5" /></el-form-item>
            <el-form-item label="关联任务">
              <el-button @click="taskPickerVisible = true">选择任务（已选 {{ logForm.tasks.length }}）</el-button>
              <el-tag v-for="id in logForm.tasks" :key="id" size="small" closable @close="removeTaskId(id)" style="margin-left: 4px">
                {{ taskTitle(id) }}
              </el-tag>
            </el-form-item>
            <el-form-item label="工作内容"><el-input v-model="logForm.description" type="textarea" :rows="2" placeholder="工作内容（可多行）" style="width: 320px" /></el-form-item>
            <el-form-item><el-button type="primary" @click="addLog">登记</el-button></el-form-item>
          </el-form>

          <div class="export-bar">
            <el-date-picker v-model="exportRange" type="daterange" value-format="YYYY-MM-DD" range-separator="~" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px" />
            <el-button type="success" :loading="exporting" @click="exportExcel">导出 Excel</el-button>
          </div>

          <el-descriptions :column="3" border size="small" style="margin: 8px 0 16px">
            <el-descriptions-item label="总工时">{{ stat.total_hours ?? "-" }} h</el-descriptions-item>
            <el-descriptions-item label="项目工时">
              <span v-for="p in stat.by_project" :key="p.project_id" style="margin-right: 10px">{{ p.name }}: {{ p.hours }}h</span>
            </el-descriptions-item>
            <el-descriptions-item label="个人工时">
              <span v-for="u in stat.by_user" :key="u.user_id" style="margin-right: 10px">{{ u.username }}: {{ u.hours }}h</span>
            </el-descriptions-item>
          </el-descriptions>

          <div class="query-bar">
            <el-date-picker v-model="qRange" type="daterange" value-format="YYYY-MM-DD" range-separator="~" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px" />
            <el-select v-model="qUser" placeholder="成员" clearable filterable style="width: 150px">
              <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
            </el-select>
            <el-button type="primary" @click="applyQuery">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
          </div>

          <el-table :data="pagedLogs" v-loading="loading" stripe>
            <el-table-column prop="project_name" label="项目" width="140" />
            <el-table-column prop="username" label="成员" width="100" />
            <el-table-column prop="date" label="日期" width="110" />
            <el-table-column prop="hours" label="工时(h)" width="90" />
            <el-table-column label="关联任务" min-width="180">
              <template #default="{ row }">
                <el-tag v-for="t in row.tasks_display" :key="t" size="small" style="margin-right: 4px">{{ t }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="工作内容" min-width="200" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="showDetail(row)">详情</el-button>
                <el-button size="small" type="warning" text @click="openEditLog(row)">编辑</el-button>
                <el-button size="small" type="danger" text @click="removeLog(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pager" v-if="logs.length">
            <el-pagination background layout="total, prev, pager, next, sizes" :total="logs.length" v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" />
          </div>
        </el-tab-pane>

        <!-- 周总结 -->
        <el-tab-pane label="周总结" name="summary">
          <el-form :inline="true" :model="sumForm" class="log-form">
            <el-form-item label="周起始日"><el-date-picker v-model="sumForm.week_start" type="date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="内容"><el-input v-model="sumForm.content" type="textarea" :rows="4" placeholder="本周工作、进度、问题、下周计划" style="width: 460px" /></el-form-item>
            <el-form-item>
              <el-button type="primary" @click="addSummary">提交</el-button>
              <el-button type="success" :loading="generating" @click="aiSummary">AI 总结</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="pagedSummaries" v-loading="loading" stripe>
            <el-table-column prop="project_name" label="项目" width="160" />
            <el-table-column prop="username" label="成员" width="120" />
            <el-table-column prop="week_start" label="周起始日" width="120" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
            <el-table-column label="操作" width="130">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="showSummaryDetail(row)">详情</el-button>
                <el-button
                  v-if="hasPerm('btn:weekly-delete')"
                  size="small"
                  type="danger"
                  text
                  @click="removeSummary(row)"
                >删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pager" v-if="summaries.length">
            <el-pagination background layout="total, prev, pager, next, sizes" :total="summaries.length" v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 关联任务选择弹窗（可搜索） -->
    <el-dialog v-model="taskPickerVisible" title="选择关联任务" width="620px">
      <el-input v-model="taskSearch" placeholder="搜索任务名称 / 业务模块" clearable style="margin-bottom: 10px" />
      <div class="task-picker">
        <el-checkbox-group v-model="logForm.tasks">
          <div v-for="t in filteredTasks" :key="t.id" class="task-item">
            <el-checkbox :value="t.id">
              {{ t.title }}
              <span class="sub">【{{ t.module || "未分组" }} · {{ t.assignee_name || "未指派" }} · {{ t.status_display }}】</span>
            </el-checkbox>
          </div>
        </el-checkbox-group>
        <div v-if="!filteredTasks.length" class="empty">没有匹配的任务</div>
      </div>
      <template #footer>
        <el-button @click="taskPickerVisible = false">取消</el-button>
        <el-button type="primary" @click="taskPickerVisible = false">确定</el-button>
      </template>
    </el-dialog>

    <!-- 工时详情 -->
    <el-dialog v-model="detailVisible" title="工时详情" width="560px">
      <template v-if="detailLog">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="项目">{{ detailLog.project_name }}</el-descriptions-item>
          <el-descriptions-item label="成员">{{ detailLog.username }}</el-descriptions-item>
          <el-descriptions-item label="日期">{{ detailLog.date }}</el-descriptions-item>
          <el-descriptions-item label="工时">{{ detailLog.hours }} h</el-descriptions-item>
        </el-descriptions>
        <div class="detail-sec">
          <div class="detail-title">关联任务</div>
          <template v-if="detailLog.tasks_display?.length">
            <el-tag v-for="t in detailLog.tasks_display" :key="t" size="small" style="margin-right: 4px">{{ t }}</el-tag>
          </template>
          <span v-else style="color: #909399">无</span>
        </div>
        <div class="detail-sec">
          <div class="detail-title">工作内容</div>
          <pre class="detail-content">{{ detailLog.description || "（无）" }}</pre>
        </div>
      </template>
    </el-dialog>

    <!-- 编辑工时 -->
    <el-dialog v-model="editLogVisible" title="编辑工时记录" width="560px">
      <el-form :model="editLogForm" label-width="80px">
        <el-form-item label="日期"><el-date-picker v-model="editLogForm.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="工时(h)"><el-input-number v-model="editLogForm.hours" :min="0.5" :max="24" :step="0.5" /></el-form-item>
        <el-form-item label="工作内容"><el-input v-model="editLogForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="关联任务">
          <el-select v-model="editLogTasks" multiple filterable style="width: 100%">
            <el-option v-for="t in tasks" :key="t.id" :label="`${t.title}【${t.module || '未分组'}】`" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editLogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingLog" @click="doEditLog">保存</el-button>
      </template>
    </el-dialog>

    <!-- 周总结详情 -->
    <el-dialog v-model="summaryDetailVisible" title="周总结详情" width="640px">
      <template v-if="summaryDetail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="项目">{{ summaryDetail.project_name }}</el-descriptions-item>
          <el-descriptions-item label="成员">{{ summaryDetail.username }}</el-descriptions-item>
          <el-descriptions-item label="周起始日">{{ summaryDetail.week_start }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-sec">
          <div class="detail-title">总结内容</div>
          <pre class="detail-content">{{ summaryDetail.content || "（无）" }}</pre>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listUsers } from "../api/projects";
import { useProjectStore } from "../stores/project";
import { createWeeklySummary, createWorkLog, deleteWeeklySummary, deleteWorkLog, exportWorkLogs, generateWeeklySummary, listWeeklySummaries, listWorkLogs, updateWorkLog, workLogStatistics } from "../api/collaboration";
import { hasPerm } from "../rbac";
import { listTasks } from "../api/tasks";

const tab = ref("worklog");
const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const loading = ref(false);
const generating = ref(false);
const exporting = ref(false);
const exportRange = ref([]);
const logs = ref([]);
const summaries = ref([]);
const tasks = ref([]);
const users = ref([]);
const stat = ref({});
const qRange = ref([]);
const qUser = ref(null);
const page = ref(1);
const pageSize = ref(10);
const detailVisible = ref(false);
const detailLog = ref(null);
const editLogVisible = ref(false);
const savingLog = ref(false);
const editLogTasks = ref([]);
const editLogForm = reactive({ id: null, date: "", hours: 1, description: "" });
const summaryDetailVisible = ref(false);
const summaryDetail = ref(null);
const taskPickerVisible = ref(false);
const taskSearch = ref("");
const logForm = reactive({ project_id: null, date: "", hours: 1, description: "", tasks: [] });
const sumForm = reactive({ project_id: null, week_start: "", content: "" });

const pagedLogs = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return logs.value.slice(start, start + pageSize.value);
});
const pagedSummaries = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return summaries.value.slice(start, start + pageSize.value);
});

const filteredTasks = computed(() => {
  const kw = taskSearch.value.trim().toLowerCase();
  if (!kw) return tasks.value;
  return tasks.value.filter((t) => (t.title || "").toLowerCase().includes(kw) || (t.module || "").toLowerCase().includes(kw));
});

function taskTitle(id) {
  const t = tasks.value.find((x) => x.id === id);
  return t ? t.title : id;
}

function removeTaskId(id) {
  logForm.tasks = logForm.tasks.filter((x) => x !== id);
}

async function loadProjects() {
  await projectStore.ensureLoaded();
  const u = await listUsers("");
  users.value = u.data;
}

async function loadTasks() {
  if (!projectId.value) {
    tasks.value = [];
    return;
  }
  const { data } = await listTasks({ project_id: projectId.value });
  tasks.value = data;
}

async function load() {
  loading.value = true;
  try {
    const pid = projectId.value || undefined;
    if (tab.value === "worklog") {
      const params = pid ? { project_id: pid } : {};
      const start = qRange.value?.[0];
      const end = qRange.value?.[1];
      if (start) params.start = start;
      if (end) params.end = end;
      if (qUser.value) params.user_id = qUser.value;
      const [logsRes, statRes] = await Promise.all([listWorkLogs(params), workLogStatistics(params)]);
      logs.value = logsRes.data;
      stat.value = statRes.data;
      page.value = 1;
      logForm.project_id = pid;
      loadTasks();
    } else {
      const params = pid ? { project_id: pid } : {};
      const [sumRes] = await Promise.all([listWeeklySummaries(params)]);
      summaries.value = sumRes.data;
      page.value = 1;
      sumForm.project_id = pid;
    }
  } finally {
    loading.value = false;
  }
}

function applyQuery() {
  page.value = 1;
  load();
}

function resetQuery() {
  qRange.value = [];
  qUser.value = null;
  page.value = 1;
  load();
}

function showDetail(row) {
  detailLog.value = row;
  detailVisible.value = true;
}

function openEditLog(row) {
  editLogForm.id = row.id;
  editLogForm.date = row.date;
  editLogForm.hours = row.hours;
  editLogForm.description = row.description || "";
  editLogTasks.value = row.tasks || [];
  editLogVisible.value = true;
}

async function doEditLog() {
  if (!editLogForm.date) return ElMessage.warning("请选择日期");
  savingLog.value = true;
  try {
    await updateWorkLog(editLogForm.id, {
      date: editLogForm.date,
      hours: editLogForm.hours,
      description: editLogForm.description,
      tasks: editLogTasks.value,
    });
    ElMessage.success("已更新");
    editLogVisible.value = false;
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    savingLog.value = false;
  }
}

async function removeLog(row) {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.date} 的工时记录（${row.hours}h）？`, "删除工时", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteWorkLog(row.id);
    ElMessage.success("已删除");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

function showSummaryDetail(row) {
  summaryDetail.value = row;
  summaryDetailVisible.value = true;
}

async function removeSummary(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.username} ${row.week_start}」的周总结？删除后不可恢复。`,
      "删除周总结",
      { type: "warning" }
    );
  } catch {
    return;
  }
  try {
    await deleteWeeklySummary(row.id);
    ElMessage.success("已删除");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

async function addLog() {
  if (!logForm.project_id) return ElMessage.warning("请选择项目");
  await createWorkLog({
    project: logForm.project_id,
    date: logForm.date,
    hours: logForm.hours,
    description: logForm.description,
    tasks: logForm.tasks,
  });
  ElMessage.success("登记成功");
  logForm.description = "";
  logForm.tasks = [];
  load();
}

async function exportExcel() {
  if (!projectId.value) return ElMessage.warning("请选择项目");
  exporting.value = true;
  try {
    const res = await exportWorkLogs({
      project_id: projectId.value,
      start: exportRange.value?.[0] || undefined,
      end: exportRange.value?.[1] || undefined,
    });
    const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `工时_${projectId.value}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

async function addSummary() {
  if (!sumForm.project_id) return ElMessage.warning("请选择项目");
  await createWeeklySummary({
    project: sumForm.project_id,
    week_start: sumForm.week_start,
    content: sumForm.content,
  });
  ElMessage.success("提交成功");
  sumForm.content = "";
  load();
}

async function aiSummary() {
  if (!sumForm.project_id) return ElMessage.warning("请选择项目");
  if (!sumForm.week_start) return ElMessage.warning("请选择周起始日");
  generating.value = true;
  try {
    const { data } = await generateWeeklySummary({
      project_id: sumForm.project_id,
      week_start: sumForm.week_start,
    });
    sumForm.content = data.content;
    ElMessage.success("AI 总结已生成，请确认后提交");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "AI 总结失败");
  } finally {
    generating.value = false;
  }
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
.task-picker {
  max-height: 50vh;
  overflow: auto;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 8px;
}
.task-item {
  padding: 4px 0;
}
.task-item .sub {
  color: #909399;
  font-size: 12px;
  margin-left: 6px;
}
.empty {
  color: #909399;
  text-align: center;
  padding: 20px 0;
}
.log-form {
  padding: 12px 0;
}
.query-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}
.detail-sec {
  margin-top: 14px;
}
.detail-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}
.detail-content {
  white-space: pre-wrap;
  word-break: break-word;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 10px;
  margin: 0;
  line-height: 1.6;
}
</style>
