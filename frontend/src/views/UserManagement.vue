<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">用户管理</h3>
        <el-button type="primary" :disabled="!hasBtn('btn:user-create')" @click="openCreate">新增用户</el-button>
      </div>

      <el-table :data="users" v-loading="loading" stripe style="margin-top: 12px">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="name" label="姓名" min-width="110">
          <template #default="{ row }">{{ row.name || "-" }}</template>
        </el-table-column>
        <el-table-column prop="capability" label="能力描述" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.capability || "-" }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="160" />
        <el-table-column label="MCP Token" min-width="200">
          <template #default="{ row }">
            <el-tag size="small" type="info" style="font-family: monospace">{{ maskToken(row.mcp_token) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号类型" width="120">
          <template #default="{ row }">
            <el-select v-model="row.role" size="small" :disabled="isProtected(row) || !hasBtn('btn:user-active')" @change="(v) => updateRole(row, v)">
              <el-option v-for="r in roleOpts" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="权限组" min-width="180">
          <template #default="{ row }">
            <el-select
              v-model="row.groups"
              multiple
              size="small"
              :disabled="isProtected(row) || !hasBtn('btn:user-group')"
              placeholder="选择权限组（可多选）"
              @change="(v) => updateGroups(row, v)"
            >
              <el-option v-for="g in groupOpts" :key="g.id" :label="g.label" :value="g.id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" :disabled="isProtected(row) || !hasBtn('btn:user-active')" @change="(v) => updateActive(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-button size="small" type="primary" text :disabled="isProtected(row) || !hasBtn('btn:user-edit')" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text @click="viewToken(row)">查看Token</el-button>
            <el-button size="small" text :disabled="isProtected(row) || !hasBtn('btn:user-token-regen')" @click="regenerateToken(row)">重新生成Token</el-button>
            <el-button size="small" text :disabled="isProtected(row) || !hasBtn('btn:user-reset-pwd')" @click="resetPwd(row)">重置密码</el-button>
            <el-button size="small" type="danger" text :disabled="isProtected(row) || !hasBtn('btn:user-delete')" @click="removeUser(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新增用户'" width="460px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名" v-if="!editing"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" placeholder="用户姓名（可选）" /></el-form-item>
        <el-form-item label="能力描述">
          <el-input v-model="form.capability" type="textarea" :rows="2" placeholder="如：擅长 Vue/Java、可独立完成全栈功能；用于 AI 生成项目计划时分配任务参考" />
        </el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="账号类型">
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="r in roleOpts" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <div style="color: #909399; font-size: 12px; line-height: 1.5; margin-top: 4px">仅作系统标识（管理员特殊），页面/功能权限请在下方「权限组」中选择。</div>
        </el-form-item>
        <el-form-item label="权限组">
          <el-select v-model="form.groups" multiple style="width: 100%" placeholder="选择权限组（可多选，决定该用户的页面/功能权限）">
            <el-option v-for="g in groupOpts" :key="g.id" :label="g.label" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password :placeholder="editing ? '留空则不修改' : '初始密码'" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { adminCreateUser, adminDeleteUser, adminListUsers, adminRegenerateToken, adminResetPassword, adminUpdateUser } from "../api/auth";
import { listRoles } from "../api/rbac";
import { hasPerm } from "../rbac";

const users = ref([]);
const loading = ref(false);
const dialogVisible = ref(false);
const editing = ref(null);
const saving = ref(false);
const form = reactive({ username: "", name: "", capability: "", email: "", role: "developer", groups: [], password: "" });
const groupOpts = ref([]);

const hasBtn = (code) => hasPerm(code);

const roleOpts = [
  { value: "admin", label: "管理员" },
  { value: "manager", label: "项目经理" },
  { value: "developer", label: "开发" },
  { value: "tester", label: "测试" },
  { value: "guest", label: "访客" },
];

// 系统账号保护：admin 不允许删除/修改（后端同样拦截）
function isProtected(row) {
  return row?.username === "admin";
}

// 权限组选项直接使用库中 name

async function load() {
  loading.value = true;
  try {
    const [usersRes, rolesRes] = await Promise.all([adminListUsers(), listRoles()]);
    users.value = usersRes.data;
    groupOpts.value = (rolesRes.data || []).map((g) => ({
      ...g,
      label: g.name,
    }));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editing.value = null;
  form.username = "";
  form.name = "";
  form.capability = "";
  form.email = "";
  form.role = "developer";
  form.groups = [];
  form.password = "";
  dialogVisible.value = true;
}

function openEdit(row) {
  editing.value = row;
  form.username = row.username;
  form.name = row.name || "";
  form.capability = row.capability || "";
  form.email = row.email;
  form.role = row.role;
  form.groups = [...(row.groups || [])];
  form.password = "";
  dialogVisible.value = true;
}

async function submit() {
  if (!editing.value) {
    if (!form.username.trim()) return ElMessage.warning("请输入用户名");
    if (!form.password) return ElMessage.warning("请输入初始密码");
  }
  saving.value = true;
  try {
    const payload = { name: form.name, capability: form.capability, email: form.email, role: form.role, groups: form.groups, password: form.password || undefined };
    if (editing.value) {
      await adminUpdateUser(editing.value.id, payload);
      ElMessage.success("已保存");
    } else {
      await adminCreateUser({ username: form.username, ...payload });
      ElMessage.success("用户已创建");
    }
    dialogVisible.value = false;
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.username?.[0] || "操作失败");
  } finally {
    saving.value = false;
  }
}

async function updateRole(row, role) {
  await adminUpdateUser(row.id, { role });
  ElMessage.success("角色已更新");
}
async function updateGroups(row, groups) {
  await adminUpdateUser(row.id, { groups });
  ElMessage.success("权限分组已更新");
}
async function updateActive(row, active) {
  await adminUpdateUser(row.id, { is_active: active });
  ElMessage.success(active ? "已启用" : "已禁用");
}

async function resetPwd(row) {
  try {
    const { value } = await ElMessageBox.prompt(`为「${row.username}」设置新密码（至少6位）`, "重置密码", {
      inputType: "password",
      inputValidator: (v) => (v && v.length >= 6 ? true : "密码至少 6 位"),
    });
    await adminResetPassword(row.id, value);
    ElMessage.success("密码已重置");
  } catch (e) {
    if (e !== "cancel" && e?.response) ElMessage.error(e.response?.data?.detail || "重置失败");
  }
}

async function removeUser(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, "删除用户", { type: "warning" });
  } catch {
    return;
  }
  try {
    await adminDeleteUser(row.id);
    ElMessage.success("已删除");
    load();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

function maskToken(t) {
  if (!t) return "-";
  return t.length <= 16 ? t : `${t.slice(0, 12)}…`;
}

async function viewToken(row) {
  try {
    await ElMessageBox.alert(
      `<div style="word-break:break-all;font-family:monospace;font-size:13px;line-height:1.6">${row.mcp_token}</div>
       <p style="margin:12px 0 0;color:#909399;font-size:12px">该 Token 用于 MCP 与平台接口通信，标识该用户身份，仅项目成员或管理员可操作对应项目接口，请妥善保管。</p>`,
      `「${row.username}」的 MCP Token`,
      { dangerouslyUseHTMLString: true, confirmButtonText: "复制并关闭", cancelButtonText: "关闭", showCancelButton: true }
    );
    navigator.clipboard?.writeText(row.mcp_token);
    ElMessage.success("已复制");
  } catch {
    /* 关闭弹窗 */
  }
}

async function regenerateToken(row) {
  try {
    await ElMessageBox.confirm(`确定重新生成「${row.username}」的 MCP Token？旧 Token 将立即失效。`, "重新生成 MCP Token", { type: "warning" });
  } catch {
    return;
  }
  try {
    const { data } = await adminRegenerateToken(row.id);
    row.mcp_token = data.mcp_token;
    ElMessage.success("已重新生成，请将新 Token 配置到 MCP 服务端");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "重新生成失败");
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
</style>
