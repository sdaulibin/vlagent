<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, FileDiff } from 'lucide-vue-next';
import { compareContracts, getTaskDiffs, getFilePreviewUrl, getCompareTasks, deleteCompareTask } from '../api';
import ContractUpload from '../components/ContractUpload.vue';
import ContractHistory from '../components/ContractHistory.vue';
import ContractResultView from '../components/ContractResultView.vue';

const router = useRouter();

// 状态管理
const activeView = ref<'upload' | 'result'>('upload');
const isProcessing = ref(false);
const fileA = ref<File | null>(null);
const fileB = ref<File | null>(null);
const filter = ref('all');
const syncScroll = ref(true);
const currentTaskId = ref<number | null>(null);

// 比对历史
interface TaskItem {
    id: number;
    file_a_name: string;
    file_b_name: string;
    status: string;
    created_at: string;
    content_a?: string;
    content_b?: string;
}
const historyList = ref<TaskItem[]>([]);

// 文档内容
const contentA = ref('');
const contentB = ref('');
const selectedDiffId = ref<number | null>(null);

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

// 加载历史列表
const loadHistory = async () => {
    try {
        historyList.value = await getCompareTasks();
    } catch (e) {
        console.error('Failed to load history:', e);
    }
};

// 删除历史任务
const handleDeleteTask = async (taskId: number) => {
    if (!confirm('确定要删除这个比对任务吗？')) return;
    try {
        await deleteCompareTask(taskId);
        await loadHistory();
    } catch (e) {
        console.error('Failed to delete task:', e);
    }
};

// 查看历史任务结果
const viewHistoryTask = async (task: TaskItem) => {
    currentTaskId.value = task.id;
    contentA.value = task.content_a || '';
    contentB.value = task.content_b || '';
    
    fileA.value = { name: task.file_a_name } as File;
    fileB.value = { name: task.file_b_name } as File;
    
    const diffsData = await getTaskDiffs(task.id);
    diffs.value = diffsData;
    
    activeView.value = 'result';
};

// 初始化加载
onMounted(() => {
    loadHistory();
});

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

// 开始比对
const startCompare = async () => {
    if (!fileA.value || !fileB.value) {
        alert('请上传两份文档');
        return;
    }
    
    isProcessing.value = true;
    
    try {
        const result = await compareContracts(fileA.value, fileB.value);
        
        currentTaskId.value = result.task_id;
        contentA.value = result.content_a || '';
        contentB.value = result.content_b || '';
        
        const diffsData = await getTaskDiffs(result.task_id);
        diffs.value = diffsData;
        
        await loadHistory();
        activeView.value = 'result';
    } catch (error: any) {
        console.error('Compare failed:', error);
        alert(error.response?.data?.detail || '比对失败，请重试');
    } finally {
        isProcessing.value = false;
    }
};

// 处理差异点击
const handleDiffClick = async (diff: DiffItem) => {
    selectedDiffId.value = diff.id;
    
    await nextTick();
    
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

// 忽略差异
const handleIgnore = (id: number) => {
    diffs.value = diffs.value.map(d => 
        d.id === id ? { ...d, status: 'ignored' } : d
    );
};

// 返回
const goBack = () => {
    if (activeView.value === 'result') {
        activeView.value = 'upload';
        selectedDiffId.value = null;
    } else {
        router.push('/');
    }
};

// 文件选择处理
const handleFileAUpdate = (file: File) => {
    fileA.value = file;
};

const handleFileBUpdate = (file: File) => {
    fileB.value = file;
};
</script>

<template>
    <div class="min-h-screen bg-slate-50">
        <!-- Upload View -->
        <div v-if="activeView === 'upload'" class="min-h-screen flex flex-col p-8">
            <!-- Header -->
            <div class="w-full max-w-7xl mx-auto mb-6">
                <button @click="goBack" class="page-back-btn">
                    <ArrowLeft class="w-5 h-5" />
                    返回首页
                </button>
                <div class="page-title-group">
                    <div class="contract-logo">
                        <FileDiff class="w-8 h-8 text-white" />
                    </div>
                    <div>
                        <h1 class="page-title">合同比对</h1>
                        <p class="page-subtitle">上传两份文档以自动识别差异，支持 PDF, Word, 图片格式</p>
                    </div>
                </div>
            </div>

            <!-- Main Content: Left upload, Right history -->
            <div class="flex-1 flex gap-8">
                <ContractUpload 
                    :fileA="fileA"
                    :fileB="fileB"
                    :isProcessing="isProcessing"
                    @update:fileA="handleFileAUpdate"
                    @update:fileB="handleFileBUpdate"
                    @compare="startCompare"
                />
                
                <ContractHistory 
                    :historyList="historyList"
                    @view="viewHistoryTask"
                    @delete="handleDeleteTask"
                />
            </div>
        </div>

        <!-- Result View -->
        <ContractResultView 
            v-else
            :fileAName="fileA?.name || ''"
            :fileBName="fileB?.name || ''"
            :fileAType="fileAType"
            :fileBType="fileBType"
            :fileAPreviewUrl="fileAPreviewUrl"
            :fileBPreviewUrl="fileBPreviewUrl"
            :contentA="contentA"
            :contentB="contentB"
            :diffs="diffs"
            :selectedDiffId="selectedDiffId"
            :filter="filter"
            :syncScroll="syncScroll"
            @back="goBack"
            @update:filter="filter = $event"
            @update:syncScroll="syncScroll = $event"
            @selectDiff="handleDiffClick"
            @ignoreDiff="handleIgnore"
        />
    </div>
</template>
