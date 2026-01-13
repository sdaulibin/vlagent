<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { CheckCircle, Clock, AlertCircle, ChevronLeft, ChevronRight, FileText, Loader2 } from 'lucide-vue-next';
import type { Transaction, Summary, BankType } from '../types';
import { BANK_TYPE_NAMES } from '../types';
import { getSummaryComponent } from './bank-results';

const props = defineProps<{
    results: Transaction[];
    summary: Summary | Summary[] | null;  // 支持汇总数组（广发银行多汇总）
    isProcessing: boolean;
    selectedFileId: number | null;
    selectedFileName: string;
}>();

const emit = defineEmits<{
    (e: 'export'): void;
}>();

const currentPage = ref(1);
const itemsPerPage = 10;
const activeSummaryTab = ref(0);  // 当前选中的汇总 Tab 索引

// 监听选中的文件变化，重置页码和 Tab
watch(() => props.selectedFileId, () => {
    currentPage.value = 1;
    activeSummaryTab.value = 0;
});

// 判断是否为多汇总模式
const isMultiSummary = computed(() => {
    return Array.isArray(props.summary) && props.summary.length > 1;
});

// 汇总列表（统一为数组）
const summaryList = computed<Summary[]>(() => {
    if (!props.summary) return [];
    return Array.isArray(props.summary) ? props.summary : [props.summary];
});

// 当前选中的汇总
const currentSummary = computed<Summary | null>(() => {
    if (summaryList.value.length === 0) return null;
    return summaryList.value[activeSummaryTab.value] ?? summaryList.value[0] ?? null;
});

// 获取当前 Tab 对应的交易明细
const currentResults = computed(() => {
    // 如果是广发银行多汇总模式，按 summary_id 过滤
    if (isMultiSummary.value && currentSummary.value?.id) {
        return props.results.filter(r => r.summary_id === currentSummary.value?.id);
    }
    return props.results;
});

const totalPages = computed(() => Math.ceil(currentResults.value.length / itemsPerPage));

const paginatedResults = computed(() => {
    const start = (currentPage.value - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    return currentResults.value.slice(start, end);
});

// 切换 Tab 时重置页码
const switchTab = (index: number) => {
    activeSummaryTab.value = index;
    currentPage.value = 1;
};

// 获取当前银行类型
const bankType = computed<BankType>(() => {
    return currentSummary.value?.bank_type || props.results[0]?.bank_type || 'shandong_local';
});

// 银行类型显示名称
const bankTypeName = computed(() => {
    return BANK_TYPE_NAMES[bankType.value] || '未知银行';
});

// 银行类型对应的颜色
const bankTypeColor = computed(() => {
    const colors: Record<BankType, string> = {
        'shandong_local': 'bg-blue-100 text-blue-700',
        'everbright': 'bg-purple-100 text-purple-700',
        'cmb': 'bg-red-100 text-red-700',
        'jining': 'bg-teal-100 text-teal-700',
        'cgb': 'bg-orange-100 text-orange-700',
        'psbc': 'bg-green-100 text-green-700',
        'icbc': 'bg-rose-100 text-rose-700',
        'ccb': 'bg-sky-100 text-sky-700',
        'abc': 'bg-emerald-100 text-emerald-700',
        'boc': 'bg-red-100 text-red-700',
        'bocom': 'bg-indigo-100 text-indigo-700'
    };
    return colors[bankType.value] || 'bg-gray-100 text-gray-700';
});

// 动态汇总组件
const SummaryComponent = computed(() => {
    return getSummaryComponent(bankType.value);
});

// 获取交易金额显示（用于交易明细）
const getAmountDisplay = (item: Transaction) => {
    if (bankType.value === 'everbright') {
        const isDebit = item.debit_credit === '借' || item.debit_credit === '借方';
        return {
            text: item.amount || '0',
            isIncome: !isDebit,
            prefix: isDebit ? '-' : '+'
        };
    } else if (bankType.value === 'cmb') {
        if (item.credit_amount && parseFloat(item.credit_amount) > 0) {
            return { text: item.credit_amount, isIncome: true, prefix: '+' };
        }
        return { text: item.debit_amount || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'jining') {
        // 济宁银行：收入/支出
        if (item.income && parseFloat(item.income) > 0) {
            return { text: item.income, isIncome: true, prefix: '+' };
        }
        return { text: item.expense || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'cgb') {
        // 广发银行：收入/支出
        if (item.income && parseFloat(item.income) > 0) {
            return { text: item.income, isIncome: true, prefix: '+' };
        }
        return { text: item.expense || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'psbc') {
        // 邮储银行：收入/支出
        if (item.income && parseFloat(item.income) > 0) {
            return { text: item.income, isIncome: true, prefix: '+' };
        }
        return { text: item.expense || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'icbc') {
        // 工商银行：转入/转出
        if (item.income && parseFloat(item.income) > 0) {
            return { text: item.income, isIncome: true, prefix: '+' };
        }
        return { text: item.expense || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'ccb') {
        // 建设银行：贷方发生额（收入）/借方发生额（支出）
        if (item.credit_amount && parseFloat(item.credit_amount) > 0) {
            return { text: item.credit_amount, isIncome: true, prefix: '+' };
        }
        return { text: item.debit_amount || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'abc') {
        // 农业银行：收入金额/支出金额
        if (item.income && parseFloat(item.income) > 0) {
            return { text: item.income, isIncome: true, prefix: '+' };
        }
        return { text: item.expense || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'boc') {
        // 中国银行：贷方发生额（收入）/借方发生额（支出）
        if (item.credit_amount && parseFloat(item.credit_amount) > 0) {
            return { text: item.credit_amount, isIncome: true, prefix: '+' };
        }
        return { text: item.debit_amount || '0', isIncome: false, prefix: '-' };
    } else if (bankType.value === 'bocom') {
        // 交通银行：贷方发生额（收入）/借方发生额（支出）
        if (item.credit_amount && parseFloat(item.credit_amount) > 0) {
            return { text: item.credit_amount, isIncome: true, prefix: '+' };
        }
        return { text: item.debit_amount || '0', isIncome: false, prefix: '-' };
    } else {
        // 山东地方银行
        if (item.income && parseFloat(item.income) > 0) {
            return { text: item.income, isIncome: true, prefix: '+' };
        }
        return { text: item.expense || '0', isIncome: false, prefix: '-' };
    }
};

// 获取交易日期显示
const getDateDisplay = (item: Transaction) => {
    return item.transaction_date || item.transaction_time || item.booking_date || '-';
};

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
                <!-- 银行类型标签 -->
                <span v-if="currentSummary" :class="['text-xs font-medium px-2 py-1 rounded-full', bankTypeColor]">
                    {{ bankTypeName }}
                </span>
            </span>
            <span v-if="isProcessing" class="text-sm font-normal text-blue-600 flex items-center gap-2 animate-pulse">
                <Clock class="w-4 h-4" />
                AI正在分析数据...
            </span>
        </h2>
        
        <div class="flex-1 overflow-hidden bg-gray-50 rounded-lg border border-gray-200 flex flex-col min-h-0">
            <!-- 加载状态 -->
            <div v-if="isProcessing && results.length === 0 && !summary" class="h-full flex flex-col items-center justify-center text-blue-500 space-y-4">
                <Loader2 class="w-12 h-12 animate-spin text-blue-400" />
                <p class="text-slate-500 font-medium">正在读取数据...</p>
            </div>
            
            <!-- 空状态 -->
            <div v-else-if="results.length === 0 && !summary" class="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
                <div class="bg-gray-100 p-6 rounded-full">
                    <AlertCircle class="w-12 h-12 text-gray-300" />
                </div>
                <p>请点击左侧文件查看识别结果</p>
            </div>
            <div v-else class="flex flex-col h-full">
                <div class="flex-1 overflow-auto custom-scrollbar p-4">
                    <!-- 多汇总 Tab 导航 -->
                    <div v-if="isMultiSummary" class="mb-4 border-b border-gray-200">
                        <nav class="flex gap-1 -mb-px overflow-x-auto">
                            <button
                                v-for="(item, index) in summaryList"
                                :key="index"
                                @click="switchTab(index)"
                                :class="[
                                    'px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors',
                                    activeSummaryTab === index
                                        ? 'border-orange-500 text-orange-600'
                                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                ]"
                            >
                                {{ item.date_range || `汇总${index + 1}` }}
                            </button>
                        </nav>
                    </div>
                    
                    <!-- 汇总信息区域 -->
                    <div v-if="currentSummary" class="summary-section mb-6">
                        <div class="flex items-center gap-2 mb-4">
                            <FileText class="w-5 h-5 text-blue-500" />
                            <h3 class="font-semibold text-gray-700">汇总信息</h3>
                        </div>
                        
                        <!-- 动态汇总组件 -->
                        <component :is="SummaryComponent" :summary="currentSummary" />
                    </div>
                    
                    <!-- 明细列表分隔线 -->
                    <div v-if="currentSummary && currentResults.length > 0" class="flex items-center gap-2 mb-4">
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
                                        <div v-if="bankType === 'shandong_local'">
                                            <p class="text-xs text-gray-400">交易时间</p>
                                            <p class="font-medium text-gray-700">{{ getDateDisplay(item) }}</p>
                                        </div>
                                        <div v-else>
                                            <p class="text-xs text-gray-400">交易日期</p>
                                            <p class="font-medium text-gray-700">{{ getDateDisplay(item) }}</p>
                                        </div>
                                        <!-- 光大银行时间字段 -->
                                        <div v-if="bankType === 'everbright'">
                                            <p class="text-xs text-gray-400">时间</p>
                                            <p class="font-medium text-gray-700">{{ item.time || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'shandong_local'">
                                            <p class="text-xs text-gray-400">交易渠道</p>
                                            <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                                                {{ item.channel || '-' }}
                                            </span>
                                        </div>
                                        <div v-else-if="bankType === 'everbright'">
                                            <p class="text-xs text-gray-400">借/贷</p>
                                            <span :class="['inline-block px-2 py-0.5 rounded text-xs font-medium', item.debit_credit === '贷' || item.debit_credit === '贷方' ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600']">
                                                {{ item.debit_credit || '-' }}
                                            </span>
                                        </div>
                                        <div v-else-if="bankType === 'cmb'">
                                            <p class="text-xs text-gray-400">交易类型</p>
                                            <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                                                {{ item.transaction_type || '-' }}
                                            </span>
                                        </div>
                                        <div v-else-if="bankType === 'jining'">
                                            <p class="text-xs text-gray-400">交易渠道</p>
                                            <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                                                {{ item.channel || '-' }}
                                            </span>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">交易金额</p>
                                            <p :class="['font-bold', getAmountDisplay(item).isIncome ? 'text-red-500' : 'text-green-600']">
                                                {{ getAmountDisplay(item).prefix }}{{ getAmountDisplay(item).text }}
                                            </p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">账户余额</p>
                                            <p class="font-medium text-gray-700">{{ item.balance || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'shandong_local'">
                                            <p class="text-xs text-gray-400">币种</p>
                                            <p class="text-sm text-gray-600">{{ item.currency || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'everbright'">
                                            <p class="text-xs text-gray-400">流水号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.serial_no">{{ item.serial_no || '-' }}</p>
                                        </div>
                                        <!-- 招商银行交易流水号 -->
                                        <div v-else-if="bankType === 'cmb'">
                                            <p class="text-xs text-gray-400">交易流水号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.transaction_serial_no">{{ item.transaction_serial_no || '-' }}</p>
                                        </div>
                                        <!-- 广发银行流水号 -->
                                        <div v-else-if="bankType === 'cgb'">
                                            <p class="text-xs text-gray-400">流水号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.serial_no">{{ item.serial_no || '-' }}</p>
                                        </div>
                                        <!-- 邮储银行流水号 -->
                                        <div v-else-if="bankType === 'psbc'">
                                            <p class="text-xs text-gray-400">交易流水号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.serial_no">{{ item.serial_no || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'psbc'">
                                            <p class="text-xs text-gray-400">全局路由号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.global_route_no">{{ item.global_route_no || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'psbc'">
                                            <p class="text-xs text-gray-400">记账日期</p>
                                            <p class="text-sm text-gray-600">{{ item.transaction_date || '-' }}</p>
                                        </div>
                                        <!-- 工商银行字段 -->
                                        <div v-else-if="bankType === 'icbc'">
                                            <p class="text-xs text-gray-400">借贷标志</p>
                                            <span :class="['inline-block px-2 py-0.5 rounded text-xs font-medium', item.debit_credit === '贷' ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600']">
                                                {{ item.debit_credit || '-' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                                        <!-- 山东银行/光大银行: 对方户名/对方名称 -->
                                        <div v-if="bankType === 'shandong_local'">
                                            <p class="text-xs text-gray-400">对方户名</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'everbright'">
                                            <p class="text-xs text-gray-400">对方名称</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'cmb'">
                                            <p class="text-xs text-gray-400">收(付)方名称</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'cgb'">
                                            <p class="text-xs text-gray-400">对方户名</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'psbc'">
                                            <p class="text-xs text-gray-400">对方户名</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'icbc'">
                                            <p class="text-xs text-gray-400">对方单位</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'ccb'">
                                            <p class="text-xs text-gray-400">对方户名</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_name">{{ item.counterparty_name || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'boc'">
                                            <p class="text-xs text-gray-400">备注 (对方信息)</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.notes">{{ item.notes || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'psbc'">
                                            <p class="text-xs text-gray-400">对方行名</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_bank">{{ item.counterparty_bank || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'icbc'">
                                            <p class="text-xs text-gray-400">对方行号</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_bank_code">{{ item.counterparty_bank_code || '-' }}</p>
                                        </div>
                                        
                                        <!-- 对方账号/收付方账号 -->
                                        <div v-if="bankType === 'cmb'">
                                            <p class="text-xs text-gray-400">收(付)方账号</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_account">{{ item.counterparty_account || '-' }}</p>
                                        </div>
                                        <div v-else>
                                            <p class="text-xs text-gray-400">对方账号</p>
                                            <p class="text-sm text-gray-700 truncate" :title="item.counterparty_account">{{ item.counterparty_account || '-' }}</p>
                                        </div>
                                        
                                        <!-- 摘要备注/摘要 -->
                                        <div v-if="bankType === 'shandong_local'">
                                            <p class="text-xs text-gray-400">摘要备注</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.description">{{ item.description || '-' }}</p>
                                        </div>
                                        <div v-else-if="bankType === 'boc'">
                                            <p class="text-xs text-gray-400">凭证号/业务号/用途/摘要</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.transaction_details">{{ item.transaction_details || '-' }}</p>
                                        </div>
                                        <div v-else>
                                            <p class="text-xs text-gray-400">摘要</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.description">{{ item.description || '-' }}</p>
                                        </div>
                                        
                                        <!-- 光大银行凭证号 -->
                                        <div v-if="bankType === 'everbright'">
                                            <p class="text-xs text-gray-400">凭证号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.voucher_no">{{ item.voucher_no || '-' }}</p>
                                        </div>
                                        
                                        <div v-if="bankType === 'cmb'">
                                            <p class="text-xs text-gray-400">公司一卡通号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.card_no">{{ item.card_no || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'psbc'">
                                            <p class="text-xs text-gray-400">用途</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.purpose">{{ item.purpose || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'icbc'">
                                            <p class="text-xs text-gray-400">用途</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.purpose">{{ item.purpose || '-' }}</p>
                                        </div>
                                        <div v-if="bankType === 'psbc'">
                                            <p class="text-xs text-gray-400">附言</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.postscript">{{ item.postscript || '-' }}</p>
                                        </div>
                                    </div>
                                    <!-- 招商银行打印实例号单独一行 -->
                                    <div v-if="bankType === 'cmb'" class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-2">
                                        <div>
                                            <p class="text-xs text-gray-400">打印实例号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.print_instance_no">{{ item.print_instance_no || '-' }}</p>
                                        </div>
                                    </div>
                                    <!-- 济宁银行交易对手信息单独一行 -->
                                    <div v-if="bankType === 'jining'" class="grid grid-cols-1 gap-4 mt-2">
                                        <div>
                                            <p class="text-xs text-gray-400">交易对手信息</p>
                                            <p class="text-sm text-gray-600" :title="item.counterparty_info">{{ item.counterparty_info || '-' }}</p>
                                        </div>
                                    </div>
                                    <!-- 广发银行额外字段 -->
                                    <div v-if="bankType === 'cgb'" class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-2">
                                        <div>
                                            <p class="text-xs text-gray-400">对方开户行</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.counterparty_bank">{{ item.counterparty_bank || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">凭证号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.voucher_no">{{ item.voucher_no || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">备注</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.remark">{{ item.remark || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">附言</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.postscript">{{ item.postscript || '-' }}</p>
                                        </div>
                                    </div>
                                    <!-- 建设银行额外字段 -->
                                    <div v-if="bankType === 'ccb'" class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-2">
                                        <div>
                                            <p class="text-xs text-gray-400">对方开户机构</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.counterparty_bank">{{ item.counterparty_bank || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">记账日期</p>
                                            <p class="text-sm text-gray-600">{{ item.booking_date || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">交易流水号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.transaction_serial">{{ item.transaction_serial || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">备注</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.remark">{{ item.remark || '-' }}</p>
                                        </div>
                                    </div>
                                    <div v-if="bankType === 'ccb'" class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-2">
                                        <div>
                                            <p class="text-xs text-gray-400">企业流水号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.enterprise_serial">{{ item.enterprise_serial || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">凭证种类</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.voucher_type">{{ item.voucher_type || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">凭证号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.voucher_number">{{ item.voucher_number || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">交易介质编号</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.transaction_medium">{{ item.transaction_medium || '-' }}</p>
                                        </div>
                                    </div>
                                    <!-- 中国银行额外字段 -->
                                    <div v-if="bankType === 'boc'" class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-2 border-t border-gray-100 pt-2">
                                        <div>
                                            <p class="text-xs text-gray-400">序号 No.</p>
                                            <p class="text-sm text-gray-600">{{ item.sequence || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">起息日 Val.D.</p>
                                            <p class="text-sm text-gray-600">{{ item.value_date || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">凭证 Vou.</p>
                                            <p class="text-sm text-gray-600">{{ item.voucher || '-' }}</p>
                                        </div>
                                        <div>
                                            <p class="text-xs text-gray-400">机构/柜员/流水 Reference No.</p>
                                            <p class="text-sm text-gray-600 truncate" :title="item.reference_no">{{ item.reference_no || '-' }}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Pagination Controls -->
                <div v-if="currentResults.length > 0" class="bg-white border-t border-gray-200 p-3 flex items-center justify-between flex-shrink-0">
                    <span class="text-sm text-gray-500">
                        显示 {{ (currentPage - 1) * itemsPerPage + 1 }} 到 {{ Math.min(currentPage * itemsPerPage, currentResults.length) }} 条，共 {{ currentResults.length }} 条
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
