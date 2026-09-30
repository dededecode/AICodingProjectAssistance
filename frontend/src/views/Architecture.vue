<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">架构设计</h3>
        <div>
          <el-button type="success" :disabled="!projectId" :loading="ingesting" @click="ingest">知识入库</el-button>
          <el-button type="primary" :disabled="!canGenerate" @click="openGenerate">生成架构设计</el-button>
        </div>
      </div>

      <el-alert
        v-if="projectId && !canGenerate"
        type="warning"
        :closable="false"
        style="margin-top: 12px"
        title="仅「架构设计」状态的项目可生成架构设计。请先完成需求分析与项目计划。"
      />

      <h4 style="margin: 20px 0 8px">已有架构设计</h4>
      <el-table :data="designs" v-loading="loading" stripe>
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="frontend_stack" label="前端技术栈" min-width="130" show-overflow-tooltip />
        <el-table-column prop="backend_stack" label="后端技术栈" min-width="130" show-overflow-tooltip />
        <el-table-column prop="base_framework_display" label="框架底座" width="120" />
        <el-table-column prop="db_type_display" label="数据库" width="90" />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="viewDesign(row)">查看</el-button>
            <el-button size="small" type="danger" text @click="removeDesign(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 生成（两步流式） -->
    <el-dialog v-model="genVisible" title="生成项目架构设计" width="80%" top="2vh" class="gen-dialog">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="前端技术栈"><el-input v-model="form.frontend_stack" placeholder="如 Vue3 + Element Plus" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="后端技术栈"><el-input v-model="form.backend_stack" placeholder="如 Spring Boot 3" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="框架底座">
              <el-select v-model="form.base_framework" style="width: 100%">
                <el-option label="无（自研）" value="" />
                <el-option label="Ruoyi-Vue-Plus（5.x）" value="ruoyi-vue-plus" />
                <el-option label="Smart-Admin" value="smart-admin" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据库类型">
              <el-select v-model="form.db_type" style="width: 100%">
                <el-option label="MySQL" value="mysql" />
                <el-option label="PostgreSQL" value="postgresql" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="约束/规则">
          <el-input v-model="form.constraints" type="textarea" :rows="2" placeholder="如：必须私有化部署、强制使用某中间件/网关、并发/性能指标要求等（可选，随提示词发送给 AI）" />
        </el-form-item>
        <el-form-item label="其它补充">
          <el-input v-model="form.extra" type="textarea" :rows="2" placeholder="其它需要 AI 参考的信息（可选，随提示词发送给 AI）" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">第一步：架构概设文档</el-divider>
      <div class="step-row">
        <el-button :loading="streaming.doc" :disabled="streaming.sql" @click="genStep('design_doc')">
          {{ docText ? "重新生成文档" : "生成架构概设文档" }}
        </el-button>
        <span class="hint">流式输出，边生成边展示</span>
      </div>
      <el-input v-model="docText" type="textarea" :rows="12" class="edit-area" />

      <el-divider content-position="left">第二步：数据库 SQL</el-divider>
      <div class="step-row">
        <el-button :loading="streaming.sql" :disabled="streaming.doc || !docText" @click="genStep('sql')">
          {{ sqlText ? "重新生成 SQL" : "生成数据库 SQL" }}
        </el-button>
        <span class="hint">流式输出，生成后可直接修改</span>
      </div>
      <el-input v-model="sqlText" type="textarea" :rows="12" class="edit-area sql" />

      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="streaming.doc || streaming.sql || !docText" @click="confirmSave">确认保存</el-button>
      </template>
    </el-dialog>

    <!-- 查看/编辑 -->
    <el-dialog v-model="viewVisible" :title="`${current?.project_name || ''} - 架构设计`" width="82%" top="2vh" class="view-dialog">
      <el-tabs v-model="tab">
        <el-tab-pane label="架构概设文档" name="doc">
          <el-input v-model="current.design_doc" type="textarea" :rows="20" class="edit-area" />
        </el-tab-pane>
        <el-tab-pane label="数据库设计 SQL" name="sql">
          <el-input v-model="current.db_sql" type="textarea" :rows="20" class="edit-area sql" />
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="viewVisible = false">关闭</el-button>
        <el-button type="primary" plain @click="openChat">AI 对话</el-button>
        <el-button type="primary" :loading="saving" @click="saveDesign">保存修改</el-button>
      </template>
    </el-dialog>

    <!-- AI 对话 -->
    <el-dialog v-model="chatVisible" :title="`${current?.project_name || ''} - AI 对话`" width="78%" top="2vh" class="chat-dialog">
      <div class="chat-head">
        <el-select v-model="chat.role" style="width: 170px" size="small">
          <el-option label="架构师" value="architect" />
          <el-option label="资深全栈开发工程师" value="fullstack" />
        </el-select>
        <el-select v-model="chat.target" style="width: 170px; margin-left: 8px" size="small">
          <el-option label="架构概设文档" value="design_doc" />
          <el-option label="数据库 SQL" value="sql" />
        </el-select>
        <el-select v-model="chat.reqId" clearable filterable placeholder="参考需求文档（默认最新）" style="width: 220px; margin-left: 8px" size="small">
          <el-option v-for="r in requirements" :key="r.id" :label="`${r.title}${r.is_confirmed ? '（已入库）' : ''}`" :value="r.id" />
        </el-select>
        <el-button type="warning" plain size="small" style="margin-left: 8px" @click="expertReview">AI 专家评审</el-button>
      </div>

      <div class="chat-body">
        <template v-for="(m, i) in chat.messages" :key="i">
          <div :class="['msg', m.role === 'user' ? 'user' : 'assistant']">
            <div class="who">{{ m.role === 'user' ? '我' : 'AI' }}</div>
            <pre class="content">{{ m.content }}</pre>
          </div>
        </template>
      </div>

      <div class="chat-input">
        <el-input v-model="chat.input" type="textarea" :rows="2" placeholder="输入你的问题，例如：补充缓存设计；订单表增加索引…" @keydown.enter.prevent="sendChat" />
        <el-button type="primary" :loading="chat.sending" @click="sendChat">发送</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useProjectStore } from "../stores/project";
import { listRequirements } from "../api/requirements";
import { createArchitecture, deleteArchitecture, getChatHistory, listArchitecture, updateArchitecture } from "../api/architecture";
import { ingestKnowledge } from "../api/knowledge";

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const selectedProject = ref(null);
const designs = ref([]);
const requirements = ref([]);
const loading = ref(false);
const genVisible = ref(false);
const saving = ref(false);
const ingesting = ref(false);
const tab = ref("doc");
const current = ref(null);
const viewVisible = ref(false);
const docText = ref("");
const sqlText = ref("");
const streaming = reactive({ doc: false, sql: false });

const form = reactive({ project_id: null, frontend_stack: "", backend_stack: "", base_framework: "", db_type: "mysql" });

const chatVisible = ref(false);
const chat = reactive({ role: "architect", target: "design_doc", input: "", sending: false, messages: [], reqId: null });

const canGenerate = computed(() => selectedProject.value && selectedProject.value.status === "architecture");

async function loadProjects() {
  await projectStore.ensureLoaded();
  onProjectChange();
}

async function onProjectChange() {
  selectedProject.value = projects.value.find((p) => p.id === projectId.value) || null;
  load();
}

async function load() {
  if (!projectId.value) {
    designs.value = [];
    return;
  }
  loading.value = true;
  try {
    const { data } = await listArchitecture(projectId.value);
    designs.value = data;
  } finally {
    loading.value = false;
  }
}

function openGenerate() {
  form.project_id = projectId.value;
  form.frontend_stack = "";
  form.backend_stack = "";
  form.base_framework = "";
  form.db_type = "mysql";
  form.constraints = "";
  form.extra = "";
  docText.value = "";
  sqlText.value = "";
  streaming.doc = false;
  streaming.sql = false;
  genVisible.value = true;
}

// 流式生成
async function genStep(target) {
  if (target === "sql" && !docText.value) return ElMessage.warning("请先生成架构概设文档");
  streaming[target === "sql" ? "sql" : "doc"] = true;
  if (target === "sql") sqlText.value = "";
  else docText.value = "";
  try {
    const token = localStorage.getItem("access_token");
    const res = await fetch("/api/architecture/generate-stream/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...form, target }),
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
          if (evt.type === "chunk") {
            if (target === "sql") sqlText.value += evt.content;
            else docText.value += evt.content;
          } else if (evt.type === "error") {
            throw new Error(evt.message || "生成失败");
          }
        }
      }
    }
    ElMessage.success(target === "sql" ? "SQL 生成完成，可直接修改" : "架构文档生成完成");
  } catch (e) {
    ElMessage.error(e.message || "生成失败");
  } finally {
    streaming[target === "sql" ? "sql" : "doc"] = false;
  }
}

async function confirmSave() {
  if (!docText.value.trim()) return ElMessage.warning("请先生成架构概设文档");
  saving.value = true;
  try {
    const { data } = await createArchitecture({
      project: form.project_id,
      frontend_stack: form.frontend_stack,
      backend_stack: form.backend_stack,
      base_framework: form.base_framework,
      db_type: form.db_type,
      design_doc: docText.value,
      db_sql: sqlText.value,
    });
    ElMessage.success("架构设计已保存");
    genVisible.value = false;
    load();
    viewDesign(data);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

function viewDesign(row) {
  current.value = row;
  tab.value = "doc";
  viewVisible.value = true;
}

async function saveDesign() {
  if (!current.value) return;
  saving.value = true;
  try {
    const payload = tab.value === "sql" ? { db_sql: current.value.db_sql } : { design_doc: current.value.design_doc };
    const { data } = await updateArchitecture(current.value.id, payload);
    current.value = data;
    ElMessage.success("已保存");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function removeDesign(row) {
  try {
    await ElMessageBox.confirm("确定删除该架构设计？", "删除架构设计", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteArchitecture(row.id);
    ElMessage.success("已删除");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

// AI 对话
async function openChat() {
  chat.role = "architect";
  chat.target = tab.value === "sql" ? "sql" : "design_doc";
  chat.input = "";
  chat.messages = [];
  chatVisible.value = true;
  try {
    const { data } = await listRequirements(projectId.value);
    requirements.value = data;
    chat.reqId = data.length ? data[0].id : null; // 默认最新
  } catch {
    /* 忽略 */
  }
  try {
    const { data } = await getChatHistory(current.value.id);
    chat.messages = data.messages || [];
  } catch {
    /* 忽略 */
  }
}

async function sendChat() {
  const text = chat.input.trim();
  if (!text) return;
  await doChat({ prompt: text, expert: false });
}

async function expertReview() {
  await doChat({ prompt: "请作为该角色的评审专家，对当前设计进行专业评审，明确指出优点、存在的问题，并给出具体、可执行的修改意见。", expert: true });
}

async function doChat(payload) {
  chat.sending = true;
  chat.messages.push({ role: "user", content: payload.prompt });
  chat.input = "";
  const aiIndex = chat.messages.length;
  chat.messages.push({ role: "assistant", content: "" });
  try {
    const token = localStorage.getItem("access_token");
    const res = await fetch(`/api/architecture/${current.value.id}/chat-stream/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...payload, role: chat.role, target: chat.target, requirement_id: chat.reqId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "对话失败");
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
          if (evt.type === "chunk") {
            chat.messages[aiIndex].content += evt.content;
          } else if (evt.type === "error") {
            throw new Error(evt.message || "对话失败");
          }
        }
      }
    }
  } catch (e) {
    ElMessage.error(e.message || "对话失败");
  } finally {
    chat.sending = false;
  }
}

async function ingest() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  ingesting.value = true;
  try {
    const { data } = await ingestKnowledge({ project_id: projectId.value, kind: "architecture" });
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
.gen-dialog :deep(.el-dialog__body) {
  max-height: 76vh;
  overflow: auto;
}
.view-dialog :deep(.el-dialog__body) {
  max-height: 80vh;
  overflow: auto;
}
.chat-dialog :deep(.el-dialog__body) {
  max-height: 82vh;
  overflow: auto;
}
.step-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.edit-area {
  font-family: Consolas, Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.edit-area.sql {
  background: #0f172a;
  color: #e2e8f0;
}
.chat-head {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}
.chat-body {
  height: 460px;
  overflow: auto;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 10px;
  background: #fafafa;
}
.msg {
  margin-bottom: 10px;
}
.who {
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px;
}
.msg.user .content {
  background: #ecf5ff;
}
.content {
  white-space: pre-wrap;
  word-break: break-word;
  background: #fff;
  border-radius: 4px;
  padding: 8px;
  margin: 0;
  line-height: 1.6;
}
.chat-input {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  align-items: flex-end;
}
</style>
