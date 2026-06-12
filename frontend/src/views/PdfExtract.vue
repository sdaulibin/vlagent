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
import type { PdfExtractTaskItem as TaskItem, PdfExtractTaskDetail as TaskDetail, ExtractField, ExtractFieldItem } from '../types';

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
  if (!field) return;
  if (!field.items) field.items = [];
  field.items.push({ name: '', type: 'string' });
};

const removeSubField = (fieldIndex: number, subIndex: number) => {
  fields.value[fieldIndex]?.items?.splice(subIndex, 1);
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

const handleDownload = async (taskId: number) => {
  const url = await downloadPdfExtract(taskId);
  window.open(url + '#toolbar=0', '_blank');
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
    case 'pending': return 'status-badge status-badge--pending';
    case 'processing': return 'status-badge status-badge--processing';
    case 'done': return 'status-badge status-badge--done';
    case 'failed': return 'status-badge status-badge--failed';
    default: return 'status-badge';
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
  <div class="page-container">
    <!-- Header -->
    <header class="page-header">
      <button @click="goBack" class="page-back-btn">
        <ArrowLeft class="w-5 h-5" />
        返回首页
      </button>
      <div class="page-title-group">
        <div class="page-icon bg-gradient-to-br from-cyan-500 to-blue-600">
          <FileScan class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="page-title">通用 PDF 提取</h1>
          <p class="page-subtitle">自定义提取字段，AI 自动从 PDF 文件中提取结构化信息</p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="page-main">
      <!-- Left: Config + File List -->
      <div class="page-left-col">
        <!-- Field Config -->
        <div class="content-card">
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
        <label class="upload-zone hover:border-cyan-400">
          <Upload class="w-5 h-5 text-slate-400" />
          <span class="text-slate-600">{{ isUploading ? '上传中...' : '点击上传 PDF' }}</span>
          <input type="file" accept=".pdf" multiple class="hidden" @change="handleFileUpload" :disabled="isUploading" />
        </label>

        <!-- Task List -->
        <div class="file-list">
          <div class="file-list-header">
            <h3 class="content-card-title">任务列表 ({{ tasks.length }})</h3>
          </div>
          <ul class="file-list-items">
            <li
              v-for="task in tasks"
              :key="task.id"
              @click="selectTask(task.id)"
              :class="[
                'file-list-item',
                selectedTaskId === task.id ? 'bg-cyan-50' : ''
              ]"
            >
              <div class="file-list-item-info">
                <p class="file-list-item-name">{{ task.filename }}</p>
                <div class="file-list-item-meta">
                  <span :class="getStatusClass(task.status)">
                    {{ getStatusText(task.status) }}
                  </span>
                  <span v-if="task.page_count" class="text-xs text-slate-400">{{ task.page_count }}页</span>
                  <span v-if="task.processing_duration" class="text-xs text-slate-400">{{ formatDuration(task.processing_duration) }}</span>
                </div>
              </div>
              <div class="file-list-item-actions">
                <button
                  v-if="task.status === 'done' && task.output_format !== 'json'"
                  @click.stop="handleDownload(task.id)"
                  class="p-1.5 text-slate-400 hover:text-cyan-500 transition-colors"
                >
                  <Download class="w-4 h-4" />
                </button>
                <button
                  @click.stop="handleDelete(task.id)"
                  class="file-list-delete-btn"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
                <ChevronRight class="w-4 h-4 text-slate-300" />
              </div>
            </li>
            <li v-if="tasks.length === 0" class="file-list-empty">
              暂无提取记录，请上传 PDF 文件
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Result -->
      <div class="page-right-col">
        <div class="content-card-header">
          <h3 class="content-card-title">提取结果</h3>
          <div v-if="selectedDetail" class="flex items-center gap-3 text-sm text-slate-500">
            <span v-if="selectedDetail.page_count">共 {{ selectedDetail.page_count }} 页</span>
            <span v-if="selectedDetail.processing_duration">
              耗时 {{ formatDuration(selectedDetail.processing_duration) }}
            </span>
            <span :class="getStatusClass(selectedDetail.status)">
              {{ getStatusText(selectedDetail.status) }}
            </span>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="selectedDetail && selectedDetail.status === 'processing'" class="loading-state">
          <Loader2 class="w-8 h-8 animate-spin text-cyan-400" />
          <p>正在提取中，请稍候...</p>
        </div>

        <!-- Error -->
        <div v-else-if="selectedDetail && selectedDetail.status === 'failed'" class="error-state">
          <p class="text-lg font-medium">提取失败</p>
          <p class="text-sm">{{ selectedDetail.error_msg }}</p>
        </div>

        <!-- Result Content -->
        <div v-else-if="selectedDetail && selectedDetail.result" class="content-card-body">
          <!-- Toolbar -->
          <div class="px-4 pt-3 flex items-center justify-between border-b border-slate-100 pb-3">
            <div class="view-mode-tabs">
              <button
                @click="resultViewMode = 'table'"
                :class="[
                  'view-mode-tab',
                  resultViewMode === 'table' ? 'view-mode-tab--active' : ''
                ]"
              >
                <Table2 class="w-3.5 h-3.5" />
                表格视图
              </button>
              <button
                @click="resultViewMode = 'json'"
                :class="[
                  'view-mode-tab',
                  resultViewMode === 'json' ? 'view-mode-tab--active' : ''
                ]"
              >
                <FileJson class="w-3.5 h-3.5" />
                JSON
              </button>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="downloadJson"
                class="btn-toolbar"
              >
                <Download class="w-3.5 h-3.5" />
                JSON
              </button>
              <button
                v-if="selectedDetail.output_format !== 'json'"
                @click="handleDownload(selectedDetail.id)"
                class="btn-toolbar"
              >
                <Download class="w-3.5 h-3.5" />
                {{ selectedDetail.output_format.toUpperCase() }}
              </button>
              <button
                @click="copyResultJson"
                class="btn-toolbar"
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
              <div class="result-grid">
                <div
                  v-for="(value, key) in scalarResult"
                  :key="key"
                  class="result-field"
                >
                  <p class="result-field-label">{{ getFieldLabel(key as string) }}</p>
                  <p v-if="Array.isArray(value)" class="result-field-value">
                    {{ value.join(', ') || '-' }}
                  </p>
                  <p v-else class="result-field-value break-all">{{ value ?? '-' }}</p>
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
                <table class="data-table">
                  <thead>
                    <tr class="data-table-header">
                      <th class="data-table-index">#</th>
                      <th
                        v-for="col in tableField.columns"
                        :key="col.name"
                        class="data-table-header-cell"
                      >
                        {{ col.description || col.name }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, rowIdx) in tableField.data"
                      :key="rowIdx"
                      class="data-table-row"
                    >
                      <td class="data-table-index">{{ rowIdx + 1 }}</td>
                      <td
                        v-for="col in tableField.columns"
                        :key="col.name"
                        class="data-table-cell"
                      >
                        <span v-if="row[col.name] !== null && row[col.name] !== undefined">
                          {{ row[col.name] }}
                        </span>
                        <span v-else class="data-table-cell--empty">-</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Fallback: all scalar, no tables -->
            <div v-if="Object.keys(scalarResult).length === 0 && tableFields.length === 0" class="empty-state py-8">
              无结构化数据可展示
            </div>
          </div>

          <!-- JSON View -->
          <div v-else class="p-4">
            <pre class="p-4 bg-slate-50 rounded-xl text-xs text-slate-600 overflow-auto max-h-[calc(100vh-320px)] leading-relaxed border border-slate-200">{{ JSON.stringify(selectedDetail.result, null, 2) }}</pre>
          </div>
        </div>

        <!-- Done but no result -->
        <div v-else-if="selectedDetail && selectedDetail.status === 'done' && !selectedDetail.result" class="empty-state">
          未提取到有效信息
        </div>

        <!-- Empty -->
        <div v-else class="empty-state">
          请从左侧选择一个任务查看提取结果
        </div>
      </div>
    </main>
  </div>
</template>
