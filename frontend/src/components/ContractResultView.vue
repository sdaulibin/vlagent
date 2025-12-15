<script setup lang="ts">
import { computed } from 'vue';
import { 
    ChevronLeft, ChevronRight, ZoomIn, ZoomOut, 
    ArrowRightLeft, Download, AlertCircle, CheckCircle2 
} from 'lucide-vue-next';
import VueOfficeDocx from '@vue-office/docx';
import '@vue-office/docx/lib/index.css';

interface DiffItem {
    id: number;
    diff_type: string;
    original_text: string;
    comparison_text: string;
    location: string;
    status: string;
}

interface Props {
    fileAName: string;
    fileBName: string;
    fileAType: 'pdf' | 'image' | 'doc' | 'unknown';
    fileBType: 'pdf' | 'image' | 'doc' | 'unknown';
    fileAPreviewUrl: string;
    fileBPreviewUrl: string;
    contentA: string;
    contentB: string;
    diffs: DiffItem[];
    selectedDiffId: number | null;
    filter: string;
    syncScroll: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    (e: 'back'): void;
    (e: 'update:filter', value: string): void;
    (e: 'update:syncScroll', value: boolean): void;
    (e: 'selectDiff', diff: DiffItem): void;
    (e: 'ignoreDiff', id: number): void;
}>();

// 辅助函数
function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeRegExp(text: string): string {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 获取当前选中的差异
const selectedDiff = computed(() => {
    if (!props.selectedDiffId) return null;
    return props.diffs.find(d => d.id === props.selectedDiffId) || null;
});

// 高亮文本的HTML（仅用于无法使用 VueOfficeDocx 时的回退方案）
const highlightedContentA = computed(() => {
    if (!props.contentA) return '';
    const diff = selectedDiff.value;
    if (!diff || !diff.original_text) return escapeHtml(props.contentA);
    
    const searchText = diff.original_text.trim();
    if (!searchText) return escapeHtml(props.contentA);
    
    const escaped = escapeHtml(props.contentA);
    const searchEscaped = escapeHtml(searchText);
    const regex = new RegExp(`(${escapeRegExp(searchEscaped)})`, 'gi');
    return escaped.replace(regex, '<mark class="bg-red-200 text-red-900 px-1 rounded">$1</mark>');
});

const highlightedContentB = computed(() => {
    if (!props.contentB) return '';
    const diff = selectedDiff.value;
    if (!diff || !diff.comparison_text) return escapeHtml(props.contentB);
    
    const searchText = diff.comparison_text.trim();
    if (!searchText) return escapeHtml(props.contentB);
    
    const escaped = escapeHtml(props.contentB);
    const searchEscaped = escapeHtml(searchText);
    const regex = new RegExp(`(${escapeRegExp(searchEscaped)})`, 'gi');
    return escaped.replace(regex, '<mark class="bg-green-200 text-green-900 px-1 rounded">$1</mark>');
});

// 过滤后的差异列表
const filteredDiffs = computed(() => {
    return props.diffs.filter(d => {
        if (d.status === 'ignored') return false;
        if (props.filter === 'all') return true;
        return d.diff_type === props.filter;
    });
});

// 统计数据
const stats = computed(() => ({
    all: props.diffs.length,
    added: props.diffs.filter(d => d.diff_type === 'added').length,
    modified: props.diffs.filter(d => d.diff_type === 'modified').length,
    deleted: props.diffs.filter(d => d.diff_type === 'deleted').length,
    ignored: props.diffs.filter(d => d.status === 'ignored').length
}));
</script>

<template>
    <div class="result-container">
        <!-- Toolbar -->
        <div class="contract-toolbar">
            <div class="flex items-center gap-4">
                <button @click="emit('back')" class="p-2 hover:bg-slate-100 rounded-lg text-slate-500">
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
                    @click="emit('update:syncScroll', !props.syncScroll)"
                    :class="['contract-sync-btn', props.syncScroll ? 'active' : '']"
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
        <div class="main-content">
            <!-- Document Panes -->
            <div class="doc-panes-container">
                <!-- Original Doc -->
                <div class="doc-pane">
                    <div class="contract-doc-header contract-doc-header-original">
                        <span class="contract-doc-badge contract-badge-original">原</span>
                        <span class="font-medium text-slate-700 truncate">{{ props.fileAName || '原文档' }}</span>
                    </div>
                    <div id="doc-content-a" class="doc-content">
                        <!-- PDF Viewer -->
                        <iframe 
                            v-if="props.fileAType === 'pdf'" 
                            :src="props.fileAPreviewUrl" 
                            class="w-full h-full border-0"
                        ></iframe>
                        
                        <!-- Image Viewer -->
                        <div v-else-if="props.fileAType === 'image'" class="w-full h-full flex items-center justify-center bg-slate-100 overflow-auto p-4">
                            <img :src="props.fileAPreviewUrl" class="max-w-full h-auto shadow-lg rounded" />
                        </div>
                        
                        <!-- DOC/DOCX Viewer -->
                        <div v-else-if="props.fileAType === 'doc'" class="docx-viewer">
                            <VueOfficeDocx 
                                :src="props.fileAPreviewUrl"
                            />
                        </div>
                        
                        <!-- Fallback Text Viewer -->
                        <div v-else class="p-6 overflow-auto h-full">
                            <div 
                                v-if="props.contentA" 
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
                <div class="doc-pane">
                    <div class="contract-doc-header contract-doc-header-compare">
                        <span class="contract-doc-badge contract-badge-compare">比对</span>
                        <span class="font-medium text-slate-700 truncate">{{ props.fileBName || '比对文档' }}</span>
                    </div>
                    <div id="doc-content-b" class="doc-content">
                        <!-- PDF Viewer -->
                        <iframe 
                            v-if="props.fileBType === 'pdf'" 
                            :src="props.fileBPreviewUrl" 
                            class="w-full h-full border-0"
                        ></iframe>
                        
                        <!-- Image Viewer -->
                        <div v-else-if="props.fileBType === 'image'" class="w-full h-full flex items-center justify-center bg-slate-100 overflow-auto p-4">
                            <img :src="props.fileBPreviewUrl" class="max-w-full h-auto shadow-lg rounded" />
                        </div>
                        
                        <!-- DOC/DOCX Viewer -->
                        <div v-else-if="props.fileBType === 'doc'" class="docx-viewer">
                            <VueOfficeDocx 
                                :src="props.fileBPreviewUrl"
                            />
                        </div>
                        
                        <!-- Fallback Text Viewer -->
                        <div v-else class="p-6 overflow-auto h-full">
                            <div 
                                v-if="props.contentB" 
                                class="max-w-3xl mx-auto whitespace-pre-wrap text-sm leading-relaxed select-text"
                                v-html="highlightedContentB"
                            ></div>
                            <p v-else class="text-slate-400 text-center py-10">暂无内容</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Diff List Sidebar -->
            <div class="diff-sidebar">
                <!-- Stats Header -->
                <div class="p-5 border-b border-slate-100 bg-slate-50/50">
                    <div class="flex items-end justify-between mb-4">
                        <h2 class="text-xl font-bold text-slate-800">
                            差异项 <span class="text-orange-600">{{ stats.all - stats.ignored }}</span>
                        </h2>
                        <span class="text-sm text-slate-500">已忽略 {{ stats.ignored }}</span>
                    </div>

                    <!-- Filter Tabs -->
                    <div class="flex bg-slate-200/60 p-1 rounded-lg">
                        <button 
                            v-for="tab in [
                                { id: 'all', label: '全部', count: stats.all },
                                { id: 'added', label: '新增', count: stats.added },
                                { id: 'modified', label: '修改', count: stats.modified },
                                { id: 'deleted', label: '删除', count: stats.deleted }
                            ]"
                            :key="tab.id"
                            @click="emit('update:filter', tab.id)"
                            :class="['contract-filter-tab', props.filter === tab.id ? 'active' : '']"
                        >
                            {{ tab.label }} ({{ tab.count }})
                        </button>
                    </div>
                </div>

                <!-- Diff Items -->
                <div class="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
                    <div 
                        v-for="diff in filteredDiffs"
                        :key="diff.id"
                        :class="['diff-item', props.selectedDiffId === diff.id ? 'ring-2 ring-orange-500' : '']"
                        @click="emit('selectDiff', diff)"
                    >
                        <div class="flex justify-between items-start mb-3">
                            <span :class="['diff-badge', `diff-badge-${diff.diff_type}`]">
                                {{ diff.diff_type === 'added' ? '新增' : diff.diff_type === 'deleted' ? '删除' : '修改' }}
                            </span>
                            <button 
                                @click.stop="emit('ignoreDiff', diff.id)"
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

                    <div v-if="filteredDiffs.length === 0" class="text-center py-10 text-slate-400">
                        <CheckCircle2 class="w-10 h-10 mx-auto mb-2 opacity-50" />
                        <p>暂无此类差异</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.result-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.main-content {
    height: calc(100vh - 64px);
    display: flex;
    overflow: hidden;
}

.doc-panes-container {
    flex: 1;
    display: flex;
    min-width: 0;
    overflow: hidden;
}

.doc-pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    max-width: 50%;
    background: white;
    overflow: hidden;
}

.doc-content {
    flex: 1;
    overflow: auto;
    position: relative;
}

.doc-content > div,
.doc-content > iframe {
    height: 100%;
    width: 100%;
}

/* VueOfficeDocx 容器样式 */
.docx-viewer {
    width: 100%;
    height: 100%;
    overflow: auto;
}

.docx-viewer :deep(.docx-wrapper) {
    padding: 20px;
    background: #f8fafc;
}

.docx-viewer :deep(.docx) {
    background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    margin: 0 auto;
    padding: 40px 60px;
    max-width: 100%;
    overflow-x: auto;
}

.diff-sidebar {
    width: 320px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: white;
    border-left: 1px solid #e2e8f0;
    box-shadow: -4px 0 6px -1px rgba(0, 0, 0, 0.1);
    overflow: hidden;
}
</style>
