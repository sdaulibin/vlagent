<script setup lang="ts">
import { Clock, Trash2, AlertCircle, CheckCircle2, Loader2, Eye } from 'lucide-vue-next';
import type { TaskItem } from '../types';

defineProps<{
  historyList: TaskItem[];
  hasProcessing?: boolean;
}>();

const emit = defineEmits<{
  (e: 'view', task: TaskItem): void;
  (e: 'delete', taskId: number): void;
}>();

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; bg: string; label: string }> = {
  done: { icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-50', label: '比对完成' },
  failed: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-50', label: '比对失败' },
  processing: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-50', label: '比对中' },
  pending: { icon: Clock, color: 'text-slate-400', bg: 'bg-slate-50', label: '等待中' },
};

const formatTime = (isoStr: string) => {
  const d = new Date(isoStr);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};
</script>

<template>
  <div class="flex-1 bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col overflow-hidden">
    <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
      <h2 class="text-base font-semibold text-slate-700">比对列表</h2>
      <span v-if="hasProcessing" class="flex items-center gap-1.5 text-xs text-blue-500">
        <Loader2 class="w-3.5 h-3.5 animate-spin" />
        比对进行中
      </span>
    </div>

    <div v-if="historyList.length === 0" class="flex-1 flex items-center justify-center text-slate-400 text-sm">
      暂无比对记录
    </div>

    <div v-else class="flex-1 overflow-y-auto p-3 space-y-2">
      <div
        v-for="task in historyList"
        :key="task.id"
        class="p-3 rounded-xl border transition-all group relative"
        :class="[
          task.status === 'done'
            ? 'border-green-100 bg-green-50/30 hover:border-green-200 hover:shadow-sm cursor-pointer'
            : task.status === 'processing'
              ? 'border-blue-100 bg-blue-50/30'
              : task.status === 'failed'
                ? 'border-red-100 bg-red-50/30'
                : 'border-slate-100 hover:border-slate-200 hover:shadow-sm cursor-pointer',
        ]"
        @click="emit('view', task)"
      >
        <button
          @click.stop="emit('delete', task.id)"
          class="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-50 text-slate-300 hover:text-red-500 transition-all"
        >
          <Trash2 class="w-4 h-4" />
        </button>

        <!-- Status badge -->
        <div class="flex items-center gap-2 mb-2">
          <span
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
            :class="[statusConfig[task.status]?.bg, statusConfig[task.status]?.color]"
          >
            <component
              :is="statusConfig[task.status]?.icon || Clock"
              :class="[
                'w-3 h-3',
                task.status === 'processing' ? 'animate-spin' : '',
              ]"
            />
            {{ statusConfig[task.status]?.label || '未知' }}
          </span>
          <span class="text-xs text-slate-400">{{ formatTime(task.created_at) }}</span>
          <span v-if="task.comparison_duration" class="text-xs text-slate-400">
            {{ task.comparison_duration }}s
          </span>
        </div>

        <p class="text-sm text-slate-700 truncate" :title="task.file_a_name">{{ task.file_a_name }}</p>
        <p class="text-xs text-slate-400 mt-0.5">vs</p>
        <p class="text-sm text-slate-700 truncate" :title="task.file_b_name">{{ task.file_b_name }}</p>

        <!-- View result button for completed tasks -->
        <div
          v-if="task.status === 'done'"
          class="mt-2 flex items-center gap-1 text-xs font-medium text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Eye class="w-3.5 h-3.5" />
          查看比对结果
        </div>
      </div>
    </div>
  </div>
</template>
