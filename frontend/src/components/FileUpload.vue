<script setup lang="ts">
import { Upload, FileSpreadsheet } from 'lucide-vue-next';

defineProps<{
  onFileSelect: (files: FileList) => void;
}>();

const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer?.files) {
        // @ts-ignore
        onFileSelect(e.dataTransfer.files);
    }
};


</script>

<template>
    <div class="card flex flex-col h-1/3">
        <h2 class="card-title">
            <Upload class="w-5 h-5 text-blue-500" />
            文件上传
        </h2>
        <div 
            class="upload-area group"
            @dragover.prevent
            @drop="handleDrop"
        >
            <input 
                type="file" 
                class="absolute inset-0 w-full h-full opacity-0 cursor-pointer" 
                @change="(e) => onFileSelect((e.target as HTMLInputElement).files!)"
                multiple
            />
            <div class="bg-white p-3 rounded-full shadow-sm mb-3 group-hover:scale-110 transition-transform">
                <FileSpreadsheet class="w-8 h-8 text-blue-500" />
            </div>
            <p class="text-sm font-medium text-gray-600">点击或拖拽上传流水文件</p>
            <p class="text-xs text-gray-400 mt-1">支持 PDF, JPG, PNG 格式</p>
        </div>
    </div>
</template>
