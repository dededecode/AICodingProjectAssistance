<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2 class="title">AICodingProjectAssistance（AICoding项目辅助、管理系统）</h2>
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="loginForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item label="验证码" prop="captchaCode">
          <div class="captcha-row">
            <el-input v-model="loginForm.captchaCode" placeholder="请输入验证码" maxlength="4" style="width: 100%" @keyup.enter="handleLogin" />
            <img v-if="captchaImage" :src="captchaImage" alt="验证码" class="captcha-img" title="点击刷新" @click="loadCaptcha" />
          </div>
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="handleLogin">
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import JSEncrypt from "jsencrypt";
import { useAuthStore } from "../stores/auth";
import { getCaptcha, getRsaPublicKey } from "../api/auth";

const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const loginFormRef = ref();
const captchaImage = ref("");
const publicKey = ref("");

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
  await loginFormRef.value.validate();
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
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f3b73 0%, #2d6a9f 100%);
}
.login-card {
  width: 420px;
  padding: 12px 8px;
}
.title {
  text-align: center;
  margin-bottom: 16px;
  color: #1f3b73;
  font-size: 17px;
  line-height: 1.4;
}
.captcha-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.captcha-img {
  height: 40px;
  width: 130px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  flex-shrink: 0;
}
</style>
