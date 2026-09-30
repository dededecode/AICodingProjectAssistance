<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">缺陷管理</h3>
      </div>

      <div class="stat-cards">
        <div class="s-card"><div class="n">{{ stat.total ?? 0 }}</div><div class="l">缺陷总数</div></div>
        <div class="s-card"><div class="n" :style="{ color: (stat.open ?? 0) > 0 ? '#f87171' : '#34d399' }">{{ stat.open ?? 0 }}</div><div class="l">未关闭</div></div>
        <div class="s-card" v-for="(v, k) in stat.by_status || {}" :key="k">
          <div class="n">{{ v }}</div><div class="l">{{ statusLabel(k) }}</div>
        </div>
      </div>

      <div class="filter-bar">
        <el-select v-model="filter.status" placeholder="状态" clearable style="width: 130px" @change="load">
          <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="filter.severity" placeholder="严重程度" clearable style="width: 130px" @change="load">
          <el-option v-for="s in severityOpts" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="filter.assignee" placeholder="处理人" clearable filterable style="width: 140px" @change="load">
          <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
        </el-select>
        <div style="flex: 1"></div>
        <el-button type="primary" :disabled="!projectId" @click="openCreate">新增缺陷</el-button>
      </div>

      <el-table :data="bugs" v-loading="loading" stripe style="margin-top: 12px">
        <el-table-column prop="title" label="缺陷标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="module" label="模块" width="100" show-overflow-tooltip />
        <el-table-column label="严重程度" width="90">
          <template #default="{ row }">
            <el-tag :type="sevType(row.severity)" size="small">{{ row.severity_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="assignee_name" label="处理人" width="90" />
        <el-table-column prop="reporter_name" label="提交人" width="90" />
        <el-table-column prop="related_test_task_name" label="来源用例" width="130" show-overflow-tooltip />
        <el-table-column prop="related_task_title" label="开发任务" width="130" show-overflow-tooltip />
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openEdit(row)">处理</el-button>
            <el-button size="small" type="danger" text @click="removeBug(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑缺陷 -->
    <el-dialog v-model="visible" :title="editing ? '处理缺陷' : '新增缺陷'" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="业务模块"><el-input v-model="form.module" placeholder="如：登录" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开发任务">
              <el-select v-model="form.related_task" clearable filterable placeholder="关联开发任务" style="width: 100%" @change="onTaskChange">
                <el-option v-for="t in tasks" :key="t.id" :label="t.title" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="严重程度">
              <el-select v-model="form.severity" style="width: 100%">
                <el-option v-for="s in severityOpts" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="处理人">
          <el-select v-model="form.assignee" clearable filterable placeholder="选择处理人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editing" label="截图">
          <div style="width: 100%">
            <el-upload :auto-upload="false" :show-file-list="false" :on-change="onImageFile" accept="image/*">
              <el-button size="small" :loading="imgUploading">上传截图</el-button>
            </el-upload>
            <div class="img-list">
              <div v-for="im in (editing.images || [])" :key="im.id" class="img-item">
                <el-image :src="im.url" fit="cover" style="width: 72px; height: 72px; border-radius: 6px" :preview-src-list="(editing.images || []).map((i) => i.url)" preview-teleported />
                <span class="del" @click="removeImage(im)">✕</span>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listUsers } from "../api/projects";
import { useProjectStore } from "../stores/project";
import { listTasks } from "../api/tasks";
import { bugStatistics, createBug, deleteBug, deleteBugImage, listBugs, updateBug, uploadBugImage } from "../api/bugs";

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const users = ref([]);
const tasks = ref([]);
const bugs = ref([]);
const stat = ref({});
const loading = ref(false);
const visible = ref(false);
const editing = ref(null);
const imgUploading = ref(false);
const filter = reactive({ status: "", severity: "", assignee: "" });
const form = reactive({ project_id: null, title: "", description: "", module: "", severity: "medium", status: "new", assignee: null, related_task: null });

const statusOpts = [
  { value: "new", label: "待处理" },
  { value: "processing", label: "处理中" },
  { value: "fixed", label: "已修复" },
  { value: "retest", label: "待复测" },
  { value: "closed", label: "已关闭" },
];
const severityOpts = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "critical", label: "严重" },
];

async function loadProjects() {
  await projectStore.ensureLoaded();
  const u = await listUsers("");
  users.value = u.data;
}

async function load() {
  if (!projectId.value) {
    bugs.value = [];
    return;
  }
  loading.value = true;
  try {
    const params = { project_id: projectId.value };
    if (filter.status) params.status = filter.status;
    if (filter.severity) params.severity = filter.severity;
    if (filter.assignee) params.assignee = filter.assignee;
    const [b, s, t] = await Promise.all([listBugs(params), bugStatistics(projectId.value), listTasks({ project_id: projectId.value })]);
    bugs.value = b.data;
    stat.value = s.data;
    tasks.value = t.data;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editing.value = null;
  form.project_id = projectId.value;
  form.title = "";
  form.description = "";
  form.module = "";
  form.severity = "medium";
  form.status = "new";
  form.assignee = null;
  form.related_task = null;
  visible.value = true;
}

function openEdit(row) {
  editing.value = row;
  form.project_id = row.project;
  form.title = row.title;
  form.description = row.description;
  form.module = row.module || "";
  form.severity = row.severity;
  form.status = row.status;
  form.assignee = row.assignee || null;
  form.related_task = row.related_task || null;
  visible.value = true;
}

function onTaskChange(id) {
  const t = tasks.value.find((x) => x.id === id);
  if (t && t.module && !form.module) form.module = t.module;
}

async function onImageFile(file) {
  if (!editing.value) return;
  imgUploading.value = true;
  try {
    const fd = new FormData();
    fd.append("image", file.raw);
    const { data } = await uploadBugImage(editing.value.id, fd);
    editing.value.images = data.images || [];
    load();
    ElMessage.success("截图已上传");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "上传失败");
  } finally {
    imgUploading.value = false;
  }
}

async function removeImage(im) {
  try {
    await ElMessageBox.confirm("删除该截图？", "删除图片", { type: "warning" });
  } catch {
    return;
  }
  await deleteBugImage(editing.value.id, im.id);
  editing.value.images = (editing.value.images || []).filter((x) => x.id !== im.id);
  ElMessage.success("已删除");
}

async function save() {
  if (!form.title.trim()) return ElMessage.warning("请输入缺陷标题");
  if (editing.value) {
    await updateBug(editing.value.id, {
      title: form.title,
      description: form.description,
      module: form.module,
      severity: form.severity,
      status: form.status,
      assignee: form.assignee || null,
      related_task: form.related_task || null,
    });
    ElMessage.success("已保存");
  } else {
    await createBug({
      project: form.project_id,
      title: form.title,
      description: form.description,
      module: form.module,
      severity: form.severity,
      assignee: form.assignee || null,
      related_task: form.related_task || null,
    });
    ElMessage.success("缺陷已创建");
  }
  visible.value = false;
  load();
}

async function removeBug(row) {
  try {
    await ElMessageBox.confirm(`确定删除缺陷「${row.title}」？`, "删除缺陷", { type: "warning" });
  } catch {
    return;
  }
  await deleteBug(row.id);
  ElMessage.success("已删除");
  load();
}

function statusLabel(k) {
  return { new: "待处理", processing: "处理中", fixed: "已修复", retest: "待复测", closed: "已关闭" }[k] || k;
}
function statusType(s) {
  return { new: "danger", processing: "warning", fixed: "primary", retest: "warning", closed: "success" }[s] || "info";
}
function sevType(s) {
  return { low: "info", medium: "warning", high: "danger", critical: "danger" }[s] || "info";
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
  background: linear-gradient(135deg, #fef2f2, #fee2e2);
  border-radius: 10px;
  padding: 12px 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.stat-cards .s-card .n { font-size: 24px; font-weight: 800; color: #ef4444; }
.stat-cards .s-card .l { color: #64748b; font-size: 12px; margin-top: 2px; }
.img-list { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.img-item { position: relative; }
.img-item .del {
  position: absolute;
  top: -6px;
  right: -6px;
  background: #ef4444;
  color: #fff;
  width: 16px;
  height: 16px;
  line-height: 16px;
  text-align: center;
  border-radius: 50%;
  font-size: 10px;
  cursor: pointer;
}
</style>
