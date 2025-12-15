<script setup lang="ts">
import { ref, nextTick, computed } from 'vue';
import { useRouter } from 'vue-router';
import { 
    ArrowLeft, FileText, Search, ChevronLeft, ChevronRight,
    ZoomIn, ZoomOut, ArrowRightLeft, Download, AlertCircle, CheckCircle2, FileDiff
} from 'lucide-vue-next';
import { compareContracts, getTaskDiffs, getFilePreviewUrl } from '../api';

const router = useRouter();

// 状态管理
const activeView = ref<'upload' | 'result'>('upload');
const isProcessing = ref(false);
const fileA = ref<File | null>(null);
const fileB = ref<File | null>(null);
const filter = ref('all');
const syncScroll = ref(true);
const currentTaskId = ref<number | null>(null);
const errorMessage = ref('');

// 文档内容
const contentA = ref('');
const contentB = ref('');
const selectedDiffId = ref<number | null>(null);

// 获取文件类型
const getFileType = (filename: string | undefined): 'pdf' | 'image' | 'doc' | 'unknown' => {
    if (!filename) return 'unknown';
    const ext = filename.toLowerCase().split('.').pop();
    if (ext === 'pdf') return 'pdf';
    if (['jpg', 'jpeg', 'png', 'gif', 'bmp'].includes(ext || '')) return 'image';
    if (['doc', 'docx'].includes(ext || '')) return 'doc';
    return 'unknown';
};

// 文件预览 URL
const fileAPreviewUrl = computed(() => {
    if (!currentTaskId.value) return '';
    return getFilePreviewUrl(currentTaskId.value, 'a');
});

const fileBPreviewUrl = computed(() => {
    if (!currentTaskId.value) return '';
    return getFilePreviewUrl(currentTaskId.value, 'b');
});

const fileAType = computed(() => getFileType(fileA.value?.name));
const fileBType = computed(() => getFileType(fileB.value?.name));

// 差异数据
interface DiffItem {
    id: number;
    diff_type: string;
    original_text: string;
    comparison_text: string;
    location: string;
    status: string;
}

const diffs = ref<DiffItem[]>([]);

// 获取当前选中的差异
const selectedDiff = computed(() => {
    if (!selectedDiffId.value) return null;
    return diffs.value.find(d => d.id === selectedDiffId.value) || null;
});

// 高亮文本的HTML（原文档）
const highlightedContentA = computed(() => {
    if (!contentA.value) return '';
    const diff = selectedDiff.value;
    if (!diff || !diff.original_text) return escapeHtml(contentA.value);
    
    const searchText = diff.original_text.trim();
    if (!searchText) return escapeHtml(contentA.value);
    
    const escaped = escapeHtml(contentA.value);
    const searchEscaped = escapeHtml(searchText);
    
    // 高亮匹配的文本
    const regex = new RegExp(`(${escapeRegExp(searchEscaped)})`, 'gi');
    return escaped.replace(regex, '<mark class="bg-red-200 text-red-900 px-1 rounded">$1</mark>');
});

// 高亮文本的HTML（比对文档）
const highlightedContentB = computed(() => {
    if (!contentB.value) return '';
    const diff = selectedDiff.value;
    if (!diff || !diff.comparison_text) return escapeHtml(contentB.value);
    
    const searchText = diff.comparison_text.trim();
    if (!searchText) return escapeHtml(contentB.value);
    
    const escaped = escapeHtml(contentB.value);
    const searchEscaped = escapeHtml(searchText);
    
    // 高亮匹配的文本
    const regex = new RegExp(`(${escapeRegExp(searchEscaped)})`, 'gi');
    return escaped.replace(regex, '<mark class="bg-green-200 text-green-900 px-1 rounded">$1</mark>');
});

// 辅助函数：转义HTML
function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 辅助函数：转义正则表达式特殊字符
function escapeRegExp(text: string): string {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 计算属性
const filteredDiffs = () => {
    return diffs.value.filter(d => {
        if (d.status === 'ignored') return false;
        if (filter.value === 'all') return true;
        return d.diff_type === filter.value;
    });
};

const stats = () => ({
    all: diffs.value.length,
    added: diffs.value.filter(d => d.diff_type === 'added').length,
    modified: diffs.value.filter(d => d.diff_type === 'modified').length,
    deleted: diffs.value.filter(d => d.diff_type === 'deleted').length,
    ignored: diffs.value.filter(d => d.status === 'ignored').length
});

// 事件处理
const handleFileASelect = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
        fileA.value = input.files[0];
        console.log('Selected file A:', fileA.value.name);
    }
};

const handleFileBSelect = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
        fileB.value = input.files[0];
        console.log('Selected file B:', fileB.value.name);
    }
};

const startCompare = async () => {
    if (!fileA.value || !fileB.value) {
        alert('请上传两份文档');
        return;
    }
    
    isProcessing.value = true;
    errorMessage.value = '';
    
    try {
        console.log('Starting comparison...');
        const result = await compareContracts(fileA.value, fileB.value);
        console.log('Compare result:', result);
        
        currentTaskId.value = result.task_id;
        contentA.value = result.content_a || '';
        contentB.value = result.content_b || '';
        
        // 获取差异列表
        const diffsData = await getTaskDiffs(result.task_id);
        console.log('Diffs:', diffsData);
        diffs.value = diffsData;
        
        activeView.value = 'result';
    } catch (error: any) {
        console.error('Compare failed:', error);
        errorMessage.value = error.response?.data?.detail || '比对失败，请重试';
        alert(errorMessage.value);
    } finally {
        isProcessing.value = false;
    }
};

const handleIgnore = (id: number) => {
    diffs.value = diffs.value.map(d => 
        d.id === id ? { ...d, status: 'ignored' } : d
    );
};

const handleDiffClick = async (diff: DiffItem) => {
    selectedDiffId.value = diff.id;
    
    await nextTick();
    
    // 滚动到高亮的文本
    setTimeout(() => {
        const markA = document.querySelector('#doc-content-a mark');
        if (markA) {
            markA.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        
        const markB = document.querySelector('#doc-content-b mark');
        if (markB) {
            markB.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 100);
};

const goBack = () => {
    if (activeView.value === 'result') {
        activeView.value = 'upload';
        selectedDiffId.value = null;
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
                        <div id="doc-content-a" class="contract-doc-content p-0">
                            <!-- PDF Viewer -->
                            <iframe 
                                v-if="fileAType === 'pdf'" 
                                :src="fileAPreviewUrl" 
                                class="w-full h-full border-0"
                            ></iframe>
                            
                            <!-- Image Viewer -->
                            <div v-else-if="fileAType === 'image'" class="w-full h-full flex items-center justify-center bg-slate-100 overflow-auto p-4">
                                <img :src="fileAPreviewUrl" class="max-w-full h-auto shadow-lg rounded" />
                            </div>
                            
                            <!-- DOC/DOCX Text Viewer -->
                            <div v-else class="p-6 overflow-auto h-full">
                                <div 
                                    v-if="contentA" 
                                    class="max-w-3xl mx-auto whitespace-pre-wrap text-sm leading-relaxed select-text"
                                    v-html="highlightedContentA"
                                ></div>
                                <p v-else class="text-slate-400 text-center py-10">暂无内容</p>
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
                        <div id="doc-content-b" class="contract-doc-content p-0">
                            <!-- PDF Viewer -->
                            <iframe 
                                v-if="fileBType === 'pdf'" 
                                :src="fileBPreviewUrl" 
                                class="w-full h-full border-0"
                            ></iframe>
                            
                            <!-- Image Viewer -->
                            <div v-else-if="fileBType === 'image'" class="w-full h-full flex items-center justify-center bg-slate-100 overflow-auto p-4">
                                <img :src="fileBPreviewUrl" class="max-w-full h-auto shadow-lg rounded" />
                            </div>
                            
                            <!-- DOC/DOCX Text Viewer -->
                            <div v-else class="p-6 overflow-auto h-full">
                                <div 
                                    v-if="contentB" 
                                    class="max-w-3xl mx-auto whitespace-pre-wrap text-sm leading-relaxed select-text"
                                    v-html="highlightedContentB"
                                ></div>
                                <p v-else class="text-slate-400 text-center py-10">暂无内容</p>
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
                            :class="['diff-item', selectedDiffId === diff.id ? 'ring-2 ring-orange-500' : '']"
                            @click="handleDiffClick(diff)"
                        >
                            <div class="flex justify-between items-start mb-3">
                                <span :class="['diff-badge', `diff-badge-${diff.diff_type}`]">
                                    {{ diff.diff_type === 'added' ? '新增' : diff.diff_type === 'deleted' ? '删除' : '修改' }}
                                </span>
                                <button 
                                    @click="handleIgnore(diff.id)"
                                    class="text-slate-400 hover:text-slate-600 text-xs underline"
                                >
                                    忽略
                                </button>
                            </div>

                            <div class="space-y-3">
                                <div v-if="diff.original_text">
                                    <div class="text-[10px] text-slate-400 font-bold uppercase mb-1">原文</div>
                                    <div class="diff-text diff-text-original">{{ diff.original_text }}</div>
                                </div>
                                <div v-if="diff.comparison_text">
                                    <div class="text-[10px] text-slate-400 font-bold uppercase mb-1">比对</div>
                                    <div class="diff-text diff-text-compare">{{ diff.comparison_text }}</div>
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
