<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">项目计划</h3>
        <div>
          <el-button type="success" :disabled="!projectId" :loading="ingesting" @click="ingest('plan')">知识入库</el-button>
        </div>
      </div>

      <el-alert
        v-if="projectId && !canPlan"
        type="warning"
        :closable="false"
        style="margin-top: 12px"
        title="该项目仍处于「需求分析」阶段，请先在需求分析中完成 AI 检测并确认入库，项目进入「项目计划」状态后才能安排计划。"
      />

      <div style="margin-top: 16px">
        <el-button type="primary" :disabled="!canPlan" @click="openGenerate">计划项目</el-button>
      </div>

      <h4 style="margin: 20px 0 8px">已有计划</h4>
      <el-table :data="plans" v-loading="loading" stripe>
        <el-table-column prop="name" label="计划名称" min-width="150" />
        <el-table-column label="成员(权重)" min-width="200">
          <template #default="{ row }">
            {{ (row.members || []).map((m) => `${m.username}(${(m.weight * 100).toFixed(0)}%)`).join("、") }}
          </template>
        </el-table-column>
        <el-table-column label="计划周期" min-width="200">
          <template #default="{ row }">{{ row.start_date }} ~ {{ row.launch_date }}</template>
        </el-table-column>
        <el-table-column prop="requirement_title" label="依据需求" min-width="150" show-overflow-tooltip />
        <el-table-column label="任务数" width="80">
          <template #default="{ row }">{{ row.task_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="viewPlan(row)">查看计划</el-button>
            <el-button size="small" type="danger" text @click="removePlan(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 计划项目 -->
    <el-dialog v-model="genVisible" title="AI 生成项目计划" width="640px" top="6vh">
      <el-form label-width="100px">
        <el-form-item label="计划名称">
          <el-input v-model="genForm.name" placeholder="如：一期迭代 / V1.0 正式版" />
        </el-form-item>
        <el-form-item label="计划开始时间">
          <el-date-picker v-model="genForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="计划上线时间">
          <el-date-picker v-model="genForm.launch_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="选择需求文档">
          <el-select v-model="genForm.requirement_id" placeholder="选择上传的需求文档" style="width: 100%">
            <el-option v-for="r in requirements" :key="r.id" :label="r.title" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划成员">
          <el-select v-model="selectedMemberIds" multiple filterable placeholder="选择项目成员（自动统计人数）" style="width: 100%">
            <el-option v-for="m in projectMembers" :key="m.id" :label="m.username" :value="m.id" />
          </el-select>
          <div style="color: #909399; font-size: 12px; margin-top: 4px">已选 {{ selectedMemberIds.length }} 人</div>
        </el-form-item>
        <el-form-item v-if="selectedMemberIds.length" label="开发权重">
          <el-table :data="weightRows" size="small" border>
            <el-table-column prop="username" label="成员" min-width="120" />
            <el-table-column label="权重(0-1，工作量占比)" min-width="180">
              <template #default="{ row }">
                <el-input-number v-model="weightMap[row.id]" :min="0" :max="1" :step="0.1" controls-position="right" style="width: 140px" />
              </template>
            </el-table-column>
          </el-table>
          <div :style="{ color: Math.abs(weightSum - 1) > 0.01 ? '#e6a23c' : '#67c23a', fontSize: '12px', marginTop: '4px' }">
            权重合计：{{ weightSum.toFixed(2) }}（建议合计为 1.00）
          </div>
        </el-form-item>
        <el-alert type="info" :closable="false" title="AI 将按业务模块拆分任务，并结合各成员权重比例分配开发任务，基于 AI Coding 全栈开发，不分前后端。" />
      </el-form>
      <div v-if="genContent || streaming" style="margin-top: 12px">
        <el-divider content-position="left">
          生成内容{{ streaming ? "（生成中…）" : aborted ? "（已中断，可继续生成）" : "" }}
        </el-divider>
        <el-input v-model="genContent" type="textarea" :rows="16" class="plan-textarea" placeholder="计划内容（流式生成中）" />
      </div>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button v-if="streaming" type="warning" @click="stopGenerate">停止生成</el-button>
        <el-button v-else-if="genContent" type="success" :loading="generating" @click="saveGeneratedPlan(false)">保存计划</el-button>
        <el-button v-else type="primary" :loading="generating" @click="startGenerate">生成计划</el-button>
        <el-button v-if="!streaming && genContent && aborted" type="primary" @click="continueGenerate">继续生成</el-button>
      </template>
    </el-dialog>

    <!-- 计划内容（可编辑） -->
    <el-dialog v-model="planVisible" :title="`${current?.project_name || ''} - ${current?.name || '项目计划'}`" width="72%" top="3vh" class="plan-view">
      <el-input v-model="editContent" type="textarea" :autosize="{ minRows: 30, maxRows: 48 }" class="plan-textarea" placeholder="计划内容" />
      <template #footer>
        <el-button @click="planVisible = false">关闭</el-button>
        <el-button :loading="saving" @click="savePlan">保存修改</el-button>
        <el-button :loading="regenerating" @click="openRegen">重新生成</el-button>
      </template>
    </el-dialog>

    <!-- 重新生成：先输入修改意见，再流式输出 -->
    <el-dialog v-model="regenVisible" title="重新生成项目计划" width="680px" top="5vh">
      <template v-if="!regenStarted">
        <el-alert type="info" :closable="false" title="AI 将结合当前计划版本与你的修改意见重新生成，可描述需要调整的地方（如成员分工、里程碑时间、任务拆分、风险等）。" style="margin-bottom: 12px" />
        <el-input v-model="regenSuggestion" type="textarea" :rows="5" placeholder="请输入修改意见…" />
      </template>
      <template v-else>
        <el-divider content-position="left">
          重新生成内容{{ regenStreaming ? "（生成中…）" : regenAborted ? "（已中断，可继续生成）" : "" }}
        </el-divider>
        <el-input v-model="regenContent" type="textarea" :rows="22" placeholder="生成中…" />
      </template>
      <template #footer>
        <el-button @click="regenVisible = false">取消</el-button>
        <el-button v-if="!regenStarted" type="primary" :loading="regenStreaming" @click="startRegenStream">开始生成</el-button>
        <template v-else>
          <el-button v-if="regenStreaming" type="warning" @click="stopRegenStream">停止生成</el-button>
          <el-button v-else-if="regenContent" type="success" :loading="regenerating" @click="saveRegen">保存并更新计划</el-button>
          <el-button v-if="!regenStreaming && regenContent && regenAborted" type="primary" @click="continueRegenStream">继续生成</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useProjectStore } from "../stores/project";
import { listRequirements } from "../api/requirements";
import { deleteProjectPlan, generateProjectPlan, listProjectPlans, updateProjectPlan } from "../api/projectPlanning";
import { ingestKnowledge } from "../api/knowledge";

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const requirements = ref([]);
const plans = ref([]);
const loading = ref(false);
const genVisible = ref(false);
const generating = ref(false);
const genContent = ref("");
const streaming = ref(false);
const aborted = ref(false);
const genAbortCtrl = ref(null);
const ingesting = ref(false);
const planVisible = ref(false);
const current = ref(null);
const editContent = ref("");
const saving = ref(false);
const regenerating = ref(false);
const regenVisible = ref(false);
const regenSuggestion = ref("");
const regenStarted = ref(false);
const regenStreaming = ref(false);
const regenContent = ref("");
const regenAborted = ref(false);
const regenAbortCtrl = ref(null);
const selectedProject = ref(null);
const selectedMemberIds = ref([]);
const weightMap = reactive({});

const genForm = reactive({ project_id: null, name: "", start_date: "", launch_date: "", requirement_id: null });

// 项目成员（用于选择）
const projectMembers = computed(() => (selectedProject.value?.members || []));
// 权重表格行
const weightRows = computed(() =>
  projectMembers.value.filter((m) => selectedMemberIds.value.includes(m.id))
);
const weightSum = computed(() =>
  weightRows.value.reduce((s, m) => s + (weightMap[m.id] || 0), 0)
);

// 成员变化时初始化/清理权重
watch(selectedMemberIds, (ids) => {
  const keep = new Set(ids);
  // 新增成员给默认均分权重（临时）
  for (const m of projectMembers.value) {
    if (keep.has(m.id) && weightMap[m.id] === undefined) {
      weightMap[m.id] = 0;
    }
  }
  // 移除已取消的成员权重
  for (const k of Object.keys(weightMap)) {
    if (!keep.has(Number(k))) delete weightMap[k];
  }
});

const canPlan = computed(() => {
  const p = selectedProject.value;
  return p && p.status !== "requirement";
});

async function loadProjects() {
  await projectStore.ensureLoaded();
  onProjectChange();
}

async function onProjectChange() {
  selectedProject.value = projects.value.find((p) => p.id === projectId.value) || null;
  loadPlans();
  loadRequirements();
}

async function loadRequirements() {
  if (!projectId.value) {
    requirements.value = [];
    return;
  }
  const { data } = await listRequirements(projectId.value);
  requirements.value = data;
}

async function loadPlans() {
  if (!projectId.value) {
    plans.value = [];
    return;
  }
  loading.value = true;
  try {
    const { data } = await listProjectPlans(projectId.value);
    plans.value = data;
  } finally {
    loading.value = false;
  }
}

function openGenerate() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  if (!canPlan.value) return ElMessage.warning("请先完成需求分析并确认入库");
  genForm.project_id = projectId.value;
  genForm.name = "";
  genForm.start_date = "";
  genForm.launch_date = "";
  genForm.requirement_id = null;
  selectedMemberIds.value = [];
  for (const k of Object.keys(weightMap)) delete weightMap[k];
  genContent.value = "";
  streaming.value = false;
  aborted.value = false;
  genVisible.value = true;
}

function validateGenForm() {
  if (!genForm.name.trim()) return "请输入计划名称";
  if (!genForm.requirement_id) return "请选择需求文档";
  if (!genForm.start_date) return "请选择计划开始时间";
  if (!genForm.launch_date) return "请选择计划上线时间";
  if (genForm.launch_date < genForm.start_date) return "计划上线时间不能早于计划开始时间";
  if (!selectedMemberIds.value.length) return "请选择计划成员";
  if (Math.abs(weightSum.value - 1) > 0.01) return "开发权重合计应约为 1.00";
  return "";
}

function genPayload() {
  return {
    project_id: genForm.project_id,
    requirement_id: genForm.requirement_id,
    name: genForm.name,
    start_date: genForm.start_date,
    launch_date: genForm.launch_date,
    members: selectedMemberIds.value.map((uid) => ({
      user_id: uid,
      weight: Number(weightMap[uid] || 0),
    })),
  };
}

async function startGenerate() {
  const msg = validateGenForm();
  if (msg) return ElMessage.warning(msg);
  genContent.value = "";
  await streamGenerate("");
}

async function streamGenerate(partial) {
  if (streaming.value) return;
  streaming.value = true;
  aborted.value = false;
  if (!partial) genContent.value = "";
  const ctrl = new AbortController();
  genAbortCtrl.value = ctrl;
  let doneOk = false;
  try {
    const token = localStorage.getItem("access_token");
    const payload = genPayload();
    if (partial) payload.partial_content = partial;
    const res = await fetch("/api/project-plans/generate-stream/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "生成失败");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
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
          else if (evt.type === "done") doneOk = true;
        }
      }
    }
    if (doneOk && !aborted.value) {
      ElMessage.success("生成完成，请确认内容后点击「保存计划」");
    }
  } catch (e) {
    if (e.name === "AbortError") {
      aborted.value = true;
      ElMessage.warning("已中断生成，可点击「继续生成」接着生成，或「保存计划」保存当前内容");
    } else {
      aborted.value = true;
      ElMessage.error(e.message || "生成失败");
    }
  } finally {
    streaming.value = false;
  }
}

function stopGenerate() {
  if (genAbortCtrl.value) genAbortCtrl.value.abort();
}

function continueGenerate() {
  streamGenerate(genContent.value);
}

async function saveGeneratedPlan(auto = false) {
  if (!genContent.value.trim()) return ElMessage.warning("计划内容为空，请先生成");
  generating.value = true;
  try {
    const { data } = await generateProjectPlan({ ...genPayload(), plan_content: genContent.value });
    genVisible.value = false;
    current.value = data;
    editContent.value = data.plan_content;
    if (!auto) ElMessage.success("计划已保存");
    loadPlans();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "计划保存失败");
  } finally {
    generating.value = false;
  }
}

async function savePlan() {
  if (!current.value) return;
  saving.value = true;
  try {
    const { data } = await updateProjectPlan(current.value.id, { plan_content: editContent.value });
    current.value = data;
    editContent.value = data.plan_content;
    ElMessage.success("计划已保存");
    loadPlans();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

function openRegen() {
  if (!current.value) return;
  regenSuggestion.value = "";
  regenStarted.value = false;
  regenStreaming.value = false;
  regenContent.value = "";
  regenAborted.value = false;
  regenVisible.value = true;
}

async function startRegenStream() {
  if (!current.value) return;
  if (!regenSuggestion.value.trim()) return ElMessage.warning("请输入修改意见");
  regenStarted.value = true;
  regenContent.value = "";
  await regenStream("", regenSuggestion.value);
}

async function regenStream(partial) {
  if (!current.value || regenStreaming.value) return;
  regenStreaming.value = true;
  regenAborted.value = false;
  const ctrl = new AbortController();
  regenAbortCtrl.value = ctrl;
  let doneOk = false;
  try {
    const token = localStorage.getItem("access_token");
    const payload = { suggestion: regenSuggestion.value };
    if (partial) payload.partial_content = partial;
    const res = await fetch(`/api/project-plans/${current.value.id}/regenerate-stream/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "重新生成失败");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
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
          if (evt.type === "chunk") regenContent.value += evt.content;
          else if (evt.type === "error") throw new Error(evt.message || "重新生成失败");
          else if (evt.type === "done") doneOk = true;
        }
      }
    }
    if (doneOk && !regenAborted.value) {
      ElMessage.success("重新生成完成，请确认内容后点击「保存并更新计划」");
    }
  } catch (e) {
    if (e.name === "AbortError") {
      regenAborted.value = true;
      ElMessage.warning("已中断生成，可点击「继续生成」或「保存并更新计划」");
    } else {
      regenAborted.value = true;
      ElMessage.error(e.message || "重新生成失败");
    }
  } finally {
    regenStreaming.value = false;
  }
}

function stopRegenStream() {
  if (regenAbortCtrl.value) regenAbortCtrl.value.abort();
}

function continueRegenStream() {
  regenStream(regenContent.value);
}

async function saveRegen() {
  if (!current.value) return;
  if (!regenContent.value.trim()) return ElMessage.warning("内容为空");
  regenerating.value = true;
  try {
    const { data } = await updateProjectPlan(current.value.id, { plan_content: regenContent.value });
    current.value = data;
    editContent.value = data.plan_content;
    regenVisible.value = false;
    ElMessage.success("计划已按修改意见更新");
    loadPlans();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    regenerating.value = false;
  }
}

function viewPlan(row) {
  current.value = row;
  editContent.value = row.plan_content;
  planVisible.value = true;
}

async function removePlan(row) {
  const { ElMessageBox } = await import("element-plus");
  try {
    await ElMessageBox.confirm(`确定删除计划「${row.name}」？其关联的任务也会一并删除。`, "删除计划", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteProjectPlan(row.id);
    ElMessage.success("计划已删除");
    loadPlans();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

async function ingest(kind) {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  ingesting.value = true;
  try {
    const { data } = await ingestKnowledge({ project_id: projectId.value, kind });
    ElMessage.success(`已入库 ${data.created ?? 0} 条知识${data.overwritten ? `（覆盖旧知识 ${data.overwritten} 条）` : ""}`);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "知识入库失败");
  } finally {
    ingesting.value = false;
  }
}

function formatTime(t) {
  return t ? new Date(t).toLocaleString() : "";
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
.plan-content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  font-family: inherit;
}
.plan-view :deep(.el-dialog__body) {
  height: calc(70vh - 66px);
  overflow: auto;
}
.plan-view :deep(.plan-textarea .el-textarea__inner) {
  font-family: Consolas, Menlo, monospace;
  line-height: 1.6;
}
</style>
