<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ShieldCheck } from 'lucide-vue-next';
import FileUpload from './components/FileUpload.vue';
import FileList from './components/FileList.vue';
import ResultList from './components/ResultList.vue';
import { uploadFile, getFiles, getFileTransactions } from './api';
import type { FileItem, Transaction } from './types';

const files = ref<FileItem[]>([]);
const results = ref<Transaction[]>([]);
const isProcessing = ref(false);

const loadFiles = async () => {
    try {
        const fileList = await getFiles();
        files.value = fileList.map((f: any) => ({
            id: f.id,
            name: f.filename,
            size: '', // Size not stored in DB currently
            status: f.status === 'done' ? 'done' : f.status === 'processing' ? 'uploading' : 'error',
            // No rawFile needed for display
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
    
    // Note: We are uploading one by one and refreshing the list
    // Ideally we should optimistically update UI, but for now we stick to simple logic
    
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
        const txs = await getFileTransactions(id);
        results.value = txs;
    } catch (e) {
        console.error("Failed to load transactions", e);
    } finally {
        isProcessing.value = false;
    }
};

const handleDeleteFile = (id: number) => {
    // Current backend doesn't support delete, just remove from UI for now or ignore
    // To be implemented in backend if needed
    files.value = files.value.filter(f => f.id !== id);
    if (files.value.length === 0) {
        results.value = [];
    }
};
</script>

<template>
    <div class="min-h-screen p-4 md:p-8 flex flex-col items-center">
        <!-- Header -->
        <header class="w-full max-w-6xl mb-8 flex items-center gap-3">
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
            <ResultList :results="results" :isProcessing="isProcessing" />
        </main>
    </div>
</template>


