<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">原型图 / UI 图管理</h3>
      </div>

      <div class="filter-bar">
        <el-checkbox
          :model-value="allSelected"
          :indeterminate="someSelected && !allSelected"
          :disabled="!images.length"
          @change="toggleSelectAll"
        >全选本页</el-checkbox>
        <el-input
          v-model="searchName"
          clearable
          placeholder="按图名称搜索…"
          style="width: 240px"
          @input="onFilterChange"
        />
        <el-select v-model="searchKind" clearable placeholder="全部类型" style="width: 130px" @change="onFilterChange">
          <el-option v-for="k in kindOpts" :key="k.value" :label="k.label" :value="k.value" />
        </el-select>
        <span style="color: #909399; font-size: 12px">共 {{ total }} 张 · 图名称建议按「端-模块-功能」命名</span>
        <div style="flex: 1"></div>
        <template v-if="selectedIds.length">
          <el-button size="small" type="danger" @click="batchRemove">批量删除（{{ selectedIds.length }}）</el-button>
          <el-button size="small" text @click="selectedIds = []">取消选择</el-button>
        </template>
        <el-button type="primary" size="small" @click="openUpload">上传图片</el-button>
      </div>

      <div v-loading="loading" class="img-grid">
        <div v-for="(img, index) in images" :key="img.id" class="img-card">
          <div class="img-cover">
            <el-image
              :src="img.image"
              :preview-src-list="images.map((i) => i.image)"
              :initial-index="index"
              preview-teleported
              fit="cover"
              class="img-preview"
            />
            <el-checkbox
              class="img-select"
              :model-value="isSelected(img.id)"
              @change="(v) => toggleSelect(img.id, v)"
            />
          </div>
          <div class="img-info">
            <div class="img-name" :title="img.name">{{ img.name }}</div>
            <div class="img-meta">
              <el-tag size="small" :type="kindTagType(img.kind)">{{ img.kind_display }}</el-tag>
              <span class="uploader">{{ img.uploader_name || "-" }} · {{ formatTime(img.created_at) }}</span>
            </div>
            <div class="img-ops">
              <el-button size="small" type="primary" text @click="openEdit(img)">编辑</el-button>
              <el-button size="small" type="danger" text @click="removeImage(img)">删除</el-button>
            </div>
          </div>
        </div>
        <el-empty v-if="!loading && !images.length" description="没有符合条件的图片，点击右上角「上传图片」或调整筛选" />
      </div>

      <div v-if="total > pageSize" class="pager">
        <el-pagination
          v-model:current-page="page"
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :page-sizes="[12, 24, 48]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>

    <!-- 上传弹窗 -->
    <el-dialog v-model="uploadVisible" title="上传原型图 / UI 图" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="图名称" required>
          <el-input v-model="form.name" maxlength="100" placeholder="如：Web-登录-验证码" />
          <div class="hint">建议按格式「端-模块-功能」命名，如 Web-登录-验证码、App-工单-分页；名称在项目内唯一。</div>
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.kind">
            <el-radio v-for="k in kindOpts" :key="k.value" :value="k.value">{{ k.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="图片" required>
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="onFileChange"
            :on-remove="clearFile"
            :file-list="fileList"
          >
            <div style="font-size: 40px; color: #909399">+</div>
            <div style="margin-top: 6px">拖拽或点击选择图片</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑图片信息" width="460px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="图名称" required>
          <el-input v-model="editForm.name" maxlength="100" placeholder="如：Web-登录-验证码" />
          <div class="hint">名称在项目内唯一，修改为与其它图片重名的名称将无法保存。</div>
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="editForm.kind">
            <el-radio v-for="k in kindOpts" :key="k.value" :value="k.value">{{ k.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editing" @click="doEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useProjectStore } from "../stores/project";
import {
  deletePrototypeImage,
  listPrototypeImages,
  updatePrototypeImage,
  uploadPrototypeImage,
} from "../api/prototypeImages";

const kindOpts = [
  { value: "prototype", label: "原型图" },
  { value: "ui", label: "UI图" },
  { value: "flow", label: "业务流程图" },
  { value: "other", label: "其它" },
];

function kindTagType(kind) {
  return { prototype: "primary", ui: "success", flow: "warning", other: "info" }[kind] || "info";
}

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const loading = ref(false);
const images = ref([]);
const searchName = ref("");
const searchKind = ref("");
const page = ref(1);
const pageSize = ref(12);
const total = ref(0);
const selectedIds = ref([]);
const uploadVisible = ref(false);
const uploading = ref(false);
const file = ref(null);
const fileList = ref([]);
const form = reactive({ name: "", kind: "prototype" });
const editVisible = ref(false);
const editing = ref(false);
const editForm = reactive({ id: null, name: "", kind: "prototype" });

async function loadProjects() {
  await projectStore.ensureLoaded();
}

async function load() {
  if (!projectId.value) {
    images.value = [];
    total.value = 0;
    return;
  }
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (searchName.value.trim()) params.name = searchName.value.trim();
    if (searchKind.value) params.kind = searchKind.value;
    const { data } = await listPrototypeImages(projectId.value, params);
    images.value = data.results || [];
    total.value = data.count || 0;
  } finally {
    loading.value = false;
  }
}

function onFilterChange() {
  page.value = 1;
  selectedIds.value = [];
  load();
}

function onPageChange() {
  selectedIds.value = [];
  load();
}

function onSizeChange(size) {
  pageSize.value = size;
  page.value = 1;
  selectedIds.value = [];
  load();
}

function isSelected(id) {
  return selectedIds.value.includes(id);
}

// 全选本页（与现有选择交互一致：翻页/筛选会清空已选）
const allSelected = computed(
  () => images.value.length > 0 && images.value.every((i) => selectedIds.value.includes(i.id))
);
const someSelected = computed(() => images.value.some((i) => selectedIds.value.includes(i.id)));

function toggleSelectAll(checked) {
  if (checked) {
    const add = images.value.map((i) => i.id).filter((id) => !selectedIds.value.includes(id));
    selectedIds.value = [...selectedIds.value, ...add];
  } else {
    const pageIds = new Set(images.value.map((i) => i.id));
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.has(id));
  }
}

function toggleSelect(id, checked) {
  if (checked) {
    if (!isSelected(id)) selectedIds.value.push(id);
  } else {
    selectedIds.value = selectedIds.value.filter((x) => x !== id);
  }
}

async function batchRemove() {
  const n = selectedIds.value.length;
  if (!n) return;
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${n} 张图片？删除后不可恢复。`, "批量删除", { type: "warning" });
  } catch {
    return;
  }
  try {
    const { data } = await batchDeletePrototypeImages(projectId.value, selectedIds.value);
    ElMessage.success(`已删除 ${data.deleted || n} 张`);
    selectedIds.value = [];
    // 当前页图片全被删光时回退一页，避免停在空页
    if (images.value.length && images.value.length <= (data.deleted || n)) {
      if (page.value > 1) page.value -= 1;
    }
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "批量删除失败");
  }
}

function onProjectChange() {
  searchName.value = "";
  searchKind.value = "";
  selectedIds.value = [];
  page.value = 1;
  load();
}

function openUpload() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  form.name = "";
  form.kind = "prototype";
  file.value = null;
  fileList.value = [];
  uploadVisible.value = true;
}

function onFileChange(uploadFile) {
  file.value = uploadFile.raw;
  fileList.value = [uploadFile];
}
function clearFile() {
  file.value = null;
  fileList.value = [];
}

async function doUpload() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  if (!form.name.trim()) return ElMessage.warning("请填写图名称");
  if (!file.value) return ElMessage.warning("请选择图片");
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("project", projectId.value);
    fd.append("name", form.name.trim());
    fd.append("kind", form.kind);
    fd.append("image", file.value);
    await uploadPrototypeImage(fd);
    ElMessage.success("上传成功");
    uploadVisible.value = false;
    page.value = 1; // 新图排在最前，回到第一页展示
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "上传失败");
  } finally {
    uploading.value = false;
  }
}

function openEdit(img) {
  editForm.id = img.id;
  editForm.name = img.name;
  editForm.kind = img.kind;
  editVisible.value = true;
}

async function doEdit() {
  if (!editForm.name.trim()) return ElMessage.warning("请填写图名称");
  editing.value = true;
  try {
    const { data } = await updatePrototypeImage(editForm.id, {
      name: editForm.name.trim(),
      kind: editForm.kind,
    });
    editVisible.value = false;
    ElMessage.success("已保存");
    // 有筛选条件时重载保持一致；无筛选时局部更新避免打断预览
    if (searchName.value.trim() || searchKind.value) {
      load();
    } else {
      const idx = images.value.findIndex((i) => i.id === data.id);
      if (idx >= 0) images.value[idx] = data;
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    editing.value = false;
  }
}

async function removeImage(img) {
  try {
    await ElMessageBox.confirm(`确定删除「${img.name}」？`, "删除图片", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deletePrototypeImage(img.id);
    ElMessage.success("已删除");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
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
.img-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.img-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.img-cover {
  position: relative;
}
.img-select {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 2;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.9);
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
.img-preview {
  width: 100%;
  height: 150px;
  display: block;
  background: #f3f4f6;
}
.img-info {
  padding: 8px 12px 6px;
}
.img-name {
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.img-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #909399;
  font-size: 12px;
}
.img-ops {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}
.hint {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 4px;
}
</style>
