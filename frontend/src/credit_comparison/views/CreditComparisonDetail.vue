<script setup>
import { nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-vue-next";

import { getTaskDetail } from "../api/view";
import CompareWorkspace from "../components/CompareWorkspace.vue";
import ExceptionExportButton from "../components/ExceptionExportButton.vue";
import ExceptionSidebar from "../components/ExceptionSidebar.vue";

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const initialized = ref(false);
const detail = ref(null);
const workspaceRef = ref(null);
const exceptionSidebarRef = ref(null);
const activeExceptionItemKey = ref("");
const activeWordRecordId = ref(0);

function buildExceptionItemKey(item) {
  if (item?.itemKey) {
    return String(item.itemKey);
  }
  return `${item.id}-${item.wordRecordId}-${item.sheet}-${item.code}`;
}

async function loadDetail() {
  const batchId = String(route.query.batch_id || "");
  const wordFileName = String(route.query.word_file_name || "");
  const excelFileName = String(route.query.excel_file_name || "");

  if (!batchId || !wordFileName) {
    detail.value = null;
    initialized.value = true;
    return;
  }

  loading.value = true;
  initialized.value = false;
  detail.value = null;
  try {
    detail.value = await getTaskDetail(batchId, wordFileName, excelFileName);
    activeExceptionItemKey.value = "";
    activeWordRecordId.value = 0;
    await nextTick();
    exceptionSidebarRef.value?.resetExpandedGroups?.();
  } catch (error) {
    detail.value = null;
    alert(error instanceof Error ? error.message : "任务详情加载失败");
  } finally {
    loading.value = false;
    initialized.value = true;
  }
}

function backToHome() {
  router.push({ name: "credit-comparison" });
}

function handleSelectExceptionItem(item) {
  activeExceptionItemKey.value = buildExceptionItemKey(item);
  activeWordRecordId.value = Number(item.wordRecordId || 0);
  workspaceRef.value?.focusByExceptionItem(item);
}

function handleWorkspaceActiveRecordChange(payload) {
  activeWordRecordId.value = Number(payload?.wordRecordId || 0);
  if (activeWordRecordId.value <= 0) {
    return;
  }
  const wordRecordToken = String(activeWordRecordId.value);
  const wordRecordPattern = new RegExp(`(?:^|-)${wordRecordToken}(?:-|$)`);
  if (activeExceptionItemKey.value && !wordRecordPattern.test(activeExceptionItemKey.value)) {
    activeExceptionItemKey.value = "";
  }
}

watch(
  () => [route.query.batch_id, route.query.word_file_name, route.query.excel_file_name],
  () => {
    loadDetail();
  },
  { immediate: true },
);
</script>

<template>
  <div v-if="detail" class="min-h-screen flex flex-col bg-slate-50">
    <!-- 顶部栏 -->
    <header class="flex items-center px-5 py-3 bg-white border-b border-slate-200 shadow-sm">
      <div class="flex items-center gap-3">
        <button class="page-back-btn" @click="backToHome">
          <ArrowLeft class="w-4 h-4" />
          返回
        </button>
        <h1 class="text-base font-semibold text-slate-800">文件对比</h1>
        <span class="text-xs text-slate-400">{{ detail.wordFileName }}</span>
        <ExceptionExportButton
          :batch-id="detail.batchId"
          :word-file-name="detail.wordFileName"
          :excel-file-name="detail.excelFileName"
        />
      </div>
    </header>

    <!-- 主体：左异常侧栏 + 右工作台 -->
    <main class="flex-1 grid gap-3 p-4 min-h-0" style="grid-template-columns: 286px minmax(0, 1fr); width: 100%; height: calc(100vh - 96px);">
      <aside class="flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden min-h-0" style="height: calc(100vh - 96px); max-height: calc(100vh - 96px);">
        <ExceptionSidebar
          ref="exceptionSidebarRef"
          :groups="detail.exceptionGroups"
          :active-item-key="activeExceptionItemKey"
          :active-word-record-id="activeWordRecordId"
          @select-item="handleSelectExceptionItem"
        />
      </aside>

      <section class="flex flex-col min-w-0 min-h-0">
        <CompareWorkspace
          ref="workspaceRef"
          :detail="detail"
          @active-record-change="handleWorkspaceActiveRecordChange"
        />
      </section>
    </main>
  </div>

  <!-- loading -->
  <div v-else-if="loading || !initialized" class="min-h-screen flex flex-col items-center justify-center gap-3 bg-slate-50">
    <Loader2 class="w-10 h-10 animate-spin text-rose-400" />
    <p class="text-sm text-slate-400">加载任务详情...</p>
  </div>

  <!-- 空状态 -->
  <div v-else class="min-h-screen flex flex-col items-center justify-center gap-4 bg-slate-50">
    <AlertTriangle class="w-12 h-12 text-amber-400" />
    <div class="text-center">
      <p class="text-base font-medium text-slate-700">未找到任务详情</p>
      <p class="text-sm text-slate-400 mt-1">请返回列表重新选择任务</p>
    </div>
    <button class="btn btn-primary" @click="backToHome">返回列表</button>
  </div>
</template>
