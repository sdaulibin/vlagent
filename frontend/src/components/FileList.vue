<script setup lang="ts">
import { FileText, Trash2 } from 'lucide-vue-next';
import type { FileItem } from '../types';

defineProps<{
    files: FileItem[];
    onDelete: (id: number) => void;
}>();
</script>

<template>
    <div class="card flex flex-col flex-1 min-h-0">
        <h2 class="card-title flex-shrink-0">
            <FileText class="w-5 h-5 text-blue-500" />
            文件列表
        </h2>
        <div class="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-3 min-h-0">
            <div v-if="files.length === 0" class="h-full flex flex-col items-center justify-center text-gray-400">
                <p>暂无文件</p>
            </div>
            <div v-else v-for="file in files" :key="file.id" class="file-item flex-shrink-0 group">
                <div class="flex items-center gap-3 overflow-hidden">
                    <div :class="`p-2 rounded-md ${file.status === 'done' ? 'bg-green-100' : 'bg-yellow-100'}`">
                        <FileText :class="`w-5 h-5 ${file.status === 'done' ? 'text-green-600' : 'text-yellow-600'}`" />
                    </div>
                    <div class="flex flex-col min-w-0">
                        <span class="text-sm font-medium text-gray-700 truncate w-32 md:w-40">{{ file.name }}</span>
                        <span class="text-xs text-gray-400">{{ file.size }}</span>
                    </div>
                </div>
                <button 
                    @click="onDelete(file.id)"
                    class="icon-btn"
                >
                    <Trash2 class="w-4 h-4" />
                </button>
            </div>
        </div>
    </div>
</template>
