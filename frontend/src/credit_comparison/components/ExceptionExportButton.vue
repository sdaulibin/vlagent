<script setup>
import { computed, ref } from "vue";
import { Download, Loader2 } from "lucide-vue-next";
import { api } from "../../api";

const props = defineProps({
  batchId: {
    type: String,
    default: "",
  },
  wordFileName: {
    type: String,
    default: "",
  },
  excelFileName: {
    type: String,
    default: "",
  },
});

const loading = ref(false);

const disabled = computed(() => !String(props.batchId || "").trim() || !String(props.wordFileName || "").trim());

function resolveFileName(headers) {
  const disposition = String(headers["content-disposition"] || "");
  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch {
      return encodedMatch[1];
    }
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (plainMatch?.[1]) {
    return plainMatch[1];
  }
  const sourceName = String(props.wordFileName || "异常记录").trim().replace(/\.[^.]+$/, "");
  return `${sourceName || "异常记录"}_异常记录.xlsx`;
}

function triggerDownload(blob, fileName) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

async function handleDownload() {
  if (disabled.value || loading.value) {
    return;
  }
  loading.value = true;
  try {
    const params = new URLSearchParams({
      word_file_name: String(props.wordFileName || ""),
    });
    if (String(props.excelFileName || "").trim()) {
      params.set("excel_file_name", String(props.excelFileName));
    }
    // 宿主 api 实例已注入 token 并统一错误处理；以 blob 方式接收 xlsx。
    const response = await api.get(
      `/credit-comparison/batches/${encodeURIComponent(props.batchId)}/exceptions/export`,
      { params: Object.fromEntries(params), responseType: "blob" },
    );
    triggerDownload(response.data, resolveFileName(response.headers));
  } catch (error) {
    const detail = error?.response?.data;
    let message = "异常记录下载失败";
    if (detail instanceof Blob) {
      try {
        message = JSON.parse(await detail.text())?.detail || message;
      } catch {
        // 非 JSON 错误体，保留默认提示。
      }
    } else if (detail?.detail) {
      message = detail.detail;
    }
    alert(message);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <button
    class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-blue-600 border border-blue-200 bg-blue-50 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mr-2"
    :disabled="disabled || loading"
    @click="handleDownload"
  >
    <Loader2 v-if="loading" class="w-3.5 h-3.5 animate-spin" />
    <Download v-else class="w-3.5 h-3.5" />
    下载异常记录
  </button>
</template>
