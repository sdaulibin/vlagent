<script setup lang="ts">
import type { Summary } from '../../types';

defineProps<{
    summary: Summary;
}>();
</script>

<template>
    <!-- 农业银行基本信息 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">账号</p>
            <p class="font-medium text-gray-700 break-all">{{ summary.account_number || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">户名</p>
            <p class="font-medium text-gray-700">{{ summary.account_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">币种</p>
            <p class="font-medium text-gray-700">{{ summary.currency || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">起止日期</p>
            <p class="font-medium text-gray-700">{{ summary.date_range || '-' }}</p>
        </div>
    </div>
    <!-- 收支汇总 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">总收入笔数</p>
            <p class="font-medium text-red-500">{{ summary.income_count || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">总收入金额</p>
            <p class="font-bold text-red-500">{{ summary.income_total || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">总支出笔数</p>
            <p class="font-medium text-green-600">{{ summary.expense_count || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">总支出金额</p>
            <p class="font-bold text-green-600">{{ summary.expense_total || '-' }}</p>
        </div>
    </div>
</template>
