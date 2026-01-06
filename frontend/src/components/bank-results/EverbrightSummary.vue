<script setup lang="ts">
import type { Summary } from '../../types';

defineProps<{
    summary: Summary;
}>();
</script>

<template>
    <!-- 光大银行基本信息 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">账户名称</p>
            <p class="font-medium text-gray-700">{{ summary.account_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">账号</p>
            <p class="font-medium text-gray-700 break-all">{{ summary.account_number || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">交易日期</p>
            <p class="font-medium text-gray-700">{{ summary.date_range || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">开户行</p>
            <p class="font-medium text-gray-700 break-all">{{ summary.bank_name || '-' }}</p>
        </div>
    </div>
    
    <!-- 光大银行汇总 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
        <div class="summary-item income-box">
            <p class="text-xs text-gray-500">贷方笔数</p>
            <p class="font-bold text-red-500">{{ summary.credit_count || '0' }}</p>
        </div>
        <div class="summary-item income-box">
            <p class="text-xs text-gray-500">贷方发生额</p>
            <p class="font-bold text-red-500">{{ summary.credit_amount || '0' }}</p>
        </div>
        <div class="summary-item expense-box">
            <p class="text-xs text-gray-500">借方笔数</p>
            <p class="font-bold text-green-600">{{ summary.debit_count || '0' }}</p>
        </div>
        <div class="summary-item expense-box">
            <p class="text-xs text-gray-500">借方发生额</p>
            <p class="font-bold text-green-600">{{ summary.debit_amount || '0' }}</p>
        </div>
    </div>
</template>
