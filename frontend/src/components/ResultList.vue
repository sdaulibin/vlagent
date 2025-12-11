<script setup lang="ts">
import { ref, computed } from 'vue';
import { CheckCircle, Clock, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-vue-next';
import type { Transaction } from '../types';

const props = defineProps<{
    results: Transaction[];
    isProcessing: boolean;
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
            <div v-if="results.length === 0" class="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
                <div class="bg-gray-100 p-6 rounded-full">
                    <AlertCircle class="w-12 h-12 text-gray-300" />
                </div>
                <p>请在左侧上传文件以开始识别</p>
            </div>
            <div v-else class="flex flex-col h-full">
                <div class="flex-1 overflow-auto custom-scrollbar p-4">
                    <div class="space-y-4">
                        <div v-for="(item, index) in paginatedResults" :key="item.id" class="result-item transition-shadow">
                            <div class="flex items-start gap-4">
                                <div class="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-bold">
                                    {{ (currentPage - 1) * itemsPerPage + index + 1 }}
                                </div>
                                <div class="flex-1 grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div>
                                        <p class="text-xs text-gray-400">交易日期</p>
                                        <p class="font-medium text-gray-700">{{ item.date }}</p>
                                    </div>
                                    <div>
                                        <p class="text-xs text-gray-400">交易类型</p>
                                        <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                                            {{ item.type }}
                                        </span>
                                    </div>
                                    <div>
                                        <p class="text-xs text-gray-400">交易金额</p>
                                        <p :class="`font-bold ${item.amount.startsWith('+') ? 'text-red-500' : 'text-green-600'}`">
                                            {{ item.amount }}
                                        </p>
                                    </div>
                                    <div>
                                        <p class="text-xs text-gray-400">摘要/备注</p>
                                        <p class="text-sm text-gray-600 truncate" :title="item.desc">{{ item.desc }}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Pagination Controls -->
                <div class="bg-white border-t border-gray-200 p-3 flex items-center justify-between flex-shrink-0">
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
            <button class="btn-secondary">导出 Excel</button>
            <button class="btn-primary">确认归档</button>
        </div>
    </div>
</template>
