<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">Wiki 知识库（LLM 编译）</h3>
        <div>
          <el-button type="success" :disabled="!projectId" @click="openQA">Wiki 问答</el-button>
          <el-button type="danger" plain :disabled="!projectId" :loading="clearing" @click="clearAll">清空 Wiki</el-button>
        </div>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-top: 12px"
        title="由 LLM 将需求 / 架构 / 计划 / 交付文档编译为结构化知识页（互相链接、可溯源），向量化存于独立 Wiki 库，与「知识库」检索互不影响。"
      />

      <template v-if="projectId">
        <!-- 源文档编译 -->
        <h4 class="section-title">源文档编译</h4>
        <el-table :data="sources" v-loading="sourcesLoading" stripe size="small">
          <el-table-column label="来源类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="sourceTagType(row.source_type)">{{ sourceTypeLabel(row.source_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag v-if="isCompiling(row)" type="warning" size="small">编译中…</el-tag>
              <el-tag v-else-if="row.stale" type="warning" size="small">已过期</el-tag>
              <el-tag v-else-if="row.compiled" type="success" size="small">已编译</el-tag>
              <el-tag v-else type="info" size="small">未编译</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="页面数" width="80">
            <template #default="{ row }">{{ row.compiled ? row.page_count : "-" }}</template>
          </el-table-column>
          <el-table-column label="最近编译" width="160">
            <template #default="{ row }">{{ row.compiled ? formatTime(row.compiled_at) : "-" }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button v-if="isCompiling(row)" size="small" type="danger" plain @click="cancelCompile(row)">
                取消
              </el-button>
              <el-button
                v-else
                size="small"
                type="primary"
                :disabled="!row.has_content"
                @click="compile(row)"
              >
                {{ row.compiled ? "重新编译" : "编译" }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- Wiki 页面浏览 -->
        <h4 class="section-title">Wiki 页面（{{ pages.length }} 页）</h4>
        <div class="filter-bar">
          <el-select v-model="pageType" placeholder="页面类型" clearable style="width: 150px" @change="loadPages">
            <el-option v-for="o in pageTypeOpts" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="按标题/内容搜索"
            clearable
            style="width: 240px"
            @keyup.enter="loadPages"
            @clear="loadPages"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button :loading="pagesLoading" @click="loadPages">搜索</el-button>
        </div>
        <el-table :data="pagedPages" v-loading="pagesLoading" stripe style="margin-top: 12px">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="标题" min-width="220">
            <template #default="{ row }">
              <el-link type="primary" @click="openPage(row)">{{ row.title }}</el-link>
            </template>
          </el-table-column>
          <el-table-column label="页面类型" width="110">
            <template #default="{ row }">
              <el-tag size="small">{{ row.page_type_display }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ sourceTypeLabel(row.source_type) }} · {{ row.source_title }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="160">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button size="small" type="primary" text @click="openPage(row)">查看</el-button>
              <el-button size="small" type="danger" text @click="removePage(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager" v-if="pages.length">
          <el-pagination
            background
            layout="total, prev, pager, next, sizes"
            :total="pages.length"
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
          />
        </div>
      </template>
      <el-empty v-else description="请选择项目" style="margin-top: 20px" />
    </el-card>

    <!-- 页面详情 -->
    <el-dialog v-model="pageVisible" :title="viewPage?.title || 'Wiki 页面'" width="70%" top="4vh">
      <template v-if="viewPage">
        <div class="page-meta">
          <el-tag size="small">{{ viewPage.page_type_display }}</el-tag>
          <el-tag size="small" type="info">{{ sourceTypeLabel(viewPage.source_type) }} · {{ viewPage.source_title }}</el-tag>
          <span class="meta-time">更新于 {{ formatTime(viewPage.updated_at) }}</span>
        </div>
        <div class="page-body"><RichText :content="viewPage.content" /></div>
        <div class="page-links" v-if="viewPage.links?.length">
          <span class="links-label">关联页面：</span>
          <el-tag
            v-for="l in viewPage.links"
            :key="l"
            size="small"
            class="link-tag"
            @click="jumpToPage(l)"
          >
            {{ l }}
          </el-tag>
        </div>
        <div class="page-links" v-if="viewPage.sources?.length">
          <span class="links-label">来源引用：</span>
          <el-tag v-for="s in viewPage.sources" :key="s" size="small" type="info" class="link-tag">{{ s }}</el-tag>
        </div>
      </template>
    </el-dialog>

    <!-- Wiki 问答 -->
    <el-dialog v-model="qaVisible" title="Wiki 问答 · 基于 LLM 编译知识页" width="80%" top="3vh" class="qa-dialog">
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
            <el-input v-model="qaInput" type="textarea" :rows="2" placeholder="输入问题，AI 将基于 Wiki 页面回答" @keydown.enter.prevent="sendQA" />
            <el-button type="primary" :loading="qaLoading" @click="sendQA">发送</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Close, Search } from "@element-plus/icons-vue";
import { useProjectStore } from "../stores/project";
import { clearWiki, cancelWikiCompile, compileWiki, deleteWikiPage, getCompileStatus, listWikiPages, listWikiSources } from "../api/wiki";
import RichText from "../components/RichText.vue";

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});

// 源文档
const sources = ref([]);
const sourcesLoading = ref(false);
// 编译为异步任务：轮询 compile-status 直到结束
const compileLogs = ref([]);
const pendingLogs = ref(new Set());
let pollTimer = null;

// Wiki 页面
const pages = ref([]);
const pagesLoading = ref(false);
const keyword = ref("");
const pageType = ref("");
const page = ref(1);
const pageSize = ref(10);
const pageVisible = ref(false);
const viewPage = ref(null);
const clearing = ref(false);

const pageTypeOpts = [
  { value: "overview", label: "总览" },
  { value: "module", label: "业务模块" },
  { value: "entity", label: "实体/概念" },
  { value: "table", label: "数据表" },
  { value: "api", label: "接口" },
  { value: "timeline", label: "时间线" },
  { value: "synthesis", label: "综合分析" },
];
const sourceTypeMap = {
  requirement: "需求文档",
  architecture: "架构设计",
  plan: "项目计划",
  delivery: "交付文档",
};

const pagedPages = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return pages.value.slice(start, start + pageSize.value);
});

function sourceTypeLabel(t) {
  return sourceTypeMap[t] || t;
}
function sourceTagType(t) {
  return { requirement: "success", architecture: "primary", plan: "warning", delivery: "info" }[t] || "info";
}
function formatTime(t) {
  return t ? new Date(t).toLocaleString() : "";
}

async function loadProjects() {
  await projectStore.ensureLoaded();
  onProjectChange();
}

function onProjectChange() {
  stopPolling();
  pendingLogs.value = new Set();
  compileLogs.value = [];
  page.value = 1;
  keyword.value = "";
  pageType.value = "";
  if (projectId.value) reload();
  else {
    sources.value = [];
    pages.value = [];
  }
}

async function reload() {
  await Promise.all([loadSources(), loadPages()]);
  checkCompile(); // 恢复进行中的编译轮询（页面刷新后也能接上）
}

async function loadSources() {
  if (!projectId.value) return;
  sourcesLoading.value = true;
  try {
    const { data } = await listWikiSources(projectId.value);
    sources.value = data.items || [];
  } finally {
    sourcesLoading.value = false;
  }
}

async function loadPages() {
  if (!projectId.value) return;
  pagesLoading.value = true;
  page.value = 1;
  try {
    const { data } = await listWikiPages(projectId.value, {
      keyword: keyword.value || undefined,
      page_type: pageType.value || undefined,
    });
    pages.value = data || [];
  } finally {
    pagesLoading.value = false;
  }
}

function isCompiling(row) {
  return compileLogs.value.some(
    (l) => l.status === "running" && l.source_type === row.source_type && l.source_id === row.source_id,
  );
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(checkCompile, 10000);
}

async function checkCompile() {
  if (!projectId.value) return stopPolling();
  try {
    const { data } = await getCompileStatus(projectId.value);
    const logs = data.logs || [];
    const prev = Object.fromEntries(compileLogs.value.map((l) => [l.id, l.status]));
    compileLogs.value = logs;
    let needReload = false;
    for (const l of logs) {
      if (prev[l.id] !== undefined && prev[l.id] !== l.status) needReload = true;
      if (!pendingLogs.value.has(l.id)) continue;
      if (l.status === "success") {
        ElMessage.success(`编译完成：「${l.source_title}」生成 ${l.page_count} 个页面（${(l.duration_ms / 1000).toFixed(1)}s）`);
        if (l.meta?.truncated) ElMessage.warning("源文档超过 30000 字符，超出部分未编译，建议拆分文档后分批编译");
        if (l.meta?.partial_output) ElMessage.warning("模型输出被截断，已保留可解析的完整页面；建议重试编译以获得更完整的结果");
        pendingLogs.value.delete(l.id);
      } else if (l.status === "failed") {
        ElMessage.error(`编译失败：「${l.source_title}」${(l.error || "").slice(0, 150)}`);
        pendingLogs.value.delete(l.id);
      }
    }
    if (logs.some((l) => l.status === "running")) {
      if (!pollTimer) startPolling();
    } else {
      stopPolling();
      if (needReload) await reload();
    }
  } catch {
    /* 轮询失败下次再试 */
  }
}

async function cancelCompile(row) {
  try {
    await ElMessageBox.confirm(
      "将取消该来源正在进行的编译任务（已完成的部分会被丢弃，可重新编译）。确定取消？",
      "取消编译",
      { type: "warning" },
    );
  } catch {
    return;
  }
  try {
    await cancelWikiCompile({
      project_id: projectId.value,
      source_type: row.source_type,
      source_id: row.source_id,
    });
    ElMessage.success("已取消编译");
    for (const l of compileLogs.value) {
      if (l.status === "running" && l.source_type === row.source_type && l.source_id === row.source_id) {
        pendingLogs.value.delete(l.id);
      }
    }
    await checkCompile();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "取消失败");
  }
}

async function compile(row) {
  if (row.compiled) {
    try {
      await ElMessageBox.confirm(
        `将重新编译「${row.title}」：该来源现有 Wiki 页面会被覆盖重建。确定继续？`,
        "重新编译",
        { type: "warning" },
      );
    } catch {
      return;
    }
  }
  try {
    const { data } = await compileWiki({
      project_id: projectId.value,
      source_type: row.source_type,
      source_id: row.source_id,
    });
    pendingLogs.value.add(data.log_id);
    ElMessage.info("编译任务已启动，正在后台执行（大文档可能需要几分钟），完成后会自动提示");
    compileLogs.value = [{ id: data.log_id, status: "running", source_type: row.source_type, source_id: row.source_id, source_title: row.title }, ...compileLogs.value];
    startPolling();
  } catch (e) {
    if (e.response?.status === 409) {
      ElMessage.info(e.response.data?.detail || "该来源正在编译中");
      if (e.response.data?.log_id) {
        pendingLogs.value.add(e.response.data.log_id);
        startPolling();
      }
    } else {
      ElMessage.error(e.response?.data?.detail || "启动编译失败");
    }
  }
}

function openPage(row) {
  viewPage.value = row;
  pageVisible.value = true;
}

function jumpToPage(title) {
  const target = pages.value.find((p) => p.title === title);
  if (target) {
    viewPage.value = target;
  } else {
    ElMessage.info(`页面「${title}」不在当前列表中，请清空筛选后查找`);
  }
}

async function removePage(row) {
  try {
    await ElMessageBox.confirm(`确定删除页面「${row.title}」？删除后 Wiki 检索中将不再包含该页。`, "删除页面", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteWikiPage(row.id);
    ElMessage.success("已删除");
    await loadPages();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

async function clearAll() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  try {
    await ElMessageBox.confirm(
      "将清空该项目的全部 Wiki（页面 + 向量），且不影响知识库。确定继续？",
      "清空 Wiki",
      { type: "warning", confirmButtonText: "确定清空" },
    );
  } catch {
    return;
  }
  clearing.value = true;
  try {
    const { data } = await clearWiki(projectId.value);
    ElMessage.success(`已清空 Wiki（页面 ${data.cleared_pages ?? 0} 个）`);
    await reload();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "清空失败（可能无权限）");
  } finally {
    clearing.value = false;
  }
}

// ── Wiki 问答（会话存本地，独立于知识库问答） ──
const qaVisible = ref(false);
const qaInput = ref("");
const qaLoading = ref(false);
const sessions = ref([]);
const currentSession = ref(null);
const qaBodyRef = ref();

const qaKey = () => `wiki_qa_sessions_${projectId.value}`;

function openQA() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  if (!pages.value.length) return ElMessage.warning("当前项目尚未编译任何 Wiki 页面，请先在「源文档编译」中编译");
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
  if (!sessions.value.length) newSession();
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
    const res = await fetch("/api/wiki/qa-stream/", {
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
  if (projectReady) onProjectChange();
});

onMounted(async () => {
  await loadProjects();
  await nextTick();
  projectReady = true;
});
onUnmounted(stopPolling);
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  margin: 20px 0 10px;
  color: #303133;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}
.page-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.meta-time {
  font-size: 12px;
  color: #909399;
}
.page-body {
  max-height: 58vh;
  overflow: auto;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 12px;
  background: #fafafa;
}
.page-links {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.links-label {
  font-size: 13px;
  color: #606266;
}
.link-tag {
  cursor: pointer;
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
