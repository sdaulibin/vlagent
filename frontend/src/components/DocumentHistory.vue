<script setup lang="ts">
import { Clock, Trash2, AlertCircle, CheckCircle2, Loader2 } from 'lucide-vue-next';

interface TaskItem {
  id: number;
  file_a_name: string;
  file_b_name: string;
  file_a_page_count: number | null;
  file_b_page_count: number | null;
  status: string;
  comparison_duration: number | null;
  created_at: string;
}

defineProps<{
  historyList: TaskItem[];
}>();

const emit = defineEmits<{
  (e: 'view', task: TaskItem): void;
  (e: 'delete', taskId: number): void;
}>();

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  done: { icon: CheckCircle2, color: 'text-green-500', label: '已完成' },
  failed: { icon: AlertCircle, color: 'text-red-500', label: '失败' },
  processing: { icon: Loader2, color: 'text-blue-500', label: '处理中' },
  pending: { icon: Clock, color: 'text-slate-400', label: '等待中' },
};

const formatTime = (isoStr: string) => {
  const d = new Date(isoStr);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};
</script>

<template>
  <div class="flex-1 bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col overflow-hidden">
    <div class="px-5 py-4 border-b border-slate-100">
      <h2 class="text-base font-semibold text-slate-700">比对历史</h2>
    </div>

    <div v-if="historyList.length === 0" class="flex-1 flex items-center justify-center text-slate-400 text-sm">
      暂无比对记录
    </div>

    <div v-else class="flex-1 overflow-y-auto p-3 space-y-2">
      <div
        v-for="task in historyList"
        :key="task.id"
        class="p-3 rounded-xl border border-slate-100 hover:border-slate-200 hover:shadow-sm transition-all cursor-pointer group relative"
        @click="emit('view', task)"
      >
        <button
          @click.stop="emit('delete', task.id)"
          class="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-50 text-slate-300 hover:text-red-500 transition-all"
        >
          <Trash2 class="w-4 h-4" />
        </button>

        <div class="flex items-center gap-2 mb-2">
          <component
            :is="statusConfig[task.status]?.icon || Clock"
            :class="['w-4 h-4', statusConfig[task.status]?.color || 'text-slate-400']"
          />
          <span class="text-xs text-slate-400">{{ formatTime(task.created_at) }}</span>
          <span v-if="task.comparison_duration" class="text-xs text-slate-400">
            {{ task.comparison_duration }}s
          </span>
        </div>

        <p class="text-sm text-slate-700 truncate" :title="task.file_a_name">{{ task.file_a_name }}</p>
        <p class="text-xs text-slate-400 mt-0.5">vs</p>
        <p class="text-sm text-slate-700 truncate" :title="task.file_b_name">{{ task.file_b_name }}</p>
      </div>
    </div>
  </div>
</template>
