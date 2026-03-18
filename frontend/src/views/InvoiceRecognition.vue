<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue';
import { Receipt, ArrowLeft, Upload, Trash2, Loader2, ChevronRight } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import {
  uploadInvoice,
  getInvoiceFiles,
  getInvoiceResult,
  deleteInvoiceFile
} from '../api';

interface InvoiceFileItem {
  id: number;
  filename: string;
  status: string;
  page_count: number | null;
  recognition_duration: number | null;
  error_msg: string | null;
  created_at: string | null;
}

interface InvoicePageResult {
  page_number: number;
  invoice_type: string | null;
  invoice_no: string | null;
  invoice_date: string | null;
  invoice_amount: string | null;
  buyer_name: string | null;
  buyer_tax_id: string | null;
  seller_name: string | null;
  seller_tax_id: string | null;
  raw_text: string | null;
  error_msg: string | null;
}

interface InvoiceDetail {
  file_id: number;
  filename: string;
  status: string;
  page_count: number | null;
  recognition_duration: number | null;
  results: InvoicePageResult[];
  error_msg: string | null;
}

const router = useRouter();
const files = ref<InvoiceFileItem[]>([]);
const selectedDetail = ref<InvoiceDetail | null>(null);
const selectedFileId = ref<number | null>(null);
const isUploading = ref(false);
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null);

const hasProcessingFiles = computed(() =>
  files.value.some(f => f.status === 'pending' || f.status === 'processing')
);

const loadFiles = async () => {
  try {
    files.value = await getInvoiceFiles();
  } catch (e) {
    console.error("加载发票文件列表失败", e);
  }
};

const selectFile = async (id: number) => {
  selectedFileId.value = id;
  try {
    selectedDetail.value = await getInvoiceResult(id);
  } catch (e) {
    console.error("加载发票识别结果失败", e);
  }
};

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const fileList = target.files;
  if (!fileList || fileList.length === 0) return;

  isUploading.value = true;
  try {
    for (const file of Array.from(fileList)) {
      await uploadInvoice(file);
    }
    await loadFiles();
    startPolling();
  } catch (e) {
    console.error("上传失败", e);
  } finally {
    isUploading.value = false;
    target.value = '';
  }
};

const handleDelete = async (id: number) => {
  if (!confirm('确定要删除这条发票记录吗？')) return;
  try {
    await deleteInvoiceFile(id);
    if (selectedFileId.value === id) {
      selectedDetail.value = null;
      selectedFileId.value = null;
    }
    await loadFiles();
  } catch (e) {
    console.error("删除失败", e);
  }
};

const goBack = () => {
  router.push('/');
};

const getStatusText = (status: string) => {
  switch (status) {
    case 'pending': return '待识别';
    case 'processing': return '识别中';
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

// 轮询：如果有 pending/processing 的文件，定时刷新状态
const startPolling = () => {
  if (pollTimer.value) return;
  pollTimer.value = setInterval(async () => {
    await loadFiles();
    // 如果当前选中的文件状态变了，也刷新详情
    if (selectedFileId.value) {
      const currentFile = files.value.find(f => f.id === selectedFileId.value);
      if (currentFile && (currentFile.status === 'done' || currentFile.status === 'failed')) {
        await selectFile(selectedFileId.value);
      }
    }
    // 没有正在处理的文件时停止轮询
    if (!hasProcessingFiles.value) {
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
  await loadFiles();
  if (hasProcessingFiles.value) {
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
        <div class="bg-gradient-to-br from-rose-500 to-red-600 p-3 rounded-xl shadow-lg">
          <Receipt class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="text-2xl font-bold text-slate-900">发票智能识别</h1>
          <p class="text-sm text-slate-500">上传发票 PDF，AI 自动提取发票类型、号码、金额、购销方等关键信息</p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="w-full max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-6 flex-1">
      <!-- Left: File List -->
      <div class="md:col-span-4 flex flex-col gap-4">
        <!-- Upload -->
        <label class="flex items-center justify-center gap-2 bg-white border-2 border-dashed border-slate-300 hover:border-rose-400 rounded-xl p-4 cursor-pointer transition-colors">
          <Upload class="w-5 h-5 text-slate-400" />
          <span class="text-slate-600">{{ isUploading ? '上传中...' : '点击上传发票（PDF / JPG / PNG）' }}</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png" multiple class="hidden" @change="handleFileUpload" :disabled="isUploading" />
        </label>

        <!-- File List -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 flex-1 overflow-auto">
          <div class="p-3 border-b border-slate-100">
            <h3 class="font-medium text-slate-700">文件列表 ({{ files.length }})</h3>
          </div>
          <ul class="divide-y divide-slate-100">
            <li
              v-for="file in files"
              :key="file.id"
              @click="selectFile(file.id)"
              :class="[
                'p-3 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors',
                selectedFileId === file.id ? 'bg-rose-50' : ''
              ]"
            >
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-700 truncate">{{ file.filename }}</p>
                <div class="flex items-center gap-2 mt-1">
                  <span :class="['text-xs px-2 py-0.5 rounded-full', getStatusClass(file.status)]">
                    {{ getStatusText(file.status) }}
                  </span>
                  <span v-if="file.page_count" class="text-xs text-slate-400">{{ file.page_count }}页</span>
                  <span v-if="file.recognition_duration" class="text-xs text-slate-400">{{ formatDuration(file.recognition_duration) }}</span>
                </div>
              </div>
              <div class="flex items-center gap-1">
                <button
                  @click.stop="handleDelete(file.id)"
                  class="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
                <ChevronRight class="w-4 h-4 text-slate-300" />
              </div>
            </li>
            <li v-if="files.length === 0" class="p-6 text-center text-slate-400 text-sm">
              暂无发票记录，请上传 PDF 文件
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Recognition Results -->
      <div class="md:col-span-8 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col">
        <div class="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 class="font-medium text-slate-700">识别结果</h3>
          <div v-if="selectedDetail" class="flex items-center gap-3 text-sm text-slate-500">
            <span v-if="selectedDetail.page_count">共 {{ selectedDetail.page_count }} 页</span>
            <span v-if="selectedDetail.recognition_duration">
              耗时 {{ formatDuration(selectedDetail.recognition_duration) }}
            </span>
            <span :class="['px-2 py-0.5 rounded-full text-xs', getStatusClass(selectedDetail.status)]">
              {{ getStatusText(selectedDetail.status) }}
            </span>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="selectedDetail && selectedDetail.status === 'processing'" class="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
          <Loader2 class="w-8 h-8 animate-spin text-rose-400" />
          <p>正在识别中，请稍候...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="selectedDetail && selectedDetail.status === 'failed'" class="flex-1 flex flex-col items-center justify-center gap-3 text-red-400 p-6">
          <p class="text-lg font-medium">识别失败</p>
          <p class="text-sm">{{ selectedDetail.error_msg }}</p>
        </div>

        <!-- Results Cards -->
        <div v-else-if="selectedDetail && selectedDetail.results.length > 0" class="flex-1 overflow-auto p-4 space-y-4">
          <div
            v-for="result in selectedDetail.results"
            :key="result.page_number"
            class="bg-white border border-slate-200 rounded-xl p-4"
          >
            <!-- Card Header -->
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <div class="w-7 h-7 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center text-sm font-bold">
                  {{ result.page_number }}
                </div>
                <span v-if="result.invoice_type" class="text-sm font-medium text-slate-700">{{ result.invoice_type }}</span>
                <span v-else class="text-sm text-slate-400">未识别发票类型</span>
              </div>
              <div class="flex items-center gap-2">
                <span v-if="result.invoice_amount" class="text-lg font-bold text-rose-600">¥{{ result.invoice_amount }}</span>
                <span v-if="result.error_msg" class="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-600" :title="result.error_msg">异常</span>
                <span v-else class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-600">正常</span>
              </div>
            </div>

            <!-- Summary Grid -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div class="py-2 px-3 bg-gray-50 rounded-lg">
                <p class="text-xs text-gray-400 mb-1">发票号码</p>
                <p class="text-sm font-medium text-gray-700 font-mono">{{ result.invoice_no || '-' }}</p>
              </div>
              <div class="py-2 px-3 bg-gray-50 rounded-lg">
                <p class="text-xs text-gray-400 mb-1">开票日期</p>
                <p class="text-sm font-medium text-gray-700">{{ result.invoice_date || '-' }}</p>
              </div>
              <div class="py-2 px-3 bg-gray-50 rounded-lg">
                <p class="text-xs text-gray-400 mb-1">价税合计</p>
                <p class="text-sm font-bold text-rose-600">{{ result.invoice_amount ? `¥${result.invoice_amount}` : '-' }}</p>
              </div>
              <div class="py-2 px-3 bg-gray-50 rounded-lg">
                <p class="text-xs text-gray-400 mb-1">发票类型</p>
                <p class="text-sm font-medium text-gray-700">{{ result.invoice_type || '-' }}</p>
              </div>
            </div>

            <!-- Buyer & Seller -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
              <div class="py-2 px-3 bg-blue-50 rounded-lg">
                <p class="text-xs text-blue-400 mb-1">购买方</p>
                <p class="text-sm font-medium text-gray-700">{{ result.buyer_name || '-' }}</p>
                <p v-if="result.buyer_tax_id" class="text-xs text-gray-400 mt-0.5 font-mono">{{ result.buyer_tax_id }}</p>
              </div>
              <div class="py-2 px-3 bg-green-50 rounded-lg">
                <p class="text-xs text-green-500 mb-1">销售方</p>
                <p class="text-sm font-medium text-gray-700">{{ result.seller_name || '-' }}</p>
                <p v-if="result.seller_tax_id" class="text-xs text-gray-400 mt-0.5 font-mono">{{ result.seller_tax_id }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="selectedDetail && selectedDetail.results.length === 0 && selectedDetail.status === 'done'" class="flex-1 flex items-center justify-center text-slate-400">
          该文件未识别到发票信息
        </div>

        <!-- No File Selected -->
        <div v-else class="flex-1 flex items-center justify-center text-slate-400">
          请从左侧选择一个文件查看识别结果
        </div>
      </div>
    </main>
  </div>
</template>
