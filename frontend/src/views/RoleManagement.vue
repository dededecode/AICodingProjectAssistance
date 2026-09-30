<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">权限组管理</h3>
        <div class="toolbar-right">
          <el-button type="primary" size="small" :disabled="!hasBtn('btn:role-create')" @click="openCreate">新建权限组</el-button>
        </div>
      </div>
      <p style="color: #909399; font-size: 12px; margin: 8px 0 0">
        机制说明：① 权限完全由「权限组」决定（白名单制）——在「用户管理」给用户分配权限组后，该组勾选的资源对其可见（多个组取并集）；② 勾选菜单即同步授权该模块的后端接口（前后端同码联动，接口层同样强校验）；③ 未分配权限组的账号（除 admin 外）登录后仅可访问首页，无任何默认权限；④ admin 始终可访问全部资源。
      </p>
    </el-card>

    <!-- 新建权限组 -->
    <el-dialog v-model="createVisible" title="新建权限组" width="400px">
      <el-form label-width="80px">
        <el-form-item label="组名称">
          <el-input v-model="newRoleName" placeholder="如：测试组长 / 运营专员" maxlength="50" @keyup.enter="doCreate" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">确定</el-button>
      </template>
    </el-dialog>

    <el-card shadow="never" style="margin-top: 16px">
      <el-row :gutter="16">
        <el-col :span="7">
          <div class="role-list-head">
            <span>权限组列表</span>
          </div>
          <div
            v-for="r in roles"
            :key="r.id"
            class="role-item"
            :class="{ active: selectedId === r.id }"
            @click="selectRole(r)"
          >
            <span>{{ r.name }}</span>
            <el-tag v-if="r.builtin" size="small" type="info">预置</el-tag>
            <el-button
              v-else
              size="small"
              text
              type="danger"
              :disabled="!hasBtn('btn:role-delete')"
              @click.stop="doDelete(r)"
            >删除</el-button>
          </div>
        </el-col>
        <el-col :span="17">
          <div class="role-tree-head">
            <span>资源勾选：{{ selectedRoleName }}</span>
            <el-button type="primary" size="small" :loading="saving" :disabled="!hasBtn('btn:role-save')" @click="save">保存资源</el-button>
          </div>
          <el-tree
            ref="treeRef"
            :data="treeData"
            node-key="id"
            show-checkbox
            default-expand-all
            :props="{ label: 'label', children: 'children' }"
            style="margin-top: 12px"
          />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createRole, deleteRole, listRoles, saveRoleResources } from "../api/rbac";
import { RESOURCES, hasPerm } from "../rbac";

const roles = ref([]);
const selectedId = ref(null);
const selectedRoleName = ref("");
const newRoleName = ref("");
const createVisible = ref(false);
const creating = ref(false);
const saving = ref(false);
const treeRef = ref(null);

const hasBtn = (code) => hasPerm(code);

const treeData = computed(() =>
  RESOURCES.map((g) => ({
    id: `group:${g.type}`,
    label: g.label,
    children: g.items.map((i) => ({ id: i.code, label: `${i.name}（${i.code}）` })),
  }))
);

async function load() {
  const { data } = await listRoles();
  roles.value = data;
  if (selectedId.value == null && data.length) {
    selectRole(data[0]);
  }
}

function selectRole(r) {
  selectedId.value = r.id;
  selectedRoleName.value = r.name;
  const checked = (r.codes || []).filter((c) => !c.startsWith("group:"));
  treeRef.value?.setCheckedKeys(checked);
}

function openCreate() {
  newRoleName.value = "";
  createVisible.value = true;
}

async function doCreate() {
  const name = newRoleName.value.trim();
  if (!name) return ElMessage.warning("请输入角色名称");
  creating.value = true;
  try {
    const { data } = await createRole(name);
    newRoleName.value = "";
    createVisible.value = false;
    ElMessage.success("权限组已创建，可在「用户管理」给用户分配该组");
    roles.value.push(data);
    selectRole(data);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "创建失败");
  } finally {
    creating.value = false;
  }
}

async function doDelete(r) {
  try {
    await ElMessageBox.confirm(`确定删除权限组「${r.name}」？该组用户的对应资源授权将失效。`, "删除权限组", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deleteRole(r.id);
    ElMessage.success("已删除");
    roles.value = roles.value.filter((x) => x.id !== r.id);
    if (selectedId.value === r.id) {
      selectedId.value = null;
      selectedRoleName.value = "";
      if (roles.value.length) selectRole(roles.value[0]);
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

async function save() {
  if (!selectedId.value) return ElMessage.warning("请先选择角色");
  const all = treeRef.value?.getCheckedKeys(true) || [];
  const codes = all.filter((k) => !k.startsWith("group:"));
  saving.value = true;
  try {
    const { data } = await saveRoleResources(selectedId.value, codes);
    const target = roles.value.find((x) => x.id === selectedId.value);
    if (target) target.codes = data.codes;
    ElMessage.success("资源已保存");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar-right {
  display: flex;
  gap: 8px;
}
.role-list-head,
.role-tree-head {
  font-weight: 600;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.role-tree-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.role-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 6px;
}
.role-item:hover {
  background: #f5f7fa;
}
.role-item.active {
  background: #ecf5ff;
  color: #409eff;
}
</style>
