<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { ShieldCheck, ArrowLeft, Play } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import FileUpload from '../components/FileUpload.vue';
import FileList from '../components/FileList.vue';
import ResultList from '../components/ResultList.vue';
import { uploadFile, getFiles, getFileTransactions, getFileSummary, deleteFile, exportExcel, startRecognition } from '../api';
import type { FileItem, Transaction, Summary } from '../types';

const router = useRouter();
const files = ref<FileItem[]>([]);
const results = ref<Transaction[]>([]);
const summary = ref<Summary | Summary[] | null>(null);  // 广发银行返回数组
const isProcessing = ref(false);
const isRecognizing = ref(false);  // 专门追踪识别过程
const selectedFileId = ref<number | null>(null);
const selectedFileName = ref('');
const lastSelectionId = ref<number | null>(null); // 追踪最后一次发起的选择请求

// 检查是否有待处理的文件
const hasPendingFiles = computed(() => {
    return files.value.some(f => f.status === 'pending');
});

const loadFiles = async () => {
    try {
        const fileList = await getFiles();
        files.value = fileList.map((f: any) => ({
            id: f.id,
            name: f.filename,
            size: '',
            status: f.status === 'done' ? 'done' : f.status === 'processing' ? 'uploading' : f.status === 'pending' ? 'pending' : 'error',
            recognition_duration: f.recognition_duration
        }));
        
        // 自动选择第一个已完成的文件
        if (!selectedFileId.value) {
            const firstDoneFile = files.value.find(f => f.status === 'done');
            if (firstDoneFile) {
                handleSelectFile(firstDoneFile.id);
            }
        }
    } catch (e) {
        console.error("Failed to load files", e);
    }
}

onMounted(() => {
    loadFiles();
});

// 文件上传（仅保存，不处理）
const handleFileSelect = async (fileList: FileList) => {
    if (fileList.length === 0) return;
    isProcessing.value = true;
    
    for (const file of Array.from(fileList)) {
        try {
            await uploadFile(file);
        } catch (error) {
            console.error(error);
        }
    }
    
    await loadFiles();
    isProcessing.value = false;
};

// 开始识别所有待处理文件
const handleStartRecognition = async () => {
    const pendingFiles = files.value.filter(f => f.status === 'pending');
    if (pendingFiles.length === 0) return;
    
    isRecognizing.value = true;
    
    for (const file of pendingFiles) {
        try {
            // 更新本地状态为处理中
            const fileIndex = files.value.findIndex(f => f.id === file.id);
            const foundFile = files.value[fileIndex];
            if (foundFile) {
                foundFile.status = 'uploading';
            }
            
            await startRecognition(file.id);
            
            // 识别完成后更新状态为完成
            if (foundFile) {
                foundFile.status = 'done';
            }
        } catch (error) {
            console.error(`识别文件 ${file.name} 失败:`, error);
            // 识别失败时更新状态
            const foundFile = files.value.find(f => f.id === file.id);
            if (foundFile) {
                foundFile.status = 'error';
            }
        }
    }
    
    await loadFiles();
    isRecognizing.value = false;
};

const handleSelectFile = async (id: number) => {
    try {
        isProcessing.value = true;
        selectedFileId.value = id;
        lastSelectionId.value = id; // 记录当前选择的 ID
        
        const file = files.value.find(f => f.id === id);
        selectedFileName.value = file?.name || '';
        
        // 切换时立即清除旧的识别结果和汇总信息，触发加载状态
        results.value = [];
        summary.value = null;
        
        const [txs, summaryData] = await Promise.all([
            getFileTransactions(id),
            getFileSummary(id)
        ]);
        
        // 如果在请求期间用户又切换了文件，则不更新结果
        if (lastSelectionId.value !== id) return;
        
        results.value = txs;
        // 处理汇总数据：广发银行返回数组，其他银行返回对象
        summary.value = summaryData;
    } catch (e) {
        if (lastSelectionId.value === id) {
            console.error("Failed to load file data", e);
        }
    } finally {
        if (lastSelectionId.value === id) {
            isProcessing.value = false;
        }
    }
};

const handleDeleteFile = async (id: number) => {
    try {
        await deleteFile(id);
        files.value = files.value.filter(f => f.id !== id);
        if (files.value.length === 0 || selectedFileId.value === id) {
            results.value = [];
            summary.value = null;
            selectedFileId.value = null;
            selectedFileName.value = '';
        }
    } catch (e) {
        console.error("Failed to delete file", e);
    }
};

const handleExport = async () => {
    if (selectedFileId.value && selectedFileName.value) {
        await exportExcel(selectedFileId.value, selectedFileName.value);
    }
};

const goBack = () => {
    router.push('/');
};
</script>

<template>
    <div class="page-container">
        <!-- Header -->
        <header class="page-header">
            <button @click="goBack" class="page-back-btn">
                <ArrowLeft class="w-5 h-5" />
                返回首页
            </button>
            <div class="page-title-group">
                <div class="page-icon bg-blue-600">
                    <ShieldCheck class="text-white w-7 h-7" />
                </div>
                <div>
                    <h1 class="page-title">流水信息识别</h1>
                    <p class="page-subtitle">智能解析银行流水 PDF，提取交易明细和汇总统计</p>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="page-main" style="height: calc(100vh - 180px)">
            <!-- Left Column -->
            <div class="page-left-col">
                <FileUpload :onFileSelect="handleFileSelect" />
                
                <!-- 开始识别按钮 - 始终显示 -->
                <button 
                    @click="handleStartRecognition"
                    :disabled="isRecognizing || !hasPendingFiles"
                    class="btn-gradient from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700"
                >
                    <Play class="w-5 h-5" />
                    {{ isRecognizing ? '识别中...' : (hasPendingFiles ? '开始识别' : '暂无待识别文件') }}
                </button>
                
                <FileList :files="files" :onDelete="handleDeleteFile" :onSelect="handleSelectFile" :selectedId="selectedFileId" />
            </div>

            <!-- Right Column -->
            <ResultList 
                :results="results" 
                :summary="summary" 
                :isProcessing="isProcessing"
                :selectedFileId="selectedFileId"
                :selectedFileName="selectedFileName"
                @export="handleExport"
            />
        </main>
    </div>
</template>
