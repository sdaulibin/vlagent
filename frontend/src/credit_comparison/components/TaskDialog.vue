<script setup>
import { reactive, watch } from "vue";
import { FileText, FileSpreadsheet, CheckCircle2, X } from "lucide-vue-next";

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue", "submit"]);

const form = reactive({
  wordFile: null,
  excelFile: null,
});

function resetForm() {
  form.wordFile = null;
  form.excelFile = null;
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      resetForm();
    }
  },
);

function closeDialog() {
  emit("update:modelValue", false);
}

function handleWordChange(event) {
  const file = event.target.files?.[0];
  form.wordFile = file || null;
  // 重置 input，使同名文件能再次触发 change
  event.target.value = "";
}

function handleExcelChange(event) {
  const file = event.target.files?.[0];
  form.excelFile = file || null;
  event.target.value = "";
}

function submitForm() {
  if (!form.wordFile || !form.excelFile) {
    return;
  }
  emit("submit", {
    wordFile: form.wordFile,
    excelFile: form.excelFile,
  });
  closeDialog();
}
</script>

<template>
  <div
    v-if="modelValue"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    @click.self="closeDialog"
  >
    <div class="w-[92%] max-w-[720px] max-h-[88vh] flex flex-col bg-white rounded-xl shadow-2xl">
      <!-- header -->
      <div class="flex items-center justify-between px-5 py-4 border-b border-slate-100">
        <h3 class="text-base font-semibold text-slate-800">新建项目</h3>
        <button class="p-1 rounded-md hover:bg-slate-100" @click="closeDialog">
          <X class="w-4 h-4 text-slate-400" />
        </button>
      </div>

      <!-- body -->
      <div class="px-5 py-4 overflow-y-auto flex-1">
        <div class="mb-4 px-4 py-3 border border-blue-100 rounded-lg bg-gradient-to-b from-white to-blue-50/40 text-sm text-slate-500 leading-relaxed">
          上传需要复核的 Word 文件及对应的 Excel 文件。
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Word 上传 -->
          <div class="flex flex-col">
            <label class="block mb-2 text-sm font-semibold text-slate-700">Word 文件</label>
            <label
              class="flex flex-col items-center justify-center gap-2 px-4 py-8 min-h-[192px] border border-dashed rounded-xl cursor-pointer transition-colors hover:border-blue-400 hover:bg-blue-50/50"
              :class="form.wordFile ? 'border-blue-400 bg-blue-50/40' : 'border-slate-300'"
            >
              <div class="flex items-center justify-center w-12 h-12 rounded-xl" :class="form.wordFile ? 'bg-blue-100 text-blue-600' : 'bg-blue-50 text-blue-500'">
                <FileText class="w-6 h-6" />
              </div>
              <div class="text-sm font-medium text-slate-700">点击上传 Word 文件</div>
              <div class="text-xs text-slate-400">支持 .doc、.docx 格式</div>
              <div v-if="form.wordFile" class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-xs">
                <CheckCircle2 class="w-3.5 h-3.5" />
                <span class="max-w-[200px] truncate">{{ form.wordFile.name }}</span>
              </div>
              <input type="file" accept=".doc,.docx" class="hidden" @change="handleWordChange" />
            </label>
          </div>

          <!-- Excel 上传 -->
          <div class="flex flex-col">
            <label class="block mb-2 text-sm font-semibold text-slate-700">Excel 文件</label>
            <label
              class="flex flex-col items-center justify-center gap-2 px-4 py-8 min-h-[192px] border border-dashed rounded-xl cursor-pointer transition-colors hover:border-emerald-400 hover:bg-emerald-50/50"
              :class="form.excelFile ? 'border-emerald-400 bg-emerald-50/40' : 'border-slate-300'"
            >
              <div class="flex items-center justify-center w-12 h-12 rounded-xl" :class="form.excelFile ? 'bg-emerald-100 text-emerald-600' : 'bg-emerald-50 text-emerald-500'">
                <FileSpreadsheet class="w-6 h-6" />
              </div>
              <div class="text-sm font-medium text-slate-700">点击上传 Excel 文件</div>
              <div class="text-xs text-slate-400">支持 .xls、.xlsx 格式</div>
              <div v-if="form.excelFile" class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs">
                <CheckCircle2 class="w-3.5 h-3.5" />
                <span class="max-w-[200px] truncate">{{ form.excelFile.name }}</span>
              </div>
              <input type="file" accept=".xls,.xlsx,.csv" class="hidden" @change="handleExcelChange" />
            </label>
          </div>
        </div>
      </div>

      <!-- footer -->
      <div class="flex justify-end gap-3 px-5 py-4 border-t border-slate-100">
        <button class="px-4 py-2 h-10 text-sm rounded-lg text-slate-600 hover:bg-slate-100 transition-colors" @click="closeDialog">取消</button>
        <button
          class="px-4 py-2 h-10 text-sm rounded-lg text-white bg-blue-600 hover:bg-blue-700 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          :disabled="!form.wordFile || !form.excelFile"
          @click="submitForm"
        >
          新建并处理
        </button>
      </div>
    </div>
  </div>
</template>
