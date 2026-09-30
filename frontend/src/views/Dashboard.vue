<template>
  <div>
    <el-card shadow="never">
      <h3 style="margin: 0">欢迎使用 AICodingProjectAssistance（AICoding项目辅助、管理系统）</h3>
      <p style="color: #666; margin-top: 8px">
        当前用户：{{ auth.displayName }}（{{ roleLabel }}）
      </p>
    </el-card>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>我的工时</b></template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="本周工时">
              <b style="color: #409eff">{{ stat.my?.week_hours ?? "-" }} h</b>
            </el-descriptions-item>
            <el-descriptions-item label="本月工时">
              <b style="color: #67c23a">{{ stat.my?.month_hours ?? "-" }} h</b>
            </el-descriptions-item>
          </el-descriptions>
          <div style="color: #909399; font-size: 12px; margin-top: 8px">
            本周自 {{ stat.my?.week_start }} 起 · 本月自 {{ stat.my?.month_start }} 起
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>团队人员周工时 Top</b></template>
          <el-table :data="teamWeek" size="small" stripe>
            <el-table-column prop="username" label="成员" />
            <el-table-column prop="hours" label="本周工时(h)" width="120" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header><b>团队人员月工时</b></template>
      <el-table :data="teamMonth" size="small" stripe>
        <el-table-column prop="username" label="成员" />
        <el-table-column prop="hours" label="本月工时(h)" width="140" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useAuthStore } from "../stores/auth";
import { workLogDashboard } from "../api/collaboration";

const auth = useAuthStore();
const stat = ref({});
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

const roleLabel = computed(() => {
  const map = { admin: "管理员", manager: "项目经理", developer: "开发", tester: "测试", guest: "访客" };
  return map[auth.user?.role] || auth.user?.role || "";
});

onMounted(async () => {
  try {
    const { data } = await workLogDashboard();
    stat.value = data;
  } catch (e) {
    // 忽略统计加载失败
  }
});
</script>
