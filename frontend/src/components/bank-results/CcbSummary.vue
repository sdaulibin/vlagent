<script setup lang="ts">
import type { Summary } from "../../types";

defineProps<{
  summary: Summary;
}>();
</script>

<template>
  <!-- 建设银行基本信息 -->
  <div class="grid grid-cols-2 gap-4">
    <div class="summary-item">
      <p class="text-xs text-gray-400">本方户名</p>
      <p class="font-medium text-gray-700">{{ summary.account_name || "-" }}</p>
    </div>
    <div class="summary-item">
      <p class="text-xs text-gray-400">打印日期</p>
      <p class="font-medium text-gray-700">{{ summary.print_date || "-" }}</p>
    </div>
  </div>
</template>
