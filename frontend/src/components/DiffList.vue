<script setup lang="ts">
import { computed, ref } from "vue";
import { getDiffSummary, isOnlyInDiff } from "../utils/diffUtils";
import type { DiffRecord } from "../types";

const props = defineProps<{
  items: DiffRecord[];
  activeIndex: number | null;
  horizontal?: boolean;
}>();

const emit = defineEmits<{
  select: [number];
}>();

const kindFilter = ref<"all" | "only-in" | "other">("all");
const typeKeyword = ref("");

const filteredItems = computed(() =>
  props.items
    .map((item, originalIndex) => ({ item, originalIndex }))
    .filter(({ item }) => {
      const onlyIn = isOnlyInDiff(item);
      const matchKind =
        kindFilter.value === "all" ||
        (kindFilter.value === "only-in" && onlyIn) ||
        (kindFilter.value === "other" && !onlyIn);
      const keyword = typeKeyword.value.trim().toLowerCase();
      const summary = getDiffSummary(item).toLowerCase();
      const matchKeyword =
        !keyword ||
        item.diff_id.toLowerCase().includes(keyword) ||
        item.payload.diff_type.toLowerCase().includes(keyword) ||
        item.scope.path_a.toLowerCase().includes(keyword) ||
        item.scope.path_b.toLowerCase().includes(keyword) ||
        summary.includes(keyword);
      return matchKind && matchKeyword;
    })
);
</script>

<template>
  <div class="diff-list-wrap" :class="{ 'diff-list-wrap--horizontal': horizontal }">
    <div class="diff-toolbar">
      <el-select v-model="kindFilter" size="small">
        <el-option label="全部差异" value="all" />
        <el-option label="仅一侧存在" value="only-in" />
        <el-option label="内容差异" value="other" />
      </el-select>
      <el-input v-model="typeKeyword" size="small" placeholder="筛选 ID/类型/路径" />
    </div>

    <el-scrollbar v-if="!horizontal" class="diff-scroll">
      <div
        v-for="row in filteredItems"
        :key="row.item.diff_id"
        class="diff-item"
        :class="{ active: props.activeIndex === row.originalIndex }"
        @click="emit('select', row.originalIndex)"
      >
        <div class="diff-item-head">
          <el-tag size="small">{{ row.item.diff_id }}</el-tag>
          <el-tag size="small" :type="isOnlyInDiff(row.item) ? 'primary' : 'danger'">
            {{ row.item.payload.diff_type }}
          </el-tag>
        </div>
        <p class="diff-path">A: {{ row.item.scope.path_a }}</p>
        <p class="diff-path">B: {{ row.item.scope.path_b }}</p>
        <p class="diff-content">{{ getDiffSummary(row.item) }}</p>
      </div>
    </el-scrollbar>

    <div v-else class="diff-scroll diff-scroll-horizontal">
      <div
        v-for="row in filteredItems"
        :key="row.item.diff_id"
        class="diff-item"
        :class="{ active: props.activeIndex === row.originalIndex }"
        @click="emit('select', row.originalIndex)"
      >
        <div class="diff-item-head">
          <el-tag size="small">{{ row.item.diff_id }}</el-tag>
          <el-tag size="small" :type="isOnlyInDiff(row.item) ? 'primary' : 'danger'">
            {{ row.item.payload.diff_type }}
          </el-tag>
        </div>
        <p class="diff-path">A: {{ row.item.scope.path_a }}</p>
        <p class="diff-path">B: {{ row.item.scope.path_b }}</p>
        <p class="diff-content">{{ getDiffSummary(row.item) }}</p>
      </div>
    </div>
  </div>
</template>
