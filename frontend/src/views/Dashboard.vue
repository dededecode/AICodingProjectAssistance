<template>
  <div class="workbench">
    <!-- ── 欢迎横幅 ── -->
    <section class="hero ds-in">
      <div class="hero__deco" aria-hidden="true">
        <span class="ring ring--1" />
        <span class="ring ring--2" />
        <span class="ring ring--3" />
        <span class="glow" />
      </div>

      <div class="hero__main">
        <span class="ds-ai-chip"><el-icon><MagicStick /></el-icon> AI 工作台</span>
        <h1>{{ greeting }}，{{ auth.displayName }}</h1>
        <p class="hero__sub">
          <span>{{ todayText }}</span>
          <i />
          <span>当前项目：{{ projectName }}</span>
          <i />
          <span>{{ roleLabel }}</span>
        </p>

        <div class="hero__actions">
          <el-button
            v-for="a in actions"
            :key="a.path"
            :type="a.primary ? 'primary' : 'default'"
            @click="go(a.path)"
          >
            <el-icon><component :is="a.icon" /></el-icon>
            <span>{{ a.label }}</span>
          </el-button>
        </div>
      </div>

      <div class="hero__panel">
        <div class="hero__panel-title">我的工时</div>
        <div class="hero__nums">
          <div>
            <b class="ds-num">{{ fmt(stat.my?.week_hours) }}<small>h</small></b>
            <span>本周</span>
          </div>
          <div class="sep" />
          <div>
            <b class="ds-num">{{ fmt(stat.my?.month_hours) }}<small>h</small></b>
            <span>本月</span>
          </div>
        </div>
        <div class="hero__panel-foot">
          本周自 {{ stat.my?.week_start || "-" }} 起 · 本月自 {{ stat.my?.month_start || "-" }} 起
        </div>
      </div>
    </section>

    <!-- ── 概览指标 ── -->
    <section class="ds-grid ds-grid--4 ds-in ds-in-1">
      <div v-for="k in kpis" :key="k.label" class="ds-stat">
        <span class="ds-stat__icon" :class="k.tone"><el-icon><component :is="k.icon" /></el-icon></span>
        <div class="ds-stat__body">
          <div class="ds-stat__value">{{ k.value }}<small v-if="k.unit">{{ k.unit }}</small></div>
          <div class="ds-stat__label">{{ k.label }}</div>
        </div>
      </div>
    </section>

    <!-- ── 全流程导航 ── -->
    <section class="ds-in ds-in-2">
      <h3 class="ds-section-title">项目全流程</h3>
      <div class="flow">
        <button
          v-for="(s, i) in flowStages"
          :key="s.path"
          class="flow-step"
          type="button"
          @click="go(s.path)"
        >
          <span class="flow-step__idx">{{ String(i + 1).padStart(2, "0") }}</span>
          <span class="flow-step__icon"><el-icon><component :is="s.icon" /></el-icon></span>
          <b>{{ s.label }}</b>
          <small>{{ s.desc }}</small>
          <em v-if="s.ai" class="flow-step__ai">AI</em>
        </button>
      </div>
    </section>

    <!-- ── 团队工时 ── -->
    <section class="ds-grid ds-grid--2 ds-in ds-in-3">
      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <span>团队本周工时 Top 5</span>
            <span class="ds-chip"><el-icon><Clock /></el-icon> 单位：小时</span>
          </div>
        </template>
        <div v-if="teamWeek.length" class="bars">
          <div v-for="(m, i) in teamWeek" :key="m.user_id || m.username" class="bar-row">
            <span class="bar-rank" :class="{ 'is-top': i === 0 }">{{ i + 1 }}</span>
            <span class="bar-name">{{ m.username }}</span>
            <span class="bar-track"><i :style="{ width: barWidth(m.hours) }" /></span>
            <b class="bar-val ds-num">{{ fmt(m.hours) }}</b>
          </div>
        </div>
        <el-empty v-else description="本周暂无工时记录" :image-size="76" />
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <span>团队本月工时</span>
            <span class="ds-chip"><el-icon><DataAnalysis /></el-icon> 共 {{ teamMonth.length }} 人</span>
          </div>
        </template>
        <el-table :data="teamMonth" size="small" stripe max-height="310">
          <el-table-column type="index" label="#" width="52" align="center" />
          <el-table-column prop="username" label="成员" min-width="120" show-overflow-tooltip />
          <el-table-column label="本月工时" width="150">
            <template #default="{ row }">
              <div class="cell-bar">
                <span class="cell-bar__track"><i :style="{ width: barWidth(row.hours) }" /></span>
                <b class="ds-num">{{ fmt(row.hours) }} h</b>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  Calendar,
  Clock,
  Cpu,
  DataAnalysis,
  Document,
  FolderOpened,
  List,
  MagicStick,
  Memo,
  Odometer,
  TrendCharts,
  UserFilled,
} from "@element-plus/icons-vue";
import { useAuthStore } from "../stores/auth";
import { useProjectStore } from "../stores/project";
import { workLogDashboard } from "../api/collaboration";
import { hasPerm } from "../rbac";

const router = useRouter();
const auth = useAuthStore();
const projectStore = useProjectStore();
const stat = ref({});

const fmt = (v) => (v === null || v === undefined ? "-" : Number(v).toFixed(Number.isInteger(Number(v)) ? 0 : 1));

const greeting = computed(() => {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 12) return "早上好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
});

const todayText = computed(() => {
  const d = new Date();
  const week = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][d.getDay()];
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${week}`;
});

const roleLabel = computed(() => {
  const map = { admin: "管理员", manager: "项目经理", developer: "开发", tester: "测试", guest: "访客" };
  return map[auth.user?.role] || auth.user?.role || "";
});

const projectName = computed(() => projectStore.current?.name || "未选择项目");

const teamWeek = computed(() => {
  const rows = [...(stat.value.team_week || [])];
  rows.sort((a, b) => b.hours - a.hours);
  return rows.slice(0, 5);
});
const teamMonth = computed(() => {
  const rows = [...(stat.value.team_month || [])];
  rows.sort((a, b) => b.hours - a.hours);
  return rows;
});
const maxHours = computed(() =>
  Math.max(1, ...teamMonth.value.map((r) => Number(r.hours) || 0), ...teamWeek.value.map((r) => Number(r.hours) || 0))
);
const barWidth = (h) => `${Math.max(4, Math.round(((Number(h) || 0) / maxHours.value) * 100))}%`;

const kpis = computed(() => [
  {
    label: "本周工时",
    value: fmt(stat.value.my?.week_hours),
    unit: " h",
    icon: Clock,
    tone: "",
  },
  {
    label: "本月工时",
    value: fmt(stat.value.my?.month_hours),
    unit: " h",
    icon: Calendar,
    tone: "is-violet",
  },
  {
    label: "团队本周合计",
    value: fmt((stat.value.team_week || []).reduce((s, r) => s + (Number(r.hours) || 0), 0)),
    unit: " h",
    icon: TrendCharts,
    tone: "is-cyan",
  },
  {
    label: "团队本月人数",
    value: teamMonth.value.length,
    unit: " 人",
    icon: UserFilled,
    tone: "is-green",
  },
]);

// 快捷入口：按 RBAC 过滤，避免出现点进去被弹回的菜单
const actions = computed(() =>
  [
    { label: "需求分析", path: "/projects", icon: Document, code: "menu:projects", primary: true },
    { label: "任务管理", path: "/tasks", icon: List, code: "menu:tasks" },
    { label: "工时登记", path: "/collaboration", icon: Clock, code: "menu:collaboration" },
    { label: "Wiki 知识库", path: "/llm-wiki", icon: Memo, code: "menu:llm-wiki" },
  ].filter((a) => hasPerm(a.code))
);

const flowStages = computed(() =>
  [
    { label: "需求分析", desc: "上传文档 · AI 完整度检测", path: "/projects", icon: Document, code: "menu:projects", ai: true },
    { label: "项目计划", desc: "权重拆分 · AI 生成任务", path: "/project-planning", icon: Calendar, code: "menu:project-planning", ai: true },
    { label: "架构设计", desc: "概设文档 · 建表 SQL", path: "/architecture", icon: Cpu, code: "menu:architecture", ai: true },
    { label: "开发实施", desc: "任务派单 · 工时登记", path: "/tasks", icon: List, code: "menu:tasks" },
    { label: "项目测试", desc: "用例派单 · 缺陷跟踪", path: "/testing", icon: Odometer, code: "menu:testing", ai: true },
    { label: "项目交付", desc: "交付文档 · 测试报告", path: "/delivery-docs", icon: FolderOpened, code: "menu:delivery-docs" },
  ].filter((s) => hasPerm(s.code))
);

function go(path) {
  router.push(path);
}

onMounted(async () => {
  try {
    const { data } = await workLogDashboard();
    stat.value = data;
  } catch (e) {
    // 忽略统计加载失败
  }
  projectStore.ensureLoaded().catch(() => {});
});
</script>

<style scoped>
.workbench {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ── 欢迎横幅 ── */
.hero {
  position: relative;
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 28px;
  border-radius: var(--r-lg);
  overflow: hidden;
  color: #fff;
  background: radial-gradient(700px 320px at 12% 0%, rgba(79, 110, 247, 0.55), transparent 65%),
    radial-gradient(600px 320px at 88% 120%, rgba(34, 211, 238, 0.35), transparent 62%),
    linear-gradient(120deg, #101a2e 0%, #131c33 55%, #0d1626 100%);
  background-color: #101a2e;
  box-shadow: var(--sh-md);
}
.hero__deco {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.12);
}
.ring--1 {
  width: 380px;
  height: 380px;
  right: -110px;
  top: -150px;
}
.ring--2 {
  width: 260px;
  height: 260px;
  right: -50px;
  top: -90px;
  border-color: rgba(255, 255, 255, 0.18);
}
.ring--3 {
  width: 150px;
  height: 150px;
  right: 25px;
  top: -25px;
  background: radial-gradient(circle, rgba(79, 110, 247, 0.45), transparent 70%);
  border-color: rgba(255, 255, 255, 0.22);
}
.glow {
  position: absolute;
  width: 320px;
  height: 320px;
  left: 44%;
  bottom: -220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124, 92, 255, 0.5), transparent 68%);
  filter: blur(20px);
}
.hero__main {
  position: relative;
  z-index: 1;
  min-width: 0;
  flex: 1;
}
.hero__main h1 {
  margin: 14px 0 0;
  font-size: 25px;
  font-weight: 750;
  letter-spacing: -0.4px;
}
.hero__sub {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: 10px 0 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.68);
}
.hero__sub i {
  width: 1px;
  height: 12px;
  background: rgba(255, 255, 255, 0.2);
}
.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}
.hero__actions :deep(.el-button) {
  height: 38px;
  padding: 0 16px;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.16);
  color: #fff;
}
.hero__actions :deep(.el-button:hover) {
  background: rgba(255, 255, 255, 0.18);
  border-color: rgba(255, 255, 255, 0.28);
  color: #fff;
}
.hero__actions :deep(.el-button--primary) {
  background-image: var(--grad-brand);
  border-color: transparent;
}
.hero__actions :deep(.el-button .el-icon) {
  margin-right: 6px;
}

.hero__panel {
  position: relative;
  z-index: 1;
  width: 290px;
  flex: 0 0 290px;
  align-self: center;
  padding: 18px 20px;
  border-radius: var(--r-md);
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(10px);
}
.hero__panel-title {
  font-size: 12.5px;
  color: rgba(255, 255, 255, 0.65);
  letter-spacing: 0.3px;
}
.hero__nums {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-top: 12px;
}
.hero__nums b {
  display: block;
  font-size: 27px;
  font-weight: 750;
  line-height: 1.1;
  letter-spacing: -0.6px;
}
.hero__nums b small {
  font-size: 13px;
  font-weight: 600;
  margin-left: 2px;
  opacity: 0.7;
}
.hero__nums span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
.hero__nums .sep {
  width: 1px;
  height: 34px;
  background: rgba(255, 255, 255, 0.16);
}
.hero__panel-foot {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 11.5px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.5);
}

/* ── 流程导航 ── */
.flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(178px, 1fr));
  gap: 12px;
}
.flow-step {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 16px 16px 15px;
  text-align: left;
  border-radius: var(--r-md);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--sh-xs);
  cursor: pointer;
  font-family: inherit;
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease),
    border-color var(--dur) var(--ease);
}
.flow-step:hover {
  transform: translateY(-3px);
  border-color: var(--brand-200);
  box-shadow: var(--sh-md);
}
.flow-step__idx {
  position: absolute;
  top: 12px;
  right: 14px;
  font-size: 20px;
  font-weight: 800;
  color: var(--el-fill-color-dark);
  letter-spacing: -0.5px;
}
.flow-step__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  margin-bottom: 6px;
  border-radius: 11px;
  font-size: 18px;
  color: var(--brand-500);
  background: var(--brand-50);
}
.flow-step:hover .flow-step__icon {
  color: #fff;
  background-image: var(--grad-brand);
  box-shadow: var(--sh-brand);
}
.flow-step b {
  font-size: 14px;
  font-weight: 650;
  color: var(--ink-800);
}
.flow-step small {
  font-size: 12px;
  line-height: 1.5;
  color: var(--ink-300);
}
.flow-step__ai {
  position: absolute;
  bottom: 14px;
  right: 14px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-style: normal;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #fff;
  background-image: var(--grad-ai);
}

/* ── 卡片头 / 工时可视化 ── */
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.bars {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 4px 0 6px;
}
.bar-row {
  display: grid;
  grid-template-columns: 22px minmax(72px, 108px) 1fr 58px;
  align-items: center;
  gap: 10px;
}
.bar-rank {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--ink-400);
  background: var(--el-fill-color-light);
}
.bar-rank.is-top {
  color: #fff;
  background-image: var(--grad-brand);
}
.bar-name {
  font-size: 13px;
  color: var(--ink-600);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar-track {
  height: 9px;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  overflow: hidden;
}
.bar-track i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background-image: var(--grad-ai);
  animation: grow 0.6s var(--ease) both;
}
@keyframes grow {
  from {
    transform: scaleX(0);
    transform-origin: left;
  }
  to {
    transform: scaleX(1);
    transform-origin: left;
  }
}
.bar-val {
  text-align: right;
  font-size: 13px;
  color: var(--ink-700);
}
.cell-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cell-bar__track {
  flex: 1;
  height: 7px;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  overflow: hidden;
}
.cell-bar__track i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background-image: var(--grad-brand);
}
.cell-bar b {
  width: 48px;
  text-align: right;
  font-size: 12.5px;
  color: var(--ink-600);
}

@media (max-width: 1080px) {
  .hero {
    flex-direction: column;
  }
  .hero__panel {
    width: 100%;
    flex: none;
  }
}
</style>
