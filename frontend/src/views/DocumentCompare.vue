<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, FileDiff } from 'lucide-vue-next';
import {
  compareDocuments,
  getDocumentTasks,
  getDocumentTask,
  getDocumentTaskStatus,
  deleteDocumentTask,
} from '../api';
import type { TaskItem, TaskDetail } from '../types';
import DocumentUpload from '../components/DocumentUpload.vue';
import DocumentHistory from '../components/DocumentHistory.vue';
import DocumentResultView from '../components/DocumentResultView.vue';

const router = useRouter();

const activeView = ref<'upload' | 'result'>('upload');
const isProcessing = ref(false);
const fileA = ref<File | null>(null);
const fileB = ref<File | null>(null);
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null);

const historyList = ref<TaskItem[]>([]);
const taskDetail = ref<TaskDetail | null>(null);

const loadHistory = async () => {
  try {
    historyList.value = await getDocumentTasks();
  } catch (e) {
    console.error('Failed to load history:', e);
  }
};

const startPolling = (taskId: number) => {
  stopPolling();
  pollTimer.value = setInterval(async () => {
    try {
      const status = await getDocumentTaskStatus(taskId);
      if (status.status === 'done') {
        stopPolling();
        taskDetail.value = await getDocumentTask(taskId);
        isProcessing.value = false;
        await loadHistory();
      } else if (status.status === 'failed') {
        stopPolling();
        isProcessing.value = false;
        taskDetail.value = await getDocumentTask(taskId);
        alert(`比对失败: ${status.error_msg || '未知错误'}`);
        await loadHistory();
      }
    } catch (e) {
      console.error('Polling error:', e);
    }
  }, 3000);
};

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
};

const startCompare = async () => {
  if (!fileA.value || !fileB.value) {
    alert('请上传两份文档');
    return;
  }

  isProcessing.value = true;

  try {
    const result = await compareDocuments(fileA.value, fileB.value);
    const taskId = result.task_id;

    // 立即构建一个初始 taskDetail 用于展示加载状态
    taskDetail.value = {
      id: taskId,
      file_a_name: fileA.value.name,
      file_b_name: fileB.value.name,
      file_a_page_count: null,
      file_b_page_count: null,
      status: 'processing',
      error_msg: null,
      comparison_duration: null,
      created_at: new Date().toISOString(),
      pages: [],
    };
    activeView.value = 'result';
    startPolling(taskId);
  } catch (error: any) {
    isProcessing.value = false;
    alert(error.response?.data?.detail || '比对失败，请重试');
  }
};

const viewHistoryTask = async (task: TaskItem) => {
  try {
    taskDetail.value = await getDocumentTask(task.id);
    activeView.value = 'result';
  } catch (e) {
    console.error('Failed to load task:', e);
  }
};

const handleDeleteTask = async (taskId: number) => {
  if (!confirm('确定要删除这个比对任务吗？')) return;
  try {
    await deleteDocumentTask(taskId);
    await loadHistory();
  } catch (e) {
    console.error('Failed to delete task:', e);
  }
};

const goBack = () => {
  if (activeView.value === 'result') {
    activeView.value = 'upload';
    taskDetail.value = null;
    stopPolling();
  } else {
    router.push('/');
  }
};

onMounted(() => {
  loadHistory();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Upload View -->
    <div v-if="activeView === 'upload'" class="min-h-screen flex flex-col p-8">
      <div class="w-full max-w-7xl mx-auto mb-6">
        <button @click="goBack" class="page-back-btn">
          <ArrowLeft class="w-5 h-5" />
          返回首页
        </button>
        <div class="page-title-group">
          <div class="document-logo">
            <FileDiff class="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 class="page-title">文档比对</h1>
            <p class="page-subtitle">上传两份文档以自动识别差异，支持 PDF 和 Word 格式</p>
          </div>
        </div>
      </div>

      <div class="flex-1 flex gap-8">
        <DocumentUpload
          :fileA="fileA"
          :fileB="fileB"
          :isProcessing="isProcessing"
          @update:fileA="fileA = $event"
          @update:fileB="fileB = $event"
          @compare="startCompare"
        />

        <DocumentHistory
          :historyList="historyList"
          @view="viewHistoryTask"
          @delete="handleDeleteTask"
        />
      </div>
    </div>

    <!-- Result View -->
    <DocumentResultView
      v-else-if="taskDetail"
      :taskId="taskDetail.id"
      :fileAName="taskDetail.file_a_name"
      :fileBName="taskDetail.file_b_name"
      :fileAPageCount="taskDetail.file_a_page_count"
      :fileBPageCount="taskDetail.file_b_page_count"
      :status="taskDetail.status"
      :errorMsg="taskDetail.error_msg"
      :comparisonDuration="taskDetail.comparison_duration"
      :pages="taskDetail.pages"
      @back="goBack"
    />
  </div>
</template>
