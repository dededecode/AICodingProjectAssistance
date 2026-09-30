import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { hasPerm } from "../rbac";

const routes = [
  {
    path: "/login",
    name: "login",
    component: () => import("../views/Login.vue"),
    meta: { public: true },
  },
  {
    path: "/",
    component: () => import("../layouts/MainLayout.vue"),
    children: [
      {
        path: "",
        name: "dashboard",
        component: () => import("../views/Dashboard.vue"),
        meta: { title: "首页", resource: "menu:dashboard" },
      },
      {
        path: "overview",
        name: "overview",
        component: () => import("../views/ProjectOverview.vue"),
        meta: { title: "项目概览", resource: "menu:overview" },
      },
      {
        path: "projects",
        name: "projects",
        component: () => import("../views/Projects.vue"),
        meta: { title: "需求分析", resource: "menu:projects" },
      },
      {
        path: "prototype-images",
        name: "prototype-images",
        component: () => import("../views/PrototypeImages.vue"),
        meta: { title: "原型图/UI图管理", resource: "menu:prototype-images" },
      },
      {
        path: "project-planning",
        name: "project-planning",
        component: () => import("../views/ProjectPlanning.vue"),
        meta: { title: "项目计划", resource: "menu:project-planning" },
      },
      {
        path: "tasks",
        name: "tasks",
        component: () => import("../views/TaskManagement.vue"),
        meta: { title: "任务管理", resource: "menu:tasks" },
      },
      {
        path: "architecture",
        name: "architecture",
        component: () => import("../views/Architecture.vue"),
        meta: { title: "架构设计", resource: "menu:architecture" },
      },
      {
        path: "bugs",
        name: "bugs",
        component: () => import("../views/BugManagement.vue"),
        meta: { title: "缺陷管理", resource: "menu:bugs" },
      },
      {
        path: "operation",
        name: "operation",
        component: () => import("../views/OperationManagement.vue"),
        meta: { title: "运营管理", resource: "menu:operation" },
      },
      {
        path: "projects/:id",
        name: "project-detail",
        component: () => import("../views/ProjectDetail.vue"),
        meta: { title: "项目详情", resource: "menu:projects" },
      },
      {
        path: "projects/:id/requirements",
        name: "project-requirements",
        component: () => import("../views/Requirements.vue"),
        meta: { title: "需求分析", resource: "menu:projects" },
      },
      {
        path: "collaboration",
        name: "collaboration",
        component: () => import("../views/Collaboration.vue"),
        meta: { title: "工时登记", resource: "menu:collaboration" },
      },
      {
        path: "work-groups",
        name: "work-groups",
        component: () => import("../views/WorkGroups.vue"),
        meta: { title: "工作群", resource: "menu:work-groups" },
      },
      {
        path: "knowledge",
        name: "knowledge",
        component: () => import("../views/KnowledgeBase.vue"),
        meta: { title: "知识库", resource: "menu:knowledge" },
      },
      {
        path: "llm-wiki",
        name: "llm-wiki",
        component: () => import("../views/LlmWiki.vue"),
        meta: { title: "Wiki 知识库", resource: "menu:llm-wiki" },
      },
      {
        path: "testing",
        name: "testing",
        component: () => import("../views/Testing.vue"),
        meta: { title: "测试管理", resource: "menu:testing" },
      },
      {
        path: "delivery-docs",
        name: "delivery-docs",
        component: () => import("../views/DeliveryDocs.vue"),
        meta: { title: "交付文档", resource: "menu:delivery-docs" },
      },
      {
        path: "model-config",
        name: "model-config",
        component: () => import("../views/ModelConfig.vue"),
        meta: { title: "模型管理", resource: "menu:model-config" },
      },
      {
        path: "users",
        name: "users",
        component: () => import("../views/UserManagement.vue"),
        meta: { title: "用户管理", resource: "menu:users" },
      },
      {
        path: "embedding-logs",
        name: "embedding-logs",
        component: () => import("../views/LogManagement.vue"),
        meta: { title: "日志管理", resource: "menu:embedding-logs" },
      },
      {
        path: "role-management",
        name: "role-management",
        component: () => import("../views/RoleManagement.vue"),
        meta: { title: "权限组管理", resource: "menu:rbac" },
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 登录守卫 + RBAC 资源守卫
router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: "login" };
  }
  if (to.meta.resource && !hasPerm(to.meta.resource)) {
    return { name: "dashboard" };
  }
  if (to.name === "login" && auth.isAuthenticated) {
    return { name: "dashboard" };
  }
  return true;
});

export default router;
