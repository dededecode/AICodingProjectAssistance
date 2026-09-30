<template>
  <div class="overview-page">
    <!-- 顶部横幅 -->
    <div class="banner">
      <div class="banner-text">
        <h2>🏰 项目冒险之旅</h2>
        <p>跟随小 AI，一起走完项目从需求到运营的冒险旅程吧！</p>
      </div>
      <div></div>
    </div>

    <!-- 旅程地图 -->
    <div class="map">
      <div class="road">
        <template v-for="(stage, i) in STAGES" :key="stage.key">
          <div v-if="i > 0" class="road-segment" :class="segmentClass(i)" />
          <div
            class="stage-node"
            :class="[stageState(i), { clickable: i <= currentIndex }]"
            @click="openStage(stage, i)"
          >
            <div class="icon-wrap">
              <div class="icon">{{ stage.icon }}</div>
              <div v-if="stageState(i) === 'active'" class="cheer">
                <div class="bubble">加油！</div>
                <div class="hero">🏃</div>
              </div>
            </div>
            <div class="label">{{ stage.label }}</div>
            <div class="state-text">{{ stateText(i) }}</div>
          </div>
        </template>
      </div>

      <div class="legend">
        <span><i class="dot done" />已完成（点击查看数据）</span>
        <span><i class="dot active" />进行中</span>
        <span><i class="dot todo" />未开始</span>
      </div>
    </div>

    <!-- 当前环节工作台 -->
    <div class="workbench" v-if="activeStage">
      <div class="wb-head">
        <span class="wb-icon">{{ activeStage.icon }}</span>
        <span>当前环节工作台 · {{ activeStage.label }}</span>
        <el-button size="small" text style="margin-left: auto" @click="loadWB">刷新</el-button>
      </div>

      <!-- 需求分析 -->
      <div v-if="activeStage.key === 'requirement'" class="wb-body" v-loading="wbLoading">
        <div class="wb-toolbar">
          <el-upload :auto-upload="false" :show-file-list="false" :on-change="onReqFile">
            <el-button :loading="uploading">上传需求文档</el-button>
          </el-upload>
          <span class="hint">支持 .docx / .xlsx / .md</span>
        </div>
        <el-table :data="reqs" size="small" stripe>
          <el-table-column prop="title" label="文档" min-width="150" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">{{ row.is_confirmed ? "已确认" : row.analysis_result ? "已分析" : "未分析" }}</template>
          </el-table-column>
          <el-table-column label="评分" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="(row.analysis_result?.overall_score ?? -1) >= 70 ? 'success' : 'danger'">
                {{ row.analysis_result?.overall_score ?? "-" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170">
            <template #default="{ row }">
              <el-button size="small" text type="warning" :disabled="row.is_confirmed" :loading="analyzingId === row.id" @click="analyzeReq(row)">AI 分析</el-button>
              <el-button size="small" text type="success" :disabled="row.is_confirmed || !row.analysis_result" :loading="confirmingId === row.id" @click="confirmReq(row)">确认入库</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 计划安排 -->
      <div v-if="activeStage.key === 'planning'" class="wb-body" v-loading="wbLoading">
        <div class="wb-toolbar">
          <el-button type="primary" :loading="planLoading" @click="genPlan">AI 生成项目计划</el-button>
          <span class="hint">基于项目成员与需求文档自动生成计划</span>
        </div>
        <el-table :data="plans" size="small" stripe>
          <el-table-column prop="name" label="计划" min-width="110" />
          <el-table-column label="周期" width="170">
            <template #default="{ row }">{{ row.start_date }} ~ {{ row.launch_date }}</template>
          </el-table-column>
          <el-table-column label="成员" min-width="120">
            <template #default="{ row }">{{ (row.members || []).map((m) => m.username).join("、") }}</template>
          </el-table-column>
          <el-table-column label="任务数" width="70">
            <template #default="{ row }">{{ row.task_count ?? 0 }}</template>
          </el-table-column>
          <el-table-column label="操作" width="230">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="previewPlan(row)">查看</el-button>
              <el-button size="small" text type="warning" :loading="regeneratingId === row.id" @click="openRegen(row)">重新生成</el-button>
              <el-button size="small" text type="success" :loading="genTaskId === row.id" @click="genTasks(row)">生成任务</el-button>
              <el-button size="small" text type="danger" @click="removePlan(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 架构设计 -->
      <div v-if="activeStage.key === 'architecture'" class="wb-body" v-loading="wbLoading">
        <div class="wb-toolbar">
          <el-button type="primary" @click="openGenDialog">生成架构设计</el-button>
          <span class="hint">两步流式生成：架构概设文档 → 数据库 SQL</span>
        </div>
        <el-table :data="designs" size="small" stripe>
          <el-table-column label="编号" width="70">
            <template #default="{ $index }">#{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column prop="frontend_stack" label="前端技术栈" min-width="120" show-overflow-tooltip />
          <el-table-column prop="backend_stack" label="后端技术栈" min-width="120" show-overflow-tooltip />
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="viewDesign(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 项目实施 -->
      <div v-if="activeStage.key === 'developing'" class="wb-body" v-loading="wbLoading">
        <div class="wb-toolbar">
          <el-button type="primary" @click="router.push('/tasks')">前往任务管理</el-button>
          <span class="hint">可去任务管理页维护任务与工时</span>
        </div>
        <el-tabs v-model="devTab" class="dev-tabs">
          <!-- 任务列表 -->
          <el-tab-pane label="任务列表" name="list">
            <div class="wb-stats">
              <div class="stat" v-for="(v, k) in devStats.by_status || {}" :key="k">
                <b>{{ v }}</b><span>{{ statusLabel(k) }}</span>
              </div>
              <div class="stat"><b>{{ devStats.total_tasks ?? 0 }}</b><span>任务总数</span></div>
              <div class="stat"><b>{{ devStats.hours ?? 0 }}</b><span>总工时(h)</span></div>
            </div>
            <el-table :data="devTasks" size="small" stripe>
              <el-table-column prop="title" label="任务" min-width="140" show-overflow-tooltip />
              <el-table-column prop="module" label="模块" width="100" />
              <el-table-column prop="assignee_name" label="负责人" width="90" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="devStatusType(row.status)">{{ row.status_display }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- 甘特图（基于任务列表数据） -->
          <el-tab-pane label="甘特图" name="gantt">
            <template v-if="gantt.dated.length || gantt.undated.length">
              <div class="gantt-wrap" :class="{ 'gantt-fs': ganttFullscreen }">
                <div class="gantt-bar">
                  <div class="gantt-legend">
                    <span v-for="s in ganttStatuses" :key="s.value"><i class="g-dot" :style="{ background: s.color }" />{{ s.label }}</span>
                    <span class="gantt-scale">按{{ scaleLabel }}展示</span>
                  </div>
                  <div class="gantt-bar-right">
                    <span class="gantt-hint">悬停任务条查看详情（含前置依赖）· 橙线为今天</span>
                    <el-button size="small" @click="toggleGanttFullscreen">{{ ganttFullscreen ? "退出全屏" : "全屏" }}</el-button>
                  </div>
                </div>
                <el-alert
                  v-if="columns.truncated"
                  type="warning"
                  :closable="false"
                  :title="`日期跨度超出可展示范围，已按${scaleLabel}展示前 ${columns.cols.length} 列；${ganttVisible.overflow.length} 个任务未展示`"
                  style="margin-bottom: 8px"
                />
                <div v-if="columns.cols.length" class="gantt-scroll">
                  <div class="gantt" :style="[{ width: ganttWidth + 'px' }, ganttLinesStyle]">
                    <!-- 日期轴与任务行必须绑定同一份列模板（ganttGridStyle），否则轴与条会整体错位 -->
                    <div class="g-axis g-months" :style="ganttGridStyle">
                      <div v-for="m in topAxis" :key="m.key" class="g-month" :style="axisCell(m.start, m.span)">{{ m.label }}</div>
                    </div>
                    <div class="g-axis g-days" :style="ganttGridStyle">
                      <div v-for="(c, i) in columns.cols" :key="i" class="g-day" :style="axisCell(i, 1)">{{ colLabel(c) }}</div>
                    </div>
                    <div v-for="t in ganttVisible.inRange" :key="t.id" class="g-row" :style="ganttGridStyle">
                      <div class="g-label">
                        <div class="g-title" :title="`#${t.id} ${t.title}`">#{{ t.id }}{{ t.title }}</div>
                        <div class="g-sub">{{ t.assignee_name || "未指派" }}<template v-if="t.module"> · {{ t.module }}</template></div>
                      </div>
                      <div class="g-cell" :style="barCell(t)">
                        <el-tooltip :content="ganttTip(t)" placement="top" :show-after="350" popper-class="gantt-tip">
                          <div class="g-bar" :style="{ background: ganttColor(t.status) }"></div>
                        </el-tooltip>
                      </div>
                    </div>
                    <div v-if="todayX >= 0" class="g-today" :style="{ left: LABEL_W + todayX + 'px', top: AXIS_H + 'px', height: ganttVisible.inRange.length * ROW_H + 'px' }">
                      <span>今天</span>
                    </div>
                  </div>
                </div>
                <div v-if="gantt.undated.length" class="g-undated">
                  <span class="g-undated-hint">以下 {{ gantt.undated.length }} 个任务缺少计划起止日期，未在甘特图中展示：</span>
                  <el-tag v-for="t in gantt.undated" :key="t.id" size="small" style="margin: 2px 6px 2px 0">{{ t.title }}</el-tag>
                </div>
                <div v-if="ganttVisible.overflow.length" class="g-undated">
                  <span class="g-undated-hint">以下 {{ ganttVisible.overflow.length }} 个任务日期超出可展示范围：</span>
                  <el-tag v-for="t in ganttVisible.overflow" :key="t.id" size="small" type="warning" style="margin: 2px 6px 2px 0">{{ t.title }}</el-tag>
                </div>
              </div>
            </template>
            <el-empty v-else description="暂无任务数据" />
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 项目交付 -->
      <div v-if="activeStage.key === 'delivery'" class="wb-body" v-loading="wbLoading">
        <div class="wb-toolbar">
          <el-button type="success" :loading="reportLoading" @click="genReport">生成测试报告</el-button>
          <span class="hint">通过率≥90% 时项目自动进入「项目交付」</span>
        </div>
        <el-table :data="deliveries" size="small" stripe>
          <el-table-column prop="title" label="文档" min-width="160" show-overflow-tooltip />
          <el-table-column prop="doc_type" label="类型" width="120" />
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="viewDelivery(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 运营 -->
      <div v-if="activeStage.key === 'operation'" class="wb-body" v-loading="wbLoading">
        <div class="wb-toolbar">
          <el-button type="primary" @click="router.push('/operation')">前往运营管理</el-button>
          <el-button type="success" :loading="opIngesting" @click="opIngest">知识入库</el-button>
          <span class="hint">记录迭代需求 / 优化需求 / 业务变更 / 用户反馈，并纳入知识库</span>
        </div>
        <div class="wb-stats">
          <div class="stat"><b>{{ opStats.total ?? 0 }}</b><span>记录总数</span></div>
          <div class="stat"><b>{{ opStats.open ?? 0 }}</b><span>未关闭</span></div>
          <div class="stat" v-for="(v, k) in opStats.by_category || {}" :key="k">
            <b>{{ v }}</b><span>{{ categoryLabel(k) }}</span>
          </div>
        </div>
        <div class="wb-stats metric" v-if="Object.keys(opMetricSummary).length">
          <div class="stat" v-for="(m, k) in opMetricSummary" :key="k">
            <b>{{ m.value }}</b><span>{{ metricLabel(k) }} · {{ m.month }}</span>
          </div>
        </div>
        <el-table :data="opItems" size="small" stripe>
          <el-table-column label="类型" width="90">
            <template #default="{ row }"><el-tag size="small" type="primary">{{ row.category_display }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column prop="requestor" label="提出人" width="100" />
          <el-table-column prop="status_display" label="状态" width="90" />
        </el-table>
      </div>
    </div>

    <!-- 环节数据弹窗 -->
    <el-dialog v-model="stageVisible" :title="`${currentStage?.label} · 数据与文档`" width="820px" top="4vh" class="stage-dialog">
      <div v-loading="stageLoading" style="min-height: 200px">
        <template v-if="stageData">
          <div v-if="stageData.type === 'summary' || (stageData.type === 'table' && stageData.showSummary)" class="summary-cards">
            <div class="card"><div class="num">{{ stageData.summary.tasks }}</div><div class="lbl">任务总数</div></div>
            <div class="card" v-for="(v, k) in stageData.summary.byStatus" :key="k"><div class="num">{{ v }}</div><div class="lbl">{{ statusLabel(k) }}</div></div>
            <div class="card"><div class="num">{{ stageData.summary.hours }}</div><div class="lbl">登记总工时(h)</div></div>
          </div>
          <el-table v-else-if="stageData.type === 'table'" :data="stageData.items" stripe size="small">
            <el-table-column v-for="col in stageData.columns" :key="col.key" :prop="col.key" :label="col.label" min-width="110" show-overflow-tooltip>
              <template v-if="col.key === 'score'" #default="{ row }">
                <el-tag :type="(row.score ?? -1) >= 70 ? 'success' : 'danger'" size="small">{{ row.score ?? "-" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="previewItem(row)">预览</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="运营环节功能建设中，敬请期待～" />
        </template>
        <el-empty v-else-if="!stageLoading" description="该环节暂无数据" />
      </div>
    </el-dialog>

    <!-- 架构生成弹窗（两步流式） -->
    <el-dialog v-model="archGenVisible" title="生成项目架构设计" width="80%" top="2vh" class="stage-dialog">
      <el-row :gutter="12">
        <el-col :span="12"><el-form-item label="前端技术栈"><el-input v-model="archForm.frontend_stack" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="后端技术栈"><el-input v-model="archForm.backend_stack" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="框架底座">
            <el-select v-model="archForm.base_framework" style="width: 100%">
              <el-option label="无（自研）" value="" />
              <el-option label="Ruoyi-Vue-Plus（5.x）" value="ruoyi-vue-plus" />
              <el-option label="Smart-Admin" value="smart-admin" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="数据库类型">
            <el-select v-model="archForm.db_type" style="width: 100%">
              <el-option label="MySQL" value="mysql" /><el-option label="PostgreSQL" value="postgresql" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="约束/规则">
        <el-input v-model="archForm.constraints" type="textarea" :rows="2" placeholder="如：必须私有化部署、强制使用某中间件/网关、并发/性能指标要求等（可选，随提示词发送给 AI）" />
      </el-form-item>
      <el-form-item label="其它补充">
        <el-input v-model="archForm.extra" type="textarea" :rows="2" placeholder="其它需要 AI 参考的信息（可选，随提示词发送给 AI）" />
      </el-form-item>
      <el-divider content-position="left">第一步：架构概设文档</el-divider>
      <div class="step-row">
        <el-button :loading="archStreaming.doc" :disabled="archStreaming.sql" @click="archGenStep('design_doc')">
          {{ archDoc ? "重新生成文档" : "生成架构概设文档" }}
        </el-button>
        <span class="hint">流式输出，边生成边展示</span>
      </div>
      <el-input v-model="archDoc" type="textarea" :rows="10" class="edit-area" />
      <el-divider content-position="left">第二步：数据库 SQL</el-divider>
      <div class="step-row">
        <el-button :loading="archStreaming.sql" :disabled="archStreaming.doc || !archDoc" @click="archGenStep('sql')">
          {{ archSql ? "重新生成 SQL" : "生成数据库 SQL" }}
        </el-button>
        <span class="hint">流式输出，生成后可直接修改</span>
      </div>
      <el-input v-model="archSql" type="textarea" :rows="10" class="edit-area sql" />
      <template #footer>
        <el-button @click="archGenVisible = false">取消</el-button>
        <el-button type="primary" :loading="archSaving" :disabled="archStreaming.doc || archStreaming.sql || !archDoc" @click="archConfirmSave">确认保存</el-button>
      </template>
    </el-dialog>

    <!-- 文档/详情预览弹窗 -->
    <el-dialog v-model="previewVisible" :title="preview?.title" width="72%" top="4vh" class="stage-dialog">
      <template v-if="preview">
        <div v-if="preview.kind === 'analysis'">
          <div class="analysis-head">
            <span class="item">完整度评分：<b :style="{ color: preview.overall >= 70 ? '#34d399' : '#f87171' }">{{ preview.overall }}</b></span>
            <el-tag :type="preview.verdict === 'passed' ? 'success' : 'warning'">{{ preview.verdict === 'passed' ? '建议通过' : '需补充完善' }}</el-tag>
            <el-button type="primary" text @click="openFile(preview.fileUrl)">📄 打开原始文档</el-button>
          </div>
          <el-table :data="preview.elements" size="small" stripe>
            <el-table-column prop="name" label="需求要素" min-width="140" />
            <el-table-column prop="score" label="评分" width="80" />
            <el-table-column prop="comment" label="说明" min-width="260" show-overflow-tooltip />
          </el-table>
          <div v-if="preview.missing?.length" class="note warn"><b>缺失项：</b><ul><li v-for="(m, i) in preview.missing" :key="i">{{ m }}</li></ul></div>
          <div v-if="preview.suggestions?.length" class="note"><b>改进建议：</b><ul><li v-for="(s, i) in preview.suggestions" :key="i">{{ s }}</li></ul></div>
        </div>
        <el-tabs v-else-if="preview.kind === 'arch'">
          <el-tab-pane label="架构概设文档"><pre class="preview-text">{{ preview.doc }}</pre></el-tab-pane>
          <el-tab-pane label="数据库 SQL"><pre class="preview-text sql">{{ preview.sql }}</pre></el-tab-pane>
        </el-tabs>
        <pre v-else class="preview-text">{{ preview.text }}</pre>
      </template>
    </el-dialog>

    <!-- 重新生成计划：先输入修改意见 -->
    <el-dialog v-model="regenVisible" title="重新生成项目计划" width="560px">
      <el-alert type="info" :closable="false" title="AI 将结合当前计划版本与你的修改意见重新生成，可描述需要调整的地方（如成员分工、里程碑时间、任务拆分等）。" style="margin-bottom: 12px" />
      <el-input v-model="regenSuggestion" type="textarea" :rows="5" placeholder="请输入修改意见…" />
      <template #footer>
        <el-button @click="regenVisible = false">取消</el-button>
        <el-button type="primary" :loading="regeneratingId" @click="doRegen">确认重新生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { useProjectStore } from "../stores/project";
import { listRequirements, uploadRequirement, analyzeRequirement, confirmRequirement } from "../api/requirements";
import { deleteProjectPlan, generatePlanTasks, generateProjectPlan, listProjectPlans, regenerateProjectPlan } from "../api/projectPlanning";
import { listArchitecture, createArchitecture } from "../api/architecture";
import { listTasks } from "../api/tasks";
import { workLogStatistics } from "../api/collaboration";
import { listDeliveryDocs } from "../api/delivery";
import { generateTestReport } from "../api/testing";
import { listOperationItems, listOperationMetrics, operationStatistics } from "../api/operation";
import { ingestKnowledge } from "../api/knowledge";

const router = useRouter();

const ORDER = ["requirement", "planning", "architecture", "developing", "delivery", "operation"];
const STAGES = [
  { key: "requirement", label: "需求分析", icon: "📋" },
  { key: "planning", label: "计划安排", icon: "📅" },
  { key: "architecture", label: "架构设计", icon: "🏗️" },
  { key: "developing", label: "项目实施", icon: "🛠️" },
  { key: "delivery", label: "项目交付", icon: "📦" },
  { key: "operation", label: "运营", icon: "🚀" },
];

const projectStore = useProjectStore();
const projects = computed(() => projectStore.projects);
// 绑定全局当前项目（右上角选择，所有菜单共享）
const projectId = computed({
  get: () => projectStore.currentId,
  set: (v) => projectStore.setCurrent(v),
});
const selectedProject = ref(null);
const stageVisible = ref(false);
const stageLoading = ref(false);
const stageData = ref(null);
const currentStage = ref(null);
const previewVisible = ref(false);
const preview = ref(null);

// 工作台数据
const wbLoading = ref(false);
const reqs = ref([]);
const plans = ref([]);
const designs = ref([]);
const devTasks = ref([]);
const devStats = ref({});
const devTab = ref("list");
const deliveries = ref([]);
const uploading = ref(false);
const analyzingId = ref(null);
const confirmingId = ref(null);
const planLoading = ref(false);
const regeneratingId = ref(null);
const regenVisible = ref(false);
const regenSuggestion = ref("");
const regenTarget = ref(null);
const genTaskId = ref(null);
const reportLoading = ref(false);
const opItems = ref([]);
const opStats = ref({});
const opMetrics = ref([]);
const opIngesting = ref(false);

// 架构生成
const archGenVisible = ref(false);
const archDoc = ref("");
const archSql = ref("");
const archSaving = ref(false);
const archStreaming = reactive({ doc: false, sql: false });
const archForm = reactive({ project_id: null, frontend_stack: "", backend_stack: "", base_framework: "", db_type: "mysql" });

const currentIndex = computed(() => {
  const i = ORDER.indexOf(selectedProject.value?.status);
  return i === -1 ? 0 : i;
});
const activeStage = computed(() => STAGES[currentIndex.value] || null);

// 各指标取最新月份的值，形成运营看板
const opMetricSummary = computed(() => {
  const seen = {};
  const out = {};
  for (const m of opMetrics.value) {
    if (!seen[m.indicator]) {
      seen[m.indicator] = true;
      out[m.indicator] = m;
    }
  }
  return out;
});
const metricLabel = (k) => ({ renewal: "续期/续费", satisfaction: "满意度", active_users: "活跃用户", custom: "自定义" }[k] || k);

function stageState(i) {
  if (i < currentIndex.value) return "done";
  if (i === currentIndex.value) return "active";
  return "todo";
}
function segmentClass(i) {
  return i <= currentIndex.value ? "seg-done" : "";
}
function stateText(i) {
  const s = stageState(i);
  return s === "done" ? "已完成" : s === "active" ? "进行中" : "未开始";
}
function statusLabel(k) {
  return { pending: "待执行", executing: "执行中", done: "已完成", blocked: "阻塞" }[k] || k;
}
function devStatusType(s) {
  return { pending: "info", executing: "warning", done: "success", blocked: "danger" }[s] || "info";
}

// ── 甘特图（项目实施 Tab，基于 devTasks 数据）──
const LABEL_W = 190, COL_W = 20, ROW_H = 36, AXIS_H = 42;
const DAY_MS = 86400000;
// 刻度降级阈值：长周期/异常日期自动降级，避免列数过多撑爆 DOM（评估 #4）
const SCALE_DAY_MAX = 120;
const SCALE_WEEK_MAX = 730;
const SCALE_COL_MAX = 366;
const SCALE_LABEL = { day: "天", week: "周", month: "月" };
const ganttStatuses = [
  { value: "pending", label: "待执行", color: "#cbd5e1" },
  { value: "executing", label: "执行中", color: "#60a5fa" },
  { value: "done", label: "已完成", color: "#34d399" },
  { value: "blocked", label: "阻塞", color: "#f87171" },
];
function parseDate(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function addDays(d, n) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}
const gantt = computed(() => {
  const dated = [];
  const undated = [];
  let minDate = null, maxDate = null;
  for (const t of devTasks.value) {
    if (t.start_date && t.end_date) {
      const s = parseDate(t.start_date), e = parseDate(t.end_date);
      dated.push({ ...t, _s: s, _e: e });
      if (!minDate || s < minDate) minDate = s;
      if (!maxDate || e > maxDate) maxDate = e;
    } else {
      undated.push(t);
    }
  }
  dated.sort((a, b) => a._s - b._s || (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id);
  return { dated, undated, minDate, maxDate };
});
const totalDays = computed(() =>
  gantt.value.minDate && gantt.value.maxDate ? Math.round((gantt.value.maxDate - gantt.value.minDate) / DAY_MS) + 1 : 0
);
// 刻度选择：≤120 天按天（列=1 天）、≤730 天按周（列=7 天）、更长按月（列=自然月）
const scaleUnit = computed(() => {
  if (totalDays.value <= SCALE_DAY_MAX) return "day";
  if (totalDays.value <= SCALE_WEEK_MAX) return "week";
  return "month";
});
const scaleLabel = computed(() => SCALE_LABEL[scaleUnit.value] || "天");
// 列定义：startDay/spanDays 均为相对 minDate 的天偏移。首列从 minDate 起算，保证左边界与天数对齐
const columns = computed(() => {
  const g = gantt.value;
  if (!g.minDate) return { cols: [], coveredDays: 0, truncated: false };
  const unit = scaleUnit.value;
  const cols = [];
  if (unit === "day") {
    for (let i = 0; i < totalDays.value && cols.length < SCALE_COL_MAX; i++) {
      cols.push({ startDay: i, spanDays: 1, date: addDays(g.minDate, i) });
    }
  } else if (unit === "week") {
    for (let i = 0; i < totalDays.value && cols.length < SCALE_COL_MAX; i += 7) {
      cols.push({ startDay: i, spanDays: Math.min(7, totalDays.value - i), date: addDays(g.minDate, i) });
    }
  } else {
    let day = 0;
    while (day < totalDays.value && cols.length < SCALE_COL_MAX) {
      const date = addDays(g.minDate, day);
      // 当月剩余天数：月份 +1 的「0 号」= 本月最后一天（取 00:00，避免 dayIndex 取整多算一天）
      const monthEnd = new Date(date.getFullYear(), date.getMonth() + 1, 0);
      const spanDays = Math.min(Math.round((monthEnd - date) / DAY_MS) + 1, totalDays.value - day);
      cols.push({ startDay: day, spanDays, date });
      day += spanDays;
    }
  }
  const coveredDays = cols.reduce((a, c) => a + c.spanDays, 0);
  return { cols, coveredDays, truncated: coveredDays < totalDays.value };
});
const ganttCols = computed(() => `${LABEL_W}px repeat(${columns.value.cols.length}, ${COL_W}px)`);
const ganttWidth = computed(() => LABEL_W + columns.value.cols.length * COL_W);
// 列模板的唯一来源：日期轴与任务行都绑它，避免两处模板不一致导致轴与条错位
const ganttGridStyle = computed(() => ({ gridTemplateColumns: ganttCols.value }));
// 任务区竖向分隔线：按 COL_W 生成并偏移 LABEL_W，不写死在 CSS 里（标题列与刻度行有底色，会自然盖住左侧部分）
const ganttLinesStyle = computed(() => ({
  backgroundImage: `linear-gradient(to right, #eef2f7 0 1px, transparent 1px)`,
  backgroundSize: `${COL_W}px 100%`,
  backgroundPosition: `${LABEL_W}px 0`,
  backgroundRepeat: "repeat",
}));
// 可见任务 / 超出展示范围任务（仅极端日期触发截断时后者非空）
const ganttVisible = computed(() => {
  const cover = columns.value.coveredDays;
  const inRange = [];
  const overflow = [];
  for (const t of gantt.value.dated) {
    if (dayIndex(t._s) < cover) inRange.push(t);
    else overflow.push(t);
  }
  return { inRange, overflow };
});
function dayIndex(d) {
  return Math.round((d - gantt.value.minDate) / DAY_MS);
}
// 天偏移 -> 所在列下标（列连续有序，二分查找）
function colAt(offset) {
  const cols = columns.value.cols;
  if (!cols.length) return 0;
  let lo = 0, hi = cols.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const c = cols[mid];
    if (offset < c.startDay) hi = mid - 1;
    else if (offset >= c.startDay + c.spanDays) lo = mid + 1;
    else return mid;
  }
  return offset < 0 ? 0 : cols.length - 1;
}
// 天偏移 -> 时间轴内左边界像素。按列内比例换算，保证降级到周/月刻度后任务条依然精确到天
function dayToPx(offset) {
  const { cols, coveredDays } = columns.value;
  if (!cols.length) return 0;
  if (offset <= 0) return 0;
  if (offset >= coveredDays) return cols.length * COL_W;
  const ci = colAt(offset);
  const c = cols[ci];
  return ci * COL_W + ((offset - c.startDay) / c.spanDays) * COL_W;
}
// 顶部大刻度：按天/周时按自然月分组，按月时按年分组
const topAxis = computed(() => {
  const byMonth = scaleUnit.value !== "month";
  const segs = [];
  columns.value.cols.forEach((c, i) => {
    const d = c.date;
    const key = byMonth ? `${d.getFullYear()}-${d.getMonth()}` : `${d.getFullYear()}`;
    const last = segs[segs.length - 1];
    if (last && last.key === key) last.span += 1;
    else {
      segs.push({
        key,
        label: byMonth ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}` : `${d.getFullYear()}年`,
        start: i,
        span: 1,
      });
    }
  });
  return segs;
});
// 底部小刻度标签：天 -> 日号；周 -> 周起始 M/D；月 -> 月份
function colLabel(c) {
  const unit = scaleUnit.value;
  if (unit === "day") return c.date.getDate();
  if (unit === "week") return `${c.date.getMonth() + 1}/${c.date.getDate()}`;
  return `${c.date.getMonth() + 1}月`;
}
const todayX = computed(() => {
  const g = gantt.value;
  if (!g.minDate) return -1;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const off = dayIndex(today);
  if (off < 0 || off >= columns.value.coveredDays) return -1;
  return dayToPx(off);
});
function axisCell(start, span) {
  return { gridColumn: `${2 + start} / span ${span}` };
}
// 任务条：列跨度决定 grid 位置，列内比例决定左右内缩，二者结合使粗刻度下仍精确到天
function barCell(t) {
  const cover = columns.value.coveredDays;
  if (!cover) return {};
  const s = Math.max(0, Math.min(dayIndex(t._s), cover - 1));
  const e = Math.max(s, Math.min(dayIndex(t._e), cover - 1));
  const ci = colAt(s);
  const cj = colAt(e);
  const leftPx = dayToPx(s);
  const rightPx = dayToPx(e + 1);
  return {
    gridColumn: `${2 + ci} / span ${cj - ci + 1}`,
    paddingLeft: `${Math.max(0, leftPx - ci * COL_W)}px`,
    paddingRight: `${Math.max(0, (cj + 1) * COL_W - rightPx)}px`,
  };
}
function ganttColor(status) {
  return { pending: "#cbd5e1", executing: "#60a5fa", done: "#34d399", blocked: "#f87171" }[status] || "#cbd5e1";
}
function ganttTip(t) {
  return `#${t.id} ${t.title}\n负责人：${t.assignee_name || "未指派"}\n状态：${t.status_display}\n计划：${t.start_date} ~ ${t.end_date}${t.module ? `\n模块：${t.module}` : ""}${t.depends ? `\n前置依赖：${t.depends}` : ""}`;
}

// ── 甘特图全屏：页面内固定层。z-index 取 1900，低于 Element Plus 弹层（2000 起），
//    这样 teleport 到 body 的 tooltip 仍能浮在遮罩之上 ──
const ganttFullscreen = ref(false);
let prevBodyOverflow = "";
function exitGanttFullscreen() {
  ganttFullscreen.value = false;
  document.body.style.overflow = prevBodyOverflow;
}
function toggleGanttFullscreen() {
  if (ganttFullscreen.value) {
    exitGanttFullscreen();
    return;
  }
  prevBodyOverflow = document.body.style.overflow;
  ganttFullscreen.value = true;
  document.body.style.overflow = "hidden";
}
function onGanttKeydown(e) {
  if (e.key === "Escape" && ganttFullscreen.value) exitGanttFullscreen();
}
onMounted(() => document.addEventListener("keydown", onGanttKeydown));
onBeforeUnmount(() => {
  document.removeEventListener("keydown", onGanttKeydown);
  if (ganttFullscreen.value) document.body.style.overflow = prevBodyOverflow;
});
// 切换到其它环节/Tab 时兜底退出，避免遮罩残留导致页面无法滚动
watch([devTab, () => activeStage.value?.key], () => {
  if (ganttFullscreen.value) exitGanttFullscreen();
});

async function loadProjects() {
  await projectStore.ensureLoaded();
  onProjectChange();
}

function onProjectChange() {
  selectedProject.value = projects.value.find((p) => p.id === projectId.value) || null;
  loadWB();
}

// ── 工作台数据加载 ──
async function loadWB() {
  if (!projectId.value) return;
  const key = activeStage.value?.key;
  wbLoading.value = true;
  try {
    if (key === "requirement") {
      const { data } = await listRequirements(projectId.value);
      reqs.value = data;
    } else if (key === "planning") {
      const { data } = await listProjectPlans(projectId.value);
      plans.value = data;
    } else if (key === "architecture") {
      const { data } = await listArchitecture(projectId.value);
      designs.value = data;
    } else if (key === "developing") {
      const [t, w] = await Promise.all([
        listTasks({ project_id: projectId.value }),
        workLogStatistics({ project_id: projectId.value }),
      ]);
      devTasks.value = t.data;
      const by_status = { pending: 0, executing: 0, done: 0, blocked: 0 };
      t.data.forEach((x) => {
        by_status[x.status] = (by_status[x.status] || 0) + 1;
      });
      devStats.value = { total_tasks: t.data.length, by_status, hours: w.data.total_hours ?? 0 };
    } else if (key === "delivery") {
      const { data } = await listDeliveryDocs(projectId.value);
      deliveries.value = data;
    } else if (key === "operation") {
      const [i, s, m] = await Promise.all([
        listOperationItems({ project_id: projectId.value }),
        operationStatistics(projectId.value),
        listOperationMetrics({ project_id: projectId.value }),
      ]);
      opItems.value = i.data;
      opStats.value = s.data;
      opMetrics.value = m.data;
    }
  } finally {
    wbLoading.value = false;
  }
}

// ── 需求环节 ──
function onReqFile(file) {
  const fd = new FormData();
  fd.append("project_id", projectId.value);
  fd.append("file", file.raw);
  uploading.value = true;
  uploadRequirement(fd)
    .then(() => {
      ElMessage.success("上传并解析成功");
      loadWB();
    })
    .catch((e) => ElMessage.error(e.response?.data?.detail || "上传失败"))
    .finally(() => {
      uploading.value = false;
    });
}
async function analyzeReq(row) {
  analyzingId.value = row.id;
  try {
    const { data } = await analyzeRequirement(row.id);
    ElMessage.success("AI 分析完成，完整度 " + (data.analysis_result?.overall_score ?? "?"));
    loadWB();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "分析失败");
  } finally {
    analyzingId.value = null;
  }
}
async function confirmReq(row) {
  confirmingId.value = row.id;
  try {
    await confirmRequirement(row.id);
    ElMessage.success("需求已确认入库，项目进入「计划安排」");
    loadWB();
    onProjectChange();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "确认失败");
  } finally {
    confirmingId.value = null;
  }
}

// ── 计划环节 ──
async function genPlan() {
  if (!projectId.value) return ElMessage.warning("请先选择项目");
  const members = (selectedProject.value?.members || []).map((m) => ({ user_id: m.id, weight: 1 }));
  if (!members.length) return ElMessage.warning("项目暂无成员，请先在项目管理中邀请成员");
  planLoading.value = true;
  try {
    await generateProjectPlan({ project_id: projectId.value, members });
    ElMessage.success("计划已生成，可查看/重新生成/生成任务");
    loadWB();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "生成失败");
  } finally {
    planLoading.value = false;
  }
}
function openRegen(row) {
  regenTarget.value = row;
  regenSuggestion.value = "";
  regenVisible.value = true;
}
async function doRegen() {
  const row = regenTarget.value;
  if (!row) return;
  if (!regenSuggestion.value.trim()) return ElMessage.warning("请输入修改意见");
  regeneratingId.value = row.id;
  try {
    await regenerateProjectPlan(row.id, { suggestion: regenSuggestion.value });
    ElMessage.success("已按修改意见重新生成");
    regenVisible.value = false;
    loadWB();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "重新生成失败");
  } finally {
    regeneratingId.value = null;
  }
}
async function genTasks(row) {
  genTaskId.value = row.id;
  try {
    await generatePlanTasks(row.id);
    ElMessage.success("任务已生成并指派");
    loadWB();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "生成任务失败");
  } finally {
    genTaskId.value = null;
  }
}
async function removePlan(row) {
  try {
    await ElMessageBox.confirm(`删除计划「${row.name}」？`, "删除计划", { type: "warning" });
  } catch {
    return;
  }
  await deleteProjectPlan(row.id);
  ElMessage.success("已删除");
  loadWB();
}

// ── 架构环节 ──
function openGenDialog() {
  archForm.project_id = projectId.value;
  archForm.frontend_stack = "";
  archForm.backend_stack = "";
  archForm.base_framework = "";
  archForm.db_type = "mysql";
  archForm.constraints = "";
  archForm.extra = "";
  archDoc.value = "";
  archSql.value = "";
  archGenVisible.value = true;
}
async function archGenStep(target) {
  if (target === "sql" && !archDoc.value) return ElMessage.warning("请先生成架构概设文档");
  archStreaming[target === "sql" ? "sql" : "doc"] = true;
  if (target === "sql") archSql.value = "";
  else archDoc.value = "";
  try {
    const token = localStorage.getItem("access_token");
    const res = await fetch("/api/architecture/generate-stream/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...archForm, target }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "生成失败");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          let evt;
          try {
            evt = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (evt.type === "chunk") {
            if (target === "sql") archSql.value += evt.content;
            else archDoc.value += evt.content;
          } else if (evt.type === "error") {
            throw new Error(evt.message || "生成失败");
          }
        }
      }
    }
    ElMessage.success(target === "sql" ? "SQL 生成完成" : "架构文档生成完成");
  } catch (e) {
    ElMessage.error(e.message || "生成失败");
  } finally {
    archStreaming[target === "sql" ? "sql" : "doc"] = false;
  }
}
async function archConfirmSave() {
  archSaving.value = true;
  try {
    await createArchitecture({
      project: archForm.project_id,
      frontend_stack: archForm.frontend_stack,
      backend_stack: archForm.backend_stack,
      base_framework: archForm.base_framework,
      db_type: archForm.db_type,
      design_doc: archDoc.value,
      db_sql: archSql.value,
    });
    ElMessage.success("架构设计已保存，项目进入「项目实施」");
    archGenVisible.value = false;
    loadWB();
    onProjectChange();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    archSaving.value = false;
  }
}

// ── 交付环节 ──
async function genReport() {
  if (!projectId.value) return ElMessage.warning("请选择项目");
  reportLoading.value = true;
  try {
    const { data } = await generateTestReport({ project_id: projectId.value });
    ElMessage.success(`测试报告已生成（通过率 ${data.pass_rate}%）`);
    if (data.advanced) ElMessage.success("通过率达标，项目已推进到「项目交付」");
    loadWB();
    onProjectChange();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "报告生成失败");
  } finally {
    reportLoading.value = false;
  }
}

// ── 运营环节 ──
async function opIngest() {
  if (!projectId.value) return ElMessage.warning("请选择项目");
  opIngesting.value = true;
  try {
    const { data } = await ingestKnowledge({ project_id: projectId.value, kind: "operation" });
    ElMessage.success(`已入库 ${data.created ?? 0} 条知识${data.overwritten ? `（覆盖旧知识 ${data.overwritten} 条）` : ""}`);
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "知识入库失败");
  } finally {
    opIngesting.value = false;
  }
}
function categoryLabel(k) {
  return { iteration: "迭代需求", optimization: "优化需求", change: "业务变更", feedback: "用户反馈" }[k] || k;
}

// ── 弹窗预览 ──
async function openStage(stage, i) {
  if (i > currentIndex.value) return;
  currentStage.value = stage;
  stageVisible.value = true;
  stageLoading.value = true;
  stageData.value = null;
  preview.value = null;
  try {
    stageData.value = await stage.fetch();
  } finally {
    stageLoading.value = false;
  }
}

const stageFetch = {
  requirement: fetchRequirement,
  planning: fetchPlan,
  architecture: fetchArch,
  developing: fetchDevelop,
  delivery: fetchDelivery,
  operation: fetchOperation,
};
STAGES.forEach((s) => (s.fetch = stageFetch[s.key]));

function previewItem(row) {
  const key = currentStage.value?.key;
  if (key === "requirement") {
    preview.value = {
      kind: "analysis",
      title: row.title,
      overall: row.score,
      verdict: row.verdict,
      fileUrl: row.file_url,
      elements: row.elements || [],
      missing: row.missing || [],
      suggestions: row.suggestions || [],
    };
  } else if (key === "planning") {
    preview.value = { kind: "text", title: `计划 · ${row.name}`, text: row.content };
  } else if (key === "architecture") {
    preview.value = { kind: "arch", title: `架构设计 · ${row.name}`, doc: row.design_doc, sql: row.db_sql };
  } else if (key === "delivery") {
    preview.value = { kind: "text", title: row.title, text: row.content };
  } else {
    preview.value = { kind: "text", title: row.title, text: row.detail };
  }
  previewVisible.value = true;
}
function previewPlan(row) {
  preview.value = { kind: "text", title: `计划 · ${row.name}`, text: row.plan_content || "（无内容）" };
  previewVisible.value = true;
}
function viewDesign(row) {
  preview.value = { kind: "arch", title: `架构设计 #${row.id}`, doc: row.design_doc, sql: row.db_sql };
  previewVisible.value = true;
}
function viewDelivery(row) {
  preview.value = { kind: "text", title: row.title, text: row.content || "（附件形式）" };
  previewVisible.value = true;
}
function openFile(url) {
  if (url) window.open(url, "_blank");
}

// ── 已完成环节数据 ──
async function fetchRequirement() {
  const { data } = await listRequirements(projectId.value);
  return {
    type: "table",
    columns: [
      { key: "title", label: "需求文档" },
      { key: "status", label: "状态" },
      { key: "score", label: "完整度评分" },
      { key: "verdict", label: "AI 结论" },
    ],
    items: data.map((r) => ({
      title: r.title,
      status: r.is_confirmed ? "已确认" : "待确认",
      score: r.analysis_result?.overall_score,
      verdict: r.analysis_result?.verdict === "passed" ? "建议通过" : "需补充",
      file_url: r.original_file,
      elements: r.analysis_result?.elements || [],
      missing: r.analysis_result?.missing || [],
      suggestions: r.analysis_result?.suggestions || [],
    })),
  };
}
async function fetchPlan() {
  const { data } = await listProjectPlans(projectId.value);
  return {
    type: "table",
    columns: [
      { key: "name", label: "计划名称" },
      { key: "period", label: "计划周期" },
      { key: "members", label: "成员" },
      { key: "task_count", label: "任务数" },
    ],
    items: data.map((p) => ({
      name: p.name,
      period: `${p.start_date} ~ ${p.launch_date}`,
      members: (p.members || []).map((m) => m.username).join("、"),
      task_count: p.task_count ?? 0,
      content: p.plan_content,
    })),
  };
}
async function fetchArch() {
  const { data } = await listArchitecture(projectId.value);
  return {
    type: "table",
    columns: [
      { key: "name", label: "编号" },
      { key: "front", label: "前端技术栈" },
      { key: "back", label: "后端技术栈" },
      { key: "db", label: "数据库" },
    ],
    items: data.map((a, idx) => ({
      name: `设计 #${idx + 1}`,
      front: a.frontend_stack,
      back: a.backend_stack,
      base: a.base_framework_display,
      db: a.db_type_display,
      design_doc: a.design_doc,
      db_sql: a.db_sql,
    })),
  };
}
async function fetchDevelop() {
  const [t, w] = await Promise.all([
    listTasks({ project_id: projectId.value }),
    workLogStatistics({ project_id: projectId.value }),
  ]);
  const byStatus = { pending: 0, executing: 0, done: 0, blocked: 0 };
  const items = t.data.map((x) => {
    byStatus[x.status] = (byStatus[x.status] || 0) + 1;
    return { title: x.title, detail: `任务：${x.title}\n负责人：${x.assignee_name || "-"}\n状态：${x.status_display}\n描述：${x.description || "无"}` };
  });
  return { type: "table", columns: [{ key: "title", label: "任务" }], items, summary: { tasks: items.length, byStatus, hours: w.data.total_hours ?? 0 }, showSummary: true };
}
async function fetchDelivery() {
  const { data } = await listDeliveryDocs(projectId.value);
  return {
    type: "table",
    columns: [
      { key: "title", label: "文档标题" },
      { key: "doc_type", label: "类型" },
      { key: "creator", label: "上传人" },
      { key: "created_at", label: "时间" },
    ],
    items: data.map((d) => ({
      title: d.title,
      doc_type: d.doc_type,
      creator: d.creator,
      created_at: d.created_at ? new Date(d.created_at).toLocaleString() : "",
      content: d.content || "（该文档为附件形式，无内联内容）",
    })),
  };
}
async function fetchOperation() {
  const { data } = await listOperationItems({ project_id: projectId.value });
  return {
    type: "table",
    columns: [
      { key: "title", label: "标题" },
      { key: "category", label: "类型" },
      { key: "status", label: "状态" },
      { key: "requestor", label: "提出人" },
    ],
    items: data.map((x) => ({
      title: x.title,
      category: x.category_display,
      status: x.status_display,
      requestor: x.requestor || "-",
      detail: `类型：${x.category_display}\n优先级：${x.priority_display}\n状态：${x.status_display}\n提出人：${x.requestor || "-"}\n\n内容：\n${x.content || "（无）"}`,
    })),
  };
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
});
</script>

<style scoped>
.overview-page {
  min-height: calc(100vh - 130px);
  background: linear-gradient(180deg, #bfe3ff 0%, #e8f7ff 55%, #d9f7d9 100%);
  border-radius: 12px;
  padding: 24px;
  position: relative;
  overflow: hidden;
}
.overview-page::before,
.overview-page::after {
  content: "☁️";
  position: absolute;
  font-size: 60px;
  opacity: 0.4;
}
.overview-page::before { top: 20px; left: 30px; animation: floaty 6s ease-in-out infinite; }
.overview-page::after { top: 60px; right: 60px; font-size: 80px; animation: floaty 8s ease-in-out infinite; }
@keyframes floaty {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}

.banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.75);
  border-radius: 16px;
  padding: 16px 24px;
  box-shadow: 0 6px 16px rgba(31, 59, 115, 0.15);
  margin-bottom: 24px;
}
.banner h2 { margin: 0; color: #1f3b73; font-size: 24px; }
.banner p { margin: 4px 0 0; color: #5a6b8c; }

.map {
  background: rgba(255, 255, 255, 0.5);
  border-radius: 16px;
  padding: 40px 24px 24px;
  box-shadow: 0 6px 16px rgba(31, 59, 115, 0.12);
}
.road {
  display: flex;
  align-items: flex-start;
}
.road-segment {
  flex: 1;
  height: 8px;
  margin-top: 34px;
  border-radius: 4px;
  background: #d1d5db;
}
.road-segment.seg-done {
  background: linear-gradient(90deg, #4ade80, #60a5fa);
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.6);
}
.stage-node {
  width: 110px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: default;
  position: relative;
}
.stage-node.clickable { cursor: pointer; }
.stage-node .icon-wrap { position: relative; }
.stage-node .icon {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 38px;
  border: 4px solid #fff;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.18);
  transition: transform 0.2s;
}
.stage-node.clickable:hover .icon { transform: scale(1.08); }
.stage-node.done .icon { background: linear-gradient(135deg, #4ade80, #34d399); }
.stage-node.active .icon {
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  animation: pulse 1.6s ease-in-out infinite;
}
.stage-node.todo .icon { background: #e5e7eb; filter: grayscale(1); opacity: 0.85; }
@keyframes pulse {
  0%, 100% { box-shadow: 0 4px 10px rgba(0,0,0,.18), 0 0 0 0 rgba(251,191,36,.6); }
  50% { box-shadow: 0 4px 10px rgba(0,0,0,.18), 0 0 0 14px rgba(251,191,36,0); }
}
.stage-node .label { margin-top: 10px; font-weight: 700; color: #1f3b73; }
.stage-node .state-text { font-size: 12px; color: #8a93a8; margin-top: 2px; }

.cheer {
  position: absolute;
  top: -34px;
  right: -26px;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 2;
}
.cheer .bubble {
  background: #fff;
  border: 2px solid #f59e0b;
  color: #f59e0b;
  font-weight: 700;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  position: relative;
  white-space: nowrap;
  box-shadow: 0 2px 6px rgba(0,0,0,.15);
}
.cheer .bubble::after {
  content: "";
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #f59e0b;
  border-bottom: none;
}
.cheer .hero { font-size: 26px; animation: bounce 0.6s ease-in-out infinite; }
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.legend { margin-top: 28px; display: flex; gap: 24px; justify-content: center; }
.legend span { display: flex; align-items: center; gap: 6px; color: #5a6b8c; font-size: 13px; }
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.dot.done { background: #34d399; }
.dot.active { background: #f59e0b; animation: pulse 1.6s infinite; }
.dot.todo { background: #d1d5db; }

/* 工作台 */
.workbench {
  margin-top: 24px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 16px;
  padding: 16px 20px;
  box-shadow: 0 6px 16px rgba(31, 59, 115, 0.12);
}
.wb-head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  color: #1f3b73;
  font-size: 16px;
  margin-bottom: 12px;
}
.wb-icon { font-size: 22px; }
.wb-body { min-height: 120px; }
.wb-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.hint { color: #909399; font-size: 12px; }
.wb-stats { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.wb-stats .stat {
  flex: 1;
  min-width: 90px;
  text-align: center;
  background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
  border-radius: 10px;
  padding: 10px 6px;
}
.wb-stats .stat b { display: block; font-size: 22px; color: #0ea5e9; }
.wb-stats .stat span { color: #64748b; font-size: 12px; }
.wb-stats.metric .stat { background: linear-gradient(135deg, #fdf4ff, #fae8ff); }
.wb-stats.metric .stat b { color: #a21caf; }
.step-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.edit-area { font-family: Consolas, Menlo, monospace; font-size: 13px; line-height: 1.6; }
.edit-area.sql { background: #0f172a; color: #e2e8f0; }

/* ── 甘特图 ── */
.dev-tabs { margin-top: 2px; }
.gantt-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.gantt-bar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.gantt-legend { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 12px; color: #64748b; }
.gantt-legend span { display: inline-flex; align-items: center; gap: 5px; }
.g-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.gantt-scale { color: #0ea5e9; background: #e0f2fe; border-radius: 10px; padding: 1px 8px; }
.gantt-hint { color: #94a3b8; font-size: 12px; }
.gantt-scroll { overflow: auto; max-height: 480px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
/* 全屏：页面内固定层。z-index 取 1900，低于 Element Plus 弹层（2000 起），
   使 teleport 到 body 的 tooltip 仍浮在遮罩之上 */
.gantt-fs {
  position: fixed;
  inset: 0;
  z-index: 1900;
  background: #fff;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.gantt-fs .gantt-scroll { flex: 1; min-height: 0; max-height: none; }
.gantt-fs .g-undated { flex: none; }
.gantt { position: relative; }
.g-axis { display: grid; position: sticky; z-index: 5; height: 21px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.g-months { top: 0; }
.g-days { top: 21px; }
.g-month {
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  border-right: 1px solid #e2e8f0;
  line-height: 20px;
  white-space: nowrap;
  overflow: hidden;
}
.g-day {
  text-align: center;
  font-size: 10px;
  color: #94a3b8;
  border-right: 1px solid #f1f5f9;
  line-height: 20px;
}
/* 行高固定为 36px，与脚本中的 ROW_H 保持一致（今天线按此坐标计算） */
.g-row { display: grid; height: 36px; border-bottom: 1px solid #f1f5f9; }
.g-label {
  grid-column: 1;
  padding: 2px 8px;
  overflow: hidden;
  border-right: 1px solid #e2e8f0;
  background: #fafbfc;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.g-title { font-size: 12px; line-height: 16px; color: #1f3b73; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.g-sub { font-size: 11px; line-height: 14px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
/* padding-top 8px + 条高 20px：条形在 36px 行内的垂直位置 */
.g-cell { position: relative; padding: 8px 2px 0 0; }
/* 条形只用颜色表达状态，不含任何"进度"含义（后端无真实进度字段） */
.g-bar {
  height: 20px;
  border-radius: 6px;
  cursor: pointer;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}
.g-today {
  position: absolute;
  width: 2px;
  background: #f59e0b;
  z-index: 3;
  pointer-events: none;
}
.g-today span {
  position: absolute;
  top: -16px;
  left: -14px;
  font-size: 10px;
  color: #f59e0b;
  font-weight: 700;
  white-space: nowrap;
  background: rgba(255, 255, 255, 0.85);
  padding: 0 3px;
  border-radius: 4px;
}
.g-undated { margin-top: 10px; }
.g-undated-hint { font-size: 12px; color: #b45309; margin-right: 8px; }

.stage-dialog :deep(.el-dialog__body) { max-height: 76vh; overflow: auto; }
.summary-cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
.summary-cards .card {
  flex: 1;
  min-width: 120px;
  text-align: center;
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
  border-radius: 12px;
  padding: 18px 10px;
  box-shadow: 0 4px 10px rgba(0,0,0,.08);
}
.summary-cards .card .num { font-size: 30px; font-weight: 800; color: #f59e0b; }
.summary-cards .card .lbl { color: #7c6a4d; font-size: 13px; margin-top: 4px; }

.preview-text {
  white-space: pre-wrap;
  word-break: break-word;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 12px;
  max-height: 68vh;
  overflow: auto;
  line-height: 1.6;
}
.preview-text.sql { background: #0f172a; color: #e2e8f0; font-family: Consolas, Menlo, monospace; }
.analysis-head { display: flex; align-items: center; gap: 14px; margin-bottom: 12px; }
.analysis-head .item { color: #5a6b8c; }
.note { margin-top: 10px; background: #eff6ff; border-radius: 6px; padding: 8px 12px; color: #475569; }
.note.warn { background: #fffbeb; }
.note ul { margin: 4px 0 0; padding-left: 18px; }

/* ══════════════════════════════════════════════════════════════════════════
   视觉升级：接入全局设计系统（本节在最后，用于覆盖上方历史配色）
   仅调整颜色 / 圆角 / 阴影 / 间距，不改动任何布局结构与交互逻辑。
   ══════════════════════════════════════════════════════════════════════ */
.overview-page {
  min-height: auto;
  padding: 0;
  border-radius: 0;
  background: transparent;
  overflow: visible;
}
/* 去掉天空渐变上的云朵装饰（与新的深色品牌横幅不搭） */
.overview-page::before,
.overview-page::after {
  content: none;
}

.banner {
  padding: 20px 24px;
  border-radius: var(--r-lg);
  color: #fff;
  background: radial-gradient(600px 260px at 8% 0%, rgba(79, 110, 247, 0.5), transparent 65%),
    linear-gradient(120deg, #101a2e 0%, #131c33 60%, #0d1626 100%);
  box-shadow: var(--sh-md);
}
.banner h2 {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: #fff;
}
.banner p {
  margin-top: 6px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.62);
}

.map {
  padding: 30px 24px 20px;
  border-radius: var(--r-lg);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--sh-sm);
}
.road-segment {
  height: 6px;
  margin-top: 32px;
  background: var(--el-fill-color-dark);
}
.road-segment.seg-done {
  background: var(--grad-brand);
  box-shadow: none;
}
.stage-node .icon {
  width: 64px;
  height: 64px;
  font-size: 30px;
  border: none;
  background: #fff;
  box-shadow: 0 0 0 1px var(--line), var(--sh-sm);
}
.stage-node.done .icon {
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  box-shadow: 0 0 0 1px var(--brand-100), var(--sh-sm);
}
.stage-node.active .icon {
  background-image: var(--grad-brand);
  box-shadow: 0 14px 28px -14px rgba(79, 110, 247, 0.95);
  animation: none;
}
.stage-node.todo .icon {
  background: var(--el-fill-color-light);
  filter: grayscale(1);
  opacity: 0.7;
}
.stage-node .label {
  margin-top: 9px;
  font-size: 13.5px;
  font-weight: 650;
  color: var(--ink-800);
}
.stage-node .state-text {
  color: var(--ink-300);
}
.cheer .bubble {
  border-color: var(--brand-500);
  color: var(--brand-600);
  box-shadow: var(--sh-sm);
}
.cheer .bubble::after {
  border-top-color: var(--brand-500);
}
.legend {
  margin-top: 24px;
}
.legend span {
  color: var(--ink-400);
}
.dot.done {
  background: var(--brand-500);
}
.dot.active {
  background: var(--warn-500);
}
.dot.todo {
  background: var(--ink-200);
}

.workbench {
  margin-top: 16px;
  padding: 18px 22px 20px;
  border-radius: var(--r-lg);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--sh-sm);
}
.wb-head {
  font-size: 15px;
  font-weight: 650;
  color: var(--ink-800);
}
.wb-stats .stat {
  border-radius: var(--r-sm);
  border: 1px solid var(--brand-100);
  background: var(--brand-50);
}
.wb-stats .stat b {
  color: var(--brand-600);
}
.wb-stats.metric .stat {
  border-color: #ede9fe;
  background: #faf5ff;
}
.wb-stats.metric .stat b {
  color: #7c3aed;
}
.hint {
  color: var(--ink-300);
}

/* 甘特图：仅统一描边与文字层级 */
.gantt-scroll {
  border-color: var(--line);
  border-radius: var(--r-sm);
}
.g-axis {
  background: var(--bg-soft);
  border-bottom-color: var(--line);
}
.g-month {
  color: var(--ink-500);
  border-right-color: var(--line);
}
.g-day {
  border-right-color: var(--line);
}
.g-row {
  border-bottom-color: var(--line);
}
.g-label {
  background: #fcfdff;
  border-right-color: var(--line);
}
.g-title {
  color: var(--ink-700);
}
.gantt-scale {
  color: var(--brand-600);
  background: var(--brand-50);
}
.gantt-hint {
  color: var(--ink-300);
}

.summary-cards .card {
  border-radius: var(--r-md);
  border: 1px solid var(--brand-100);
  background: var(--grad-soft);
  box-shadow: var(--sh-sm);
}
.summary-cards .card .num {
  color: var(--brand-600);
}
.summary-cards .card .lbl {
  color: var(--ink-400);
}

.preview-text {
  border-radius: var(--r-sm);
  background: var(--bg-soft);
}
.note {
  border-radius: var(--r-sm);
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
}
.note.warn {
  background: #fffbeb;
  border-color: #fde68a;
}
.analysis-head .item {
  color: var(--ink-500);
}
</style>

<style>
/* 甘特图任务条 tooltip（挂载在 body 下，需全局样式） */
.gantt-tip { white-space: pre-line; line-height: 1.5; max-width: 320px; }
</style>
