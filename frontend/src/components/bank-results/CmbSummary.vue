<script setup lang="ts">
import type { Summary } from '../../types';

defineProps<{
    summary: Summary;
}>();
</script>

<template>
    <!-- 招商银行基本信息 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">账号名</p>
            <p class="font-medium text-gray-700">{{ summary.account_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">账号</p>
            <p class="font-medium text-gray-700 break-all">{{ summary.account_number || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">开始日期</p>
            <p class="font-medium text-gray-700">{{ summary.start_date || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">结束日期</p>
            <p class="font-medium text-gray-700">{{ summary.end_date || '-' }}</p>
        </div>
    </div>
    
    <!-- 招商银行汇总 -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4">
        <div class="summary-item income-box">
            <p class="text-xs text-gray-500">入账总笔数</p>
            <p class="font-bold text-red-500">{{ summary.credit_count || '0' }}</p>
        </div>
        <div class="summary-item income-box">
            <p class="text-xs text-gray-500">入账总金额</p>
            <p class="font-bold text-red-500">{{ summary.credit_total || '0' }}</p>
        </div>
        <div class="summary-item expense-box">
            <p class="text-xs text-gray-500">出账总笔数</p>
            <p class="font-bold text-green-600">{{ summary.debit_count || '0' }}</p>
        </div>
        <div class="summary-item expense-box">
            <p class="text-xs text-gray-500">出账总金额</p>
            <p class="font-bold text-green-600">{{ summary.debit_total || '0' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-500">笔数</p>
            <p class="font-bold text-gray-700">{{ summary.total_count || '0' }}</p>
        </div>
    </div>
</template>
