<script setup lang="ts">
import { ref, computed, nextTick } from 'vue';
import { 
    ChevronLeft, ChevronRight, ZoomIn, ZoomOut, 
    ArrowRightLeft, Download, AlertCircle, CheckCircle2, Eye
} from 'lucide-vue-next';
import TiptapViewer from './TiptapViewer.vue';

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

// 视图模式: 'format' = 原格式视图, 'diff' = 差异对比视图
const viewMode = ref<'format' | 'diff'>('format');

// 切换视图模式
const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'format' ? 'diff' : 'format';
};

// 处理差异点击 - 自动切换到差异视图并滚动
const handleDiffItemClick = async (diff: DiffItem) => {
    emit('selectDiff', diff);
    
    // 自动切换到差异视图
    if (viewMode.value === 'format') {
        viewMode.value = 'diff';
    }
    
    await nextTick();
    
    // 滚动到高亮位置
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

// 获取当前选中的差异
const selectedDiff = computed(() => {
    if (!props.selectedDiffId) return null;
    return props.diffs.find(d => d.id === props.selectedDiffId) || null;
});

// 获取高亮文本 (用于 Tiptap)
const highlightTextA = computed(() => {
    const diff = selectedDiff.value;
    return diff?.original_text?.trim() || '';
});

const highlightTextB = computed(() => {
    const diff = selectedDiff.value;
    return diff?.comparison_text?.trim() || '';
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
                
                <!-- 视图模式切换 -->
                <button 
                    @click="toggleViewMode"
                    :class="['contract-sync-btn', viewMode === 'diff' ? 'active' : '']"
                >
                    <Eye class="w-4 h-4" />
                    {{ viewMode === 'format' ? '格式视图' : '差异视图' }}
                </button>
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
                        <!-- 差异视图 - 使用 Tiptap 编辑器 -->
                        <TiptapViewer 
                            v-if="viewMode === 'diff'"
                            :key="'docA-' + props.selectedDiffId"
                            :content="props.contentA"
                            :highlightText="highlightTextA"
                            highlightColor="red"
                        />
                        
                        <!-- 格式视图 -->
                        <template v-else>
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
                            
                            <!-- Text/DOC/DOCX Viewer - 使用 Tiptap -->
                            <TiptapViewer 
                                v-else
                                :content="props.contentA"
                            />
                        </template>
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
                        <!-- 差异视图 - 使用 Tiptap 编辑器 -->
                        <TiptapViewer 
                            v-if="viewMode === 'diff'"
                            :key="'docB-' + props.selectedDiffId"
                            :content="props.contentB"
                            :highlightText="highlightTextB"
                            highlightColor="green"
                        />
                        
                        <!-- 格式视图 -->
                        <template v-else>
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
                            
                            <!-- Text/DOC/DOCX Viewer - 使用 Tiptap -->
                            <TiptapViewer 
                                v-else
                                :content="props.contentB"
                            />
                        </template>
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
                        @click="handleDiffItemClick(diff)"
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
