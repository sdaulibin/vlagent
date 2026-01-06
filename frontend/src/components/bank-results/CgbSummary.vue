<script setup lang="ts">
import type { Summary } from '../../types';

defineProps<{
    summary: Summary;
}>();
</script>

<template>
    <!-- 广发银行基本信息 -->
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
            <p class="text-xs text-gray-400">起止日期</p>
            <p class="font-medium text-gray-700">{{ summary.date_range || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">账户当前余额</p>
            <p class="font-medium text-gray-700">{{ summary.current_balance || '-' }}</p>
        </div>
    </div>
    
    <!-- 广发银行汇总 -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4">
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
        <div class="summary-item">
            <p class="text-xs text-gray-500">记录数</p>
            <p class="font-bold text-gray-700">{{ summary.record_count || '0' }}</p>
        </div>
    </div>
</template>
