<script setup lang="ts">
import type { Summary } from "../../types";

defineProps<{
  summary: Summary;
}>();
</script>

<template>
  <!-- 交通银行基本信息 -->
  <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
    <div class="summary-item">
      <p class="text-xs text-gray-400">开户机构</p>
      <p class="font-medium text-gray-700">{{ summary.bank_branch || "-" }}</p>
    </div>
    <div class="summary-item">
      <p class="text-xs text-gray-400">账号</p>
      <p class="font-medium text-gray-700 break-all">
        {{ summary.account_number || "-" }}
      </p>
    </div>
    <div class="summary-item">
      <p class="text-xs text-gray-400">户名</p>
      <p class="font-medium text-gray-700">{{ summary.account_name || "-" }}</p>
    </div>
  </div>
  <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mt-4">
    <div class="summary-item">
      <p class="text-xs text-gray-400">币种</p>
      <p class="font-medium text-gray-700">{{ summary.currency || "-" }}</p>
    </div>
    <div class="summary-item">
      <p class="text-xs text-gray-400">年份</p>
      <p class="font-medium text-gray-700">{{ summary.year || "-" }}</p>
    </div>
    <div class="summary-item">
      <p class="text-xs text-gray-400">月份</p>
      <p class="font-medium text-gray-700">{{ summary.month || "-" }}</p>
    </div>
  </div>
</template>
