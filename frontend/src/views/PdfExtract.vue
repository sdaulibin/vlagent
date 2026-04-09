<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue';
import { FileScan, ArrowLeft, Upload, Trash2, Loader2, ChevronRight, Plus, X, Download, Copy, Check, FileJson, Table2 } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import {
  uploadPdfExtract,
  getPdfExtractTasks,
  getPdfExtractTask,
  deletePdfExtractTask,
  downloadPdfExtract
} from '../api';

interface ExtractFieldItem {
  name: string;
  type: string;
  description?: string;
}

interface ExtractField {
  name: string;
  description: string;
  type: string;
  items?: ExtractFieldItem[];
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
const copied = ref(false);

// 字段配置
const fields = ref<ExtractField[]>([
  { name: '', description: '', type: 'string' }
]);
const outputFormat = ref('json');

// 是否显示配置面板
const showConfig = ref(true);

// 结果展示模式：table / json
const resultViewMode = ref<'table' | 'json'>('table');

const hasProcessingTasks = computed(() =>
  tasks.value.some(t => t.status === 'pending' || t.status === 'processing')
);

// 分离标量字段和表格字段
const scalarResult = computed(() => {
  if (!selectedDetail.value?.result) return {};
  const result = selectedDetail.value.result;
  const tableFieldNames = new Set(
    (selectedDetail.value.fields || [])
      .filter(f => f.type === 'object_array')
      .map(f => f.name)
  );
  // 也把值为对象数组但字段定义中未标记的识别为表格
  const scalar: Record<string, any> = {};
  for (const [key, value] of Object.entries(result)) {
    if (!tableFieldNames.has(key) && !isObjectArray(value)) {
      scalar[key] = value;
    }
  }
  return scalar;
});

const tableFields = computed(() => {
  if (!selectedDetail.value?.result) return [];
  const result = selectedDetail.value.result;
  const fieldDefs = selectedDetail.value.fields || [];

  // 从字段定义中获取 object_array 类型
  const definedTableFields = fieldDefs
    .filter(f => f.type === 'object_array' && result[f.name] && Array.isArray(result[f.name]))
    .map(f => ({
      key: f.name,
      label: f.description || f.name,
      columns: f.items || [],
      data: result[f.name] as Record<string, any>[]
    }));

  // 自动检测结果中的对象数组（未被字段定义覆盖的）
  const definedKeys = new Set(definedTableFields.map(f => f.key));
  for (const [key, value] of Object.entries(result)) {
    if (!definedKeys.has(key) && isObjectArray(value)) {
      const arr = value as Record<string, any>[];
      const cols = extractColumns(arr);
      const fieldDef = fieldDefs.find(f => f.name === key);
      definedTableFields.push({
        key,
        label: fieldDef?.description || key,
        columns: cols,
        data: arr
      });
    }
  }

  return definedTableFields;
});

// 判断值是否为对象数组
const isObjectArray = (value: any): boolean => {
  return Array.isArray(value) && value.length > 0 && typeof value[0] === 'object' && !Array.isArray(value[0]);
};

// 从对象数组中提取列定义
const extractColumns = (arr: Record<string, any>[]): ExtractFieldItem[] => {
  const colSet = new Set<string>();
  for (const item of arr) {
    for (const key of Object.keys(item)) {
      colSet.add(key);
    }
  }
  return Array.from(colSet).map(name => ({
    name,
    type: 'string',
    description: name
  }));
};

// 获取字段显示标签
const getFieldLabel = (key: string): string => {
  const fieldDef = (selectedDetail.value?.fields || []).find(f => f.name === key);
  return fieldDef?.description || key;
};

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
    // 如果有表格数据，默认显示表格视图；否则显示 JSON
    if (tableFields.value.length > 0) {
      resultViewMode.value = 'table';
    } else {
      resultViewMode.value = 'json';
    }
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

// 添加 object_array 子字段
const addSubField = (fieldIndex: number) => {
  const field = fields.value[fieldIndex];
  if (!field.items) field.items = [];
  field.items.push({ name: '', type: 'string' });
};

const removeSubField = (fieldIndex: number, subIndex: number) => {
  fields.value[fieldIndex].items?.splice(subIndex, 1);
};

// 当字段类型变为 object_array 时初始化 items
const onFieldTypeChange = (field: ExtractField) => {
  if (field.type === 'object_array' && !field.items) {
    field.items = [{ name: '', type: 'string' }];
  }
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

  // 校验 object_array 子字段
  for (const field of validFields) {
    if (field.type === 'object_array') {
      const validItems = (field.items || []).filter(i => i.name.trim());
      if (validItems.length === 0) {
        alert(`字段"${field.name}"为对象数组类型，请至少定义一个子字段`);
        target.value = '';
        return;
      }
      field.items = validItems;
    }
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

// 复制 JSON 到剪贴板
const copyResultJson = async () => {
  if (!selectedDetail.value?.result) return;
  try {
    await navigator.clipboard.writeText(JSON.stringify(selectedDetail.value.result, null, 2));
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2000);
  } catch (e) {
    console.error("复制失败", e);
  }
};

// 下载 JSON 文件
const downloadJson = () => {
  if (!selectedDetail.value?.result || !selectedDetail.value.filename) return;
  const json = JSON.stringify(selectedDetail.value.result, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = selectedDetail.value.filename.replace('.pdf', '.json');
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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

// 格式化显示值
const formatValue = (value: any): string => {
  if (value === null || value === undefined) return '-';
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
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
                  @change="onFieldTypeChange(field)"
                  class="px-2 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
                >
                  <option value="string">文本</option>
                  <option value="number">数字</option>
                  <option value="array">数组</option>
                  <option value="object_array">对象数组</option>
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
              <!-- object_array 子字段编辑 -->
              <div v-if="field.type === 'object_array'" class="ml-3 pl-3 border-l-2 border-cyan-200 space-y-2">
                <p class="text-xs text-slate-400">子字段定义：</p>
                <div v-for="(sub, subIdx) in field.items" :key="subIdx" class="flex items-center gap-2">
                  <input
                    v-model="sub.name"
                    type="text"
                    placeholder="子字段名称"
                    class="flex-1 px-2 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
                  />
                  <select
                    v-model="sub.type"
                    class="px-2 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
                  >
                    <option value="string">文本</option>
                    <option value="number">数字</option>
                  </select>
                  <input
                    v-model="sub.description"
                    type="text"
                    placeholder="描述"
                    class="flex-1 px-2 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:border-cyan-400"
                  />
                  <button @click="removeSubField(index, subIdx)" class="p-1 text-slate-400 hover:text-red-500">
                    <X class="w-3 h-3" />
                  </button>
                </div>
                <button
                  @click="addSubField(index)"
                  class="flex items-center gap-1 py-1 text-xs text-cyan-600 hover:text-cyan-700"
                >
                  <Plus class="w-3 h-3" />
                  添加子字段
                </button>
              </div>
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

        <!-- Result Content -->
        <div v-else-if="selectedDetail && selectedDetail.result" class="flex-1 overflow-auto">
          <!-- Toolbar -->
          <div class="px-4 pt-3 flex items-center justify-between border-b border-slate-100 pb-3">
            <div class="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
              <button
                @click="resultViewMode = 'table'"
                :class="[
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  resultViewMode === 'table' ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                ]"
              >
                <Table2 class="w-3.5 h-3.5" />
                表格视图
              </button>
              <button
                @click="resultViewMode = 'json'"
                :class="[
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  resultViewMode === 'json' ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                ]"
              >
                <FileJson class="w-3.5 h-3.5" />
                JSON
              </button>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="downloadJson"
                class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-700 bg-slate-50 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <Download class="w-3.5 h-3.5" />
                JSON
              </button>
              <button
                v-if="selectedDetail.output_format !== 'json'"
                @click="handleDownload(selectedDetail.id)"
                class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-700 bg-slate-50 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <Download class="w-3.5 h-3.5" />
                {{ selectedDetail.output_format.toUpperCase() }}
              </button>
              <button
                @click="copyResultJson"
                class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-700 bg-slate-50 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <Check v-if="copied" class="w-3.5 h-3.5 text-green-500" />
                <Copy v-else class="w-3.5 h-3.5" />
                {{ copied ? '已复制' : '复制' }}
              </button>
            </div>
          </div>

          <!-- Table View -->
          <div v-if="resultViewMode === 'table'" class="p-4 space-y-5">
            <!-- Scalar fields as key-value cards -->
            <div v-if="Object.keys(scalarResult).length > 0">
              <h4 class="text-sm font-medium text-slate-600 mb-3">基本信息</h4>
              <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div
                  v-for="(value, key) in scalarResult"
                  :key="key"
                  class="py-2.5 px-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <p class="text-xs text-gray-400 mb-1">{{ getFieldLabel(key as string) }}</p>
                  <p v-if="Array.isArray(value)" class="text-sm font-medium text-gray-700">
                    {{ value.join(', ') || '-' }}
                  </p>
                  <p v-else class="text-sm font-medium text-gray-700 break-all">{{ value ?? '-' }}</p>
                </div>
              </div>
            </div>

            <!-- Table fields -->
            <div v-for="tableField in tableFields" :key="tableField.key">
              <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-medium text-slate-600">{{ tableField.label }}</h4>
                <span class="text-xs text-slate-400">共 {{ tableField.data.length }} 条</span>
              </div>
              <div class="border border-slate-200 rounded-xl overflow-hidden">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="bg-slate-50">
                      <th class="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 w-10">#</th>
                      <th
                        v-for="col in tableField.columns"
                        :key="col.name"
                        class="px-4 py-2.5 text-left text-xs font-semibold text-slate-500"
                      >
                        {{ col.description || col.name }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, rowIdx) in tableField.data"
                      :key="rowIdx"
                      class="border-t border-slate-100 hover:bg-slate-50 transition-colors"
                    >
                      <td class="px-4 py-2.5 text-xs text-slate-400">{{ rowIdx + 1 }}</td>
                      <td
                        v-for="col in tableField.columns"
                        :key="col.name"
                        class="px-4 py-2.5 text-slate-700"
                      >
                        <span v-if="row[col.name] !== null && row[col.name] !== undefined">
                          {{ row[col.name] }}
                        </span>
                        <span v-else class="text-slate-300">-</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Fallback: all scalar, no tables -->
            <div v-if="Object.keys(scalarResult).length === 0 && tableFields.length === 0" class="text-center text-slate-400 py-8">
              无结构化数据可展示
            </div>
          </div>

          <!-- JSON View -->
          <div v-else class="p-4">
            <pre class="p-4 bg-slate-50 rounded-xl text-xs text-slate-600 overflow-auto max-h-[calc(100vh-320px)] leading-relaxed border border-slate-200">{{ JSON.stringify(selectedDetail.result, null, 2) }}</pre>
          </div>
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
