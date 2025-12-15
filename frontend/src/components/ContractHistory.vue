<script setup lang="ts">
import { FileText, Clock, Trash2 } from 'lucide-vue-next';

interface TaskItem {
    id: number;
    file_a_name: string;
    file_b_name: string;
    status: string;
    created_at: string;
    content_a?: string;
    content_b?: string;
}

interface Props {
    historyList: TaskItem[];
}

const props = defineProps<Props>();

const emit = defineEmits<{
    (e: 'view', task: TaskItem): void;
    (e: 'delete', taskId: number): void;
}>();
</script>

<template>
    <div class="flex-1 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
            <h2 class="text-lg font-semibold text-slate-800">比对历史</h2>
            <p class="text-sm text-slate-500">查看之前的比对任务</p>
        </div>
        <div class="flex-1 overflow-y-auto p-4 space-y-3">
            <!-- Empty State -->
            <div v-if="props.historyList.length === 0" class="text-center text-slate-400 py-10">
                <FileText class="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>暂无比对历史</p>
                <p class="text-sm">完成比对后会在此处显示</p>
            </div>
            
            <!-- History Items -->
            <div 
                v-for="task in props.historyList" 
                :key="task.id"
                class="p-4 rounded-xl border border-slate-100 hover:border-slate-200 hover:shadow-sm transition-all cursor-pointer group"
                @click="emit('view', task)"
            >
                <div class="flex items-start justify-between">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-2">
                            <span :class="[
                                'px-2 py-0.5 rounded-full text-xs font-medium',
                                task.status === 'done' ? 'bg-green-100 text-green-700' :
                                task.status === 'failed' ? 'bg-red-100 text-red-700' :
                                'bg-yellow-100 text-yellow-700'
                            ]">
                                {{ task.status === 'done' ? '已完成' : task.status === 'failed' ? '失败' : '处理中' }}
                            </span>
                            <span class="text-xs text-slate-400 flex items-center gap-1">
                                <Clock class="w-3 h-3" />
                                {{ new Date(task.created_at).toLocaleString() }}
                            </span>
                        </div>
                        <div class="text-sm text-slate-700 truncate mb-1">
                            <span class="font-medium">原文档:</span> {{ task.file_a_name }}
                        </div>
                        <div class="text-sm text-slate-500 truncate">
                            <span class="font-medium">比对:</span> {{ task.file_b_name }}
                        </div>
                    </div>
                    <button 
                        @click.stop="emit('delete', task.id)"
                        class="opacity-0 group-hover:opacity-100 p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                    >
                        <Trash2 class="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
