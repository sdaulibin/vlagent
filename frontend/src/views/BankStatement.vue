<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ShieldCheck, ArrowLeft } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import FileUpload from '../components/FileUpload.vue';
import FileList from '../components/FileList.vue';
import ResultList from '../components/ResultList.vue';
import { uploadFile, getFiles, getFileTransactions, getFileSummary, deleteFile } from '../api';
import type { FileItem, Transaction, Summary } from '../types';

const router = useRouter();
const files = ref<FileItem[]>([]);
const results = ref<Transaction[]>([]);
const summary = ref<Summary | null>(null);
const isProcessing = ref(false);

const loadFiles = async () => {
    try {
        const fileList = await getFiles();
        files.value = fileList.map((f: any) => ({
            id: f.id,
            name: f.filename,
            size: '',
            status: f.status === 'done' ? 'done' : f.status === 'processing' ? 'uploading' : 'error',
        }));
    } catch (e) {
        console.error("Failed to load files", e);
    }
}

onMounted(() => {
    loadFiles();
});

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

const handleSelectFile = async (id: number) => {
    try {
        isProcessing.value = true;
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
        if (files.value.length === 0) {
            results.value = [];
            summary.value = null;
        }
    } catch (e) {
        console.error("Failed to delete file", e);
    }
};

const goBack = () => {
    router.push('/');
};
</script>

<template>
    <div class="min-h-screen p-4 md:p-8 flex flex-col items-center">
        <!-- Header -->
        <header class="w-full max-w-6xl mb-8 flex items-center gap-3">
            <button @click="goBack" class="p-2 rounded-lg hover:bg-gray-100 transition-colors">
                <ArrowLeft class="w-6 h-6 text-gray-600" />
            </button>
            <div class="bg-blue-600 p-2 rounded-lg shadow-lg">
                <ShieldCheck class="text-white w-8 h-8" />
            </div>
            <h1 class="header-title">银行流水信息识别</h1>
        </header>

        <!-- Main Content -->
        <main class="w-full max-w-6xl grid grid-cols-1 md:grid-cols-12 gap-6 h-[80vh] min-h-[600px]">
            <!-- Left Column -->
            <div class="md:col-span-4 flex flex-col gap-6 h-full min-h-0">
                <FileUpload :onFileSelect="handleFileSelect" />
                <FileList :files="files" :onDelete="handleDeleteFile" :onSelect="handleSelectFile" />
            </div>

            <!-- Right Column -->
            <ResultList :results="results" :summary="summary" :isProcessing="isProcessing" />
        </main>
    </div>
</template>
