<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <h3 style="margin: 0">日志管理</h3>
        <div>
          <el-tag type="info" style="margin-right: 8px">嵌入模型远程调用日志</el-tag>
          <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
      <el-alert
        type="info"
        :closable="false"
        title="记录远程 Embedding 的调用时间与调用账号：当前用户未配置大模型 Key 时默认使用 admin 账号的 Key，日志中的「调用账号」即实际使用的 Key 归属账号。"
        style="margin-top: 12px"
      />
      <el-table :data="items" v-loading="loading" stripe style="margin-top: 12px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="调用账号" min-width="160">
          <template #default="{ row }">
            <el-tag size="small" :type="row.username === 'admin' ? 'warning' : row.username === 'env' ? 'info' : 'primary'">
              {{ row.username }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="called_at" label="调用时间" min-width="180" />
      </el-table>
      <div v-if="total" style="display: flex; justify-content: flex-end; margin-top: 12px">
        <el-pagination
          v-model:current-page="page"
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          @current-change="load"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { getEmbeddingLogs } from "../api/aiConfig";

const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const { data } = await getEmbeddingLogs({ page: page.value, page_size: pageSize.value });
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "加载日志失败");
  } finally {
    loading.value = false;
  }
}

function onSizeChange(size) {
  pageSize.value = size;
  page.value = 1;
  load();
}

onMounted(load);
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
