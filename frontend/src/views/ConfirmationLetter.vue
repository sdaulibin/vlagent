<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { FileText, ArrowLeft, Play, Trash2, Upload, RefreshCcw } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import {
  uploadConfirmationLetter,
  getConfirmationLetters,
  getConfirmationLetter,
  recognizeConfirmationLetter,
  deleteConfirmationLetter,
  getConfirmationPreviewUrl
} from '../api';
import type { ConfirmationLetterItem } from '../types';

const router = useRouter();
const letters = ref<ConfirmationLetterItem[]>([]);
const selectedLetter = ref<ConfirmationLetterItem | null>(null);
const previewUrl = ref('');
const isUploading = ref(false);
const isRecognizing = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

const startPolling = () => {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    await loadLetters();
    if (selectedLetter.value) {
      const current = letters.value.find(l => l.id === selectedLetter.value!.id);
      if (current && (current.status === 'done' || current.status === 'failed')) {
        await selectLetter(current.id);
      }
    }
    if (!letters.value.some(l => l.status === 'processing' || l.status === 'pending')) {
      stopPolling();
    }
  }, 10000);
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

// 字段定义（用于展示）
const displayFields = [
  { key: 'confirmation_no', label: '函证编号' },
  { key: 'recipient_bank', label: '询证函抬头' },
  { key: 'accounting_firm', label: '事务所名称' },
  { key: 'reply_address', label: '回函地址' },
  { key: 'contact_person', label: '联系人' },
  { key: 'phone', label: '电话' },
  { key: 'postal_code', label: '邮编' },
  { key: 'debit_account', label: '扣费账号' },
  { key: 'cutoff_date', label: '截止日期' },
  { key: 'start_date', label: '起始日期' },
  { key: 'end_date', label: '终止日期' },
  { key: 'seal_date', label: '印章日期' },
  { key: 'seal_name', label: '印章名称' },
  { key: 'signature_name', label: '落款名称' },
];

const loadLetters = async () => {
  try {
    letters.value = await getConfirmationLetters();
  } catch (e) {
    console.error("加载询证函列表失败", e);
  }
};

const selectLetter = async (id: number) => {
  try {
    const detail = await getConfirmationLetter(id);
    selectedLetter.value = detail;
    previewUrl.value = await getConfirmationPreviewUrl(id);
    // Sync latest status back to the list
    const idx = letters.value.findIndex(l => l.id === id);
    if (idx !== -1) {
      letters.value[idx] = { ...letters.value[idx], status: detail.status, recognition: detail.recognition };
    }
  } catch (e) {
    console.error("加载询证函详情失败", e);
  }
};

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const files = target.files;
  if (!files || files.length === 0) return;

  isUploading.value = true;
  try {
    for (const file of Array.from(files)) {
      await uploadConfirmationLetter(file);
    }
    await loadLetters();
  } catch (e) {
    console.error("上传失败", e);
  } finally {
    isUploading.value = false;
    target.value = '';
  }
};

const handleStartRecognition = async () => {
  const retryableLetters = letters.value.filter(l => l.status === 'pending' || l.status === 'failed');
  if (retryableLetters.length === 0) return;

  isRecognizing.value = true;

  retryableLetters.forEach(letter => {
    const idx = letters.value.findIndex(l => l.id === letter.id);
    if (idx !== -1) {
      letters.value[idx] = { ...letters.value[idx], status: 'processing' } as ConfirmationLetterItem;
    }
  });

  try {
    for (const letter of retryableLetters) {
      await recognizeConfirmationLetter(letter.id);
    }
    await loadLetters();
    if (selectedLetter.value) {
      await selectLetter(selectedLetter.value.id);
    }
    startPolling();
  } catch (e) {
    console.error("识别失败", e);
    await loadLetters();
  } finally {
    isRecognizing.value = false;
  }
};

const handleRecognizeOne = async (id: number) => {
  const idx = letters.value.findIndex(l => l.id === id);
  if (idx !== -1) {
    letters.value[idx] = { ...letters.value[idx], status: 'processing' } as ConfirmationLetterItem;
  }
  try {
    await recognizeConfirmationLetter(id);
    await loadLetters();
    startPolling();
    if (selectedLetter.value?.id === id) {
      await selectLetter(id);
    }
  } catch (e) {
    console.error("单条识别失败", e);
    await loadLetters();
  }
};

const handleDelete = async (id: number) => {
  if (!confirm('确定要删除这条询证函记录吗？')) return;

  try {
    await deleteConfirmationLetter(id);
    if (selectedLetter.value?.id === id) {
      selectedLetter.value = null;
      previewUrl.value = '';
    }
    await loadLetters();
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

const getFieldValue = (key: string): string => {
  const recognition = selectedLetter.value?.recognition;
  if (!recognition) return '-';
  return (recognition as any)[key] || '-';
};

onMounted(async () => {
  await loadLetters();
  if (letters.value.some(l => l.status === 'processing' || l.status === 'pending')) {
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
      <div class="flex items-center gap-3">
        <div class="page-icon bg-emerald-600">
          <FileText class="text-white w-7 h-7" />
        </div>
        <div class="page-title-group">
          <h1 class="page-title">询证函智能识别</h1>
          <p class="page-subtitle">智能识别银行询证函关键字段</p>
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
          <span class="text-slate-600">{{ isUploading ? '上传中...' : '点击上传询证函 PDF' }}</span>
          <input type="file" accept=".pdf" multiple class="hidden" @change="handleFileUpload" :disabled="isUploading" />
        </label>

        <!-- Start Recognition -->
        <button
          @click="handleStartRecognition"
          :disabled="isRecognizing"
          class="btn-gradient bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700"
        >
          <Play class="w-5 h-5" />
          {{ isRecognizing ? '识别中...' : '开始识别 / 重试失败' }}
        </button>

        <!-- File List -->
        <div class="file-list">
          <div class="file-list-header">
            <h3 class="font-medium text-slate-700">文件列表</h3>
          </div>
          <ul class="file-list-items">
            <li
              v-for="letter in letters"
              :key="letter.id"
              @click="selectLetter(letter.id)"
              :class="[
                'file-list-item',
                selectedLetter?.id === letter.id ? 'file-list-item--active' : ''
              ]"
            >
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-700 truncate">{{ letter.filename }}</p>
                <span :class="getStatusClass(letter.status)">
                  {{ getStatusText(letter.status) }}
                </span>
              </div>
              <button
                @click.stop="handleDelete(letter.id)"
                class="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
              >
                <Trash2 class="w-4 h-4" />
              </button>
              <button
                v-if="letter.status === 'pending' || letter.status === 'failed'"
                @click.stop="handleRecognizeOne(letter.id)"
                class="p-1.5 text-slate-400 hover:text-emerald-600 transition-colors"
              >
                <RefreshCcw class="w-4 h-4" />
              </button>
            </li>
            <li v-if="letters.length === 0" class="file-list-empty">
              暂无询证函记录
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Recognition Result -->
      <div class="page-right-col">
        <div class="content-card-header">
          <h3 class="content-card-title">识别结果</h3>
          <div v-if="selectedLetter" class="flex items-center gap-2">
            <span :class="getStatusClass(selectedLetter.status)">
              {{ getStatusText(selectedLetter.status) }}
            </span>
          </div>
        </div>

        <div v-if="selectedLetter && selectedLetter.recognition" class="p-4 flex-1 overflow-auto">
          <!-- 原文预览 -->
          <div v-if="previewUrl" class="border-b border-slate-100 bg-slate-50 mb-4">
            <div class="p-3">
              <p class="text-xs font-medium text-slate-500 mb-2">原文预览</p>
              <div class="file-preview-container">
                <iframe :src="previewUrl + '#toolbar=0'" class="file-preview-iframe" />
              </div>
            </div>
          </div>
          <!-- Format Check Banner -->
          <div
            class="info-section"
            :class="selectedLetter.recognition.format_check_passed ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'"
          >
            <p class="info-section-title">
              格式类型：{{ selectedLetter.recognition.format_type || 'unknown' }}
            </p>
            <p class="text-xs mt-1" :class="selectedLetter.recognition.format_check_passed ? 'text-emerald-700' : 'text-amber-700'">
              {{ selectedLetter.recognition.format_check_passed ? '格式校验通过' : '格式存在不一致项' }}
            </p>
            <ul
              v-if="selectedLetter.recognition.format_mismatches && selectedLetter.recognition.format_mismatches.length > 0"
              class="mt-2 text-xs text-amber-800 space-y-1"
            >
              <li v-for="(m, idx) in selectedLetter.recognition.format_mismatches" :key="idx">
                [{{ m.item }}] 期望: {{ m.expected }} | 实际: {{ m.actual }}
              </li>
            </ul>
          </div>

          <!-- Summary Card -->
          <div class="info-section">
            <div class="flex items-center gap-2 mb-4">
              <FileText class="w-5 h-5 text-emerald-500" />
              <h3 class="info-section-title">询证函信息</h3>
            </div>

            <div class="result-grid">
              <div v-for="field in displayFields" :key="field.key" class="result-field">
                <p class="result-field-label">{{ field.label }}</p>
                <p class="result-field-value">{{ getFieldValue(field.key) }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Pending/Processing State -->
        <div v-else-if="selectedLetter && (selectedLetter.status === 'processing' || selectedLetter.status === 'pending')" class="flex-1 flex items-center justify-center text-slate-400">
          <p v-if="selectedLetter.status === 'processing'" class="animate-pulse">正在识别中，请稍候...</p>
          <p v-else>待识别，请点击"开始识别"按钮</p>
        </div>

        <!-- No File Selected -->
        <div v-else class="flex-1 flex items-center justify-center text-slate-400">
          请选择一个询证函查看识别结果
        </div>
      </div>
    </main>
  </div>
</template>
