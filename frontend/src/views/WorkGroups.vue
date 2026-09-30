<template>
  <div class="work-groups">
    <!-- 左侧：群列表 -->
    <el-card shadow="never" class="left-panel">
      <div class="panel-toolbar">
        <span class="panel-title">工作群</span>
        <el-button size="small" type="primary" @click="openCreate">新建群</el-button>
      </div>
      <el-button type="warning" size="small" style="width: 100%" :loading="creatingDefault" @click="defaultVisible = true">
        一键创建默认开发工作群
      </el-button>
      <div v-loading="loadingGroups" class="group-list">
        <div
          v-for="g in groups"
          :key="g.id"
          class="group-item"
          :class="{ active: current && current.id === g.id, dismissed: g.status === 'dismissed' }"
          @click="selectGroup(g)"
        >
          <div class="group-name">{{ g.name }} <el-tag v-if="g.status === 'dismissed'" size="small" type="danger" style="margin-left: 4px">已解散</el-tag></div>
          <div class="group-meta">#{{ g.id }} · {{ g.project_name }} · {{ (g.members || []).length }}人</div>
        </div>
        <el-empty v-if="!groups.length && !loadingGroups" description="暂无工作群" :image-size="60" />
      </div>
    </el-card>

    <!-- 右侧：群聊 -->
    <el-card v-if="current" shadow="never" class="chat-panel">
      <div class="chat-header">
        <div>
          <span class="chat-title">{{ current.name }} <span style="font-size: 12px; color: #909399; font-weight: 400">#{{ current.id }}</span></span>
          <el-tag size="small" type="info" style="margin-left: 8px">{{ current.project_name }}</el-tag>
          <el-tag v-if="current.status === 'dismissed'" size="small" type="danger" style="margin-left: 4px">已解散</el-tag>
        </div>
        <div>
          <el-button size="small" type="success" :loading="summarizing" @click="doSummarize">群总结</el-button>
          <el-button size="small" @click="showPrompt('dev')">开发任务提示词</el-button>
          <el-button size="small" @click="showPrompt('test')">测试任务提示词</el-button>
          <el-button size="small" type="primary" plain @click="openSettings">群设置</el-button>
          <el-button v-if="hasBtn('btn:workgroup-dismiss') && current.status === 'active'" size="small" type="danger" @click="doDismiss">解散群</el-button>
          <el-button v-if="hasBtn('btn:workgroup-delete') && current.status === 'dismissed'" size="small" type="danger" plain @click="doHardDelete">彻底删除</el-button>
        </div>
      </div>

      <div ref="messageBox" v-loading="loadingMessages" class="message-list">
        <div v-for="m in messages" :key="m.id" class="message-item">
          <div class="message-head">
            <span class="message-sender">{{ m.sender_name }}</span>
            <span class="message-time">{{ formatTime(m.created_at) }}</span>
          </div>
          <div class="message-content">{{ m.content }}</div>
        </div>
        <el-empty v-if="!messages.length && !loadingMessages" description="暂无消息，在下方输入第一条消息吧" :image-size="60" />
      </div>

      <div class="chat-input" v-if="current.status !== 'dismissed'">
        <div class="input-toolbar">
          <span class="identity-label">发言身份：</span>
          <el-select v-model="senderId" size="small" style="width: 160px">
            <el-option v-for="m in current.members" :key="m.user" :label="m.username" :value="m.user" />
          </el-select>
          <span class="tip">切换身份可模拟不同 agent 发言</span>
        </div>
        <div class="input-row">
          <el-input
            v-model="draft"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="输入 agent 的总结和回复…（Ctrl+Enter 发送）"
            @keydown.ctrl.enter="send"
          />
          <el-button type="primary" :loading="sending" @click="send">发送</el-button>
        </div>
      </div>
      <div class="chat-input" v-else>
        <el-alert type="warning" :closable="false" title="该群已解散，仅供查看历史消息" />
      </div>
    </el-card>

    <el-card v-else shadow="never" class="chat-panel">
      <el-empty description="选择或创建一个工作群" />
    </el-card>

    <!-- 新建群 -->
    <el-dialog v-model="createVisible" title="新建工作群" width="640px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="所属项目">
          <el-select v-model="form.project" filterable style="width: 100%" @change="form.members = []">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="群名称"><el-input v-model="form.name" placeholder="如：开发工作群" /></el-form-item>
        <el-form-item label="工作流程定义">
          <el-input v-model="form.workflow_desc" type="textarea" :rows="4" placeholder="用一段话描述该群的工作流程…" />
        </el-form-item>
        <el-form-item label="开发任务提示词">
          <el-input v-model="form.dev_task_prompt" type="textarea" :rows="4" placeholder="开发任务开始时的通用提示词（复制给开发 agent 触发任务）" />
        </el-form-item>
        <el-form-item label="测试任务提示词">
          <el-input v-model="form.test_task_prompt" type="textarea" :rows="4" placeholder="测试任务开始时的通用提示词（复制给测试 agent 触发任务）" />
        </el-form-item>
        <el-form-item label="群成员">
          <el-select v-model="form.members" multiple filterable style="width: 100%" placeholder="从所选项目成员中选择">
            <el-option v-for="m in projectMembers" :key="m.id" :label="m.username" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 一键默认群：选项目 -->
    <el-dialog v-model="defaultVisible" title="创建默认开发工作群" width="420px">
      <el-form label-width="90px">
        <el-form-item label="选择项目">
          <el-select v-model="defaultProjectId" filterable style="width: 100%" placeholder="选择项目">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        title="将自动创建「开发工作群」：预置工作流程、开发/测试任务开始通用提示词，项目所有成员自动入群。"
      />
      <template #footer>
        <el-button @click="defaultVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingDefault" :disabled="!defaultProjectId" @click="doCreateDefault">创建</el-button>
      </template>
    </el-dialog>

    <!-- 群设置 -->
    <el-dialog v-model="settingsVisible" title="群设置" width="640px">
      <el-alert v-if="current?.status === 'dismissed'" type="warning" :closable="false" title="该群已解散，仅可查看，不可编辑/变更成员" style="margin-bottom: 12px" />
      <el-form :model="settingsForm" label-width="120px">
        <el-form-item label="群名称"><el-input v-model="settingsForm.name" :disabled="current?.status === 'dismissed'" /></el-form-item>
        <el-form-item label="工作流程定义"><el-input v-model="settingsForm.workflow_desc" type="textarea" :rows="5" :disabled="current?.status === 'dismissed'" /></el-form-item>
        <el-form-item label="开发任务提示词"><el-input v-model="settingsForm.dev_task_prompt" type="textarea" :rows="5" :disabled="current?.status === 'dismissed'" /></el-form-item>
        <el-form-item label="测试任务提示词"><el-input v-model="settingsForm.test_task_prompt" type="textarea" :rows="5" :disabled="current?.status === 'dismissed'" /></el-form-item>
        <el-form-item label="群成员">
          <div class="member-manage">
            <el-tag
              v-for="m in current?.members || []"
              :key="m.user"
              :closable="current?.status !== 'dismissed'"
              style="margin: 0 6px 6px 0"
              @close="doRemoveMember(m)"
            >
              {{ m.username }}
            </el-tag>
          </div>
          <div style="display: flex; gap: 8px">
            <el-select v-model="memberToAdd" filterable placeholder="添加项目成员" size="small" style="width: 200px" :disabled="current?.status === 'dismissed'">
              <el-option v-for="u in addableMembers" :key="u.id" :label="u.username" :value="u.id" />
            </el-select>
            <el-button size="small" type="primary" plain :disabled="!memberToAdd || current?.status === 'dismissed'" @click="doAddMember">添加</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button
          v-if="current?.status === 'active' || hasBtn('btn:workgroup-message')"
          type="danger"
          plain
          @click="current?.status === 'dismissed' ? doHardDelete() : doDeleteGroup()"
        >
          {{ current?.status === 'dismissed' ? '彻底删除' : '删除群' }}
        </el-button>
        <el-button @click="settingsVisible = false">取消</el-button>
        <el-button type="primary" :disabled="current?.status === 'dismissed'" :loading="saving" @click="saveSettings">保存</el-button>
      </template>
    </el-dialog>

    <!-- 群总结 -->
    <el-dialog v-model="summaryVisible" title="群内容总结（项目历程与改进建议）" width="680px" top="5vh">
      <div v-loading="summarizing" style="min-height: 120px">
        <el-input v-model="summaryContent" type="textarea" :rows="20" readonly placeholder="点击「群总结」按钮生成…" />
      </div>
      <template #footer>
        <el-button @click="summaryVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="!summaryContent" @click="copySummary">复制总结</el-button>
      </template>
    </el-dialog>

    <!-- 提示词查看/复制 -->
    <el-dialog
      v-model="promptVisible"
      :title="promptType === 'dev' ? '开发任务开始通用提示词' : '测试任务开始通用提示词'"
      width="640px"
    >
      <el-input :model-value="promptContent" type="textarea" :rows="14" readonly />
      <template #footer>
        <el-button @click="promptVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyPrompt">复制提示词</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listProjects } from "../api/projects";
import { hasPerm } from "../rbac";
import {
  addWorkGroupMember,
  createDefaultWorkGroup,
  createWorkGroup,
  deleteWorkGroup,
  dismissWorkGroup,
  listGroupMessages,
  listWorkGroups,
  removeWorkGroupMember,
  sendGroupMessage,
  summarizeWorkGroup,
  updateWorkGroup,
} from "../api/workGroups";

const hasBtn = (code) => hasPerm(code);

const projects = ref([]);
const groups = ref([]);
const current = ref(null);
const messages = ref([]);
const loadingGroups = ref(false);
const loadingMessages = ref(false);
const messageBox = ref(null);

const me = JSON.parse(localStorage.getItem("user") || "{}");
const senderId = ref(me.id || null);

const createVisible = ref(false);
const creating = ref(false);
const defaultVisible = ref(false);
const defaultProjectId = ref(null);
const creatingDefault = ref(false);
const settingsVisible = ref(false);
const saving = ref(false);
const memberToAdd = ref(null);
const promptVisible = ref(false);
const promptType = ref("dev");
const summaryVisible = ref(false);
const summaryContent = ref("");
const summarizing = ref(false);
const draft = ref("");
const sending = ref(false);

const form = reactive({ project: null, name: "", workflow_desc: "", dev_task_prompt: "", test_task_prompt: "", members: [] });
const settingsForm = reactive({ name: "", workflow_desc: "", dev_task_prompt: "", test_task_prompt: "" });

let pollTimer = null;

const projectMembers = computed(() => projects.value.find((p) => p.id === form.project)?.members || []);
const addableMembers = computed(() => {
  const inGroup = new Set((current.value?.members || []).map((m) => m.user));
  const project = projects.value.find((p) => p.id === current.value?.project);
  return (project?.members || []).filter((m) => !inGroup.has(m.id));
});
const promptContent = computed(
  () => (promptType.value === "dev" ? current.value?.dev_task_prompt : current.value?.test_task_prompt) || ""
);

async function loadProjects() {
  const { data } = await listProjects();
  projects.value = data;
}

async function loadGroups() {
  loadingGroups.value = true;
  try {
    const { data } = await listWorkGroups();
    groups.value = data;
    if (current.value) {
      current.value = data.find((g) => g.id === current.value.id) || data[0] || null;
    } else {
      current.value = data[0] || null;
    }
    if (current.value) {
      loadMessages();
    } else {
      messages.value = [];
    }
  } finally {
    loadingGroups.value = false;
  }
}

function selectGroup(g) {
  if (current.value?.id === g.id) return;
  current.value = g;
  draft.value = "";
  loadMessages();
}

async function loadMessages(silent = false) {
  if (!current.value) return;
  if (!silent) loadingMessages.value = true;
  try {
    const { data } = await listGroupMessages(current.value.id);
    messages.value = data;
    scrollBottom();
  } finally {
    if (!silent) loadingMessages.value = false;
  }
}

function scrollBottom() {
  nextTick(() => {
    if (messageBox.value) messageBox.value.scrollTop = messageBox.value.scrollHeight;
  });
}

async function send() {
  if (!draft.value.trim()) return ElMessage.warning("请输入消息内容");
  sending.value = true;
  try {
    await sendGroupMessage(current.value.id, { content: draft.value, sender_id: senderId.value });
    draft.value = "";
    await loadMessages(true);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "发送失败");
  } finally {
    sending.value = false;
  }
}

function openCreate() {
  Object.assign(form, { project: null, name: "", workflow_desc: "", dev_task_prompt: "", test_task_prompt: "", members: [] });
  createVisible.value = true;
}

async function doCreate() {
  if (!form.project) return ElMessage.warning("请选择所属项目");
  if (!form.name.trim()) return ElMessage.warning("请输入群名称");
  creating.value = true;
  try {
    const { data } = await createWorkGroup({
      project: form.project,
      name: form.name,
      workflow_desc: form.workflow_desc,
      dev_task_prompt: form.dev_task_prompt,
      test_task_prompt: form.test_task_prompt,
    });
    if (form.members.length) {
      await Promise.all(form.members.map((uid) => addWorkGroupMember(data.id, uid)));
    }
    ElMessage.success("工作群已创建");
    createVisible.value = false;
    current.value = null;
    await loadGroups();
    const g = groups.value.find((x) => x.id === data.id);
    if (g) selectGroup(g);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "创建失败");
  } finally {
    creating.value = false;
  }
}

async function doCreateDefault() {
  creatingDefault.value = true;
  try {
    const { data } = await createDefaultWorkGroup(defaultProjectId.value);
    ElMessage.success(`「${data.name}」已就绪`);
    defaultVisible.value = false;
    current.value = null;
    await loadGroups();
    const g = groups.value.find((x) => x.id === data.id);
    if (g) selectGroup(g);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "创建失败");
  } finally {
    creatingDefault.value = false;
  }
}

function openSettings() {
  Object.assign(settingsForm, {
    name: current.value.name,
    workflow_desc: current.value.workflow_desc,
    dev_task_prompt: current.value.dev_task_prompt,
    test_task_prompt: current.value.test_task_prompt,
  });
  memberToAdd.value = null;
  settingsVisible.value = true;
}

async function saveSettings() {
  if (!settingsForm.name.trim()) return ElMessage.warning("请输入群名称");
  saving.value = true;
  try {
    const { data } = await updateWorkGroup(current.value.id, { ...settingsForm });
    current.value = data;
    const idx = groups.value.findIndex((g) => g.id === data.id);
    if (idx >= 0) groups.value[idx] = data;
    ElMessage.success("已保存");
    settingsVisible.value = false;
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function doAddMember() {
  try {
    const { data } = await addWorkGroupMember(current.value.id, memberToAdd.value);
    current.value = data;
    const idx = groups.value.findIndex((g) => g.id === data.id);
    if (idx >= 0) groups.value[idx] = data;
    memberToAdd.value = null;
    ElMessage.success("成员已添加");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "添加失败");
  }
}

async function doRemoveMember(m) {
  try {
    const { data } = await removeWorkGroupMember(current.value.id, m.user);
    current.value = data;
    const idx = groups.value.findIndex((g) => g.id === data.id);
    if (idx >= 0) groups.value[idx] = data;
    if (senderId.value === m.user) senderId.value = me.id || null;
    ElMessage.success("成员已移除");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "移除失败");
  }
}

async function doDeleteGroup() {
  try {
    await ElMessageBox.confirm(`确定删除工作群「${current.value.name}」？群消息将一并删除。`, "删除工作群", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteWorkGroup(current.value.id);
    ElMessage.success("已删除");
    settingsVisible.value = false;
    current.value = null;
    loadGroups();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

async function doDismiss() {
  try {
    await ElMessageBox.confirm(
      `确定解散工作群「${current.value.name}」？解散后群与历史消息保留，但所有成员无法再发言或编辑群。`,
      "解散工作群",
      { type: "warning", confirmButtonText: "确认解散", confirmButtonClass: "el-button--danger" }
    );
  } catch {
    return;
  }
  try {
    const { data } = await dismissWorkGroup(current.value.id);
    current.value = data;
    const idx = groups.value.findIndex((g) => g.id === data.id);
    if (idx >= 0) groups.value[idx] = data;
    settingsVisible.value = false;
    ElMessage.success("工作群已解散");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "解散失败");
  }
}

async function doHardDelete() {
  try {
    await ElMessageBox.confirm(
      `彻底删除群「${current.value.name}」？群及其全部消息将永久删除，无法恢复！`,
      "彻底删除群",
      { type: "error", confirmButtonText: "彻底删除", confirmButtonClass: "el-button--danger" }
    );
  } catch {
    return;
  }
  try {
    await deleteWorkGroup(current.value.id);
    ElMessage.success("群已彻底删除");
    settingsVisible.value = false;
    current.value = null;
    loadGroups();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

function showPrompt(type) {
  promptType.value = type;
  promptVisible.value = true;
}

async function doSummarize() {
  summarizing.value = true;
  summaryVisible.value = true;
  summaryContent.value = "";
  try {
    const { data } = await summarizeWorkGroup(current.value.id);
    summaryContent.value = data.content || "";
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "AI 总结失败");
    summaryVisible.value = false;
  } finally {
    summarizing.value = false;
  }
}

async function copySummary() {
  try {
    await navigator.clipboard.writeText(summaryContent.value);
    ElMessage.success("已复制到剪贴板");
  } catch {
    ElMessage.warning("复制失败，请手动选中文本复制");
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(promptContent.value);
    ElMessage.success("已复制到剪贴板");
  } catch {
    ElMessage.warning("复制失败，请手动选中文本复制");
  }
}

function formatTime(t) {
  return t ? t.slice(0, 16).replace("T", " ") : "";
}

onMounted(async () => {
  await loadProjects();
  await loadGroups();
  // 轻量轮询，便于后续 agent 自动发言时实时看到消息
  pollTimer = setInterval(() => {
    if (current.value && !document.hidden) loadMessages(true);
  }, 5000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<style scoped>
.work-groups {
  display: flex;
  gap: 12px;
  height: calc(100vh - 130px);
  min-height: 520px;
}
.left-panel {
  width: 280px;
  flex-shrink: 0;
}
.left-panel :deep(.el-card__body),
.chat-panel :deep(.el-card__body) {
  height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.panel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title {
  font-weight: 600;
}
.group-list {
  flex: 1;
  overflow-y: auto;
  margin-top: 8px;
}
.group-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}
.group-item:hover {
  background: #f5f7fa;
}
.group-item.active {
  background: #ecf5ff;
}
.group-item.dismissed {
  opacity: 0.65;
}
.group-name {
  font-weight: 600;
  font-size: 14px;
}
.group-meta {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.chat-panel {
  flex: 1;
  min-width: 0;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.chat-title {
  font-weight: 600;
  font-size: 16px;
}
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 4px;
}
.message-item {
  margin-bottom: 12px;
}
.message-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.message-sender {
  font-weight: 600;
  font-size: 13px;
  color: #409eff;
}
.message-time {
  font-size: 12px;
  color: #c0c4cc;
}
.message-content {
  margin-top: 4px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
}
.chat-input {
  border-top: 1px solid #ebeef5;
  padding-top: 8px;
}
.input-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.identity-label {
  font-size: 13px;
  color: #606266;
}
.tip {
  font-size: 12px;
  color: #c0c4cc;
}
.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.member-manage {
  line-height: 1.6;
}
</style>
