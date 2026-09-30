<template>
  <div class="rich-text">
    <template v-for="(seg, i) in segments" :key="i">
      <span v-if="seg.type === 'text'" class="rt-text">{{ seg.text }}</span>
      <span v-else class="rt-img" :key="'img' + i">
        <el-image
          :src="seg.url"
          :preview-src-list="[seg.url]"
          fit="contain"
          class="rt-image"
        />
        <div class="rt-img-name">{{ seg.name }}</div>
      </span>
    </template>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  content: { type: String, default: "" },
});

// 图片标记： 【图片:名称】(requirements/images/xxx/001_xx.png)
const IMG_RE = /【图片:([^】]+)】\(([^)]+)\)/g;

const segments = computed(() => {
  const text = props.content || "";
  const out = [];
  let last = 0;
  let m;
  IMG_RE.lastIndex = 0;
  while ((m = IMG_RE.exec(text)) !== null) {
    if (m.index > last) {
      out.push({ type: "text", text: text.slice(last, m.index) });
    }
    const rel = m[2].trim();
    out.push({ type: "img", name: m[1].trim(), url: `/media/${rel}` });
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    out.push({ type: "text", text: text.slice(last) });
  }
  return out;
});
</script>

<style scoped>
.rich-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.rt-text {
  white-space: pre-wrap;
}
.rt-img {
  display: block;
  margin: 8px 0;
}
.rt-image {
  max-width: 100%;
  max-height: 420px;
  cursor: pointer;
  border-radius: 4px;
}
.rt-img-name {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
</style>
