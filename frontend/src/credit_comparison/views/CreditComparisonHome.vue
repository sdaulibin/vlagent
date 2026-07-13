<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { Trash2, Eye, Loader2, Plus, Search, Scale, ArrowLeft } from "lucide-vue-next";
import { useRouter } from "vue-router";

import { createTaskItem, deleteTaskItem, listTaskItems } from "../api/view";
import FormatGuideEntry from "../components/FormatGuideEntry.vue";
import TaskDialog from "../components/TaskDialog.vue";

const router = useRouter();
const keyword = ref("");
const dialogVisible = ref(false);
const loading = ref(false);
const tasks = ref([]);
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const actionBatchId = ref("");
let pollTimer = null;

const totalPages = computed(() => {
  const size = Math.max(1, Number(pageSize.value || 10));
  const count = Math.max(0, Number(total.value || 0));
  return Math.max(1, Math.ceil(count / size));
});

const visiblePages = computed(() => {
  const current = Math.max(1, Number(page.value || 1));
  const last = totalPages.value;
  const span = 2;
  const start = Math.max(1, current - span);
  const end = Math.min(last, current + span);
  const pages = [];
  for (let i = start; i <= end; i += 1) {
    pages.push(i);
  }
  return pages;
});

function isTaskActiveStatus(status) {
  return status === "待处理" || status === "处理中";
}

function openCreateDialog() {
  dialogVisible.value = true;
}

async function loadTasks() {
  loading.value = true;
  try {
    const data = await listTaskItems({
      page: page.value,
      pageSize: pageSize.value,
      keyword: keyword.value,
    });
    tasks.value = data.items;
    total.value = data.total;
    page.value = data.page;
    pageSize.value = data.pageSize;
  } catch (error) {
    alert(error instanceof Error ? error.message : "任务列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function refreshTasks() {
  try {
    const data = await listTaskItems({
      page: page.value,
      pageSize: pageSize.value,
      keyword: keyword.value,
    });
    tasks.value = data.items;
    total.value = data.total;
    page.value = data.page;
    pageSize.value = data.pageSize;
  } catch (error) {
    console.error("刷新任务列表失败", error);
  }
}

function stopTaskPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function scheduleTaskPolling() {
  stopTaskPolling();
  if (!tasks.value.some((item) => isTaskActiveStatus(item.status))) {
    return;
  }
  pollTimer = window.setTimeout(async () => {
    await refreshTasks();
    scheduleTaskPolling();
  }, 2000);
}

async function handleSearch() {
  keyword.value = keyword.value.trim();
  page.value = 1;
  await loadTasks();
  scheduleTaskPolling();
}

async function handlePageChange(nextPage) {
  const targetPage = Math.max(1, Math.min(Number(nextPage || 1), totalPages.value));
  if (targetPage === page.value) {
    return;
  }
  page.value = targetPage;
  await loadTasks();
  scheduleTaskPolling();
}

async function handlePageSizeChange(nextPageSize) {
  pageSize.value = Math.max(1, Number(nextPageSize || 10));
  page.value = 1;
  await loadTasks();
  scheduleTaskPolling();
}

function goToDetail(task) {
  if (task.status !== "已完成") {
    alert("请先处理任务，再查看详情。");
    return;
  }
  router.push({
    name: "credit-comparison-detail",
    query: {
      batch_id: task.batchId,
      word_file_name: task.wordFileName,
      excel_file_name: task.excelFileName === "未匹配" ? "" : task.excelFileName,
    },
  });
}

async function handleCreateTask(payload) {
  loading.value = true;
  try {
    await createTaskItem(payload);
    page.value = 1;
    await refreshTasks();
    scheduleTaskPolling();
  } catch (error) {
    alert(error instanceof Error ? error.message : "项目创建或处理失败");
    await loadTasks();
  } finally {
    loading.value = false;
  }
}

async function handleDeleteTask(task) {
  if (!confirm(`确认删除任务 ${task.wordFileName} 吗？`)) {
    return;
  }
  actionBatchId.value = task.batchId;
  try {
    await deleteTaskItem(task.batchId);
    if (tasks.value.length === 1 && page.value > 1) {
      page.value -= 1;
    }
    await loadTasks();
    scheduleTaskPolling();
  } catch (error) {
    alert(error instanceof Error ? error.message : "删除任务失败");
  } finally {
    actionBatchId.value = "";
  }
}

function getStatusClass(status) {
  if (status === "已完成") return "status-badge status-badge--done";
  if (status === "处理中") return "status-badge status-badge--processing";
  if (status === "待处理") return "status-badge status-badge--pending";
  if (status === "处理失败") return "status-badge status-badge--failed";
  return "status-badge";
}

function backToHome() {
  router.push({ name: "Home" });
}

onMounted(() => {
  loadTasks().then(() => {
    scheduleTaskPolling();
  });
});

onUnmounted(() => {
  stopTaskPolling();
});
</script>

<template>
  <div class="page-container">
    <!-- header -->
    <div class="page-header">
      <button class="page-back-btn" @click="backToHome">
        <ArrowLeft class="w-4 h-4" />
        返回首页
      </button>
      <div class="page-title-group">
        <div class="page-icon bg-gradient-to-br from-emerald-500 to-teal-600">
          <Scale class="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 class="page-title">统计报送数据核对</h1>
          <p class="page-subtitle">Word 数据变动说明与 Excel 报表的跨源对账</p>
        </div>
      </div>
    </div>

    <!-- main -->
    <div class="w-full max-w-7xl mx-auto flex-1 flex flex-col gap-4">
      <!-- 工具栏 -->
      <div class="content-card">
        <div class="content-card-header">
          <div class="flex items-center gap-3 flex-1">
            <label class="text-sm text-slate-500">Word 文件</label>
            <input
              v-model="keyword"
              type="text"
              placeholder="按 Word 文件名搜索"
              class="flex-1 max-w-md px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
              @keyup.enter="handleSearch"
            />
            <button class="btn btn-primary inline-flex items-center gap-1.5" @click="handleSearch">
              <Search class="w-4 h-4" />
              搜索
            </button>
          </div>
          <div class="flex items-center gap-2">
            <FormatGuideEntry />
            <button class="btn btn-primary inline-flex items-center gap-1.5" @click="openCreateDialog">
              <Plus class="w-4 h-4" />
              新建对账
            </button>
          </div>
        </div>
      </div>

      <!-- 任务列表 -->
      <div class="content-card flex-1 flex flex-col">
        <div class="content-card-header">
          <h3 class="content-card-title">任务列表（{{ tasks.length }}）</h3>
        </div>

        <!-- loading -->
        <div v-if="loading && tasks.length === 0" class="loading-state">
          <Loader2 class="w-8 h-8 animate-spin text-rose-400" />
          <p class="text-sm text-slate-400">加载中...</p>
        </div>

        <div v-else-if="tasks.length === 0" class="empty-state">
          <p class="text-sm text-slate-400">暂无任务，点击"新建对账"上传文件</p>
        </div>

        <div v-else class="flex-1 overflow-auto custom-scrollbar">
          <table class="w-full text-sm border-collapse">
            <thead class="sticky top-0 z-10">
              <tr class="bg-slate-100 text-slate-600">
                <th class="px-4 py-3 text-left font-medium">Word 文件</th>
                <th class="px-4 py-3 text-left font-medium">Excel 文件</th>
                <th class="px-4 py-3 text-left font-medium">创建时间</th>
                <th class="px-4 py-3 text-center font-medium">关联/异常/未匹配</th>
                <th class="px-4 py-3 text-center font-medium">状态</th>
                <th class="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="task in tasks"
                :key="task.batchId"
                class="border-t border-slate-100 hover:bg-slate-50 transition-colors"
              >
                <td class="px-4 py-3 text-slate-700">{{ task.wordFileName }}</td>
                <td class="px-4 py-3 text-slate-500">{{ task.excelFileName }}</td>
                <td class="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">{{ task.createdAt }}</td>
                <td class="px-4 py-3 text-center text-xs text-slate-500">
                  <span class="text-slate-700">{{ task.linkCount }}</span>
                  /
                  <span :class="task.exceptionCount > 0 ? 'text-red-600 font-medium' : 'text-slate-400'">{{ task.exceptionCount }}</span>
                  /
                  <span :class="task.unmatchedCount > 0 ? 'text-amber-600' : 'text-slate-400'">{{ task.unmatchedCount }}</span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span :class="getStatusClass(task.status)">
                    <Loader2 v-if="task.status === '处理中' || task.status === '待处理'" class="w-3 h-3 inline animate-spin mr-0.5" />
                    {{ task.status }}
                  </span>
                  <p v-if="task.status === '处理失败' && task.errorMessage" class="mt-1 text-xs text-red-500 max-w-[200px] truncate" :title="task.errorMessage">{{ task.errorMessage }}</p>
                </td>
                <td class="px-4 py-3">
                  <div class="flex items-center justify-center gap-2">
                    <button
                      class="p-1.5 rounded-md text-slate-400 hover:text-blue-600 hover:bg-blue-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      :disabled="task.status !== '已完成'"
                      title="查看详情"
                      @click="goToDetail(task)"
                    >
                      <Eye class="w-4 h-4" />
                    </button>
                    <button
                      class="p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                      :disabled="actionBatchId === task.batchId"
                      title="删除"
                      @click="handleDeleteTask(task)"
                    >
                      <Loader2 v-if="actionBatchId === task.batchId" class="w-4 h-4 animate-spin" />
                      <Trash2 v-else class="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="total > 0" class="border-t border-slate-100 px-4 py-3 flex items-center justify-between gap-3">
          <div class="text-xs text-slate-500">共 {{ total }} 条，{{ totalPages }} 页</div>
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-2 text-xs text-slate-500">
              <span>每页</span>
              <select
                v-model.number="pageSize"
                class="px-2 py-1 border border-slate-200 rounded-md bg-white text-slate-700 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
                @change="handlePageSizeChange(pageSize)"
              >
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
              <span>条</span>
            </div>

            <div class="flex items-center gap-1">
              <button
                class="px-2 py-1 text-xs rounded-md border border-slate-200 text-slate-600 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                :disabled="page <= 1"
                @click="handlePageChange(page - 1)"
              >
                上一页
              </button>

              <button
                v-for="p in visiblePages"
                :key="p"
                class="min-w-[32px] px-2 py-1 text-xs rounded-md border border-slate-200 bg-white hover:bg-slate-50"
                :class="p === page ? 'text-blue-600 border-blue-300 bg-blue-50 hover:bg-blue-50' : 'text-slate-600'"
                @click="handlePageChange(p)"
              >
                {{ p }}
              </button>

              <button
                class="px-2 py-1 text-xs rounded-md border border-slate-200 text-slate-600 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                :disabled="page >= totalPages"
                @click="handlePageChange(page + 1)"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传弹窗 -->
    <TaskDialog v-model="dialogVisible" @submit="handleCreateTask" />
  </div>
</template>
