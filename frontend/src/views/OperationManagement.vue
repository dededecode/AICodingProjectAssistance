<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">运营管理</h3>
        <div>
          <el-button type="success" :disabled="!projectId" :loading="ingesting" @click="ingest">知识入库</el-button>
        </div>
      </div>

      <div class="stat-cards">
        <div class="s-card"><div class="n">{{ stat.total ?? 0 }}</div><div class="l">运营记录总数</div></div>
        <div class="s-card"><div class="n" :style="{ color: (stat.open ?? 0) > 0 ? '#f59e0b' : '#34d399' }">{{ stat.open ?? 0 }}</div><div class="l">未关闭</div></div>
        <div class="s-card" v-for="(v, k) in stat.by_category || {}" :key="k">
          <div class="n">{{ v }}</div><div class="l">{{ categoryLabel(k) }}</div>
        </div>
      </div>

      <el-tabs v-model="tab" style="margin-top: 12px" @tab-change="load">
        <!-- 运营记录 -->
        <el-tab-pane label="运营记录" name="items">
          <div class="filter-bar">
            <el-select v-model="filter.category" placeholder="类型" clearable style="width: 130px" @change="load">
              <el-option v-for="c in categoryOpts" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
            <el-select v-model="filter.status" placeholder="状态" clearable style="width: 130px" @change="load">
              <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <div style="flex: 1"></div>
            <el-button type="primary" size="small" :disabled="!projectId" @click="openCreate">新增记录</el-button>
          </div>
          <el-table :data="items" v-loading="loading" stripe style="margin-top: 12px">
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <el-tag :type="catType(row.category)" size="small">{{ row.category_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="优先级" width="80">
              <template #default="{ row }">
                <el-tag :type="priType(row.priority)" size="small">{{ row.priority_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-select v-model="row.status" size="small" @change="(v) => updateStatus(row, v)">
                  <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column prop="requestor" label="提出人" width="100" />
            <el-table-column label="更新时间" width="150">
              <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="130">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="openEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" text @click="removeItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 运营指标 -->
        <el-tab-pane label="运营指标" name="metrics">
          <div class="filter-bar">
            <el-date-picker v-model="metricMonth" type="month" value-format="YYYY-MM" placeholder="按月筛选" clearable style="width: 140px" @change="load" />
            <div style="flex: 1"></div>
            <el-button type="primary" size="small" :disabled="!projectId" @click="openMetric(null)">新增指标</el-button>
          </div>
          <el-table :data="metrics" v-loading="loading" stripe style="margin-top: 12px">
            <el-table-column prop="month" label="月份" width="100" />
            <el-table-column prop="indicator_display" label="指标" width="120" />
            <el-table-column prop="value" label="数值" width="100" />
            <el-table-column prop="note" label="说明" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="130">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="openMetric(row)">编辑</el-button>
                <el-button size="small" type="danger" text @click="removeMetric(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新增/编辑运营记录 -->
    <el-dialog v-model="itemVisible" :title="editingItem ? '编辑运营记录' : '新增运营记录'" width="560px">
      <el-form :model="itemForm" label-width="90px">
        <el-form-item label="类型">
          <el-select v-model="itemForm.category" style="width: 100%">
            <el-option v-for="c in categoryOpts" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题"><el-input v-model="itemForm.title" /></el-form-item>
        <el-form-item label="内容"><el-input v-model="itemForm.content" type="textarea" :rows="3" placeholder="描述该迭代/优化/变更/反馈的详细内容" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="itemForm.priority" style="width: 100%">
                <el-option label="低" value="low" /><el-option label="中" value="medium" /><el-option label="高" value="high" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="itemForm.status" style="width: 100%">
                <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="提出人"><el-input v-model="itemForm.requestor" placeholder="如：客户 / 产品 / 运营" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemVisible = false">取消</el-button>
        <el-button type="primary" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑指标 -->
    <el-dialog v-model="metricVisible" :title="editingMetric ? '编辑指标' : '新增指标'" width="460px">
      <el-form :model="metricForm" label-width="90px">
        <el-form-item label="月份"><el-date-picker v-model="metricForm.month" type="month" value-format="YYYY-MM" style="width: 100%" /></el-form-item>
        <el-form-item label="指标">
          <el-select v-model="metricForm.indicator" style="width: 100%">
            <el-option v-for="i in indicatorOpts" :key="i.value" :label="i.label" :value="i.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="数值"><el-input-number v-model="metricForm.value" :min="0" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="metricForm.note" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="metricVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMetric">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useProjectStore } from "../stores/project";
import { createOperationItem, createOperationMetric, deleteOperationItem, deleteOperationMetric, listOperationItems, listOperationMetrics, operationStatistics, updateOperationItem, updateOperationMetric } from "../api/operation";
import { ingestKnowledge } from "../api/knowledge";

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const loading = ref(false);
const ingesting = ref(false);
const tab = ref("items");
const items = ref([]);
const metrics = ref([]);
const stat = ref({});
const metricMonth = ref(null);

const itemVisible = ref(false);
const editingItem = ref(null);
const metricVisible = ref(false);
const editingMetric = ref(null);
const filter = reactive({ category: "", status: "" });
const itemForm = reactive({ project_id: null, category: "iteration", title: "", content: "", priority: "medium", status: "evaluating", requestor: "" });
const metricForm = reactive({ project_id: null, month: "", indicator: "custom", value: 0, note: "" });

const categoryOpts = [
  { value: "iteration", label: "迭代需求" },
  { value: "optimization", label: "优化需求" },
  { value: "change", label: "业务变更" },
  { value: "feedback", label: "用户反馈" },
];
const statusOpts = [
  { value: "evaluating", label: "待评估" },
  { value: "accepted", label: "已接受" },
  { value: "scheduled", label: "已安排" },
  { value: "online", label: "已上线" },
  { value: "closed", label: "已关闭" },
];
const indicatorOpts = [
  { value: "renewal", label: "续期/续费" },
  { value: "satisfaction", label: "满意度" },
  { value: "active_users", label: "活跃用户" },
  { value: "custom", label: "自定义" },
];

async function loadProjects() {
  await projectStore.ensureLoaded();
}

async function load() {
  if (!projectId.value) return;
  loading.value = true;
  try {
    const [s] = await Promise.all([operationStatistics(projectId.value)]);
    stat.value = s.data;
    if (tab.value === "items") {
      const params = { project_id: projectId.value };
      if (filter.category) params.category = filter.category;
      if (filter.status) params.status = filter.status;
      const { data } = await listOperationItems(params);
      items.value = data;
    } else {
      const params = { project_id: projectId.value };
      if (metricMonth.value) params.month = metricMonth.value;
      const { data } = await listOperationMetrics(params);
      metrics.value = data;
    }
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingItem.value = null;
  itemForm.project_id = projectId.value;
  itemForm.category = "iteration";
  itemForm.title = "";
  itemForm.content = "";
  itemForm.priority = "medium";
  itemForm.status = "evaluating";
  itemForm.requestor = "";
  itemVisible.value = true;
}

function openEdit(row) {
  editingItem.value = row;
  itemForm.project_id = row.project;
  itemForm.category = row.category;
  itemForm.title = row.title;
  itemForm.content = row.content;
  itemForm.priority = row.priority;
  itemForm.status = row.status;
  itemForm.requestor = row.requestor || "";
  itemVisible.value = true;
}

async function saveItem() {
  if (!itemForm.title.trim()) return ElMessage.warning("请输入标题");
  const payload = {
    title: itemForm.title,
    content: itemForm.content,
    category: itemForm.category,
    priority: itemForm.priority,
    status: itemForm.status,
    requestor: itemForm.requestor,
  };
  if (editingItem.value) {
    await updateOperationItem(editingItem.value.id, payload);
    ElMessage.success("已保存");
  } else {
    await createOperationItem({ project: itemForm.project_id, ...payload });
    ElMessage.success("已创建");
  }
  itemVisible.value = false;
  load();
}

async function updateStatus(row, status) {
  await updateOperationItem(row.id, { status });
  ElMessage.success("状态已更新");
  load();
}

async function removeItem(row) {
  try {
    await ElMessageBox.confirm(`删除「${row.title}」？`, "删除记录", { type: "warning" });
  } catch {
    return;
  }
  await deleteOperationItem(row.id);
  ElMessage.success("已删除");
  load();
}

function openMetric(row) {
  editingMetric.value = row || null;
  metricForm.project_id = projectId.value;
  if (row) {
    metricForm.month = row.month;
    metricForm.indicator = row.indicator;
    metricForm.value = row.value;
    metricForm.note = row.note || "";
  } else {
    metricForm.month = "";
    metricForm.indicator = "custom";
    metricForm.value = 0;
    metricForm.note = "";
  }
  metricVisible.value = true;
}

async function saveMetric() {
  if (!metricForm.month) return ElMessage.warning("请选择月份");
  const payload = { month: metricForm.month, indicator: metricForm.indicator, value: metricForm.value, note: metricForm.note };
  if (editingMetric.value) {
    await updateOperationMetric(editingMetric.value.id, payload);
    ElMessage.success("已保存");
  } else {
    await createOperationMetric({ project: metricForm.project_id, ...payload });
    ElMessage.success("已创建");
  }
  metricVisible.value = false;
  load();
}

async function removeMetric(row) {
  try {
    await ElMessageBox.confirm("删除该指标？", "删除指标", { type: "warning" });
  } catch {
    return;
  }
  await deleteOperationMetric(row.id);
  ElMessage.success("已删除");
  load();
}

async function ingest() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  ingesting.value = true;
  try {
    const { data } = await ingestKnowledge({ project_id: projectId.value, kind: "operation" });
    ElMessage.success(`已入库 ${data.created ?? 0} 条知识${data.overwritten ? `（覆盖旧知识 ${data.overwritten} 条）` : ""}`);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "知识入库失败");
  } finally {
    ingesting.value = false;
  }
}

function categoryLabel(k) {
  return { iteration: "迭代需求", optimization: "优化需求", change: "业务变更", feedback: "用户反馈" }[k] || k;
}
function catType(c) {
  return { iteration: "primary", optimization: "success", change: "warning", feedback: "info" }[c] || "info";
}
function priType(p) {
  return { low: "info", medium: "warning", high: "danger" }[p] || "info";
}
function formatTime(t) {
  return t ? new Date(t).toLocaleString() : "";
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
.stat-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin: 12px 0;
}
.stat-cards .s-card {
  flex: 1;
  min-width: 90px;
  text-align: center;
  background: linear-gradient(135deg, #f0fdf4, #dcfce7);
  border-radius: 10px;
  padding: 12px 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.stat-cards .s-card .n { font-size: 24px; font-weight: 800; color: #16a34a; }
.stat-cards .s-card .l { color: #64748b; font-size: 12px; margin-top: 2px; }
</style>
