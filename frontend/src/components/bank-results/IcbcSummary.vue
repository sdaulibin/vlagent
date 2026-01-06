<script setup lang="ts">
import type { Summary } from '../../types';

defineProps<{
    summary: Summary;
}>();
</script>

<template>
    <!-- 工商银行基本信息 -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div class="summary-item">
            <p class="text-xs text-gray-400">本方账号户名</p>
            <p class="font-medium text-gray-700">{{ summary.account_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">账号</p>
            <p class="font-medium text-gray-700 break-all">{{ summary.account_number || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">币种</p>
            <p class="font-medium text-gray-700">{{ summary.currency || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">本方账号开户行</p>
            <p class="font-medium text-gray-700">{{ summary.bank_name || '-' }}</p>
        </div>
        <div class="summary-item">
            <p class="text-xs text-gray-400">财务日期范围</p>
            <p class="font-medium text-gray-700">{{ summary.date_range || '-' }}</p>
        </div>
    </div>
</template>
