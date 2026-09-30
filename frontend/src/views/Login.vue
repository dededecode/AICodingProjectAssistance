<template>
  <div class="login">
    <!-- 左侧：品牌 / 能力展示（窄屏隐藏） -->
    <section class="login__brand">
      <div class="deco-grid" aria-hidden="true" />
      <div class="deco-orb deco-orb--a" aria-hidden="true" />
      <div class="deco-orb deco-orb--b" aria-hidden="true" />

      <header class="brand-head ds-in">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 64 64" width="34" height="34">
            <defs>
              <linearGradient id="lg-mark" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#ffffff" />
                <stop offset="1" stop-color="#c7d2fe" />
              </linearGradient>
            </defs>
            <path
              d="M32 11.5l4.8 12.9 12.9 4.8-12.9 4.8L32 46.9l-4.8-12.9-12.9-4.8 12.9-4.8z"
              fill="url(#lg-mark)"
            />
            <circle cx="46" cy="18" r="3.2" fill="#ffffff" opacity="0.85" />
          </svg>
        </span>
        <div class="brand-head__text">
          <b>AICoding Project Assistance</b>
          <span>AICoding 项目辅助、管理系统</span>
        </div>
      </header>

      <div class="brand-main">
        <span class="ds-ai-chip ds-in ds-in-1">
          <el-icon><MagicStick /></el-icon> AI 驱动 · 全流程闭环
        </span>
        <h1 class="ds-in ds-in-2">从需求到运营<br />一站式 AI 项目管理平台</h1>
        <p class="brand-sub ds-in ds-in-3">
          需求分析 → 项目计划 → 架构设计 → 开发实施 → 项目交付 → 项目运营，
          每个阶段由 AI 辅助生成，由人与 Agent 协同推进。
        </p>

        <ul class="feature-list ds-in ds-in-4">
          <li v-for="f in FEATURES" :key="f.title">
            <span class="f-icon"><el-icon><component :is="f.icon" /></el-icon></span>
            <div>
              <b>{{ f.title }}</b>
              <small>{{ f.desc }}</small>
            </div>
          </li>
        </ul>

        <div class="flow-line ds-in ds-in-4">
          <span v-for="(s, i) in STAGES" :key="s">
            <i>{{ i + 1 }}</i>{{ s }}<em v-if="i < STAGES.length - 1" />
          </span>
        </div>
      </div>

      <footer class="brand-foot ds-in ds-in-4">
        <div class="stat"><b>6</b><span>阶段闭环</span></div>
        <div class="stat"><b>55<small>+</small></b><span>MCP 工具</span></div>
        <div class="stat"><b>2</b><span>套知识体系</span></div>
        <div class="stat"><b>1</b><span>个数据卷部署</span></div>
      </footer>
    </section>

    <!-- 右侧：登录表单 -->
    <section class="login__panel">
      <div class="panel-card ds-in">
        <div class="panel-logo">
          <span class="brand-mark brand-mark--light" aria-hidden="true">
            <svg viewBox="0 0 64 64" width="30" height="30">
              <path
                d="M32 11.5l4.8 12.9 12.9 4.8-12.9 4.8L32 46.9l-4.8-12.9-12.9-4.8 12.9-4.8z"
                fill="#fff"
              />
            </svg>
          </span>
          <b>AICodingProjectAssistance</b>
        </div>

        <h2>欢迎回来 👋</h2>
        <p class="panel-sub">登录以继续你的项目全流程管理</p>

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="rules"
          label-position="top"
          size="large"
          @submit.prevent
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="loginForm.username" placeholder="请输入用户名" autocomplete="username">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              show-password
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="handleLogin"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>

          <el-form-item label="验证码" prop="captchaCode">
            <div class="captcha-row">
              <el-input
                v-model="loginForm.captchaCode"
                placeholder="请输入右侧 4 位验证码"
                maxlength="4"
                @keyup.enter="handleLogin"
              >
                <template #prefix><el-icon><Key /></el-icon></template>
              </el-input>
              <button
                type="button"
                class="captcha-box"
                :class="{ 'is-empty': !captchaImage }"
                title="点击刷新验证码"
                @click="loadCaptcha"
              >
                <img v-if="captchaImage" :src="captchaImage" alt="验证码" />
                <span v-else class="captcha-refresh"><el-icon><Refresh /></el-icon></span>
                <span class="captcha-mask"><el-icon><Refresh /></el-icon> 点击刷新</span>
              </button>
            </div>
          </el-form-item>

          <el-button class="submit" type="primary" size="large" :loading="loading" @click="handleLogin">
            {{ loading ? "登录中…" : "登 录" }}
          </el-button>
        </el-form>

        <div class="panel-foot">
          <el-icon><InfoFilled /></el-icon>
          <span>
            系统无注册入口：账号由管理员在「用户管理」中创建，或使用
            <code>createsuperuser</code> / <code>seed_demo</code> 生成。
          </span>
        </div>
      </div>

      <p class="panel-copy">© {{ year }} AICodingProjectAssistance · 本地化部署，数据不出内网</p>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  Collection,
  Connection,
  InfoFilled,
  Key,
  Lock,
  MagicStick,
  Promotion,
  Refresh,
  User,
} from "@element-plus/icons-vue";
import JSEncrypt from "jsencrypt";
import { useAuthStore } from "../stores/auth";
import { getCaptcha, getRsaPublicKey } from "../api/auth";

const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const loginFormRef = ref();
const captchaImage = ref("");
const publicKey = ref("");
const year = new Date().getFullYear();

const STAGES = ["需求", "计划", "架构", "开发", "交付", "运营"];
const FEATURES = [
  { icon: Connection, title: "全流程闭环", desc: "阶段前置校验，确认后自动流转" },
  { icon: MagicStick, title: "AI 生成", desc: "需求检测 / 计划拆分 / 架构与 SQL" },
  { icon: Collection, title: "双知识体系", desc: "知识库原文精确 + Wiki 全局理解" },
  { icon: Promotion, title: "人机协作", desc: "工作群消息总线，MCP 供 Agent 读写" },
];

const loginForm = reactive({ username: "", password: "", captchaId: "", captchaCode: "" });

const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
  captchaCode: [{ required: true, message: "请输入验证码", trigger: "blur" }],
};

async function loadCaptcha() {
  try {
    const { data } = await getCaptcha();
    captchaImage.value = data.image;
    loginForm.captchaId = data.captcha_id;
    loginForm.captchaCode = "";
  } catch {
    captchaImage.value = "";
  }
}

async function loadRsaKey() {
  try {
    const { data } = await getRsaPublicKey();
    publicKey.value = data.public_key;
  } catch {
    publicKey.value = "";
  }
}

// 用 RSA 公钥加密登录参数（username/password/验证码整体）
function buildEncrypted() {
  const enc = new JSEncrypt();
  enc.setPublicKey(publicKey.value);
  return enc.encrypt(
    JSON.stringify({
      username: loginForm.username,
      password: loginForm.password,
      captcha_id: loginForm.captchaId,
      captcha_code: loginForm.captchaCode,
    })
  );
}

async function handleLogin() {
  const valid = await loginFormRef.value.validate().catch(() => false);
  if (!valid) return;
  if (!publicKey.value) {
    ElMessage.error("未获取到加密公钥，请刷新页面重试");
    return;
  }
  const encrypted = buildEncrypted();
  if (!encrypted) {
    ElMessage.error("登录参数加密失败，请刷新验证码后重试");
    loadCaptcha();
    return;
  }
  loading.value = true;
  try {
    await auth.login({ encrypted });
    ElMessage.success("登录成功");
    router.push({ name: "dashboard" });
  } catch (e) {
    ElMessage.error(
      e.response?.data?.non_field_errors?.[0] ||
        e.response?.data?.encrypted?.[0] ||
        e.response?.data?.detail ||
        "登录失败"
    );
    loadCaptcha();
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadCaptcha();
  loadRsaKey();
});
</script>

<style scoped>
.login {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(420px, 0.95fr);
  min-height: 100vh;
  background: var(--bg-page);
}

/* ── 左侧品牌区 ── */
.login__brand {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 28px;
  padding: 44px 56px;
  overflow: hidden;
  color: #fff;
  background: radial-gradient(1100px 620px at 8% 0%, rgba(79, 110, 247, 0.42), transparent 62%),
    radial-gradient(900px 520px at 96% 100%, rgba(34, 211, 238, 0.26), transparent 60%),
    linear-gradient(158deg, #0b1224 0%, #121b31 58%, #0d1626 100%);
}
.deco-grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: radial-gradient(120% 90% at 20% 10%, #000 20%, transparent 78%);
  -webkit-mask-image: radial-gradient(120% 90% at 20% 10%, #000 20%, transparent 78%);
}
.deco-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.55;
  pointer-events: none;
}
.deco-orb--a {
  width: 420px;
  height: 420px;
  right: -120px;
  top: -90px;
  background: radial-gradient(circle, rgba(124, 92, 255, 0.85), transparent 68%);
  animation: orb-float 14s ease-in-out infinite;
}
.deco-orb--b {
  width: 360px;
  height: 360px;
  left: -110px;
  bottom: -120px;
  background: radial-gradient(circle, rgba(34, 211, 238, 0.65), transparent 68%);
  animation: orb-float 18s ease-in-out infinite reverse;
}
@keyframes orb-float {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(-24px, 26px, 0) scale(1.06);
  }
}

.brand-head {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(6px);
}
.brand-head__text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}
.brand-head__text b {
  font-size: 15px;
  letter-spacing: 0.2px;
}
.brand-head__text span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.brand-main {
  position: relative;
  max-width: 620px;
}
.brand-main h1 {
  margin: 18px 0 0;
  font-size: clamp(28px, 3.1vw, 40px);
  line-height: 1.22;
  font-weight: 750;
  letter-spacing: -0.6px;
}
.brand-sub {
  margin: 14px 0 0;
  max-width: 520px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(255, 255, 255, 0.68);
}

.feature-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
  margin: 26px 0 0;
  padding: 0;
  list-style: none;
}
.feature-list li {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 13px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.055);
  border: 1px solid rgba(255, 255, 255, 0.09);
  transition: background var(--dur) var(--ease), transform var(--dur) var(--ease);
}
.feature-list li:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}
.f-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 9px;
  font-size: 16px;
  background: linear-gradient(135deg, rgba(79, 110, 247, 0.9), rgba(124, 92, 255, 0.9));
  box-shadow: 0 8px 18px -10px rgba(79, 110, 247, 0.9);
}
.feature-list b {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
}
.feature-list small {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.55);
}

.flow-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 24px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}
.flow-line span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.flow-line i {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  font-style: normal;
  font-weight: 700;
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.16);
}
.flow-line em {
  width: 16px;
  height: 1px;
  margin: 0 2px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0.12));
}

.brand-foot {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  gap: 34px;
  padding-top: 22px;
  border-top: 1px solid rgba(255, 255, 255, 0.09);
}
.brand-foot .stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.brand-foot .stat b {
  font-size: 22px;
  font-weight: 750;
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
}
.brand-foot .stat b small {
  font-size: 13px;
  margin-left: 1px;
}
.brand-foot .stat span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

/* ── 右侧表单区 ── */
.login__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding: 40px 32px;
  background: radial-gradient(900px 600px at 100% 0%, #eef2ff 0%, transparent 58%),
    radial-gradient(700px 500px at 0% 100%, #ecfeff 0%, transparent 55%), var(--bg-page);
}
.panel-card {
  width: 100%;
  max-width: 420px;
  padding: 34px 34px 28px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 32px 64px -32px rgba(15, 23, 42, 0.32), 0 2px 8px -4px rgba(15, 23, 42, 0.06);
}
.panel-logo {
  display: none;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  font-size: 14px;
  color: var(--ink-700);
}
.brand-mark--light {
  background: var(--grad-brand);
  border: none;
  width: 40px;
  height: 40px;
  border-radius: 12px;
}
.panel-card h2 {
  margin: 0;
  font-size: 25px;
  font-weight: 750;
  letter-spacing: -0.4px;
  color: var(--ink-900);
}
.panel-sub {
  margin: 8px 0 24px;
  font-size: 13.5px;
  color: var(--ink-400);
}
.panel-card :deep(.el-form-item) {
  margin-bottom: 18px;
}
.panel-card :deep(.el-form-item__label) {
  padding-bottom: 6px;
  font-size: 13px;
  color: var(--ink-500);
}
.panel-card :deep(.el-input__wrapper) {
  padding: 4px 14px;
  border-radius: 12px;
}
.captcha-row {
  display: flex;
  gap: 10px;
  width: 100%;
}
.captcha-box {
  position: relative;
  width: 132px;
  height: 42px;
  flex: 0 0 132px;
  padding: 0;
  border-radius: 12px;
  border: 1px solid var(--line-strong);
  background: #fff;
  overflow: hidden;
  cursor: pointer;
  transition: border-color var(--dur) var(--ease);
}
.captcha-box:hover {
  border-color: var(--brand-400);
}
.captcha-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.captcha-refresh {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--ink-300);
  font-size: 18px;
}
.captcha-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 12px;
  color: #fff;
  background: rgba(15, 23, 42, 0.62);
  opacity: 0;
  transition: opacity var(--dur) var(--ease);
}
.captcha-box:hover .captcha-mask {
  opacity: 1;
}
.submit {
  width: 100%;
  height: 46px;
  margin-top: 4px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
}
.panel-foot {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px dashed var(--line-strong);
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-400);
}
.panel-foot .el-icon {
  margin-top: 3px;
  color: var(--brand-400);
}
.panel-foot code {
  padding: 1px 5px;
  border-radius: 5px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--brand-600);
  background: var(--brand-50);
}
.panel-copy {
  margin: 0;
  font-size: 12px;
  color: var(--ink-300);
}

/* ── 响应式 ── */
@media (max-width: 1120px) {
  .login__brand {
    padding: 36px 34px;
  }
  .feature-list {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .login {
    grid-template-columns: 1fr;
  }
  .login__brand {
    display: none;
  }
  .login__panel {
    padding: 24px 18px 34px;
  }
  .panel-logo {
    display: flex;
  }
}
</style>
