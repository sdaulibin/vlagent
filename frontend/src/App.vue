<script setup lang="ts">
import { ref } from 'vue';
import { ShieldCheck } from 'lucide-vue-next';
import FileUpload from './components/FileUpload.vue';
import FileList from './components/FileList.vue';
import ResultList from './components/ResultList.vue';
import { uploadFile } from './api';
import type { FileItem, Transaction } from './types';

const files = ref<FileItem[]>([]);
const results = ref<Transaction[]>([]);
const isProcessing = ref(false);

const handleFileSelect = async (fileList: FileList) => {
    if (fileList.length === 0) return;

    const newFiles = Array.from(fileList).map(file => ({
        id: Date.now() + Math.random(),
        name: file.name,
        size: (file.size / 1024).toFixed(2) + ' KB',
        status: 'uploading' as const,
        rawFile: file // Keep raw file for upload
    }));

    files.value = [...files.value, ...newFiles];
    isProcessing.value = true;

    // Process each file (sequentially for simplicity in this demo)
    for (const fileItem of newFiles) {
        try {
            const data = await uploadFile(fileItem.rawFile);
            // Update status
            const index = files.value.findIndex(f => f.id === fileItem.id);
            if (index !== -1 && files.value[index]) {
                files.value[index].status = 'done';
            }
            // Append results
            if (data.transactions) {
                results.value = [...results.value, ...data.transactions];
            }
        } catch (error) {
            console.error(error);
            const index = files.value.findIndex(f => f.id === fileItem.id);
            if (index !== -1 && files.value[index]) {
                files.value[index].status = 'error';
            }
        }
    }
    isProcessing.value = false;
};

const handleDeleteFile = (id: number) => {
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
                <FileList :files="files" :onDelete="handleDeleteFile" />
            </div>

            <!-- Right Column -->
            <ResultList :results="results" :isProcessing="isProcessing" />
        </main>
    </div>
</template>


