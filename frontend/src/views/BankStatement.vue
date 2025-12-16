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
const summary = ref<Summary | null>(null);
const isProcessing = ref(false);
const selectedFileId = ref<number | null>(null);
const selectedFileName = ref('');

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
        }));
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
    
    isProcessing.value = true;
    
    for (const file of pendingFiles) {
        try {
            // 更新本地状态为处理中
            const fileIndex = files.value.findIndex(f => f.id === file.id);
            const foundFile = files.value[fileIndex];
            if (foundFile) {
                foundFile.status = 'uploading';
            }
            
            await startRecognition(file.id);
        } catch (error) {
            console.error(`识别文件 ${file.name} 失败:`, error);
        }
    }
    
    await loadFiles();
    isProcessing.value = false;
};

const handleSelectFile = async (id: number) => {
    try {
        isProcessing.value = true;
        selectedFileId.value = id;
        const file = files.value.find(f => f.id === id);
        selectedFileName.value = file?.name || '';
        const [txs, summaryData] = await Promise.all([
            getFileTransactions(id),
            getFileSummary(id)
        ]);
        results.value = txs;
        summary.value = summaryData;
    } catch (e) {
        console.error("Failed to load file data", e);
    } finally {
        isProcessing.value = false;
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
    <div class="min-h-screen p-4 md:p-8 flex flex-col">
        <!-- Header -->
        <header class="w-full max-w-6xl mx-auto mb-6">
            <button @click="goBack" class="flex items-center gap-2 text-slate-500 hover:text-slate-700 mb-4">
                <ArrowLeft class="w-5 h-5" />
                返回首页
            </button>
            <div class="flex items-center gap-3">
                <div class="bg-blue-600 p-3 rounded-xl shadow-lg">
                    <ShieldCheck class="text-white w-7 h-7" />
                </div>
                <div>
                    <h1 class="text-2xl font-bold text-slate-900">流水信息识别</h1>
                    <p class="text-sm text-slate-500">智能解析银行流水 PDF，提取交易明细和汇总统计</p>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="w-full max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-6 h-[calc(100vh-180px)]">
            <!-- Left Column -->
            <div class="md:col-span-4 flex flex-col gap-6 h-full min-h-0">
                <FileUpload :onFileSelect="handleFileSelect" />
                
                <!-- 开始识别按钮 -->
                <button 
                    v-if="hasPendingFiles"
                    @click="handleStartRecognition"
                    :disabled="isProcessing"
                    class="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white py-3 px-4 rounded-xl font-medium shadow-lg hover:from-blue-600 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Play class="w-5 h-5" />
                    {{ isProcessing ? '识别中...' : '开始识别' }}
                </button>
                
                <FileList :files="files" :onDelete="handleDeleteFile" :onSelect="handleSelectFile" />
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
