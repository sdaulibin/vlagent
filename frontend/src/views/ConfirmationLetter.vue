<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { FileText, ArrowLeft, Play, Save, Trash2, Upload } from 'lucide-vue-next';
import { useRouter } from 'vue-router';
import {
  uploadConfirmationLetter,
  getConfirmationLetters,
  getConfirmationLetter,
  recognizeConfirmationLetter,
  updateConfirmationLetter,
  deleteConfirmationLetter
} from '../api';

interface ConfirmationLetterItem {
  id: number;
  filename: string;
  status: string;
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
  recognition_duration: number | null;
}

const router = useRouter();
const letters = ref<ConfirmationLetterItem[]>([]);
const selectedLetter = ref<ConfirmationLetterItem | null>(null);
const isUploading = ref(false);
const isRecognizing = ref(false);
const isSaving = ref(false);

// 表单字段定义
const formFields = [
  { key: 'confirmation_no', label: '函证编号' },
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
];

// 编辑表单数据
const formData = ref<Record<string, string>>({});

const hasPendingLetters = computed(() => {
  return letters.value.some(l => l.status === 'pending');
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
    const letter = await getConfirmationLetter(id);
    selectedLetter.value = letter;
    // 初始化表单数据
    formData.value = {};
    formFields.forEach(f => {
      formData.value[f.key] = letter[f.key as keyof ConfirmationLetterItem] as string || '';
    });
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
    target.value = ''; // 重置 input
  }
};

const handleStartRecognition = async () => {
  const pendingLetters = letters.value.filter(l => l.status === 'pending');
  if (pendingLetters.length === 0) return;

  isRecognizing.value = true;
  try {
    for (const letter of pendingLetters) {
      await recognizeConfirmationLetter(letter.id);
    }
    await loadLetters();
    // 自动选中第一个已完成的
    const doneLetter = letters.value.find(l => l.status === 'done');
    if (doneLetter) {
      await selectLetter(doneLetter.id);
    }
  } catch (e) {
    console.error("识别失败", e);
  } finally {
    isRecognizing.value = false;
  }
};

const handleSave = async () => {
  if (!selectedLetter.value) return;

  isSaving.value = true;
  try {
    await updateConfirmationLetter(selectedLetter.value.id, formData.value);
    await selectLetter(selectedLetter.value.id);
  } catch (e) {
    console.error("保存失败", e);
  } finally {
    isSaving.value = false;
  }
};

const handleDelete = async (id: number) => {
  if (!confirm('确定要删除这条询证函记录吗？')) return;

  try {
    await deleteConfirmationLetter(id);
    if (selectedLetter.value?.id === id) {
      selectedLetter.value = null;
      formData.value = {};
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
    case 'pending': return 'bg-yellow-100 text-yellow-700';
    case 'processing': return 'bg-blue-100 text-blue-700';
    case 'done': return 'bg-green-100 text-green-700';
    case 'failed': return 'bg-red-100 text-red-700';
    default: return 'bg-gray-100 text-gray-700';
  }
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
          <p class="text-sm text-slate-500">智能识别银行询证函关键字段，支持人工修正</p>
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
          :disabled="isRecognizing || !hasPendingLetters"
          class="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white py-3 px-4 rounded-xl font-medium shadow-lg hover:from-emerald-600 hover:to-emerald-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play class="w-5 h-5" />
          {{ isRecognizing ? '识别中...' : (hasPendingLetters ? '开始识别' : '暂无待识别文件') }}
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
            </li>
            <li v-if="letters.length === 0" class="p-4 text-center text-slate-400 text-sm">
              暂无询证函记录
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Recognition Result Form -->
      <div class="md:col-span-8 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col">
        <div class="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 class="font-medium text-slate-700">识别结果</h3>
          <button
            v-if="selectedLetter"
            @click="handleSave"
            :disabled="isSaving"
            class="flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-sm px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          >
            <Save class="w-4 h-4" />
            {{ isSaving ? '保存中...' : '保存修改' }}
          </button>
        </div>

        <div v-if="selectedLetter" class="p-4 flex-1 overflow-auto">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div v-for="field in formFields" :key="field.key" class="flex flex-col gap-1">
              <label class="text-sm font-medium text-slate-600">{{ field.label }}</label>
              <input
                v-model="formData[field.key]"
                type="text"
                class="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                :placeholder="`请输入${field.label}`"
              />
            </div>
          </div>
        </div>

        <div v-else class="flex-1 flex items-center justify-center text-slate-400">
          请选择一个询证函查看识别结果
        </div>
      </div>
    </main>
  </div>
</template>
