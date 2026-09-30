<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <span class="logo-en">AICodingProjectAssistance</span>
        <span class="logo-cn">（AICoding项目辅助、管理系统）</span>
      </div>
      <el-menu :default-active="$route.path" router background-color="#1f6f43" text-color="#d6ecdd" active-text-color="#ffffff">
        <template v-for="item in visibleMenus" :key="item.label">
          <el-sub-menu v-if="item.children && item.children.length" :index="item.label">
            <template #title><span>{{ item.label }}</span></template>
            <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
              <span>{{ child.label }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <span>{{ item.label }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">{{ $route.meta.title || "" }}</div>
        <div class="header-right">
          <el-select
            v-model="currentProjectId"
            placeholder="选择项目"
            clearable
            filterable
            style="width: 220px; margin-right: 16px"
          >
            <el-option v-for="p in projectStore.projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-dropdown @command="handleCommand">
          <span class="user-info">
            {{ auth.displayName }}
            <el-tag size="small" style="margin-left: 6px">{{ roleLabel }}</el-tag>
            <el-icon style="margin-left: 4px"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="password">修改密码</el-dropdown-item>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 修改密码 -->
    <el-dialog v-model="pwdVisible" title="修改密码" width="420px">
      <el-form label-width="90px">
        <el-form-item label="原密码"><el-input v-model="pwdForm.old_password" type="password" show-password /></el-form-item>
        <el-form-item label="新密码"><el-input v-model="pwdForm.new_password" type="password" show-password /></el-form-item>
        <el-form-item label="确认新密码"><el-input v-model="pwdForm.confirm" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="submitPwd">确认</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import { useAuthStore } from "../stores/auth";
import { useProjectStore } from "../stores/project";
import { changePassword } from "../api/auth";
import { MENU_TREE, hasPerm } from "../rbac";

const router = useRouter();
const auth = useAuthStore();
const projectStore = useProjectStore();

// 全局当前项目（右上角选择，所有菜单共享，持久化到 localStorage）
const currentProjectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});

const pwdVisible = ref(false);
const pwdLoading = ref(false);
const pwdForm = reactive({ old_password: "", new_password: "", confirm: "" });

const roleLabel = computed(() => {
  const map = { admin: "管理员", manager: "项目经理", developer: "开发", tester: "测试", guest: "访客" };
  return map[auth.user?.role] || auth.user?.role || "";
});

// 菜单按 RBAC 资源码过滤：未配置的菜单码默认全放行，启用后按角色分组授权
const visibleMenus = computed(() =>
  MENU_TREE.map((item) => {
    const children = item.children
      ? item.children.filter((c) => hasPerm(c.code))
      : [];
    const selfVisible = item.children ? children.length > 0 : hasPerm(item.code);
    return selfVisible ? { ...item, children } : null;
  }).filter(Boolean)
);

onMounted(() => {
  auth.fetchResources();
  projectStore.ensureLoaded().catch(() => {});
});

function handleCommand(cmd) {
  if (cmd === "password") {
    pwdForm.old_password = "";
    pwdForm.new_password = "";
    pwdForm.confirm = "";
    pwdVisible.value = true;
  } else if (cmd === "logout") {
    auth.logout();
    router.push({ name: "login" });
  }
}

async function submitPwd() {
  if (!pwdForm.old_password || !pwdForm.new_password) return ElMessage.warning("请填写完整");
  if (pwdForm.new_password.length < 6) return ElMessage.warning("新密码至少 6 位");
  if (pwdForm.new_password !== pwdForm.confirm) return ElMessage.warning("两次输入的新密码不一致");
  pwdLoading.value = true;
  try {
    await changePassword({ old_password: pwdForm.old_password, new_password: pwdForm.new_password });
    ElMessage.success("密码修改成功，请重新登录");
    pwdVisible.value = false;
    auth.logout();
    router.push({ name: "login" });
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.old_password?.[0] || "修改失败");
  } finally {
    pwdLoading.value = false;
  }
}
</script>

<style scoped>
.layout {
  height: 100%;
}
.aside {
  background: #1f6f43;
}
.logo {
  height: 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: bold;
  line-height: 1.3;
}
.logo-en {
  font-size: 12px;
  white-space: nowrap;
}
.logo-cn {
  font-size: 11px;
  white-space: nowrap;
  opacity: 0.85;
}
.aside :deep(.el-menu) {
  border-right: none;
}
.header {
  background: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
}
.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #333;
}
.header-right {
  display: flex;
  align-items: center;
}
.main {
  background: #f5f7fa;
}
</style>
