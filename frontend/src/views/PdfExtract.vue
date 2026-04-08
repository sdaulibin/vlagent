<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue';
import { FileScan, ArrowLeft, Upload, Trash2, Loader2, ChevronRight, Plus, X, Download } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import {
  uploadPdfExtract,
  getPdfExtractTasks,
  getPdfExtractTask,
  deletePdfExtractTask,
  downloadPdfExtract
} from '../api';

interface ExtractField {
  name: string;
  description: string;
  type: string;
  items?: { name: string; type: string; description?: string }[];
}

interface TaskItem {
  id: number;
  filename: string;
  status: string;
  output_format: string;
  page_count: number | null;
  processing_duration: number | null;
  error_msg: string | null;
  created_at: string | null;
}

interface TaskDetail {
  id: number;
  filename: string;
  status: string;
  output_format: string;
  page_count: number | null;
  processing_duration: number | null;
  fields: ExtractField[];
  result: Record<string, any> | null;
  error_msg: string | null;
}

const router = useRouter();
const tasks = ref<TaskItem[]>([]);
const selectedDetail = ref<TaskDetail | null>(null);
const selectedTaskId = ref<number | null>(null);
const isUploading = ref(false);
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null);

// 字段配置
const fields = ref<ExtractField[]>([
  { name: '', description: '', type: 'string' }
]);
const outputFormat = ref('json');

// 是否显示配置面板
const showConfig = ref(true);

const hasProcessingTasks = computed(() =>
  tasks.value.some(t => t.status === 'pending' || t.status === 'processing')
);

const loadTasks = async () => {
  try {
    tasks.value = await getPdfExtractTasks();
  } catch (e) {
    console.error("加载任务列表失败", e);
  }
};

const selectTask = async (id: number) => {
  selectedTaskId.value = id;
  try {
    selectedDetail.value = await getPdfExtractTask(id);
  } catch (e) {
    console.error("加载任务详情失败", e);
  }
};

// 字段管理
const addField = () => {
  if (fields.value.length >= 10) return;
  fields.value.push({ name: '', description: '', type: 'string' });
};

const removeField = (index: number) => {
  fields.value.splice(index, 1);
};

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const fileList = target.files;
  if (!fileList || fileList.length === 0) return;

  // 校验字段
  const validFields = fields.value.filter(f => f.name.trim());
  if (validFields.length === 0) {
    alert('请至少配置一个提取字段');
    target.value = '';
    return;
  }

  isUploading.value = true;
  try {
    for (const file of Array.from(fileList)) {
      await uploadPdfExtract(
        file,
        JSON.stringify(validFields),
        outputFormat.value
      );
    }
    await loadTasks();
    startPolling();
  } catch (e) {
    console.error("上传失败", e);
  } finally {
    isUploading.value = false;
    target.value = '';
  }
};

const handleDelete = async (id: number) => {
  if (!confirm('确定要删除这条记录吗？')) return;
  try {
    await deletePdfExtractTask(id);
    if (selectedTaskId.value === id) {
      selectedDetail.value = null;
      selectedTaskId.value = null;
    }
    await loadTasks();
  } catch (e) {
    console.error("删除失败", e);
  }
};

const handleDownload = (taskId: number) => {
  const url = downloadPdfExtract(taskId);
  window.open(url, '_blank');
};

const goBack = () => {
  router.push('/');
};

const getStatusText = (status: string) => {
  switch (status) {
    case 'pending': return '待提取';
    case 'processing': return '提取中';
    case 'done': return '已完成';
    case 'failed': return '失败';
    default: return status;
  }
};

const getStatusClass = (status: string) => {
  switch (status) {
    case 'pending': return 'bg-yellow-100 text-yellow-700';
    case 'processing': return 'bg-blue-100 text-blue-700 animate-pulse';
    case 'done': return 'bg-green-100 text-green-700';
    case 'failed': return 'bg-red-100 text-red-700';
    default: return 'bg-gray-100 text-gray-700';
  }
};

const formatDuration = (seconds: number | null) => {
  if (seconds === null || seconds === undefined) return '-';
  return `${seconds.toFixed(1)}s`;
};

const startPolling = () => {
  if (pollTimer.value) return;
  pollTimer.value = setInterval(async () => {
    await loadTasks();
    if (selectedTaskId.value) {
      const current = tasks.value.find(t => t.id === selectedTaskId.value);
      if (current && (current.status === 'done' || current.status === 'failed')) {
        await selectTask(selectedTaskId.value);
      }
    }
    if (!hasProcessingTasks.value) {
      stopPolling();
    }
  }, 3000);
};

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
};

onMounted(async () => {
  await loadTasks();
  if (hasProcessingTasks.value) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="min-h-screen p-4 md:p-8 flex flex-col">
    <!-- Header -->
    <header class="w-full max-w-7xl mx-auto mb-6">
      <button @click="goBack" class="flex items-center gap-2 text-slate-500 hover:text-slate-700 mb-4">
        <ArrowLeft class="w-5 h-5" />
        返回首页
      </button>
      <div class="flex items-center gap-3">
        <div class="bg-gradient-to-br from-cyan-500 to-blue-600 p-3 rounded-xl shadow-lg">
          <FileScan class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="text-2xl font-bold text-slate-900">通用 PDF 提取</h1>
          <p class="text-sm text-slate-500">自定义提取字段，AI 自动从 PDF 文件中提取结构化信息</p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="w-full max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-6 flex-1">
      <!-- Left: Config + File List -->
      <div class="md:col-span-4 flex flex-col gap-4">
        <!-- Field Config -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200">
          <button
            @click="showConfig = !showConfig"
            class="w-full p-3 border-b border-slate-100 flex items-center justify-between"
          >
            <h3 class="font-medium text-slate-700">提取字段配置 ({{ fields.length }}/10)</h3>
            <span class="text-xs text-slate-400">{{ showConfig ? '收起' : '展开' }}</span>
          </button>
          <div v-if="showConfig" class="p-3 space-y-3">
            <div v-for="(field, index) in fields" :key="index" class="space-y-2">
              <div class="flex items-center gap-2">
                <input
                  v-model="field.name"
                  type="text"
                  placeholder="字段名称"
                  class="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
                />
                <select
                  v-model="field.type"
                  class="px-2 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
                >
                  <option value="string">文本</option>
                  <option value="number">数字</option>
                  <option value="array">数组</option>
                </select>
                <button @click="removeField(index)" class="p-1.5 text-slate-400 hover:text-red-500">
                  <X class="w-4 h-4" />
                </button>
              </div>
              <input
                v-model="field.description"
                type="text"
                placeholder="字段描述（可选，帮助模型理解）"
                class="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
              />
            </div>
            <button
              v-if="fields.length < 10"
              @click="addField"
              class="w-full flex items-center justify-center gap-1 py-2 text-sm text-cyan-600 hover:text-cyan-700 border border-dashed border-slate-300 hover:border-cyan-400 rounded-lg transition-colors"
            >
              <Plus class="w-4 h-4" />
              添加字段
            </button>

            <!-- Output Format -->
            <div class="pt-2 border-t border-slate-100">
              <label class="text-xs text-slate-500 mb-1 block">输出格式</label>
              <select
                v-model="outputFormat"
                class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
              >
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
                <option value="xlsx">Excel (XLSX)</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Upload -->
        <label class="flex items-center justify-center gap-2 bg-white border-2 border-dashed border-slate-300 hover:border-cyan-400 rounded-xl p-4 cursor-pointer transition-colors">
          <Upload class="w-5 h-5 text-slate-400" />
          <span class="text-slate-600">{{ isUploading ? '上传中...' : '点击上传 PDF' }}</span>
          <input type="file" accept=".pdf" multiple class="hidden" @change="handleFileUpload" :disabled="isUploading" />
        </label>

        <!-- Task List -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 flex-1 overflow-auto">
          <div class="p-3 border-b border-slate-100">
            <h3 class="font-medium text-slate-700">任务列表 ({{ tasks.length }})</h3>
          </div>
          <ul class="divide-y divide-slate-100">
            <li
              v-for="task in tasks"
              :key="task.id"
              @click="selectTask(task.id)"
              :class="[
                'p-3 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors',
                selectedTaskId === task.id ? 'bg-cyan-50' : ''
              ]"
            >
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-700 truncate">{{ task.filename }}</p>
                <div class="flex items-center gap-2 mt-1">
                  <span :class="['text-xs px-2 py-0.5 rounded-full', getStatusClass(task.status)]">
                    {{ getStatusText(task.status) }}
                  </span>
                  <span v-if="task.page_count" class="text-xs text-slate-400">{{ task.page_count }}页</span>
                  <span v-if="task.processing_duration" class="text-xs text-slate-400">{{ formatDuration(task.processing_duration) }}</span>
                </div>
              </div>
              <div class="flex items-center gap-1">
                <button
                  v-if="task.status === 'done' && task.output_format !== 'json'"
                  @click.stop="handleDownload(task.id)"
                  class="p-1.5 text-slate-400 hover:text-cyan-500 transition-colors"
                >
                  <Download class="w-4 h-4" />
                </button>
                <button
                  @click.stop="handleDelete(task.id)"
                  class="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
                <ChevronRight class="w-4 h-4 text-slate-300" />
              </div>
            </li>
            <li v-if="tasks.length === 0" class="p-6 text-center text-slate-400 text-sm">
              暂无提取记录，请上传 PDF 文件
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Result -->
      <div class="md:col-span-8 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col">
        <div class="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 class="font-medium text-slate-700">提取结果</h3>
          <div v-if="selectedDetail" class="flex items-center gap-3 text-sm text-slate-500">
            <span v-if="selectedDetail.page_count">共 {{ selectedDetail.page_count }} 页</span>
            <span v-if="selectedDetail.processing_duration">
              耗时 {{ formatDuration(selectedDetail.processing_duration) }}
            </span>
            <span :class="['px-2 py-0.5 rounded-full text-xs', getStatusClass(selectedDetail.status)]">
              {{ getStatusText(selectedDetail.status) }}
            </span>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="selectedDetail && selectedDetail.status === 'processing'" class="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
          <Loader2 class="w-8 h-8 animate-spin text-cyan-400" />
          <p>正在提取中，请稍候...</p>
        </div>

        <!-- Error -->
        <div v-else-if="selectedDetail && selectedDetail.status === 'failed'" class="flex-1 flex flex-col items-center justify-center gap-3 text-red-400 p-6">
          <p class="text-lg font-medium">提取失败</p>
          <p class="text-sm">{{ selectedDetail.error_msg }}</p>
        </div>

        <!-- Result JSON -->
        <div v-else-if="selectedDetail && selectedDetail.result" class="flex-1 overflow-auto p-4">
          <!-- Field cards -->
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
            <div
              v-for="(value, key) in selectedDetail.result"
              :key="key"
              class="py-3 px-4 bg-gray-50 rounded-lg"
            >
              <p class="text-xs text-gray-400 mb-1">{{ key }}</p>
              <p v-if="Array.isArray(value)" class="text-sm font-medium text-gray-700">
                {{ value.join(', ') }}
              </p>
              <p v-else class="text-sm font-medium text-gray-700 break-all">{{ value ?? '-' }}</p>
            </div>
          </div>

          <!-- Raw JSON toggle -->
          <details class="mt-4">
            <summary class="text-xs text-slate-400 cursor-pointer hover:text-slate-600">查看原始 JSON</summary>
            <pre class="mt-2 p-3 bg-slate-50 rounded-lg text-xs text-slate-600 overflow-auto max-h-96">{{ JSON.stringify(selectedDetail.result, null, 2) }}</pre>
          </details>
        </div>

        <!-- Done but no result -->
        <div v-else-if="selectedDetail && selectedDetail.status === 'done' && !selectedDetail.result" class="flex-1 flex items-center justify-center text-slate-400">
          未提取到有效信息
        </div>

        <!-- Empty -->
        <div v-else class="flex-1 flex items-center justify-center text-slate-400">
          请从左侧选择一个任务查看提取结果
        </div>
      </div>
    </main>
  </div>
</template>
