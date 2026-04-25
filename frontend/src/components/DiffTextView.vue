<script setup lang="ts">
import { computed } from 'vue';

interface DiffOp {
  op: number;  // -1=删除, 0=相等, 1=新增
  text: string;
}

const props = defineProps<{
  diffOpsJson: string | null;
  rawText: string | null;
  side: 'a' | 'b';
}>();

const diffOps = computed<DiffOp[]>(() => {
  if (!props.diffOpsJson) return [];
  try {
    const raw = JSON.parse(props.diffOpsJson);
    if (!Array.isArray(raw)) return [];
    // 后端序列化为 [[op, text], ...]，转为 [{op, text}, ...]
    return raw.map((item: any) => {
      if (Array.isArray(item)) {
        return { op: item[0] as number, text: item[1] as string };
      }
      return item as DiffOp;
    });
  } catch {
    return [];
  }
});

const filteredOps = computed(() => {
  if (props.side === 'a') {
    return diffOps.value.filter(d => d.op !== 1);
  }
  return diffOps.value.filter(d => d.op !== -1);
});

const hasDiffContent = computed(() => filteredOps.value.length > 0);
</script>

<template>
  <div v-if="hasDiffContent" class="diff-text-view">
    <span
      v-for="(item, idx) in filteredOps"
      :key="idx"
      :class="{
        'diff-del': item.op === -1,
        'diff-ins': item.op === 1,
      }"
    >{{ item.text }}</span>
  </div>
  <div v-else-if="rawText" class="diff-text-view">{{ rawText }}</div>
  <div v-else class="diff-empty">未提取到文本内容</div>
</template>

<style scoped>
.diff-text-view {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
  font-size: 14px;
  color: #1e293b;
}
.diff-del {
  background: #fca5a5;
  text-decoration: line-through;
  text-decoration-color: #dc2626;
  border-radius: 2px;
  padding: 0 1px;
}
.diff-ins {
  background: #86efac;
  border-radius: 2px;
  padding: 0 1px;
}
.diff-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  font-size: 14px;
}
</style>
