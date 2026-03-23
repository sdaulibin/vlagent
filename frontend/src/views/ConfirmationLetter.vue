<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { FileText, ArrowLeft, Play, Trash2, Upload, RefreshCcw, ExternalLink } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import {
  uploadConfirmationLetter,
  getConfirmationLetters,
  getConfirmationLetter,
  recognizeConfirmationLetter,
  deleteConfirmationLetter,
  getConfirmationPreviewUrl
} from '../api';

interface FormatMismatch {
  item: string;
  expected: string;
  actual: string;
  severity: string;
}

interface RecognitionData {
  confirmation_no: string;
  accounting_firm: string;
  reply_address: string;
  contact_person: string;
  phone: string;
  postal_code: string;
  debit_account: string;
  cutoff_date: string;
  start_date: string;
  end_date: string;
  seal_date: string;
  seal_name: string;
  signature_name: string;
  recipient_bank: string;
  format_type?: string;
  format_check_passed?: boolean;
  format_mismatches?: FormatMismatch[];
}

interface ConfirmationLetterItem {
  id: number;
  filename: string;
  status: string;
  recognition: RecognitionData | null;
  recognition_duration: number | null;
}

const router = useRouter();
const letters = ref<ConfirmationLetterItem[]>([]);
const selectedLetter = ref<ConfirmationLetterItem | null>(null);
const isUploading = ref(false);
const isRecognizing = ref(false);

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

const hasRetryableLetters = computed(() => {
  return letters.value.some(l => l.status === 'pending' || l.status === 'failed');
});

const loadLetters = async () => {
  try {
    letters.value = await getConfirmationLetters();
  } catch (e) {
    console.error("加载询证函列表失败", e);
  }
};

const selectLetter = async (id: number) => {
  try {
    selectedLetter.value = await getConfirmationLetter(id);
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
    const doneLetter = letters.value.find(l => l.status === 'done');
    if (doneLetter) {
      await selectLetter(doneLetter.id);
    }
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
    }
    await loadLetters();
  } catch (e) {
    console.error("删除失败", e);
  }
};

const goBack = () => {
  router.push('/');
};

const openPreview = () => {
  if (!selectedLetter.value) return;
  const url = getConfirmationPreviewUrl(selectedLetter.value.id);
  window.open(url, '_blank');
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
    case 'processing': return 'bg-blue-100 text-blue-700';
    case 'done': return 'bg-green-100 text-green-700';
    case 'failed': return 'bg-red-100 text-red-700';
    default: return 'bg-gray-100 text-gray-700';
  }
};

const getFieldValue = (key: string): string => {
  const recognition = selectedLetter.value?.recognition;
  if (!recognition) return '-';
  return (recognition as any)[key] || '-';
};

onMounted(() => {
  loadLetters();
});
</script>

<template>
  <div class="min-h-screen p-4 md:p-8 flex flex-col">
    <!-- Header -->
    <header class="w-full max-w-6xl mx-auto mb-6">
      <button @click="goBack" class="flex items-center gap-2 text-slate-500 hover:text-slate-700 mb-4">
        <ArrowLeft class="w-5 h-5" />
        返回首页
      </button>
      <div class="flex items-center gap-3">
        <div class="bg-emerald-600 p-3 rounded-xl shadow-lg">
          <FileText class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="text-2xl font-bold text-slate-900">询证函智能识别</h1>
          <p class="text-sm text-slate-500">智能识别银行询证函关键字段</p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="w-full max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-6 flex-1">
      <!-- Left: File List -->
      <div class="md:col-span-4 flex flex-col gap-4">
        <!-- Upload -->
        <label class="flex items-center justify-center gap-2 bg-white border-2 border-dashed border-slate-300 hover:border-emerald-400 rounded-xl p-4 cursor-pointer transition-colors">
          <Upload class="w-5 h-5 text-slate-400" />
          <span class="text-slate-600">{{ isUploading ? '上传中...' : '点击上传询证函 PDF' }}</span>
          <input type="file" accept=".pdf" multiple class="hidden" @change="handleFileUpload" :disabled="isUploading" />
        </label>

        <!-- Start Recognition -->
        <button
          @click="handleStartRecognition"
          :disabled="isRecognizing || !hasRetryableLetters"
          class="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white py-3 px-4 rounded-xl font-medium shadow-lg hover:from-emerald-600 hover:to-emerald-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play class="w-5 h-5" />
          {{ isRecognizing ? '识别中...' : (hasRetryableLetters ? '开始识别/重试失败' : '暂无可识别文件') }}
        </button>

        <!-- File List -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 flex-1 overflow-auto">
          <div class="p-3 border-b border-slate-100">
            <h3 class="font-medium text-slate-700">文件列表</h3>
          </div>
          <ul class="divide-y divide-slate-100">
            <li
              v-for="letter in letters"
              :key="letter.id"
              @click="selectLetter(letter.id)"
              :class="[
                'p-3 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors',
                selectedLetter?.id === letter.id ? 'bg-emerald-50' : ''
              ]"
            >
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-700 truncate">{{ letter.filename }}</p>
                <span :class="['text-xs px-2 py-0.5 rounded-full', getStatusClass(letter.status)]">
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
            <li v-if="letters.length === 0" class="p-4 text-center text-slate-400 text-sm">
              暂无询证函记录
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Recognition Result -->
      <div class="md:col-span-8 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col">
        <div class="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 class="font-medium text-slate-700">识别结果</h3>
          <div v-if="selectedLetter" class="flex items-center gap-2">
            <span :class="['text-xs px-2 py-0.5 rounded-full', getStatusClass(selectedLetter.status)]">
              {{ getStatusText(selectedLetter.status) }}
            </span>
            <button
              @click="openPreview"
              class="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm px-3 py-1.5 rounded-lg transition-colors"
            >
              <ExternalLink class="w-4 h-4" />
              预览原文
            </button>
          </div>
        </div>

        <div v-if="selectedLetter && selectedLetter.recognition" class="p-4 flex-1 overflow-auto">
          <!-- Format Check Banner -->
          <div
            class="mb-4 p-3 rounded-lg border"
            :class="selectedLetter.recognition.format_check_passed ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'"
          >
            <p class="text-sm font-medium text-slate-700">
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
          <div class="bg-white border border-slate-200 rounded-xl p-4">
            <div class="flex items-center gap-2 mb-4">
              <FileText class="w-5 h-5 text-emerald-500" />
              <h3 class="font-semibold text-gray-700">询证函信息</h3>
            </div>

            <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div v-for="field in displayFields" :key="field.key" class="py-2 px-3 bg-gray-50 rounded-lg">
                <p class="text-xs text-gray-400 mb-1">{{ field.label }}</p>
                <p class="text-sm font-medium text-gray-700">{{ getFieldValue(field.key) }}</p>
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
