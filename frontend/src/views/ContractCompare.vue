<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { 
    ArrowLeft, FileText, Search, ChevronLeft, ChevronRight,
    ZoomIn, ZoomOut, ArrowRightLeft, Download, AlertCircle, CheckCircle2, FileDiff
} from 'lucide-vue-next';

const router = useRouter();

// 状态管理
const activeView = ref<'upload' | 'result'>('upload');
const isProcessing = ref(false);
const fileA = ref<File | null>(null);
const fileB = ref<File | null>(null);
const filter = ref('all');
const syncScroll = ref(true);

// 模拟差异数据
const diffs = ref([
    {
        id: 1,
        type: 'modified',
        original: '提供统一的集成开发环境（IDE）及全套开发管理工具，支持敏捷开发与标准化交付。',
        comparison: '支持接入行内统一运维平台进行应用自动化部署、服务管控、故障自愈、链路追踪等操作',
        location: '2.6 开发平台 / 3.1 兼容能力',
        status: 'pending'
    },
    {
        id: 2,
        type: 'deleted',
        original: '2.7 运维平台：运维平台需基于容器化架构，支持DevOps自动化体系...',
        comparison: '',
        location: '2.7 运维平台',
        status: 'pending'
    },
    {
        id: 3,
        type: 'added',
        original: '',
        comparison: '3.1 ★兼容能力：支持接入行内统一调度平台对批量任务进行操作管理',
        location: '3.1 兼容能力',
        status: 'pending'
    }
]);

// 计算属性
const filteredDiffs = () => {
    return diffs.value.filter(d => {
        if (d.status === 'ignored') return false;
        if (filter.value === 'all') return true;
        return d.type === filter.value;
    });
};

const stats = () => ({
    all: diffs.value.length,
    added: diffs.value.filter(d => d.type === 'added').length,
    modified: diffs.value.filter(d => d.type === 'modified').length,
    deleted: diffs.value.filter(d => d.type === 'deleted').length,
    ignored: diffs.value.filter(d => d.status === 'ignored').length
});

// 事件处理
const handleFileASelect = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
        fileA.value = input.files[0];
    }
};

const handleFileBSelect = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
        fileB.value = input.files[0];
    }
};

const startCompare = async () => {
    if (!fileA.value || !fileB.value) {
        alert('请上传两份文档');
        return;
    }
    isProcessing.value = true;
    // TODO: 调用后端 API
    setTimeout(() => {
        isProcessing.value = false;
        activeView.value = 'result';
    }, 1500);
};

const handleIgnore = (id: number) => {
    diffs.value = diffs.value.map(d => 
        d.id === id ? { ...d, status: 'ignored' } : d
    );
};

const goBack = () => {
    if (activeView.value === 'result') {
        activeView.value = 'upload';
    } else {
        router.push('/');
    }
};
</script>

<template>
    <div class="min-h-screen bg-slate-50">
        <!-- Upload View -->
        <div v-if="activeView === 'upload'" class="min-h-screen flex flex-col items-center justify-center p-8">
            <!-- Header -->
            <div class="w-full max-w-5xl mb-8">
                <button @click="goBack" class="flex items-center gap-2 text-slate-500 hover:text-slate-700 mb-6">
                    <ArrowLeft class="w-5 h-5" />
                    返回首页
                </button>
                <div class="text-center">
                    <div class="flex items-center justify-center gap-3 mb-4">
                        <div class="contract-logo">
                            <FileDiff class="w-8 h-8 text-white" />
                        </div>
                        <h1 class="text-3xl font-bold text-slate-900">合同比对</h1>
                    </div>
                    <p class="text-slate-500">上传两份文档以自动识别差异，支持 PDF, Word, 图片格式</p>
                </div>
            </div>

            <!-- Upload Areas -->
            <div class="w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                <!-- Document A -->
                <label class="contract-upload-area contract-upload-original">
                    <div class="contract-upload-badge contract-badge-original">原文档</div>
                    <input type="file" class="hidden" accept=".pdf,.docx,.doc,.jpg,.png" @change="handleFileASelect" />
                    <div class="contract-upload-icon contract-icon-original">
                        <FileText class="w-10 h-10" />
                    </div>
                    <h3 class="text-lg font-semibold text-slate-800 mb-2">
                        {{ fileA ? fileA.name : '点击或拖拽上传原文档' }}
                    </h3>
                    <p class="text-sm text-slate-400">支持 PDF, Word, 图片 (最大 50MB)</p>
                </label>

                <!-- Document B -->
                <label class="contract-upload-area contract-upload-compare">
                    <div class="contract-upload-badge contract-badge-compare">比对文档</div>
                    <input type="file" class="hidden" accept=".pdf,.docx,.doc,.jpg,.png" @change="handleFileBSelect" />
                    <div class="contract-upload-icon contract-icon-compare">
                        <FileText class="w-10 h-10" />
                    </div>
                    <h3 class="text-lg font-semibold text-slate-800 mb-2">
                        {{ fileB ? fileB.name : '点击或拖拽上传比对文档' }}
                    </h3>
                    <p class="text-sm text-slate-400">支持 PDF, Word, 图片 (最大 50MB)</p>
                </label>
            </div>

            <!-- Start Button -->
            <button 
                @click="startCompare" 
                :disabled="!fileA || !fileB || isProcessing"
                class="contract-btn-primary"
            >
                <Search class="w-5 h-5" />
                {{ isProcessing ? '比对中...' : '开始智能比对' }}
            </button>
        </div>

        <!-- Result View -->
        <div v-else class="h-screen flex flex-col">
            <!-- Toolbar -->
            <div class="contract-toolbar">
                <div class="flex items-center gap-4">
                    <button @click="goBack" class="p-2 hover:bg-slate-100 rounded-lg text-slate-500">
                        <ChevronLeft class="w-5 h-5" />
                    </button>
                    <div class="flex items-center gap-2 bg-slate-100 rounded-lg p-1">
                        <button class="p-1.5 hover:bg-white rounded-md">
                            <ChevronLeft class="w-4 h-4" />
                        </button>
                        <span class="text-sm font-medium w-16 text-center text-slate-600">1 / 1</span>
                        <button class="p-1.5 hover:bg-white rounded-md">
                            <ChevronRight class="w-4 h-4" />
                        </button>
                    </div>
                    <button 
                        @click="syncScroll = !syncScroll"
                        :class="['contract-sync-btn', syncScroll ? 'active' : '']"
                    >
                        <ArrowRightLeft class="w-4 h-4" />
                        同步翻页
                    </button>
                    <div class="flex items-center gap-1 text-slate-500">
                        <button class="p-2 hover:bg-slate-100 rounded-full">
                            <ZoomIn class="w-5 h-5" />
                        </button>
                        <button class="p-2 hover:bg-slate-100 rounded-full">
                            <ZoomOut class="w-5 h-5" />
                        </button>
                    </div>
                </div>
                <button class="contract-btn-export">
                    <Download class="w-4 h-4" />
                    导出差异报告
                </button>
            </div>

            <!-- Main Content -->
            <div class="flex-1 flex overflow-hidden">
                <!-- Document Panes -->
                <div class="flex-1 flex">
                    <!-- Original Doc -->
                    <div class="contract-doc-pane">
                        <div class="contract-doc-header contract-doc-header-original">
                            <span class="contract-doc-badge contract-badge-original">原</span>
                            <span class="font-medium text-slate-700 truncate">{{ fileA?.name || '原文档' }}</span>
                        </div>
                        <div class="contract-doc-content">
                            <div class="max-w-3xl mx-auto">
                                <p class="text-slate-600">文档内容预览区域...</p>
                            </div>
                        </div>
                    </div>

                    <!-- Divider -->
                    <div class="w-px bg-slate-300"></div>

                    <!-- Compare Doc -->
                    <div class="contract-doc-pane">
                        <div class="contract-doc-header contract-doc-header-compare">
                            <span class="contract-doc-badge contract-badge-compare">比对</span>
                            <span class="font-medium text-slate-700 truncate">{{ fileB?.name || '比对文档' }}</span>
                        </div>
                        <div class="contract-doc-content">
                            <div class="max-w-3xl mx-auto">
                                <p class="text-slate-600">文档内容预览区域...</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Diff List Sidebar -->
                <div class="contract-diff-sidebar">
                    <!-- Stats Header -->
                    <div class="p-5 border-b border-slate-100 bg-slate-50/50">
                        <div class="flex items-end justify-between mb-4">
                            <h2 class="text-xl font-bold text-slate-800">
                                差异项 <span class="text-orange-600">{{ stats().all - stats().ignored }}</span>
                            </h2>
                            <span class="text-sm text-slate-500">已忽略 {{ stats().ignored }}</span>
                        </div>

                        <!-- Filter Tabs -->
                        <div class="flex bg-slate-200/60 p-1 rounded-lg">
                            <button 
                                v-for="tab in [
                                    { id: 'all', label: '全部', count: stats().all },
                                    { id: 'added', label: '新增', count: stats().added },
                                    { id: 'modified', label: '修改', count: stats().modified },
                                    { id: 'deleted', label: '删除', count: stats().deleted }
                                ]"
                                :key="tab.id"
                                @click="filter = tab.id"
                                :class="['contract-filter-tab', filter === tab.id ? 'active' : '']"
                            >
                                {{ tab.label }} ({{ tab.count }})
                            </button>
                        </div>
                    </div>

                    <!-- Diff Items -->
                    <div class="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
                        <div 
                            v-for="diff in filteredDiffs()"
                            :key="diff.id"
                            class="diff-item"
                        >
                            <div class="flex justify-between items-start mb-3">
                                <span :class="['diff-badge', `diff-badge-${diff.type}`]">
                                    {{ diff.type === 'added' ? '新增' : diff.type === 'deleted' ? '删除' : '修改' }}
                                </span>
                                <button 
                                    @click="handleIgnore(diff.id)"
                                    class="text-slate-400 hover:text-slate-600 text-xs underline"
                                >
                                    忽略
                                </button>
                            </div>

                            <div class="space-y-3">
                                <div v-if="diff.original">
                                    <div class="text-[10px] text-slate-400 font-bold uppercase mb-1">原文</div>
                                    <div class="diff-text diff-text-original">{{ diff.original }}</div>
                                </div>
                                <div v-if="diff.comparison">
                                    <div class="text-[10px] text-slate-400 font-bold uppercase mb-1">比对</div>
                                    <div class="diff-text diff-text-compare">{{ diff.comparison }}</div>
                                </div>
                            </div>

                            <div class="mt-3 pt-3 border-t border-slate-50 flex items-center text-xs text-slate-400">
                                <AlertCircle class="w-3 h-3 mr-1" />
                                {{ diff.location }}
                            </div>
                        </div>

                        <div v-if="filteredDiffs().length === 0" class="text-center py-10 text-slate-400">
                            <CheckCircle2 class="w-10 h-10 mx-auto mb-2 opacity-50" />
                            <p>暂无此类差异</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
