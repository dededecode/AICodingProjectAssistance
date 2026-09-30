<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">项目管理</h3>
        <el-button type="primary" @click="openCreate">新建项目</el-button>
      </div>

      <el-table :data="projects" v-loading="loading" stripe style="margin-top: 16px">
        <el-table-column prop="id" label="项目ID" width="90" />
        <el-table-column prop="name" label="项目名称" min-width="180">
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row.id)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
        <el-table-column prop="owner_name" label="负责人" width="120" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="成员数" width="90">
          <template #default="{ row }">{{ row.members?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" v-if="hasBtn('btn:project-delete')">
          <template #default="{ row }">
            <el-button size="small" type="danger" text @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建项目 -->
    <el-dialog v-model="dialogVisible" title="新建项目" width="480px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="请输入项目描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { createProject, deleteProject, listProjects } from "../api/projects";
import { useProjectStore } from "../stores/project";
import { hasPerm } from "../rbac";

const router = useRouter();
const projectStore = useProjectStore();

const hasBtn = (code) => hasPerm(code);

const projects = ref([]);
const loading = ref(false);
const dialogVisible = ref(false);
const submitting = ref(false);
const formRef = ref();
const form = reactive({ name: "", description: "" });
const rules = {
  name: [{ required: true, message: "请输入项目名称", trigger: "blur" }],
};

async function load() {
  loading.value = true;
  try {
    const { data } = await listProjects();
    projects.value = data;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.name = "";
  form.description = "";
  dialogVisible.value = true;
}

async function handleCreate() {
  await formRef.value.validate();
  submitting.value = true;
  try {
    const { data } = await createProject(form);
    ElMessage.success("项目创建成功");
    dialogVisible.value = false;
    projects.value.unshift(data);
    projectStore.ensureLoaded();
  } finally {
    submitting.value = false;
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除项目「${row.name}」？`, "提示", { type: "warning" });
  await deleteProject(row.id);
  ElMessage.success("已删除");
  load();
  projectStore.ensureLoaded();
}

function goDetail(id) {
  router.push({ name: "project-detail", params: { id } });
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
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
