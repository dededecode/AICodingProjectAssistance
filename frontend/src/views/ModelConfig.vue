<template>
  <div v-loading="loading">
    <el-card shadow="never">
      <h3 style="margin: 0 0 16px">模型管理</h3>
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 16px"
        title="此处配置你个人的大模型与多模态模型，保存后仅你的请求使用该 Key（未配置回退服务器环境变量）。嵌入模型为全局共享配置，仅管理员可修改。"
      />

      <el-divider content-position="left">大模型（LLM，OpenAI 兼容协议）</el-divider>
      <el-form :model="user" label-width="200px" style="max-width: 640px">
        <el-form-item label="Base URL">
          <el-input v-model="user.llm_base_url" placeholder="如 https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="user.llm_api_key" placeholder="留空则回退环境变量" show-password />
        </el-form-item>
        <el-form-item label="模型名">
          <el-input v-model="user.llm_model" placeholder="如 deepseek-chat" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">多模态 LLM（Vision，用于图文文档图片解析）</el-divider>
      <el-form :model="user" label-width="200px" style="max-width: 640px">
        <el-form-item label="Base URL">
          <el-input v-model="user.vision_base_url" placeholder="留空则复用 LLM Base URL" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="user.vision_api_key" placeholder="留空则复用 LLM API Key" show-password />
        </el-form-item>
        <el-form-item label="多模态模型名">
          <el-input v-model="user.vision_model" placeholder="如 gpt-4o / qwen-vl" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">嵌入模型（Embedding，全局共享）</el-divider>
      <el-form :model="embedding" label-width="200px" style="max-width: 640px">
        <el-form-item label="模式">
          <el-select v-model="embedding.embedding_mode" style="width: 100%" :disabled="!hasBtn('btn:model-embedding')">
            <el-option label="本地（local，sentence-transformers）" value="local" />
            <el-option label="远程（remote，OpenAI 兼容端点）" value="remote" />
          </el-select>
        </el-form-item>
        <el-form-item label="本地模型名">
          <el-input v-model="embedding.embedding_model" placeholder="如 BAAI/bge-small-zh-v1.5" :disabled="embedding.embedding_mode === 'remote' || !hasBtn('btn:model-embedding')" />
        </el-form-item>
        <el-form-item label="远程 Base URL">
          <el-input v-model="embedding.llm_embedding_base_url" placeholder="如 http://localhost:11434/v1" :disabled="embedding.embedding_mode !== 'remote' || !hasBtn('btn:model-embedding')" />
        </el-form-item>
        <el-form-item label="远程模型名">
          <el-input v-model="embedding.llm_embedding_model" placeholder="如 nomic-embed-text" :disabled="embedding.embedding_mode !== 'remote' || !hasBtn('btn:model-embedding')" />
        </el-form-item>
        <el-form-item v-if="!hasBtn('btn:model-embedding')">
          <span style="color: #909399; font-size: 12px">嵌入模型为全局共享，当前角色无修改权限。</span>
        </el-form-item>
      </el-form>

      <div style="margin-top: 16px">
        <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
        <el-button :loading="testing.llm" @click="test('llm')">测试 LLM 连接</el-button>
        <el-button :loading="testing.vision" @click="test('vision')">测试多模态</el-button>
        <el-button :loading="testing.embedding" @click="test('embedding')">测试 Embedding</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { getAiConfig, saveAiConfig, testAiConfig } from "../api/aiConfig";
import { hasPerm } from "../rbac";

const hasBtn = (code) => hasPerm(code);

const loading = ref(false);
const saving = ref(false);
const testing = reactive({ llm: false, vision: false, embedding: false });
const user = reactive({
  llm_base_url: "",
  llm_api_key: "",
  llm_model: "",
  vision_base_url: "",
  vision_api_key: "",
  vision_model: "",
});
const embedding = reactive({
  embedding_mode: "local",
  embedding_model: "",
  llm_embedding_base_url: "",
  llm_embedding_model: "",
});

async function load() {
  loading.value = true;
  try {
    const { data } = await getAiConfig();
    if (data.user) Object.assign(user, data.user);
    if (data.embedding) Object.assign(embedding, data.embedding);
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const payload = { user: { ...user } };
    if (hasBtn("btn:model-embedding")) payload.embedding = { ...embedding };
    await saveAiConfig(payload);
    ElMessage.success("配置已保存");
    load();
  } finally {
    saving.value = false;
  }
}

async function test(kind) {
  testing[kind] = true;
  try {
    const { data } = await testAiConfig(kind);
    if (data.ok) ElMessage.success(data.message);
    else ElMessage.error(data.message);
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "测试失败");
  } finally {
    testing[kind] = false;
  }
}

onMounted(load);
</script>
