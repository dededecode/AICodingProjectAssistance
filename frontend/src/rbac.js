// RBAC 资源清单 + 菜单树 + 权限判定工具。
// 约定：某资源码只要被任一角色配置过即视为「已启用」；
//       已启用 → 按本人分组授权判定；未启用 → 一律放行（沿用原有 role 硬编码兜底）。
import { useAuthStore } from "./stores/auth";

// 菜单树：MainLayout 渲染用，每项挂 menu:* 资源码
export const MENU_TREE = [
  { code: "menu:dashboard", path: "/", label: "首页" },
  { code: "menu:overview", path: "/overview", label: "项目概览" },
  {
    code: "menu:project-manage",
    label: "项目管理",
    children: [
      { code: "menu:projects", path: "/projects", label: "需求分析" },
      { code: "menu:prototype-images", path: "/prototype-images", label: "原型图/UI图管理" },
      { code: "menu:project-planning", path: "/project-planning", label: "项目计划" },
      { code: "menu:tasks", path: "/tasks", label: "任务管理" },
      { code: "menu:architecture", path: "/architecture", label: "架构设计" },
      { code: "menu:bugs", path: "/bugs", label: "缺陷管理" },
      { code: "menu:operation", path: "/operation", label: "运营管理" },
    ],
  },
  { code: "menu:collaboration", path: "/collaboration", label: "工时登记" },
  { code: "menu:work-groups", path: "/work-groups", label: "工作群" },
  { code: "menu:knowledge", path: "/knowledge", label: "知识库" },
  { code: "menu:llm-wiki", path: "/llm-wiki", label: "Wiki 知识库" },
  { code: "menu:testing", path: "/testing", label: "测试管理" },
  { code: "menu:delivery-docs", path: "/delivery-docs", label: "交付文档" },
  { code: "menu:model-config", path: "/model-config", label: "模型管理" },
  { code: "menu:users", path: "/users", label: "用户管理" },
  { code: "menu:embedding-logs", path: "/embedding-logs", label: "日志管理" },
  { code: "menu:rbac", path: "/role-management", label: "权限组管理" },
];

// 完整资源清单（角色管理页树形勾选用）
export const RESOURCES = [
  {
    type: "menu",
    label: "菜单",
    items: [
      { code: "menu:dashboard", name: "首页" },
      { code: "menu:overview", name: "项目概览" },
      { code: "menu:project-manage", name: "项目管理(父级)" },
      { code: "menu:projects", name: "需求分析" },
      { code: "menu:prototype-images", name: "原型图/UI图管理" },
      { code: "menu:project-planning", name: "项目计划" },
      { code: "menu:tasks", name: "任务管理" },
      { code: "menu:architecture", name: "架构设计" },
      { code: "menu:bugs", name: "缺陷管理" },
      { code: "menu:operation", name: "运营管理" },
      { code: "menu:collaboration", name: "工时登记" },
      { code: "menu:work-groups", name: "工作群" },
      { code: "menu:knowledge", name: "知识库" },
      { code: "menu:llm-wiki", name: "Wiki 知识库" },
      { code: "menu:testing", name: "测试管理" },
      { code: "menu:delivery-docs", name: "交付文档" },
      { code: "menu:model-config", name: "模型管理" },
      { code: "menu:users", name: "用户管理" },
      { code: "menu:embedding-logs", name: "日志管理" },
      { code: "menu:rbac", name: "权限组管理" },
    ],
  },
  {
    type: "btn",
    label: "按钮",
    items: [
      { code: "btn:user-create", name: "用户-新增" },
      { code: "btn:user-edit", name: "用户-编辑" },
      { code: "btn:user-delete", name: "用户-删除" },
      { code: "btn:user-reset-pwd", name: "用户-重置密码" },
      { code: "btn:user-token-regen", name: "用户-重新生成Token" },
      { code: "btn:user-active", name: "用户-启用/禁用" },
      { code: "btn:user-group", name: "用户-分配权限分组" },
      { code: "btn:weekly-delete", name: "周总结-删除" },
      { code: "btn:role-create", name: "角色-新建" },
      { code: "btn:role-delete", name: "角色-删除" },
      { code: "btn:role-save", name: "角色-保存资源" },
      { code: "btn:project-delete", name: "项目-删除" },
      { code: "btn:project-status", name: "项目-变更状态" },
      { code: "btn:project-invite", name: "项目-邀请成员" },
      { code: "btn:project-remove-member", name: "项目-移除成员" },
      { code: "btn:kb-delete", name: "知识库-删除知识" },
      { code: "btn:model-embedding", name: "模型管理-全局嵌入配置" },
      { code: "btn:workgroup-dismiss", name: "工作群-解散群" },
      { code: "btn:workgroup-delete", name: "工作群-彻底删除" },
      { code: "btn:workgroup-message", name: "工作群-解散后发消息" },
    ],
  },
];

// 始终可见的基础资源：未分配权限组的账号登录后至少能看到首页
const ALWAYS_VISIBLE = ["menu:dashboard"];

// 权限判定（白名单制）：除 admin（始终全权）外，权限完全由「权限组」决定——
// 本人分组勾选过的码可见，未勾选的一律不可见，不再有基于账号角色(role)的默认权限。
export function hasPerm(code) {
  const auth = useAuthStore();
  if (auth.user?.role === "admin" || auth.user?.is_superuser) return true;
  if (ALWAYS_VISIBLE.includes(code)) return true;
  const allowed = auth.allowedCodes || [];
  return allowed.includes(code);
}
