<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue';
import { Receipt, ArrowLeft, Upload, Trash2, Loader2, ChevronRight } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import {
  uploadInvoice,
  getInvoiceFiles,
  getInvoiceResult,
  deleteInvoiceFile,
  getInvoiceFileUrl
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
const invoiceFileUrl = ref<string>('');
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
      // 异步加载文件预览 blob URL
      if (selectedDetail.value) {
        invoiceFileUrl.value = await getInvoiceFileUrl(selectedDetail.value.file_id);
      }
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
  <div class="page-container">
    <!-- Header -->
    <header class="page-header">
      <button @click="goBack" class="page-back-btn">
        <ArrowLeft class="w-5 h-5" />
        返回首页
      </button>
      <div class="page-title-group">
        <div class="page-icon bg-gradient-to-br from-rose-500 to-red-600">
          <Receipt class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="page-title">发票智能识别</h1>
          <p class="page-subtitle">上传发票 PDF，AI 自动提取发票类型、号码、金额、购销方等关键信息</p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="page-main">
      <!-- Left: File List -->
      <div class="page-left-col">
        <!-- Upload -->
        <label class="upload-zone">
          <Upload class="w-5 h-5 text-slate-400" />
          <span class="text-slate-600">{{ isUploading ? '上传中...' : '点击上传发票（PDF / JPG / PNG）' }}</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png" multiple class="hidden" @change="handleFileUpload" :disabled="isUploading" />
        </label>

        <!-- File List -->
        <div class="file-list">
          <div class="file-list-header">
            <h3 class="font-medium text-slate-700">文件列表 ({{ files.length }})</h3>
          </div>
          <ul class="file-list-items">
            <li
              v-for="file in files"
              :key="file.id"
              @click="selectFile(file.id)"
              :class="[
                'file-list-item',
                selectedFileId === file.id ? 'file-list-item--active' : ''
              ]"
            >
              <div class="file-list-item-info">
                <p class="file-list-item-name">{{ file.filename }}</p>
                <div class="file-list-item-meta">
                  <span :class="getStatusClass(file.status)">
                    {{ getStatusText(file.status) }}
                  </span>
                  <span v-if="file.page_count" class="text-xs text-slate-400">{{ file.page_count }}页</span>
                  <span v-if="file.recognition_duration" class="text-xs text-slate-400">{{ formatDuration(file.recognition_duration) }}</span>
                </div>
              </div>
              <div class="file-list-item-actions">
                <button
                  @click.stop="handleDelete(file.id)"
                  class="file-list-delete-btn"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
                <ChevronRight class="w-4 h-4 text-slate-300" />
              </div>
            </li>
            <li v-if="files.length === 0" class="file-list-empty">
              暂无发票记录，请上传 PDF 文件
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Recognition Results -->
      <div class="page-right-col">
        <div class="content-card-header">
          <h3 class="content-card-title">识别结果</h3>
          <div v-if="selectedDetail" class="flex items-center gap-3 text-sm text-slate-500">
            <span v-if="selectedDetail.page_count">共 {{ selectedDetail.page_count }} 页</span>
            <span v-if="selectedDetail.recognition_duration">
              耗时 {{ formatDuration(selectedDetail.recognition_duration) }}
            </span>
            <span :class="getStatusClass(selectedDetail.status)">
              {{ getStatusText(selectedDetail.status) }}
            </span>
          </div>
        </div>

        <!-- Original File Preview -->
        <div v-if="selectedDetail" class="border-b border-slate-200 p-4">
          <div class="flex items-center justify-between mb-2">
            <h4 class="text-sm font-medium text-slate-600">原始文件</h4>
            <span class="text-xs text-slate-400">{{ selectedDetail.filename }}</span>
          </div>
          <div class="file-preview-container">
            <iframe
              v-if="selectedDetail.filename.toLowerCase().endsWith('.pdf')"
              :src="invoiceFileUrl"
              class="file-preview-iframe"
            ></iframe>
            <img
              v-else
              :src="invoiceFileUrl"
              class="file-preview-img"
              :alt="selectedDetail.filename"
            />
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="selectedDetail && selectedDetail.status === 'processing'" class="loading-state">
          <Loader2 class="w-8 h-8 animate-spin text-rose-400" />
          <p>正在识别中，请稍候...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="selectedDetail && selectedDetail.status === 'failed'" class="error-state">
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
        <div v-else-if="selectedDetail && selectedDetail.results.length === 0 && selectedDetail.status === 'done'" class="empty-state">
          该文件未识别到发票信息
        </div>

        <!-- No File Selected -->
        <div v-else class="empty-state">
          请从左侧选择一个文件查看识别结果
        </div>
      </div>
    </main>
  </div>
</template>
