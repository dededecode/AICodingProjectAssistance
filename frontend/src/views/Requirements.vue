<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">需求分析</h3>
        <el-button type="primary" @click="openUpload">上传需求文档</el-button>
      </div>
      <el-alert
        style="margin-top: 12px"
        type="info"
        :closable="false"
        title="支持 Word(.docx)、Excel(.xlsx)、Markdown(.md/.txt)。上传后执行 AI 完整度检测，确认无误后入库并初始化项目知识库。"
      />
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 16px">
        <el-table-column label="文档标题" min-width="160">
          <template #default="{ row }">
            <el-link type="primary" @click="openPreview(row)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="reqStatusType(row)" size="small">{{ reqStatusLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="完整度评分" width="120">
          <template #default="{ row }">
            <span v-if="row.analysis_result">{{ row.analysis_result.overall_score }}</span>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="AI 结论" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.analysis_result" :type="row.analysis_result.verdict === 'passed' ? 'success' : 'warning'" size="small">
              {{ row.analysis_result.verdict === "passed" ? "建议通过" : "需补充" }}
            </el-tag>
            <span v-else style="color: #999">未分析</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="240">
          <template #default="{ row }">
            <el-button size="small" type="primary" text :loading="analyzingId === row.id" @click="handleAnalyze(row)">AI 分析</el-button>
            <el-button size="small" type="success" text @click="showResult(row)">查看结果</el-button>
            <el-button size="small" type="warning" text :disabled="row.is_confirmed || !row.analysis_result" :loading="confirmingId === row.id" @click="handleConfirm(row)">确认入库</el-button>
            <el-button size="small" type="danger" text @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 文档预览 -->
    <el-dialog v-model="previewVisible" :title="preview?.title || '文档预览'" width="760px" top="5vh">
      <div style="margin-bottom: 8px">
        <a v-if="preview?.original_file" :href="preview.original_file" target="_blank">
          <el-button size="small" type="primary" plain>下载原文件</el-button>
        </a>
      </div>
      <div style="max-height: 68vh; overflow: auto; background: #fff; padding: 8px; border-radius: 4px">
        <RichText :content="preview?.parsed_text || ''" />
      </div>
    </el-dialog>

    <!-- 上传 -->
    <el-dialog v-model="uploadVisible" title="上传需求文档" width="520px">
      <el-form label-width="80px">
        <el-form-item label="文档标题">
          <el-input v-model="uploadForm.title" placeholder="留空则使用文件名" />
        </el-form-item>
        <el-form-item label="文档类型">
          <el-radio-group v-model="uploadForm.doc_type">
            <el-radio value="text">纯文本</el-radio>
            <el-radio value="rich">图文（Word，自动解析图片）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="文档文件">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".docx,.xlsx,.md,.txt"
            :on-change="onFileChange"
            :on-remove="() => (uploadForm.file = null)"
          >
            <el-button>选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-alert
          v-if="uploadForm.doc_type === 'rich'"
          type="info"
          :closable="false"
          title="图文模式会把 Word 文档中的图片抽取出来，自动保存为项目的原型图/UI 图（AI 依据上下文命名与分类，可在原型图管理中修改），正文中图片以占位标记保留。"
        />
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传并解析</el-button>
      </template>
    </el-dialog>

    <!-- 分析结果 -->
    <el-dialog v-model="resultVisible" title="需求完整度分析结果" width="70%" top="3vh">
      <template v-if="current?.analysis_result">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="完整度评分">
            <b :style="{ color: scoreColor(current.analysis_result.overall_score) }">{{ current.analysis_result.overall_score }}</b>
          </el-descriptions-item>
          <el-descriptions-item label="结论">
            <el-tag :type="current.analysis_result.verdict === 'passed' ? 'success' : 'warning'">
              {{ current.analysis_result.verdict === "passed" ? "建议通过" : "需补充完善" }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <h4 style="margin: 16px 0 8px">内容质量</h4>
        <div class="quality-grid">
          <div class="q-item" v-for="q in qualityItems" :key="q.key">
            <div class="q-head">
              <span>{{ q.label }}</span>
              <el-tag :type="qType(q.score)" size="small">{{ q.score }}</el-tag>
            </div>
            <el-progress :percentage="q.score" :color="qColor(q.score)" :stroke-width="8" />
          </div>
        </div>
        <p v-if="current.analysis_result.quality?.comment" class="q-comment">{{ current.analysis_result.quality.comment }}</p>

        <h4 style="margin: 16px 0 8px">要素覆盖</h4>
        <el-table :data="current.analysis_result.elements" size="small">
          <el-table-column prop="name" label="要素" min-width="140" />
          <el-table-column prop="present" label="覆盖" width="70">
            <template #default="{ row }">
              <el-tag :type="row.present ? 'success' : 'danger'" size="small">{{ row.present ? "有" : "缺" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="score" label="评分" width="80" />
          <el-table-column prop="comment" label="说明" min-width="320" show-overflow-tooltip />
        </el-table>

        <h4 style="margin: 16px 0 8px">缺失 / 不足</h4>
        <ul v-if="current.analysis_result.missing?.length">
          <li v-for="(m, i) in current.analysis_result.missing" :key="i">{{ m }}</li>
        </ul>
        <p v-else style="color: #999">无</p>

        <h4 style="margin: 16px 0 8px">改进建议</h4>
        <ul v-if="current.analysis_result.suggestions?.length">
          <li v-for="(s, i) in current.analysis_result.suggestions" :key="i">{{ s }}</li>
        </ul>
        <p v-else style="color: #999">无</p>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { analyzeRequirement, confirmRequirement, deleteRequirement, listRequirements, uploadRequirement } from "../api/requirements";
import RichText from "../components/RichText.vue";

const route = useRoute();
const projectId = route.params.id;

const list = ref([]);
const loading = ref(false);
const uploadVisible = ref(false);
const uploading = ref(false);
const analyzingId = ref(null);
const confirmingId = ref(null);
const resultVisible = ref(false);
const current = ref(null);
const previewVisible = ref(false);
const preview = ref(null);
const uploadForm = reactive({ title: "", doc_type: "text", file: null });

const qualityItems = computed(() => {
  const q = current.value?.analysis_result?.quality || {};
  return [
    { key: "clarity", label: "阐述清晰（无歧义、具体）", score: q.clarity || 0 },
    { key: "understandability", label: "可被开发团队理解", score: q.understandability || 0 },
    { key: "logic", label: "逻辑清晰一致", score: q.logic || 0 },
  ];
});
function qType(s) {
  return s >= 80 ? "success" : s >= 60 ? "warning" : "danger";
}
function qColor(s) {
  return s >= 80 ? "#34d399" : s >= 60 ? "#f59e0b" : "#ef4444";
}

async function load() {
  loading.value = true;
  try {
    const { data } = await listRequirements(projectId);
    list.value = data;
  } finally {
    loading.value = false;
  }
}

function openPreview(row) {
  preview.value = row;
  previewVisible.value = true;
}

function onFileChange(file) {
  uploadForm.file = file.raw;
}

function openUpload() {
  uploadForm.title = "";
  uploadForm.doc_type = "text";
  uploadForm.file = null;
  uploadVisible.value = true;
}

async function handleUpload() {
  if (!uploadForm.file) {
    ElMessage.warning("请选择文件");
    return;
  }
  const fd = new FormData();
  fd.append("project_id", projectId);
  fd.append("title", uploadForm.title);
  fd.append("doc_type", uploadForm.doc_type);
  fd.append("file", uploadForm.file);
  uploading.value = true;
  try {
    const { data } = await uploadRequirement(fd);
    const n = data.prototype_images_created || 0;
    ElMessage.success(n > 0 ? `上传并解析成功，已将 ${n} 张图片保存到原型图库` : "上传并解析成功");
    uploadVisible.value = false;
    load();
  } finally {
    uploading.value = false;
  }
}

async function handleAnalyze(row) {
  analyzingId.value = row.id;
  try {
    const { data } = await analyzeRequirement(row.id);
    ElMessage.success("分析完成");
    load();
  } finally {
    analyzingId.value = null;
  }
}

function showResult(row) {
  current.value = row;
  resultVisible.value = true;
}

async function handleConfirm(row) {
  await ElMessageBox.confirm("确认该需求无误？确认后将初始化项目知识库，项目进入开发阶段。", "确认入库", { type: "warning" });
  confirmingId.value = row.id;
  try {
    await confirmRequirement(row.id);
    ElMessage.success("已入库，项目进入开发阶段");
    load();
  } finally {
    confirmingId.value = null;
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除需求文档「${row.title}」？将同时清理其入库知识、上传文件与解析图片。`, "删除文档", { type: "warning" });
  } catch {
    return;
  }
  await deleteRequirement(row.id);
  ElMessage.success("已删除");
  load();
}

function reqStatusLabel(row) {
  if (row.is_confirmed) return "已入库";
  if (row.analysis_result) return "已分析";
  return "未分析";
}
function reqStatusType(row) {
  if (row.is_confirmed) return "success";
  if (row.analysis_result) return "primary";
  return "info";
}
function scoreColor(s) {
  if (s >= 80) return "#67c23a";
  if (s >= 60) return "#e6a23c";
  return "#f56c6c";
}

onMounted(load);
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.quality-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.quality-grid .q-item {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px 12px;
}
.quality-grid .q-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 13px;
  color: #475569;
}
.q-comment {
  margin-top: 8px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}
</style>
