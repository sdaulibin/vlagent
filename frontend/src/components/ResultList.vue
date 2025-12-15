<script setup lang="ts">
import { ref, computed } from 'vue';
import { CheckCircle, Clock, AlertCircle, ChevronLeft, ChevronRight, FileText } from 'lucide-vue-next';
import type { Transaction, Summary } from '../types';

const props = defineProps<{
    results: Transaction[];
    summary: Summary | null;
    isProcessing: boolean;
    selectedFileId: number | null;
    selectedFileName: string;
}>();

const emit = defineEmits<{
    (e: 'export'): void;
}>();

const currentPage = ref(1);
const itemsPerPage = 10;

const totalPages = computed(() => Math.ceil(props.results.length / itemsPerPage));

const paginatedResults = computed(() => {
    const start = (currentPage.value - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    return props.results.slice(start, end);
});

const nextPage = () => {
    if (currentPage.value < totalPages.value) {
        currentPage.value++;
    }
};

const prevPage = () => {
    if (currentPage.value > 1) {
        currentPage.value--;
    }
};
</script>

<template>
    <div class="card p-6 md:col-span-8 flex flex-col h-full min-h-0">
        <h2 class="card-title-lg flex-shrink-0">
            <span class="flex items-center gap-2">
                <CheckCircle class="w-6 h-6 text-green-500" />
                识别结果
            </span>
            <span v-if="isProcessing" class="text-sm font-normal text-blue-600 flex items-center gap-2 animate-pulse">
                <Clock class="w-4 h-4" />
                AI正在分析数据...
            </span>
        </h2>
        
        <div class="flex-1 overflow-hidden bg-gray-50 rounded-lg border border-gray-200 flex flex-col min-h-0">
            <div v-if="results.length === 0 && !summary" class="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
                <div class="bg-gray-100 p-6 rounded-full">
                    <AlertCircle class="w-12 h-12 text-gray-300" />
                </div>
                <p>请在左侧上传文件以开始识别</p>
            </div>
            <div v-else class="flex flex-col h-full">
                <div class="flex-1 overflow-auto custom-scrollbar p-4">
                    <!-- 汇总信息区域 -->
                    <div v-if="summary" class="summary-section mb-6">
                        <div class="flex items-center gap-2 mb-4">
                            <FileText class="w-5 h-5 text-blue-500" />
                            <h3 class="font-semibold text-gray-700">汇总信息</h3>
                        </div>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div class="summary-item">
                                <p class="text-xs text-gray-400">账户名称</p>
                                <p class="font-medium text-gray-700">{{ summary.account_name || '-' }}</p>
                            </div>
                            <div class="summary-item">
                                <p class="text-xs text-gray-400">账(卡)号</p>
                                <p class="font-medium text-gray-700 break-all">{{ summary.account_number || '-' }}</p>
                            </div>
                            <div class="summary-item">
                                <p class="text-xs text-gray-400">开户行</p>
                                <p class="font-medium text-gray-700 break-all">{{ summary.bank_name || '-' }}</p>
                            </div>
                            <div class="summary-item">
                                <p class="text-xs text-gray-400">起止日期</p>
                                <p class="font-medium text-gray-700">{{ summary.date_range || '-' }}</p>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                            <div class="summary-item income-box">
                                <p class="text-xs text-gray-500">收入笔数</p>
                                <p class="font-bold text-red-500">{{ summary.income_count || '0' }} 笔</p>
                            </div>
                            <div class="summary-item income-box">
                                <p class="text-xs text-gray-500">收入总额</p>
                                <p class="font-bold text-red-500">{{ summary.income_total || '0' }}</p>
                            </div>
                            <div class="summary-item expense-box">
                                <p class="text-xs text-gray-500">支出笔数</p>
                                <p class="font-bold text-green-600">{{ summary.expense_count || '0' }} 笔</p>
                            </div>
                            <div class="summary-item expense-box">
                                <p class="text-xs text-gray-500">支出总额</p>
                                <p class="font-bold text-green-600">{{ summary.expense_total || '0' }}</p>
                            </div>
                        </div>
                        <!-- <div class="grid grid-cols-2 gap-4 mt-4">
                            <div class="summary-item">
                                <p class="text-xs text-gray-400">是否盖章</p>
                                <span :class="['inline-block px-2 py-0.5 rounded text-xs font-medium', summary.has_stamp === '是' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600']">
                                    {{ summary.has_stamp || '-' }}
                                </span>
                            </div>
                            <div class="summary-item" v-if="summary.stamp_type">
                                <p class="text-xs text-gray-400">盖章类型</p>
                                <p class="font-medium text-gray-700">{{ summary.stamp_type }}</p>
                            </div>
                        </div> -->
                    </div>
                    
                    <!-- 明细列表分隔线 -->
                    <div v-if="summary && results.length > 0" class="flex items-center gap-2 mb-4">
                        <div class="flex-1 border-t border-gray-200"></div>
                        <span class="text-xs text-gray-400">交易明细</span>
                        <div class="flex-1 border-t border-gray-200"></div>
                    </div>
                    
                    <!-- 交易明细列表 -->
                    <div class="space-y-4">
                        <div v-for="(item, index) in paginatedResults" :key="item.id" class="result-item transition-shadow">
                            <div class="flex items-start gap-4">
                                <div class="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-bold">
                                    {{ (currentPage - 1) * itemsPerPage + index + 1 }}
                                </div>
                                <div class="flex-1">
                                    <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-2">
                                        <div>
                                            <p class="text-xs text-gray-400">交易日期</p>
                                            <p class="font-medium text-gray-700">{{ item.transaction_time }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">交易渠道</p>
                                            <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                                                {{ item.channel }}
                                            </span>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">交易金额</p>
                                            <p v-if="item.income && parseFloat(item.income) > 0" class="font-bold text-red-500">+{{ item.income }}</p>
                                            <p v-else class="font-bold text-green-600">-{{ item.expense }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">账户余额</p>
                                            <p class="font-medium text-gray-700">{{ item.balance }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">币种</p>
                                            <p class="text-sm text-gray-600">{{ item.currency }}</p>
                                        </div>
                                    </div>
                                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                        <div>
                                            <p class="text-xs text-gray-400">对方户名</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">对方账号</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_account">{{ item.counterparty_account }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">摘要/备注</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.description">{{ item.description }}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Pagination Controls -->
                <div v-if="results.length > 0" class="bg-white border-t border-gray-200 p-3 flex items-center justify-between flex-shrink-0">
                    <span class="text-sm text-gray-500">
                        显示 {{ (currentPage - 1) * itemsPerPage + 1 }} 到 {{ Math.min(currentPage * itemsPerPage, results.length) }} 条，共 {{ results.length }} 条
                    </span>
                    <div class="flex items-center gap-2">
                        <button 
                            @click="prevPage" 
                            :disabled="currentPage === 1"
                            class="pagination-btn"
                        >
                            <ChevronLeft class="w-5 h-5 text-gray-600" />
                        </button>
                        <span class="text-sm font-medium text-gray-700">
                            {{ currentPage }} / {{ totalPages }}
                        </span>
                        <button 
                            @click="nextPage" 
                            :disabled="currentPage === totalPages"
                            class="pagination-btn"
                        >
                            <ChevronRight class="w-5 h-5 text-gray-600" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="mt-4 pt-4 border-t border-gray-100 flex justify-end gap-3 flex-shrink-0">
            <button 
                class="btn-primary" 
                @click="emit('export')"
                :disabled="!selectedFileId"
            >导出结果</button>
        </div>
    </div>
</template>


