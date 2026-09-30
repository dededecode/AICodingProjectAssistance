<template>
  <div v-loading="loading">
    <el-card shadow="never">
      <div class="head">
        <div>
          <h3 style="margin: 0">{{ project.name }}</h3>
          <p style="color: #666; margin-top: 6px">{{ project.description }}</p>
        </div>
        <div class="head-actions">
          <el-tag :type="statusType(project.status)" size="large">{{ project.status_display }}</el-tag>
          <el-button size="small" type="success" @click="goRequirements">需求分析</el-button>
          <el-button size="small" type="warning" v-if="canManage && hasBtn('btn:project-status')" @click="openStatus">变更状态</el-button>
          <el-button size="small" @click="goBack">返回</el-button>
        </div>
      </div>
      <el-descriptions :column="3" border style="margin-top: 16px">
        <el-descriptions-item label="负责人">{{ project.owner_name }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(project.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="成员数">{{ project.members?.length || 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 成员管理 -->
    <el-card shadow="never" style="margin-top: 16px">
      <div class="toolbar">
        <h4 style="margin: 0">项目成员</h4>
        <el-button type="primary" size="small" v-if="canManage && hasBtn('btn:project-invite')" @click="openInvite">邀请成员</el-button>
      </div>
      <el-table :data="project.members || []" stripe style="margin-top: 12px">
        <el-table-column prop="username" label="用户名" />
        <el-table-column label="角色" width="140">
          <template #default="{ row }">{{ row.role_display }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" v-if="canManage && hasBtn('btn:project-remove-member')">
          <template #default="{ row }">
            <el-button size="small" type="danger" text :disabled="row.id === project.owner" @click="handleRemove(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 邀请成员 -->
    <el-dialog v-model="inviteVisible" title="邀请成员" width="460px">
      <el-form label-width="70px">
        <el-form-item label="成员">
          <el-select v-model="inviteForm.user_id" filterable remote :remote-method="searchUsers" placeholder="输入用户名搜索" style="width: 100%">
            <el-option v-for="u in userOptions" :key="u.id" :label="`${u.username}（${u.role}）`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="inviteForm.role" style="width: 100%">
            <el-option label="项目经理" value="manager" />
            <el-option label="开发" value="developer" />
            <el-option label="测试" value="tester" />
            <el-option label="访客" value="guest" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inviteVisible = false">取消</el-button>
        <el-button type="primary" :loading="inviting" @click="handleInvite">确定</el-button>
      </template>
    </el-dialog>

    <!-- 变更状态 -->
    <el-dialog v-model="statusVisible" title="变更项目状态" width="400px">
      <el-select v-model="statusForm.status" style="width: 100%">
        <el-option label="需求分析" value="requirement" />
        <el-option label="项目计划" value="planning" />
        <el-option label="架构设计" value="architecture" />
        <el-option label="开发实施" value="developing" />
        <el-option label="项目交付" value="delivery" />
        <el-option label="项目运营" value="operation" />
      </el-select>
      <template #footer>
        <el-button @click="statusVisible = false">取消</el-button>
        <el-button type="primary" @click="handleStatus">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { getProject, inviteMember, listUsers, removeMember, updateProject } from "../api/projects";
import { useAuthStore } from "../stores/auth";
import { hasPerm } from "../rbac";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const hasBtn = (code) => hasPerm(code);

const project = ref({});
const loading = ref(false);
const inviteVisible = ref(false);
const inviting = ref(false);
const statusVisible = ref(false);
const userOptions = ref([]);
const inviteForm = reactive({ user_id: null, role: "developer" });
const statusForm = reactive({ status: "" });

const canManage = computed(() => {
  const u = auth.user;
  return u?.role === "admin" || u?.role === "manager" || project.value.owner === u?.id;
});

async function load() {
  loading.value = true;
  try {
    const { data } = await getProject(route.params.id);
    project.value = data;
  } finally {
    loading.value = false;
  }
}

async function searchUsers(query) {
  const { data } = await listUsers(query || "");
  userOptions.value = data;
}

function openInvite() {
  inviteForm.user_id = null;
  inviteForm.role = "developer";
  userOptions.value = [];
  inviteVisible.value = true;
  searchUsers("");
}

async function handleInvite() {
  if (!inviteForm.user_id) {
    ElMessage.warning("请选择成员");
    return;
  }
  inviting.value = true;
  try {
    const { data } = await inviteMember(project.value.id, inviteForm);
    project.value = data;
    ElMessage.success("已邀请");
    inviteVisible.value = false;
  } finally {
    inviting.value = false;
  }
}

async function handleRemove(row) {
  await ElMessageBox.confirm(`确定移除成员「${row.username}」？`, "提示", { type: "warning" });
  await removeMember(project.value.id, row.id);
  ElMessage.success("已移除");
  load();
}

function openStatus() {
  statusForm.status = project.value.status;
  statusVisible.value = true;
}

async function handleStatus() {
  try {
    const { data } = await updateProject(project.value.id, { status: statusForm.status });
    project.value = data;
    statusVisible.value = false;
    ElMessage.success("状态已更新");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "状态更新失败");
  }
}

function goBack() {
  router.push({ name: "projects" });
}

function goRequirements() {
  router.push({ name: "project-requirements", params: { id: project.value.id } });
}

function statusType(s) {
  return { requirement: "warning", planning: "primary", architecture: "danger", developing: "success", delivery: "", operation: "info" }[s] || "info";
}

function formatTime(t) {
  return t ? new Date(t).toLocaleString() : "";
}

onMounted(load);
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
