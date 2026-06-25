<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, FileDiff, FileText, Play, Loader2, Trash2, Eye } from 'lucide-vue-next';
import {
  compareFinancialReports,
  getFinancialCompareList,
  getFinancialCompareDetail,
  getFinancialCompareStatus,
  deleteFinancialCompareTask,
  getFinancialCompareFile,
} from '../api';
import type { FinancialCompareTask, DiffRecord, ScrollLinkMode } from '../types';
import DocumentPane from '../components/DocumentPane.vue';
import DiffList from '../components/DiffList.vue';
import DiffConnector from '../components/DiffConnector.vue';
import type { PaneConnectorApi } from '../components/DiffConnector.vue';

const router = useRouter();

const activeView = ref<'upload' | 'result'>('upload');
const isSubmitting = ref(false);

// Upload state
const docxFile = ref<File | null>(null);
const pdfFile = ref<File | null>(null);
const docxStartPage = ref(1);
const docxEndPage = ref<number | null>(null);
const pdfStartPage = ref(1);
const pdfEndPage = ref<number | null>(null);

// History state
const historyList = ref<FinancialCompareTask[]>([]);
const pollingTimers = new Map<number, ReturnType<typeof setInterval>>();

const hasProcessingTasks = computed(() =>
  historyList.value.some((t) => t.status === 'processing' || t.status === 'pending'),
);

// Result state（查看历史任务时填充）
const taskDetail = ref<FinancialCompareTask | null>(null);
const fileA = ref<File | null>(null);
const fileB = ref<File | null>(null);
const diffDetails = ref<DiffRecord[]>([]);
const selectedDiffIndex = ref<number | null>(null);
const scrollLinkMode = ref<ScrollLinkMode>('independent');
const syncingScroll = ref(false);
const resultLoading = ref(false);

const viewerAreaRef = ref<HTMLElement | null>(null);
const paneARef = ref<PaneConnectorApi | null>(null);
const paneBRef = ref<PaneConnectorApi | null>(null);
const connectorRef = ref<InstanceType<typeof DiffConnector> | null>(null);

const parsedDiffStats = computed<Record<string, number> | null>(() => {
  if (!taskDetail.value?.diff_stats) return null;
  try {
    return JSON.parse(taskDetail.value.diff_stats);
  } catch {
    return null;
  }
});

const selectedDiff = computed<DiffRecord | null>(() => {
  if (selectedDiffIndex.value === null) return null;
  return diffDetails.value[selectedDiffIndex.value] ?? null;
});

// ---- Upload handlers ----
function onDocxChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) docxFile.value = f;
}
function onPdfChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) pdfFile.value = f;
}

// ---- History ----
async function loadHistory() {
  try {
    historyList.value = await getFinancialCompareList();
  } catch (e) {
    console.error('Failed to load history:', e);
  }
}

function startPolling(taskId: number) {
  stopPolling(taskId);
  const timer = setInterval(async () => {
    try {
      const status = await getFinancialCompareStatus(taskId);
      if (status.status === 'done' || status.status === 'failed') {
        stopPolling(taskId);
        await loadHistory();
      }
    } catch (e) {
      console.error('Polling error:', e);
    }
  }, 3000);
  pollingTimers.set(taskId, timer);
}

function stopPolling(taskId?: number) {
  if (taskId !== undefined) {
    const timer = pollingTimers.get(taskId);
    if (timer) {
      clearInterval(timer);
      pollingTimers.delete(taskId);
    }
  } else {
    pollingTimers.forEach((timer) => clearInterval(timer));
    pollingTimers.clear();
  }
}

// ---- Actions ----
async function startCompare() {
  if (!docxFile.value || !pdfFile.value) {
    ElMessage.warning('请上传基准文档（DOCX）和年度报告（PDF）');
    return;
  }
  isSubmitting.value = true;
  try {
    const result = await compareFinancialReports(
      docxFile.value,
      pdfFile.value,
      docxStartPage.value,
      docxEndPage.value,
      pdfStartPage.value,
      pdfEndPage.value,
    );
    const taskId = result.task_id;

    historyList.value.unshift({
      id: taskId,
      docx_file_name: docxFile.value.name,
      pdf_file_name: pdfFile.value.name,
      docx_start_page: docxStartPage.value,
      docx_end_page: docxEndPage.value,
      pdf_start_page: pdfStartPage.value,
      pdf_end_page: pdfEndPage.value,
      status: 'processing',
      error_msg: null,
      duration: null,
      diff_stats: null,
      diff_blocks: null,
      created_at: new Date().toISOString(),
    });

    docxFile.value = null;
    pdfFile.value = null;

    startPolling(taskId);
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '比对失败，请重试');
  } finally {
    isSubmitting.value = false;
  }
}

async function viewHistoryTask(task: FinancialCompareTask) {
  if (task.status === 'processing' || task.status === 'pending') return;
  if (task.status === 'failed') {
    try {
      const detail = await getFinancialCompareDetail(task.id);
      ElMessage.error(`比对失败: ${detail.error_msg || '未知错误'}`);
    } catch (e) {
      console.error('Failed to load task:', e);
    }
    return;
  }
  // done → 加载结果
  resultLoading.value = true;
  activeView.value = 'result';
  try {
    const detail = await getFinancialCompareDetail(task.id);
    taskDetail.value = detail;
    diffDetails.value = [];
    selectedDiffIndex.value = null;
    // 解析 diff 记录
    if (detail.diff_blocks) {
      try {
        diffDetails.value = JSON.parse(detail.diff_blocks) as DiffRecord[];
      } catch {
        diffDetails.value = [];
      }
    }
    // 下载文件 blob → 构造 File 传给 DocumentPane
    const [docxBlob, pdfBlob] = await Promise.all([
      getFinancialCompareFile(task.id, 'docx'),
      getFinancialCompareFile(task.id, 'pdf'),
    ]);
    fileA.value = new File([docxBlob], detail.docx_file_name, { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    fileB.value = new File([pdfBlob], detail.pdf_file_name, { type: 'application/pdf' });
  } catch (e) {
    console.error('Failed to load result:', e);
    ElMessage.error('加载比对结果失败');
  } finally {
    resultLoading.value = false;
  }
}

async function handleDeleteTask(taskId: number) {
  try {
    stopPolling(taskId);
    await deleteFinancialCompareTask(taskId);
    await loadHistory();
  } catch (e) {
    console.error('Failed to delete task:', e);
  }
}

function goBack() {
  if (activeView.value === 'result') {
    activeView.value = 'upload';
    taskDetail.value = null;
    fileA.value = null;
    fileB.value = null;
    diffDetails.value = [];
  } else {
    router.push('/');
  }
}

function formatTime(isoStr: string) {
  const d = new Date(isoStr);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

// ---- Diff interaction ----
function handleDiffSelect(index: number) {
  selectedDiffIndex.value = index;
}

function handleHighlightsUpdated() {
  void connectorRef.value?.rebindListeners?.();
}

function handlePaneScroll(source: 'A' | 'B', ratio: number) {
  connectorRef.value?.scheduleUpdate?.();
  if (scrollLinkMode.value !== 'sync' || syncingScroll.value) return;
  const target = source === 'A' ? paneBRef.value : paneARef.value;
  if (!target) return;
  syncingScroll.value = true;
  target.setScrollRatio(ratio);
  requestAnimationFrame(() => {
    syncingScroll.value = false;
  });
}

watch(
  () => selectedDiff.value?.diff_id ?? null,
  () => {
    window.setTimeout(() => {
      void connectorRef.value?.updateConnector();
    }, 350);
  },
);

onMounted(() => {
  loadHistory();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Upload / List View -->
    <div v-if="activeView === 'upload'" class="min-h-screen flex flex-col p-8">
      <div class="w-full max-w-7xl mx-auto mb-6">
        <button @click="goBack" class="page-back-btn">
          <ArrowLeft class="w-5 h-5" />
          返回首页
        </button>
        <div class="page-title-group">
          <div class="fc-logo">
            <FileDiff class="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 class="page-title">财务报告比对</h1>
            <p class="page-subtitle">基于结构化 LLM 比对引擎，精确识别简繁年报之间的语义差异</p>
          </div>
        </div>
      </div>

      <div class="flex-1 flex gap-8 max-w-7xl mx-auto w-full">
        <!-- Left: Upload -->
        <div class="shrink-0" style="width: 360px;">
          <div class="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 space-y-3">
            <label class="upload-zone" :class="{ 'border-emerald-300 bg-emerald-50': docxFile }">
              <FileText class="w-5 h-5 text-slate-400" />
              <span v-if="!docxFile" class="text-slate-600">点击上传基准文档（DOCX）</span>
              <span v-else class="text-emerald-700 font-medium truncate">{{ docxFile.name }}</span>
              <input type="file" accept=".docx" class="hidden" @change="onDocxChange" />
            </label>

            <label class="upload-zone" :class="{ 'border-emerald-300 bg-emerald-50': pdfFile }">
              <FileDiff class="w-5 h-5 text-slate-400" />
              <span v-if="!pdfFile" class="text-slate-600">点击上传年度报告（PDF）</span>
              <span v-else class="text-emerald-700 font-medium truncate">{{ pdfFile.name }}</span>
              <input type="file" accept=".pdf" class="hidden" @change="onPdfChange" />
            </label>

            <!-- 页码范围 -->
            <div class="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-2">
              <div class="text-xs text-slate-500 font-medium">DOCX 页码范围</div>
              <div class="flex items-center gap-3">
                <div class="flex items-center gap-1.5">
                  <span class="text-xs text-slate-500">起始页</span>
                  <input v-model.number="docxStartPage" type="number" min="1"
                    class="w-16 px-2 py-1 border border-slate-200 rounded text-sm text-center focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-200" />
                </div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs text-slate-500">结束页</span>
                  <input v-model.number="docxEndPage" type="number" min="1"
                    class="w-16 px-2 py-1 border border-slate-200 rounded text-sm text-center focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-200"
                    placeholder="末尾" />
                </div>
              </div>
              <div class="text-xs text-slate-500 font-medium pt-1">PDF 页码范围</div>
              <div class="flex items-center gap-3">
                <div class="flex items-center gap-1.5">
                  <span class="text-xs text-slate-500">起始页</span>
                  <input v-model.number="pdfStartPage" type="number" min="1"
                    class="w-16 px-2 py-1 border border-slate-200 rounded text-sm text-center focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-200" />
                </div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs text-slate-500">结束页</span>
                  <input v-model.number="pdfEndPage" type="number" min="1"
                    class="w-16 px-2 py-1 border border-slate-200 rounded text-sm text-center focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-200"
                    placeholder="末尾" />
                </div>
              </div>
              <p class="text-[10px] text-slate-400">留空结束页则比对到文档末尾</p>
            </div>

            <button
              @click="startCompare"
              :disabled="!docxFile || !pdfFile || isSubmitting"
              class="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-white text-sm font-medium transition-colors"
              :class="docxFile && pdfFile && !isSubmitting
                ? 'bg-teal-600 hover:bg-teal-700 cursor-pointer'
                : 'bg-slate-300 cursor-not-allowed'"
            >
              <Loader2 v-if="isSubmitting" :size="16" class="animate-spin" />
              <Play v-else :size="16" />
              {{ isSubmitting ? '提交中...' : '开始比对' }}
            </button>
          </div>
        </div>

        <!-- Right: History List -->
        <div class="flex-1 bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col overflow-hidden">
          <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 class="text-base font-semibold text-slate-700">比对列表</h2>
            <span v-if="hasProcessingTasks" class="flex items-center gap-1.5 text-xs text-blue-500">
              <Loader2 class="w-3.5 h-3.5 animate-spin" />
              比对进行中
            </span>
          </div>

          <div v-if="historyList.length === 0" class="flex-1 flex items-center justify-center text-slate-400 text-sm">
            暂无比对记录
          </div>

          <div v-else class="flex-1 overflow-y-auto p-3 space-y-2">
            <div
              v-for="task in historyList"
              :key="task.id"
              class="p-3 rounded-xl border transition-all group relative"
              :class="[
                task.status === 'done'
                  ? 'border-green-100 bg-green-50/30 hover:border-green-200 hover:shadow-sm cursor-pointer'
                  : task.status === 'processing'
                    ? 'border-blue-100 bg-blue-50/30'
                    : task.status === 'pending'
                      ? 'border-slate-200 bg-slate-50/50'
                      : 'border-red-100 bg-red-50/30'
              ]"
              @click="viewHistoryTask(task)"
            >
              <button
                @click.stop="handleDeleteTask(task.id)"
                class="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-50 text-slate-300 hover:text-red-500 transition-all"
              >
                <Trash2 class="w-4 h-4" />
              </button>

              <div class="flex items-center gap-2 mb-2">
                <span
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                  :class="{
                    'bg-green-50 text-green-600': task.status === 'done',
                    'bg-blue-50 text-blue-500': task.status === 'processing',
                    'bg-slate-50 text-slate-400': task.status === 'pending',
                    'bg-red-50 text-red-500': task.status === 'failed',
                  }"
                >
                  <Loader2 v-if="task.status === 'processing'" class="w-3 h-3 animate-spin" />
                  {{ { done: '比对完成', processing: '比对中', pending: '等待中', failed: '比对失败' }[task.status] }}
                </span>
                <span class="text-xs text-slate-400">{{ formatTime(task.created_at) }}</span>
                <span v-if="task.duration" class="text-xs text-slate-400">{{ task.duration.toFixed(1) }}s</span>
              </div>

              <p class="text-sm text-slate-700 truncate" :title="task.docx_file_name">{{ task.docx_file_name }}</p>
              <p class="text-xs text-slate-400 mt-0.5">vs</p>
              <p class="text-sm text-slate-700 truncate" :title="task.pdf_file_name">{{ task.pdf_file_name }}</p>

              <div class="mt-1.5 flex items-center gap-2 text-xs text-slate-400">
                <span>DOCX 第{{ task.docx_start_page }}页起</span>
                <span>PDF 第{{ task.pdf_start_page }}页起</span>
              </div>

              <div
                v-if="task.status === 'done'"
                class="mt-2 flex items-center gap-1 text-xs font-medium text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Eye class="w-3.5 h-3.5" />
                查看比对结果
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Result View: 完全照参考项目的 app-shell 布局 -->
    <div v-else-if="activeView === 'result' && taskDetail" class="app-shell">
      <header class="app-header">
        <button @click="goBack" class="flex items-center gap-1 text-slate-500 hover:text-slate-700 text-sm shrink-0">
          <ArrowLeft class="w-4 h-4" /> 返回
        </button>
        <div class="doc-header-names">
          <span class="doc-header-item doc-header-a">{{ taskDetail.docx_file_name }}</span>
          <span class="doc-header-sep">vs</span>
          <span class="doc-header-item doc-header-b">{{ taskDetail.pdf_file_name }}</span>
        </div>
        <div class="task-status-bar">
          <el-tag v-if="parsedDiffStats" size="small" type="danger">{{ parsedDiffStats.total_diffs || 0 }} 处差异</el-tag>
          <el-tag v-if="taskDetail.duration" size="small" type="info">{{ taskDetail.duration.toFixed(1) }}s</el-tag>
        </div>
        <div class="scroll-mode-controls">
          <span class="scroll-mode-label">滚动模式</span>
          <el-radio-group v-model="scrollLinkMode" size="default">
            <el-radio-button value="independent">独立模式</el-radio-button>
            <el-radio-button value="sync">对照模式</el-radio-button>
          </el-radio-group>
        </div>
      </header>

      <main class="main-layout">
        <!-- Loading -->
        <div v-if="resultLoading" class="flex-1 flex items-center justify-center">
          <Loader2 class="w-8 h-8 text-teal-500 animate-spin" />
        </div>

        <template v-else>
          <div ref="viewerAreaRef" class="viewer-area">
            <section class="viewer-col">
              <DocumentPane
                ref="paneARef"
                :title="taskDetail.docx_file_name"
                side="A"
                :file="fileA"
                :diffs="diffDetails"
                :active-diff="selectedDiff"
                @highlights-updated="handleHighlightsUpdated"
                @scroll="(ratio: number) => handlePaneScroll('A', ratio)"
              />
            </section>
            <section class="viewer-col">
              <DocumentPane
                ref="paneBRef"
                :title="taskDetail.pdf_file_name"
                side="B"
                :file="fileB"
                :diffs="diffDetails"
                :active-diff="selectedDiff"
                @highlights-updated="handleHighlightsUpdated"
                @scroll="(ratio: number) => handlePaneScroll('B', ratio)"
              />
            </section>
            <DiffConnector
              ref="connectorRef"
              :active-diff="selectedDiff"
              :pane-a="paneARef"
              :pane-b="paneBRef"
              :container-el="viewerAreaRef"
              :scroll-link-mode="scrollLinkMode"
            />
          </div>

          <section class="diff-panel">
            <div class="diff-panel-head">
              <h3>差异列表</h3>
              <el-tag v-if="diffDetails.length" size="small">{{ diffDetails.length }} 条</el-tag>
            </div>
            <DiffList
              horizontal
              :items="diffDetails"
              :active-index="selectedDiffIndex"
              @select="handleDiffSelect"
            />
          </section>
        </template>
      </main>
    </div>
  </div>
</template>
