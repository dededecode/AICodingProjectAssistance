<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">交付文档</h3>
        <div class="toolbar-right">
          <el-input
            v-model="keyword"
            placeholder="按标题/类型/内容搜索"
            clearable
            style="width: 240px"
            @keyup.enter="load"
            @clear="load"
          />
          <el-button @click="load">查询</el-button>
          <el-button type="primary" :disabled="!projectId" @click="openUpload">上传文档</el-button>
        </div>
      </div>

      <el-alert
        v-if="!projectId"
        type="info"
        :closable="false"
        show-icon
        title="请先在右上角选择项目"
        style="margin-bottom: 12px"
      />

      <el-table :data="docs" v-loading="loading" border stripe>
        <el-table-column prop="title" label="文档标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="130">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.doc_type)" size="small">{{ row.doc_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            {{ row.source === "manual" ? "手动上传" : "Agent 回传" }}
          </template>
        </el-table-column>
        <el-table-column prop="creator" label="创建人" width="130" />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="view(row)">查看</el-button>
            <el-button v-if="row.file" link type="primary" @click="download(row)">下载</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>暂无交付文档</template>
      </el-table>
    </el-card>

    <el-dialog v-model="uploadVisible" title="上传交付文档" width="640px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="文档标题" required>
          <el-input v-model="form.title" placeholder="如：客户工单管理系统 · 部署说明" />
        </el-form-item>
        <el-form-item label="文档类型">
          <el-select v-model="form.doc_type" style="width: 100%">
            <el-option v-for="t in typeOpts" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="提交方式">
          <el-radio-group v-model="form.mode">
            <el-radio value="file">上传文件</el-radio>
            <el-radio value="content">粘贴 Markdown</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.mode === 'file'" label="选择文件">
          <el-upload :auto-upload="false" :show-file-list="false" :on-change="onFileChange">
            <el-button>选择文件</el-button>
          </el-upload>
          <span v-if="file" class="file-name">{{ file.name }}</span>
        </el-form-item>
        <el-form-item v-else label="文档内容">
          <el-input v-model="form.content" type="textarea" :rows="8" placeholder="支持 Markdown" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="viewVisible" :title="current.title" width="820px">
      <pre class="doc-content">{{ current.content || "（该文档为附件形式，请点击「下载」查看）" }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useProjectStore } from "../stores/project";
import {
  createDeliveryDoc,
  deleteDeliveryDoc,
  listDeliveryDocs,
  uploadDeliveryDoc,
} from "../api/delivery";

const typeOpts = [
  { value: "architecture", label: "架构设计文档" },
  { value: "testing", label: "测试文档" },
  { value: "deployment", label: "部署文档" },
  { value: "other", label: "其它" },
];

function typeTag(t) {
  return { architecture: "primary", testing: "success", deployment: "warning", other: "info" }[t] || "info";
}

function formatTime(v) {
  return v ? new Date(v).toLocaleString("zh-CN", { hour12: false }) : "";
}

const projectStore = useProjectStore();
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});

const loading = ref(false);
const docs = ref([]);
const keyword = ref("");
const uploadVisible = ref(false);
const saving = ref(false);
const file = ref(null);
const viewVisible = ref(false);
const current = reactive({ title: "", content: "" });
const form = reactive({ title: "", doc_type: "other", mode: "file", content: "" });

async function load() {
  if (!projectId.value) {
    docs.value = [];
    return;
  }
  loading.value = true;
  try {
    const { data } = await listDeliveryDocs(projectId.value, keyword.value.trim());
    // 该接口未分页，返回的是数组；兼容可能的分页包裹
    docs.value = Array.isArray(data) ? data : data.results || [];
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "加载失败");
  } finally {
    loading.value = false;
  }
}

function openUpload() {
  form.title = "";
  form.doc_type = "other";
  form.mode = "file";
  form.content = "";
  file.value = null;
  uploadVisible.value = true;
}

function onFileChange(uploadFile) {
  file.value = uploadFile.raw;
}

async function doSave() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  if (!form.title.trim()) return ElMessage.warning("请填写文档标题");
  if (form.mode === "file" && !file.value) return ElMessage.warning("请选择文件");
  if (form.mode === "content" && !form.content.trim()) return ElMessage.warning("请填写文档内容");
  saving.value = true;
  try {
    if (form.mode === "file") {
      const fd = new FormData();
      fd.append("project_id", projectId.value);
      fd.append("title", form.title.trim());
      fd.append("type", form.doc_type);
      fd.append("file", file.value);
      await uploadDeliveryDoc(fd);
    } else {
      await createDeliveryDoc({
        project: projectId.value,
        // 同时带上 project_id，便于后端做项目成员校验
        project_id: projectId.value,
        title: form.title.trim(),
        doc_type: form.doc_type,
        content: form.content,
      });
    }
    ElMessage.success("提交成功");
    uploadVisible.value = false;
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "提交失败");
  } finally {
    saving.value = false;
  }
}

function view(row) {
  current.title = row.title;
  current.content = row.content;
  viewVisible.value = true;
}

function download(row) {
  window.open(row.file, "_blank");
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.title}」？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteDeliveryDoc(row.id);
    ElMessage.success("已删除");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

onMounted(async () => {
  await projectStore.ensureLoaded();
  load();
});
watch(projectId, () => load());
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.toolbar-right {
  display: flex;
  gap: 8px;
}
.file-name {
  margin-left: 8px;
  color: #666;
}
.doc-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  margin: 0;
  max-height: 60vh;
  overflow: auto;
}
</style>
