<script setup lang="ts">
import type { Summary } from '../../types';

defineProps<{
    summary: Summary;
}>();
</script>

<template>
    <!-- 中国银行基本信息（中英双语） -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">账号 Account No.</p>
            <p class="font-medium text-gray-700 break-all">{{ summary.account_number || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">账户名称 Account Name</p>
            <p class="font-medium text-gray-700">{{ summary.account_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">币种 Currency</p>
            <p class="font-medium text-gray-700">{{ summary.currency || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">账户类型 Account Type</p>
            <p class="font-medium text-gray-700">{{ summary.account_type || '-' }}</p>
        </div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mt-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">开户行 Bank Name</p>
            <p class="font-medium text-gray-700">{{ summary.bank_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">起始日期 From</p>
            <p class="font-medium text-gray-700">{{ summary.start_date || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">截止日期 To</p>
            <p class="font-medium text-gray-700">{{ summary.end_date || '-' }}</p>
        </div>
    </div>
</template>
