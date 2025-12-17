<script setup lang="ts">
import { FileText, Trash2, Loader2, CheckCircle, AlertCircle, Clock } from 'lucide-vue-next';
import type { FileItem } from '../types';

defineProps<{
    files: FileItem[];
    onDelete: (id: number) => void;
    onSelect?: (id: number) => void;
    selectedId?: number | null;
}>();

// 根据状态获取图标背景色
const getStatusBgClass = (status: string) => {
    switch (status) {
        case 'done': return 'bg-green-100';
        case 'uploading': return 'bg-blue-100';
        case 'error': return 'bg-red-100';
        default: return 'bg-yellow-100'; // pending
    }
};

// 根据状态获取图标颜色
const getStatusIconClass = (status: string) => {
    switch (status) {
        case 'done': return 'text-green-600';
        case 'uploading': return 'text-blue-600';
        case 'error': return 'text-red-600';
        default: return 'text-yellow-600'; // pending
    }
};

// 根据状态获取状态文字
const getStatusText = (status: string) => {
    switch (status) {
        case 'done': return '已完成';
        case 'uploading': return '识别中...';
        case 'error': return '识别失败';
        default: return '待识别';
    }
};
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
            <div 
                v-else 
                v-for="file in files" 
                :key="file.id" 
                :class="[
                    'file-item flex-shrink-0 group cursor-pointer transition-all',
                    selectedId === file.id 
                        ? 'bg-blue-50 border-blue-300 ring-1 ring-blue-200' 
                        : 'hover:bg-gray-100'
                ]"
                @click="onSelect?.(file.id)"
            >
                <div class="flex items-center gap-3 overflow-hidden">
                    <div :class="['p-2 rounded-md', getStatusBgClass(file.status)]">
                        <!-- 根据状态显示不同图标 -->
                        <Loader2 v-if="file.status === 'uploading'" :class="['w-5 h-5 animate-spin', getStatusIconClass(file.status)]" />
                        <CheckCircle v-else-if="file.status === 'done'" :class="['w-5 h-5', getStatusIconClass(file.status)]" />
                        <AlertCircle v-else-if="file.status === 'error'" :class="['w-5 h-5', getStatusIconClass(file.status)]" />
                        <Clock v-else :class="['w-5 h-5', getStatusIconClass(file.status)]" />
                    </div>
                    <div class="flex flex-col min-w-0">
                        <span class="text-sm font-medium text-gray-700 truncate w-32 md:w-40">{{ file.name }}</span>
                        <span :class="['text-xs', getStatusIconClass(file.status)]">{{ getStatusText(file.status) }}</span>
                    </div>
                </div>
                <button 
                    @click.stop="onDelete(file.id)"
                    class="icon-btn"
                    :disabled="file.status === 'uploading'"
                >
                    <Trash2 class="w-4 h-4" />
                </button>
            </div>
        </div>
    </div>
</template>
