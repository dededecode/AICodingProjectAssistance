<template>
  <div class="shell" :class="{ 'is-collapse': collapsed }">
    <!-- ── 侧边栏 ── -->
    <aside class="sidebar">
      <div class="side-brand">
        <span class="logo-mark" aria-hidden="true">
          <svg viewBox="0 0 64 64" width="26" height="26">
            <path
              d="M32 11.5l4.8 12.9 12.9 4.8-12.9 4.8L32 46.9l-4.8-12.9-12.9-4.8 12.9-4.8z"
              fill="#fff"
            />
            <circle cx="46" cy="18" r="3.2" fill="#fff" opacity="0.8" />
          </svg>
        </span>
        <div v-show="!collapsed" class="logo-text">
          <b>AICoding</b>
          <span>项目辅助平台</span>
        </div>
      </div>

      <el-scrollbar class="side-scroll">
        <el-menu
          :default-active="$route.path"
          :collapse="collapsed"
          :collapse-transition="false"
          router
          class="side-menu"
          popper-class="side-menu-popup"
        >
          <template v-for="item in visibleMenus" :key="item.label">
            <el-sub-menu v-if="item.children && item.children.length" :index="item.label">
              <template #title>
                <el-icon><component :is="iconOf(item.code)" /></el-icon>
                <span>{{ item.label }}</span>
              </template>
              <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
                <el-icon><component :is="iconOf(child.code)" /></el-icon>
                <template #title>{{ child.label }}</template>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.path">
              <el-icon><component :is="iconOf(item.code)" /></el-icon>
              <template #title>{{ item.label }}</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>

      <div class="side-foot">
        <span class="dot" />
        <span v-show="!collapsed">本地化部署 · 数据不出内网</span>
      </div>
    </aside>

    <!-- ── 主区域 ── -->
    <div class="shell-main">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-btn" :title="collapsed ? '展开菜单' : '收起菜单'" @click="toggleCollapse">
            <el-icon><component :is="collapsed ? Expand : Fold" /></el-icon>
          </button>
          <div class="crumb">
            <span class="crumb-root">AICoding 项目辅助平台</span>
            <span class="crumb-sep">/</span>
            <b>{{ $route.meta.title || "首页" }}</b>
          </div>
        </div>

        <div class="topbar-right">
          <el-select
            v-model="currentProjectId"
            class="project-select"
            placeholder="选择项目"
            clearable
            filterable
          >
            <template #prefix><el-icon><FolderOpened /></el-icon></template>
            <el-option v-for="p in projectStore.projects" :key="p.id" :label="p.name" :value="p.id">
              <span class="opt-name">{{ p.name }}</span>
              <span class="opt-tag">{{ statusLabel(p.status) }}</span>
            </el-option>
          </el-select>

          <span class="topbar-divider" />

          <el-dropdown trigger="click" @command="handleCommand">
            <div class="user-chip">
              <span class="avatar">{{ initial }}</span>
              <span class="user-meta">
                <b>{{ auth.displayName }}</b>
                <small>{{ roleLabel }}</small>
              </span>
              <el-icon class="caret"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <div class="dropdown-head">
                  <b>{{ auth.displayName }}</b>
                  <span>{{ auth.user?.name || auth.user?.email || "平台账号" }}</span>
                </div>
                <el-dropdown-item command="password">
                  <el-icon><Lock /></el-icon> 修改密码
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="ds-page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- ── 修改密码 ── -->
    <el-dialog v-model="pwdVisible" title="修改密码" width="430px" append-to-body>
      <el-form label-position="top">
        <el-form-item label="原密码">
          <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwdForm.confirm" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="submitPwd">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  ArrowDown,
  Calendar,
  ChatDotRound,
  Checked,
  Clock,
  Collection,
  Cpu,
  DataBoard,
  Document,
  Expand,
  Fold,
  Folder,
  FolderOpened,
  Key,
  List,
  Lock,
  Memo,
  Odometer,
  Picture,
  Reading,
  Setting,
  SwitchButton,
  TrendCharts,
  UserFilled,
  Warning,
} from "@element-plus/icons-vue";
import { useAuthStore } from "../stores/auth";
import { useProjectStore } from "../stores/project";
import { changePassword } from "../api/auth";
import { MENU_TREE, hasPerm } from "../rbac";

const router = useRouter();
const auth = useAuthStore();
const projectStore = useProjectStore();

// 菜单图标：纯表现层，按资源码映射
const MENU_ICONS = {
  "menu:dashboard": Odometer,
  "menu:overview": DataBoard,
  "menu:project-manage": Folder,
  "menu:projects": Document,
  "menu:prototype-images": Picture,
  "menu:project-planning": Calendar,
  "menu:tasks": List,
  "menu:architecture": Cpu,
  "menu:bugs": Warning,
  "menu:operation": TrendCharts,
  "menu:collaboration": Clock,
  "menu:work-groups": ChatDotRound,
  "menu:knowledge": Collection,
  "menu:llm-wiki": Reading,
  "menu:testing": Checked,
  "menu:delivery-docs": FolderOpened,
  "menu:model-config": Setting,
  "menu:users": UserFilled,
  "menu:embedding-logs": Memo,
  "menu:rbac": Key,
};
const iconOf = (code) => MENU_ICONS[code] || Document;

const PROJECT_STATUS = {
  requirement: "需求分析",
  planning: "项目计划",
  architecture: "架构设计",
  developing: "开发实施",
  delivery: "项目交付",
  operation: "项目运营",
};
const statusLabel = (s) => PROJECT_STATUS[s] || s || "未开始";

// 折叠状态持久化；窄屏默认折叠
const collapsed = ref(localStorage.getItem("sidebar_collapsed") === "1");
function toggleCollapse() {
  collapsed.value = !collapsed.value;
  localStorage.setItem("sidebar_collapsed", collapsed.value ? "1" : "0");
}

const currentProjectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});

const initial = computed(() => (auth.displayName || "U").slice(0, 1).toUpperCase());

const roleLabel = computed(() => {
  const map = { admin: "管理员", manager: "项目经理", developer: "开发", tester: "测试", guest: "访客" };
  return map[auth.user?.role] || auth.user?.role || "";
});

// 菜单按 RBAC 资源码过滤（白名单制）：admin 角色与超管全权，其余账号看权限组勾选的码，
// 未分配权限组时至少保留首页（见 rbac.js 的 hasPerm）
const visibleMenus = computed(() =>
  MENU_TREE.map((item) => {
    const children = item.children
      ? item.children.filter((c) => hasPerm(c.code))
      : [];
    const selfVisible = item.children ? children.length > 0 : hasPerm(item.code);
    return selfVisible ? { ...item, children } : null;
  }).filter(Boolean)
);

const pwdVisible = ref(false);
const pwdLoading = ref(false);
const pwdForm = reactive({ old_password: "", new_password: "", confirm: "" });

onMounted(() => {
  if (window.innerWidth < 992) collapsed.value = true;
  // 刷新本人信息与权限码：菜单直接依赖这两项，若本地缓存是旧数据（如账号刚被提为超管、
  // 刚被调整权限组），不刷新会出现「菜单一直是空的」而必须重新登录
  auth.fetchMe().catch(() => {});
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
.shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-page);
}

/* ── 侧边栏 ── */
.sidebar {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 236px;
  flex: 0 0 236px;
  background: var(--side-bg);
  transition: width var(--dur) var(--ease), flex-basis var(--dur) var(--ease);
}
.shell.is-collapse .sidebar {
  width: 68px;
  flex-basis: 68px;
}
.sidebar::after {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 220px;
  background: radial-gradient(320px 200px at 20% 0%, rgba(79, 110, 247, 0.35), transparent 70%);
  pointer-events: none;
}
.side-brand {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 11px;
  height: 62px;
  padding: 0 16px;
  flex: 0 0 62px;
  border-bottom: 1px solid var(--side-line);
}
.logo-mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 11px;
  background: var(--grad-brand);
  box-shadow: 0 10px 22px -10px rgba(79, 110, 247, 0.95);
}
.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
}
.logo-text b {
  font-size: 14.5px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.3px;
}
.logo-text span {
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.5);
}
.side-scroll {
  position: relative;
  z-index: 1;
  flex: 1;
  padding: 10px 10px 6px;
}
.shell.is-collapse .side-scroll {
  padding: 10px 8px 6px;
}
.side-menu {
  border-right: none;
  background: transparent;
}
.side-menu:not(.el-menu--collapse) {
  width: 100%;
}
/* 折叠态：收窄图标宽与内边距，使菜单宽度恰好等于 68px 侧栏减去内边距（52px） */
.shell.is-collapse .side-menu {
  --el-menu-icon-width: 20px;
  --el-menu-base-level-padding: 16px;
}
.side-foot {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 46px;
  flex: 0 0 46px;
  padding: 0 18px;
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.42);
  border-top: 1px solid var(--side-line);
  white-space: nowrap;
}
.side-foot .dot {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.18);
}

/* 菜单（深色） */
.side-menu :deep(.el-menu-item),
.side-menu :deep(.el-sub-menu__title) {
  height: 42px;
  line-height: 42px;
  margin: 3px 0;
  border-radius: 11px;
  font-size: 13.5px;
  color: var(--side-text);
  transition: background var(--dur) var(--ease), color var(--dur) var(--ease);
}
.side-menu :deep(.el-menu-item .el-icon),
.side-menu :deep(.el-sub-menu__title .el-icon) {
  font-size: 17px;
  width: 20px;
}
.side-menu :deep(.el-menu-item:hover),
.side-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}
.side-menu :deep(.el-menu-item.is-active) {
  position: relative;
  color: #fff;
  font-weight: 600;
  background: linear-gradient(90deg, rgba(79, 110, 247, 0.95) 0%, rgba(124, 92, 255, 0.72) 100%);
  box-shadow: 0 10px 22px -14px rgba(79, 110, 247, 1);
}
.side-menu :deep(.el-menu-item.is-active)::before {
  content: "";
  position: absolute;
  left: -10px;
  top: 50%;
  width: 3px;
  height: 20px;
  border-radius: 0 3px 3px 0;
  background: #fff;
  transform: translateY(-50%);
}
.side-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: #fff;
}
/* 折叠态下子菜单只显示父级图标，用同款高亮标出当前所在分组 */
.shell.is-collapse .side-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  background: linear-gradient(90deg, rgba(79, 110, 247, 0.95) 0%, rgba(124, 92, 255, 0.72) 100%);
  box-shadow: 0 10px 22px -14px rgba(79, 110, 247, 1);
}
.side-menu :deep(.el-sub-menu .el-menu) {
  background: transparent;
}
.side-menu :deep(.el-sub-menu .el-menu-item) {
  min-width: 0;
  padding-left: 42px !important;
  height: 38px;
  line-height: 38px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.66);
}
.side-menu :deep(.el-sub-menu .el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.12);
  box-shadow: none;
}
.side-menu :deep(.el-sub-menu .el-menu-item.is-active)::before {
  left: -10px;
  background: var(--brand-400);
}

/* ── 主区域 ── */
.shell-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 62px;
  flex: 0 0 62px;
  padding: 0 20px 0 14px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(12px) saturate(140%);
  border-bottom: 1px solid var(--line);
  z-index: 10;
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.icon-btn {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  color: var(--ink-500);
  cursor: pointer;
  transition: all var(--dur) var(--ease);
}
.icon-btn:hover {
  color: var(--brand-500);
  border-color: var(--brand-300);
  background: var(--brand-50);
}
.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
}
.crumb-root {
  color: var(--ink-300);
}
.crumb-sep {
  color: var(--line-strong);
}
.crumb b {
  font-weight: 650;
  color: var(--ink-900);
  letter-spacing: 0.2px;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.project-select {
  width: 232px;
}
.project-select :deep(.el-select__wrapper) {
  border-radius: 11px;
  background: #fff;
}
.opt-name {
  float: left;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.opt-tag {
  float: right;
  margin-left: 12px;
  font-size: 11px;
  color: var(--ink-300);
}
.topbar-divider {
  width: 1px;
  height: 24px;
  background: var(--line);
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 10px 5px 5px;
  border-radius: 999px;
  cursor: pointer;
  outline: none;
  transition: background var(--dur) var(--ease);
}
.user-chip:hover {
  background: var(--brand-50);
}
.avatar {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: var(--grad-brand);
  box-shadow: 0 8px 18px -10px rgba(79, 110, 247, 0.95);
}
.user-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  max-width: 130px;
}
.user-meta b {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-meta small {
  font-size: 11px;
  color: var(--ink-300);
}
.caret {
  font-size: 12px;
  color: var(--ink-300);
}
.dropdown-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px 8px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 4px;
}
.dropdown-head b {
  font-size: 13.5px;
  color: var(--ink-800);
}
.dropdown-head span {
  font-size: 11.5px;
  color: var(--ink-300);
}

.content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 22px 24px 30px;
  background: radial-gradient(900px 420px at 100% 0%, #eef2ff 0%, transparent 55%),
    radial-gradient(700px 400px at 0% 100%, #f0fdff 0%, transparent 55%), var(--bg-page);
}

@media (max-width: 900px) {
  .crumb-root,
  .crumb-sep {
    display: none;
  }
  .project-select {
    width: 150px;
  }
  .user-meta {
    display: none;
  }
  .content {
    padding: 16px 14px 24px;
  }
}
</style>
