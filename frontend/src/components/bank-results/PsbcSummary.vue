<script setup lang="ts">
import type { Summary } from '../../types';

defineProps<{
    summary: Summary;
}>();
</script>

<template>
    <!-- 邮储银行基本信息 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">户名</p>
            <p class="font-medium text-gray-700">{{ summary.account_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">账号</p>
            <p class="font-medium text-gray-700 break-all">{{ summary.account_number || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">起始日期</p>
            <p class="font-medium text-gray-700">{{ summary.start_date || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">结束日期</p>
            <p class="font-medium text-gray-700">{{ summary.end_date || '-' }}</p>
        </div>
    </div>
    
    <!-- 邮储银行汇总 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
        <div class="summary-item income-box">
            <p class="text-xs text-gray-500">收入总笔数</p>
            <p class="font-bold text-red-500">{{ summary.income_count || '0' }}</p>
        </div>
        <div class="summary-item income-box">
            <p class="text-xs text-gray-500">收入总金额</p>
            <p class="font-bold text-red-500">{{ summary.income_total || '0' }}</p>
        </div>
        <div class="summary-item expense-box">
            <p class="text-xs text-gray-500">支出总笔数</p>
            <p class="font-bold text-green-600">{{ summary.expense_count || '0' }}</p>
        </div>
        <div class="summary-item expense-box">
            <p class="text-xs text-gray-500">支出总金额</p>
            <p class="font-bold text-green-600">{{ summary.expense_total || '0' }}</p>
        </div>
    </div>
</template>
