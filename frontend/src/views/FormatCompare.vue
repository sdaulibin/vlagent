<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import {
  ArrowLeft,
  Upload,
  FileSearch,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Eye,
  ChevronDown,
  ChevronRight,
} from "lucide-vue-next";
import { useRouter } from "vue-router";
import {
  uploadFormatCompare,
  getFormatCompareTasks,
  getFormatCompareTask,
  deleteFormatCompareTask,
  getFormatCompareFileUrl,
  getFormatCompareTemplateUrl,
  getFormatCompareTemplates,
} from "../api";

interface MismatchItem {
  section: string;
  item: string;
  location: string;
  expected: string;
  actual: string;
  severity: string;
}

interface CompareTask {
  id: number;
  filename: string;
  format_type: string | null;
  status: string;
  passed: boolean | null;
  mismatches: MismatchItem[];
  extracted_content: any[] | null;
  template_content: any[] | null;
  error_msg: string | null;
  duration_ms: number | null;
  created_at: string;
}

interface TemplateInfo {
  format_key: string;
  format_name: string;
  pdf_filename: string;
}

const router = useRouter();
const tasks = ref<CompareTask[]>([]);
const selectedTask = ref<CompareTask | null>(null);
const templates = ref<TemplateInfo[]>([]);
const isUploading = ref(false);

const formatTypeLabels: Record<string, string> = {
  format_1: "格式一（银行询证函）",
  format_2: "格式二（银行询证函）",
  capital_verification: "验资询证函",
  unknown: "未知格式",
};

const loadTasks = async () => {
  try {
    tasks.value = await getFormatCompareTasks();
  } catch (e) {
    console.error("加载比对任务列表失败", e);
  }
};

const loadTemplates = async () => {
  try {
    templates.value = await getFormatCompareTemplates();
  } catch (e) {
    console.error("加载模板列表失败", e);
  }
};

const selectTask = async (id: number) => {
  try {
    selectedTask.value = await getFormatCompareTask(id);
  } catch (e) {
    console.error("加载比对详情失败", e);
  }
};

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const files = target.files;
  if (!files || files.length === 0) return;

  isUploading.value = true;
  try {
    for (const file of Array.from(files)) {
      const result = await uploadFormatCompare(file);
      selectedTask.value = result;
    }
    await loadTasks();
  } catch (e) {
    console.error("上传比对失败", e);
  } finally {
    isUploading.value = false;
    target.value = "";
  }
};

const handleDelete = async (id: number) => {
  if (!confirm("确定要删除这条比对记录吗？")) return;
  try {
    await deleteFormatCompareTask(id);
    if (selectedTask.value?.id === id) {
      selectedTask.value = null;
    }
    await loadTasks();
  } catch (e) {
    console.error("删除失败", e);
  }
};

const goBack = () => router.push("/");

const openUploadedFile = () => {
  if (!selectedTask.value) return;
  window.open(getFormatCompareFileUrl(selectedTask.value.id), "_blank");
};

const openTemplateFile = (formatKey: string) => {
  window.open(getFormatCompareTemplateUrl(formatKey), "_blank");
};

const getSeverityClass = (severity: string) => {
  switch (severity) {
    case "high":
      return "border-red-300 bg-red-50 text-red-800";
    case "medium":
      return "border-amber-300 bg-amber-50 text-amber-800";
    case "low":
      return "border-blue-300 bg-blue-50 text-blue-800";
    default:
      return "border-slate-300 bg-slate-50 text-slate-800";
  }
};

const getSeverityLabel = (severity: string) => {
  switch (severity) {
    case "high":
      return "严重";
    case "medium":
      return "中等";
    case "low":
      return "提示";
    default:
      return severity;
  }
};

const highCount = computed(
  () =>
    selectedTask.value?.mismatches.filter((m) => m.severity === "high")
      .length ?? 0,
);
const mediumCount = computed(
  () =>
    selectedTask.value?.mismatches.filter((m) => m.severity === "medium")
      .length ?? 0,
);
const lowCount = computed(
  () =>
    selectedTask.value?.mismatches.filter((m) => m.severity === "low").length ??
    0,
);

// 从 content item 中提取表头列表（支持嵌套字典）
const flattenHeaders = (headers: any[]): string[] => {
  if (!headers) return [];
  const result: string[] = [];
  for (const h of headers) {
    if (typeof h === "string") {
      result.push(h);
    } else if (typeof h === "object") {
      for (const key in h) {
        result.push(key);
        if (Array.isArray(h[key])) {
          result.push(...h[key]);
        }
      }
    }
  }
  return result;
};

// 检查某个 section 是否有差异
const sectionHasMismatch = (sectionName: string): boolean => {
  if (!selectedTask.value?.mismatches) return false;
  return selectedTask.value.mismatches.some(
    (m) => m.section === sectionName || m.item.includes(sectionName),
  );
};

// 检查某个表头是否有差异
const headerHasMismatch = (
  sectionName: string,
  headerName: string,
): boolean => {
  if (!selectedTask.value?.mismatches) return false;
  return selectedTask.value.mismatches.some(
    (m) =>
      m.section === sectionName &&
      m.location === "table_field" &&
      (m.expected === headerName || m.actual === headerName),
  );
};

onMounted(() => {
  loadTasks();
  loadTemplates();
});
</script>

<template>
  <div class="min-h-screen p-4 md:p-8 flex flex-col">
    <!-- Header -->
    <header class="w-full max-w-[1600px] mx-auto mb-6">
      <button
        @click="goBack"
        class="flex items-center gap-2 text-slate-500 hover:text-slate-700 mb-4"
      >
        <ArrowLeft class="w-5 h-5" />
        返回首页
      </button>
      <div class="flex items-center gap-3">
        <div class="bg-indigo-600 p-3 rounded-xl shadow-lg">
          <FileSearch class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="text-2xl font-bold text-slate-900">询证函格式比对</h1>
          <p class="text-sm text-slate-500">
            上传询证函，与标准模板比对格式差异
          </p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main
      class="w-full max-w-[1600px] mx-auto grid grid-cols-1 md:grid-cols-12 gap-6 flex-1"
    >
      <!-- Left: Upload + Task List -->
      <div class="md:col-span-2 flex flex-col gap-4">
        <!-- Upload -->
        <label
          class="flex items-center justify-center gap-2 bg-white border-2 border-dashed border-slate-300 hover:border-indigo-400 rounded-xl p-4 cursor-pointer transition-colors"
        >
          <Upload class="w-5 h-5 text-slate-400" />
          <span class="text-slate-600">{{
            isUploading ? "比对中..." : "上传 PDF"
          }}</span>
          <input
            type="file"
            accept=".pdf"
            multiple
            class="hidden"
            @change="handleFileUpload"
            :disabled="isUploading"
          />
        </label>

        <!-- Template Links -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-3">
          <h3 class="text-sm font-medium text-slate-700 mb-2">模板预览</h3>
          <div class="space-y-1">
            <button
              v-for="t in templates"
              :key="t.format_key"
              @click="openTemplateFile(t.format_key)"
              class="w-full text-left text-sm text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded px-2 py-1.5 transition-colors flex items-center gap-1.5"
            >
              <Eye class="w-3.5 h-3.5" />
              {{ t.format_name }}
            </button>
          </div>
        </div>

        <!-- Task List -->
        <div
          class="bg-white rounded-xl shadow-sm border border-slate-200 flex-1 overflow-auto"
        >
          <div class="p-3 border-b border-slate-100">
            <h3 class="font-medium text-slate-700">比对记录</h3>
          </div>
          <ul class="divide-y divide-slate-100">
            <li
              v-for="task in tasks"
              :key="task.id"
              @click="selectTask(task.id)"
              :class="[
                'p-3 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors',
                selectedTask?.id === task.id ? 'bg-indigo-50' : '',
              ]"
            >
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-700 truncate">
                  {{ task.filename }}
                </p>
                <div class="flex items-center gap-1.5 mt-1">
                  <AlertTriangle
                    v-if="task.status === 'failed'"
                    class="w-3.5 h-3.5 text-amber-500"
                  />
                  <CheckCircle2
                    v-else-if="task.passed === true"
                    class="w-3.5 h-3.5 text-green-500"
                  />
                  <XCircle
                    v-else-if="task.passed === false"
                    class="w-3.5 h-3.5 text-red-500"
                  />
                  <span class="text-xs text-slate-500">
                    {{
                      task.status === "failed"
                        ? "比对失败"
                        : task.status === "processing"
                          ? "比对中..."
                          : task.passed === true
                            ? "格式一致"
                            : task.passed === false
                              ? "存在差异"
                              : "待比对"
                    }}
                  </span>
                </div>
              </div>
              <button
                @click.stop="handleDelete(task.id)"
                class="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </li>
            <li
              v-if="tasks.length === 0"
              class="p-4 text-center text-slate-400 text-sm"
            >
              暂无比对记录
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: Compare Result -->
      <div class="md:col-span-10 flex flex-col gap-4">
        <template v-if="selectedTask">
          <!-- Status Banner: Failed -->
          <div
            v-if="selectedTask.status === 'failed'"
            class="rounded-xl p-4 border bg-amber-50 border-amber-200"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <AlertTriangle class="w-5 h-5 text-amber-600" />
                <span class="font-medium text-amber-800">比对失败</span>
              </div>
              <span
                v-if="selectedTask.duration_ms"
                class="text-sm text-slate-400"
                >耗时 {{ (selectedTask.duration_ms / 1000).toFixed(1) }}s</span
              >
            </div>
            <p
              v-if="selectedTask.error_msg"
              class="mt-2 text-sm text-amber-700"
            >
              {{ selectedTask.error_msg }}
            </p>
          </div>

          <!-- Status Banner: Success / Differences -->
          <div
            v-else
            class="rounded-xl p-4 border"
            :class="
              selectedTask.passed
                ? 'bg-green-50 border-green-200'
                : 'bg-red-50 border-red-200'
            "
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <CheckCircle2
                  v-if="selectedTask.passed"
                  class="w-5 h-5 text-green-600"
                />
                <XCircle v-else class="w-5 h-5 text-red-600" />
                <span
                  class="font-medium"
                  :class="
                    selectedTask.passed ? 'text-green-800' : 'text-red-800'
                  "
                >
                  {{ selectedTask.passed ? "格式比对通过" : "格式存在差异" }}
                </span>
              </div>
              <div class="flex items-center gap-3 text-sm">
                <span class="text-slate-600"
                  >格式：{{
                    formatTypeLabels[selectedTask.format_type || ""] ||
                    selectedTask.format_type ||
                    "未知"
                  }}</span
                >
                <span v-if="selectedTask.duration_ms" class="text-slate-400"
                  >耗时
                  {{ (selectedTask.duration_ms / 1000).toFixed(1) }}s</span
                >
              </div>
            </div>
            <!-- Mismatch Summary -->
            <div
              v-if="!selectedTask.passed && selectedTask.mismatches.length > 0"
              class="mt-2 flex gap-3 text-sm"
            >
              <span v-if="highCount > 0" class="text-red-700"
                >🔴 严重 {{ highCount }} 项</span
              >
              <span v-if="mediumCount > 0" class="text-amber-700"
                >🟡 中等 {{ mediumCount }} 项</span
              >
              <span v-if="lowCount > 0" class="text-blue-700"
                >🔵 提示 {{ lowCount }} 项</span
              >
            </div>
          </div>

          <!-- ===== 上方区域：PDF 预览 ===== -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Template PDF Preview -->
            <div
              class="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col"
            >
              <div
                class="p-3 border-b border-slate-100 flex items-center justify-between"
              >
                <h3 class="font-medium text-slate-700 text-sm">
                  📄 模板：{{
                    formatTypeLabels[selectedTask.format_type || ""] ||
                    "标准模板"
                  }}
                </h3>
              </div>
              <div class="flex-1 min-h-[350px]">
                <iframe
                  v-if="
                    selectedTask.format_type &&
                    selectedTask.format_type !== 'unknown'
                  "
                  :src="getFormatCompareTemplateUrl(selectedTask.format_type)"
                  class="w-full h-full min-h-[350px] rounded-b-xl"
                />
                <div
                  v-else
                  class="flex items-center justify-center h-full text-slate-400 text-sm"
                >
                  未能识别格式类型，无法显示模板
                </div>
              </div>
            </div>

            <!-- Uploaded File Preview -->
            <div
              class="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col"
            >
              <div
                class="p-3 border-b border-slate-100 flex items-center justify-between"
              >
                <h3 class="font-medium text-slate-700 text-sm">
                  📄 上传文件：{{ selectedTask.filename }}
                </h3>
                <button
                  @click="openUploadedFile"
                  class="text-xs text-indigo-600 hover:text-indigo-800"
                >
                  新窗口打开
                </button>
              </div>
              <div class="flex-1 min-h-[350px]">
                <iframe
                  :src="getFormatCompareFileUrl(selectedTask.id)"
                  class="w-full h-full min-h-[350px] rounded-b-xl"
                />
              </div>
            </div>
          </div>

          <!-- ===== 下方区域：结构化内容对比 ===== -->
          <div
            v-if="
              selectedTask.template_content || selectedTask.extracted_content
            "
            class="grid grid-cols-1 md:grid-cols-2 gap-4"
          >
            <!-- 模板结构化内容 -->
            <div class="bg-white rounded-xl shadow-sm border border-slate-200">
              <div class="p-3 border-b border-slate-100">
                <h3 class="font-medium text-slate-700 text-sm">
                  📋 模板结构内容
                </h3>
              </div>
              <div class="p-3 space-y-3 max-h-[500px] overflow-auto">
                <div
                  v-for="(item, idx) in selectedTask.template_content || []"
                  :key="'tpl-' + idx"
                  class="border rounded-lg p-3"
                  :class="
                    sectionHasMismatch(item.section)
                      ? 'border-red-200 bg-red-50/30'
                      : 'border-slate-200'
                  "
                >
                  <div class="flex items-center gap-2 mb-2">
                    <span class="text-xs font-mono text-slate-400">{{
                      idx + 1
                    }}</span>
                    <span class="text-sm font-medium text-slate-800">{{
                      item.section
                    }}</span>
                  </div>
                  <!-- Table Headers -->
                  <div
                    v-if="item.table_headers && item.table_headers.length > 0"
                    class="flex flex-wrap gap-1.5 mb-2"
                  >
                    <span
                      v-for="(h, hi) in flattenHeaders(item.table_headers)"
                      :key="'tpl-h-' + hi"
                      class="text-xs px-2 py-0.5 rounded-full"
                      :class="
                        headerHasMismatch(item.section, h)
                          ? 'bg-red-100 text-red-700 border border-red-300'
                          : 'bg-indigo-50 text-indigo-700'
                      "
                    >
                      {{ h }}
                    </span>
                  </div>
                  <!-- Description -->
                  <p
                    v-if="item.description"
                    class="text-xs text-slate-500 italic"
                  >
                    {{ item.description }}
                  </p>
                  <!-- Subsections -->
                  <div
                    v-if="item.subsections"
                    class="mt-2 space-y-2 pl-3 border-l-2 border-slate-200"
                  >
                    <div
                      v-for="(sub, si) in item.subsections"
                      :key="'tpl-sub-' + si"
                      class="text-sm"
                    >
                      <p class="text-slate-700 font-medium text-xs">
                        {{ sub.subsection }}
                      </p>
                      <div
                        v-if="sub.table_headers"
                        class="flex flex-wrap gap-1 mt-1"
                      >
                        <span
                          v-for="(sh, shi) in flattenHeaders(sub.table_headers)"
                          :key="'tpl-sh-' + shi"
                          class="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700"
                        >
                          {{ sh }}
                        </span>
                      </div>
                      <p
                        v-if="sub.description"
                        class="text-xs text-slate-500 italic mt-1"
                      >
                        {{ sub.description }}
                      </p>
                    </div>
                  </div>
                </div>
                <div
                  v-if="
                    !selectedTask.template_content ||
                    selectedTask.template_content.length === 0
                  "
                  class="text-center text-slate-400 text-sm py-8"
                >
                  无模板内容
                </div>
              </div>
            </div>

            <!-- AI 提取的结构化内容 -->
            <div class="bg-white rounded-xl shadow-sm border border-slate-200">
              <div class="p-3 border-b border-slate-100">
                <h3 class="font-medium text-slate-700 text-sm">
                  🔍 AI 提取内容
                </h3>
              </div>
              <div class="p-3 space-y-3 max-h-[500px] overflow-auto">
                <div
                  v-for="(item, idx) in selectedTask.extracted_content || []"
                  :key="'ext-' + idx"
                  class="border rounded-lg p-3"
                  :class="
                    sectionHasMismatch(item.section)
                      ? 'border-red-200 bg-red-50/30'
                      : 'border-slate-200'
                  "
                >
                  <div class="flex items-center gap-2 mb-2">
                    <span class="text-xs font-mono text-slate-400">{{
                      idx + 1
                    }}</span>
                    <span class="text-sm font-medium text-slate-800">{{
                      item.section
                    }}</span>
                  </div>
                  <!-- Table Headers -->
                  <div
                    v-if="item.table_headers && item.table_headers.length > 0"
                    class="flex flex-wrap gap-1.5 mb-2"
                  >
                    <span
                      v-for="(h, hi) in flattenHeaders(item.table_headers)"
                      :key="'ext-h-' + hi"
                      class="text-xs px-2 py-0.5 rounded-full"
                      :class="
                        headerHasMismatch(item.section, h)
                          ? 'bg-red-100 text-red-700 border border-red-300'
                          : 'bg-emerald-50 text-emerald-700'
                      "
                    >
                      {{ h }}
                    </span>
                  </div>
                  <!-- Description -->
                  <p
                    v-if="item.description"
                    class="text-xs text-slate-500 italic"
                  >
                    {{ item.description }}
                  </p>
                  <!-- Subsections -->
                  <div
                    v-if="item.subsections"
                    class="mt-2 space-y-2 pl-3 border-l-2 border-slate-200"
                  >
                    <div
                      v-for="(sub, si) in item.subsections"
                      :key="'ext-sub-' + si"
                      class="text-sm"
                    >
                      <p class="text-slate-700 font-medium text-xs">
                        {{ sub.subsection }}
                      </p>
                      <div
                        v-if="sub.table_headers"
                        class="flex flex-wrap gap-1 mt-1"
                      >
                        <span
                          v-for="(sh, shi) in flattenHeaders(sub.table_headers)"
                          :key="'ext-sh-' + shi"
                          class="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700"
                        >
                          {{ sh }}
                        </span>
                      </div>
                      <p
                        v-if="sub.description"
                        class="text-xs text-slate-500 italic mt-1"
                      >
                        {{ sub.description }}
                      </p>
                    </div>
                  </div>
                </div>
                <div
                  v-if="
                    !selectedTask.extracted_content ||
                    selectedTask.extracted_content.length === 0
                  "
                  class="text-center text-slate-400 text-sm py-8"
                >
                  无提取内容
                </div>
              </div>
            </div>
          </div>

          <!-- ===== 差异详情 ===== -->
          <div
            v-if="selectedTask.mismatches && selectedTask.mismatches.length > 0"
            class="bg-white rounded-xl shadow-sm border border-slate-200"
          >
            <div class="p-3 border-b border-slate-100">
              <h3 class="font-medium text-slate-700">
                ⚠️ 差异详情（{{ selectedTask.mismatches.length }} 项）
              </h3>
            </div>
            <div class="divide-y divide-slate-100">
              <div
                v-for="(m, idx) in selectedTask.mismatches"
                :key="idx"
                :class="['p-3 border-l-4', getSeverityClass(m.severity)]"
              >
                <div class="flex items-center gap-2 mb-1">
                  <span
                    class="text-xs font-medium px-1.5 py-0.5 rounded"
                    :class="
                      m.severity === 'high'
                        ? 'bg-red-200 text-red-800'
                        : m.severity === 'medium'
                          ? 'bg-amber-200 text-amber-800'
                          : 'bg-blue-200 text-blue-800'
                    "
                  >
                    {{ getSeverityLabel(m.severity) }}
                  </span>
                  <span class="text-sm font-medium text-slate-800">{{
                    m.item
                  }}</span>
                </div>
                <div class="grid grid-cols-2 gap-2 text-sm mt-1">
                  <div>
                    <span class="text-slate-500">模板要求：</span>
                    <span class="text-slate-700">{{ m.expected }}</span>
                  </div>
                  <div>
                    <span class="text-slate-500">实际内容：</span>
                    <span class="text-red-700 font-medium">{{ m.actual }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div
          v-else
          class="flex-1 flex items-center justify-center text-slate-400 bg-white rounded-xl shadow-sm border border-slate-200 min-h-[400px]"
        >
          上传询证函 PDF 进行格式比对，或选择已有比对记录查看结果
        </div>
      </div>
    </main>
  </div>
</template>
