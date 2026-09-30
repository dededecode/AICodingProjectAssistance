<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">知识库管理</h3>
        <div>
          <el-button type="success" :disabled="!projectId" @click="openQA">知识问答</el-button>
          <el-button type="danger" plain :disabled="!projectId" :loading="clearing" @click="clearAll">清空知识库</el-button>
        </div>
      </div>

      <el-input
        v-model="query"
        placeholder="输入检索内容，回车搜索项目知识库"
        clearable
        style="margin-top: 16px"
        @keyup.enter="doSearch"
        @clear="clearSearch"
      >
        <template #append>
          <el-button :loading="searching" @click="doSearch">搜索</el-button>
        </template>
      </el-input>

      <div class="meta-bar" v-if="projectId">
        <el-tag size="small" v-if="isSearching">检索结果</el-tag>
        <el-tag size="small" v-else type="info">全部知识（{{ count }} 条）</el-tag>
        <el-button size="small" text type="primary" @click="openAdd" v-if="!isSearching">新增知识</el-button>
      </div>

      <el-empty v-if="!projectId" description="请选择项目" />
      <template v-else>
        <el-table :data="displayList" v-loading="loading" stripe style="margin-top: 12px">
          <el-table-column label="知识内容" min-width="360">
            <template #default="{ row }">
              <div class="kb-cell">
                <div class="kb-text" :class="{ collapsed: !isExpanded(row.id) }">
                  <RichText :content="row.text" />
                </div>
                <el-button v-if="row.text && row.text.length > 120" size="small" text type="primary" class="expand-btn" @click="toggleExpand(row.id)">
                  {{ isExpanded(row.id) ? "收起" : "展开全文" }}
                </el-button>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="140">
            <template #default="{ row }">
              <el-tag :type="sourceType(row.metadata?.type)" size="small">
                {{ row.metadata?.type === "requirement" ? "需求文档" : "开发新增" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="相关度/距离" width="110" v-if="isSearching">
            <template #default="{ row }">
              {{ row.distance !== undefined ? row.distance.toFixed(4) : "-" }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button size="small" type="danger" text :disabled="!canDelete(row) || !hasBtn('btn:kb-delete')" @click="removeItem(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager" v-if="sourceList.length">
          <el-pagination background layout="total, prev, pager, next, sizes" :total="sourceList.length" v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" />
        </div>
      </template>
    </el-card>

    <!-- 新增知识 -->
    <el-dialog v-model="addVisible" title="新增知识" width="520px">
      <el-input v-model="addContent" type="textarea" :rows="6" placeholder="输入要加入项目知识库的内容（如设计决策、技术约定、关键实现细节）" />
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="doAdd">保存</el-button>
      </template>
    </el-dialog>

    <!-- 知识问答 -->
    <el-dialog v-model="qaVisible" title="知识问答 · 基于知识库" width="80%" top="3vh" class="qa-dialog">
      <div class="qa-layout">
        <div class="qa-side">
          <el-button type="primary" size="small" style="width: 100%; margin-bottom: 10px" @click="newSession">＋ 新会话</el-button>
          <div
            v-for="s in sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === currentSession?.id }"
            @click="switchSession(s)"
          >
            <span class="session-title">{{ s.title }}</span>
            <el-icon class="session-del" @click.stop="deleteSession(s)"><Close /></el-icon>
          </div>
        </div>
        <div class="qa-main">
          <div class="qa-body" ref="qaBodyRef">
            <div v-for="(m, i) in currentSession?.messages || []" :key="i" :class="['msg', m.role === 'user' ? 'user' : 'assistant']">
              <div class="who">{{ m.role === 'user' ? '我' : 'AI' }}</div>
              <pre class="content">{{ m.content }}</pre>
            </div>
            <div v-if="qaLoading" class="msg assistant"><div class="who">AI</div><div class="content">思考中…</div></div>
          </div>
          <div class="qa-input">
            <el-input v-model="qaInput" type="textarea" :rows="2" placeholder="输入问题，AI 将基于知识库回答" @keydown.enter.prevent="sendQA" />
            <el-button type="primary" :loading="qaLoading" @click="sendQA">发送</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Close } from "@element-plus/icons-vue";
import { useProjectStore } from "../stores/project";
import { addKnowledge, clearKnowledge, deleteKnowledgeItem, getAllKnowledge, searchKnowledge } from "../api/knowledge";
import RichText from "../components/RichText.vue";
import { hasPerm } from "../rbac";

const hasBtn = (code) => hasPerm(code);

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const loading = ref(false);
const query = ref("");
const allItems = ref([]);
const searchResults = ref([]);
const isSearching = ref(false);
const searching = ref(false);
const count = ref(0);
const page = ref(1);
const pageSize = ref(10);
const addVisible = ref(false);
const adding = ref(false);
const clearing = ref(false);
const addContent = ref("");

// 知识问答（会话存本地）
const qaVisible = ref(false);
const qaInput = ref("");
const qaLoading = ref(false);
const sessions = ref([]);
const currentSession = ref(null);
const qaBodyRef = ref();

const qaKey = () => `kb_qa_sessions_${projectId.value}`;

const sourceList = computed(() => (isSearching.value ? searchResults.value : allItems.value));
const displayList = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return sourceList.value.slice(start, start + pageSize.value);
});

// 知识卡片展开/收起
const expandedIds = ref([]);
function isExpanded(id) {
  return expandedIds.value.includes(id);
}
function toggleExpand(id) {
  const i = expandedIds.value.indexOf(id);
  if (i >= 0) expandedIds.value.splice(i, 1);
  else expandedIds.value.push(id);
}

async function loadProjects() {
  await projectStore.ensureLoaded();
}

async function loadAll() {
  if (!projectId.value) return;
  isSearching.value = false;
  page.value = 1;
  loading.value = true;
  try {
    const { data } = await getAllKnowledge(projectId.value);
    allItems.value = data.items || [];
    count.value = data.count || 0;
  } finally {
    loading.value = false;
  }
}

async function doSearch() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  if (!query.value.trim()) return clearSearch();
  searching.value = true;
  try {
    const { data } = await searchKnowledge({ project_id: projectId.value, query: query.value, top_k: 20 });
    searchResults.value = data.results || [];
    isSearching.value = true;
    page.value = 1;
  } finally {
    searching.value = false;
  }
}

function clearSearch() {
  query.value = "";
  isSearching.value = false;
  page.value = 1;
}

function openAdd() {
  addContent.value = "";
  addVisible.value = true;
}

async function doAdd() {
  if (!addContent.value.trim()) return ElMessage.warning("请输入内容");
  adding.value = true;
  try {
    await addKnowledge({ project_id: projectId.value, text: addContent.value });
    ElMessage.success("新增成功");
    addVisible.value = false;
    loadAll();
  } finally {
    adding.value = false;
  }
}

function sourceType(t) {
  return t === "requirement" ? "success" : "warning";
}

// 只有知识库新增/入库的知识（带 item_id）可删；需求初始知识仅存向量，无 DB 记录
function canDelete(row) {
  return row.metadata?.item_id != null;
}

async function removeItem(row) {
  try {
    await ElMessageBox.confirm("确定删除这条知识？删除后将从知识库与检索中移除。", "删除知识", { type: "warning" });
  } catch {
    return;
  }
  await deleteKnowledgeItem(row.metadata.item_id);
  ElMessage.success("已删除");
  clearSearch();
  await loadAll();
}

async function clearAll() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  try {
    await ElMessageBox.confirm(
      "将清空该项目的全部知识库数据（向量 + 条目），且不可恢复。切换 embedding 模型后需清空并重新入库。确定继续？",
      "清空知识库",
      { type: "warning", confirmButtonText: "确定清空" },
    );
  } catch {
    return;
  }
  clearing.value = true;
  try {
    const { data } = await clearKnowledge(projectId.value);
    ElMessage.success(`已清空知识库（条目 ${data.cleared_items ?? 0} 条）`);
    clearSearch();
    await loadAll();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "清空失败（可能无权限）");
  } finally {
    clearing.value = false;
  }
}

// ── 知识问答 ──
async function openQA() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  loadSessions();
  qaInput.value = "";
  qaVisible.value = true;
  scrollToBottom();
}

function loadSessions() {
  try {
    sessions.value = JSON.parse(localStorage.getItem(qaKey()) || "[]");
  } catch {
    sessions.value = [];
  }
  if (!sessions.value.length) sessions.value = [{ id: Date.now(), title: "新会话", messages: [] }];
  currentSession.value = sessions.value[sessions.value.length - 1];
}

function persist() {
  localStorage.setItem(qaKey(), JSON.stringify(sessions.value));
}

function newSession() {
  const s = { id: Date.now(), title: "新会话", messages: [] };
  sessions.value.push(s);
  currentSession.value = s;
  qaInput.value = "";
  persist();
}

function switchSession(s) {
  currentSession.value = s;
  qaInput.value = "";
  scrollToBottom();
}

async function deleteSession(s) {
  try {
    await ElMessageBox.confirm(`确定删除会话「${s.title}」？`, "删除会话", { type: "warning" });
  } catch {
    return;
  }
  const idx = sessions.value.indexOf(s);
  if (idx < 0) return;
  sessions.value.splice(idx, 1);
  if (currentSession.value?.id === s.id) {
    currentSession.value = sessions.value.length ? sessions.value[Math.max(0, idx - 1)] : null;
  }
  persist();
  if (!sessions.value.length) newSession(); // 删空后新建空会话
}

function scrollToBottom() {
  nextTick(() => {
    if (qaBodyRef.value) qaBodyRef.value.scrollTop = qaBodyRef.value.scrollHeight;
  });
}

async function sendQA() {
  const q = qaInput.value.trim();
  if (!q || !currentSession.value) return;
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  const before = currentSession.value.messages.length;
  currentSession.value.messages.push({ role: "user", content: q });
  if (currentSession.value.title === "新会话") currentSession.value.title = q.slice(0, 20);
  qaInput.value = "";
  persist();
  scrollToBottom();
  qaLoading.value = true;
  const aiIndex = currentSession.value.messages.length;
  currentSession.value.messages.push({ role: "assistant", content: "" });
  try {
    const token = localStorage.getItem("access_token");
    const history = currentSession.value.messages.slice(0, before).map((m) => ({ role: m.role, content: m.content }));
    const res = await fetch("/api/knowledge/qa-stream/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ project_id: projectId.value, question: q, history }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "回答失败");
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
            currentSession.value.messages[aiIndex].content += evt.content;
            scrollToBottom();
          } else if (evt.type === "error") {
            throw new Error(evt.message || "回答失败");
          }
        }
      }
    }
    persist();
    scrollToBottom();
  } catch (e) {
    ElMessage.error(e.message || "回答失败");
    persist();
  } finally {
    qaLoading.value = false;
  }
}

// 初始加载完成前，忽略全局项目切换（避免与首次加载重复请求）
let projectReady = false;
watch(projectId, () => {
  if (projectReady) loadAll();
});

onMounted(async () => {
  await loadProjects();
  await nextTick();
  projectReady = true;
  loadAll();
});
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.meta-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}
.kb-cell { position: relative; }
.kb-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}
.kb-text.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 6.2em;
}
.expand-btn {
  padding: 0;
  margin-top: 2px;
  height: auto;
}
.qa-dialog :deep(.el-dialog__body) {
  max-height: 82vh;
  overflow: hidden;
  padding: 12px;
}
.qa-layout {
  display: flex;
  gap: 12px;
  height: 72vh;
}
.qa-side {
  width: 180px;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 8px;
  overflow: auto;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  color: #475569;
  font-size: 13px;
  margin-bottom: 4px;
}
.session-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-item:hover { background: #f1f5f9; }
.session-item.active { background: #e0f2fe; color: #0284c7; }
.session-del {
  flex-shrink: 0;
  visibility: hidden;
  cursor: pointer;
  color: #94a3b8;
}
.session-item:hover .session-del { visibility: visible; }
.session-del:hover { color: #ef4444; }
.qa-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #eee;
  border-radius: 8px;
  overflow: hidden;
}
.qa-body {
  flex: 1;
  overflow: auto;
  padding: 10px;
  background: #fafafa;
}
.msg { margin-bottom: 10px; }
.who { font-size: 12px; color: #909399; margin-bottom: 2px; }
.msg.user .content { background: #ecf5ff; }
.content {
  white-space: pre-wrap;
  word-break: break-word;
  background: #fff;
  border-radius: 6px;
  padding: 8px;
  margin: 0;
  line-height: 1.6;
}
.qa-input {
  display: flex;
  gap: 8px;
  padding: 10px;
  align-items: flex-end;
  border-top: 1px solid #eee;
}
</style>
