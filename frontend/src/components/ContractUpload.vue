<script setup lang="ts">
import { FileText } from 'lucide-vue-next';

interface Props {
    fileA: File | null;
    fileB: File | null;
    isProcessing: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    (e: 'update:fileA', file: File): void;
    (e: 'update:fileB', file: File): void;
    (e: 'compare'): void;
}>();

const handleFileASelect = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
        emit('update:fileA', input.files[0]);
    }
};

const handleFileBSelect = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
        emit('update:fileB', input.files[0]);
    }
};
</script>

<template>
    <div class="w-96 flex flex-col gap-6">
        <!-- Document A -->
        <label class="contract-upload-area contract-upload-original h-40">
            <div class="contract-upload-badge contract-badge-original">原文档</div>
            <input type="file" class="hidden" accept=".pdf,.docx,.doc,.jpg,.png" @change="handleFileASelect" />
            <div class="contract-upload-icon contract-icon-original">
                <FileText class="w-8 h-8" />
            </div>
            <h3 class="text-base font-semibold text-slate-800 mb-1">
                {{ props.fileA ? props.fileA.name : '点击上传原文档' }}
            </h3>
            <p class="text-xs text-slate-400">PDF, Word, 图片 (最大 50MB)</p>
        </label>

        <!-- Document B -->
        <label class="contract-upload-area contract-upload-compare h-40">
            <div class="contract-upload-badge contract-badge-compare">比对文档</div>
            <input type="file" class="hidden" accept=".pdf,.docx,.doc,.jpg,.png" @change="handleFileBSelect" />
            <div class="contract-upload-icon contract-icon-compare">
                <FileText class="w-8 h-8" />
            </div>
            <h3 class="text-base font-semibold text-slate-800 mb-1">
                {{ props.fileB ? props.fileB.name : '点击上传比对文档' }}
            </h3>
            <p class="text-xs text-slate-400">PDF, Word, 图片 (最大 50MB)</p>
        </label>

        <!-- Start Button -->
        <button 
            @click="emit('compare')"
            :disabled="!props.fileA || !props.fileB || props.isProcessing"
            class="contract-btn-primary w-full"
        >
            <span class="flex items-center justify-center gap-2">
                {{ props.isProcessing ? '比对中...' : '开始智能比对' }}
            </span>
        </button>
    </div>
</template>
