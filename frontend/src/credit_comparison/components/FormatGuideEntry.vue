<script setup>
import { computed, ref } from "vue";
import { FileText, X } from "lucide-vue-next";

const visible = ref(false);

const formatGuideMarkdown = `
# 比对格式说明

## Word 文件要求

- 支持 \`.doc\`、\`.docx\`。
- 文档格式需严格按照推荐写法进行。
- 单独一行提供”表单“标识，格式建议为 \`A3301表单：\`。
- 单独一行提供”币种“标识，格式建议为 \`外币/本外币（这行可为空）\`。
- 正文段落按指标分类，每个指标一段，格式为 \`（1）“指标代码 + 指标名称”本期增加/减少 xx 元\`。
- 如果有原因拆分，补充“\`主要是XX公司增加/减少XXX元，XXX公司增加/减少XXX元。\`”等说明。

### 推荐写法

\`\`\`text
A3301表单：
外币/本外币（这行可为空）
（1）“A330101 利息收入”本期增加/减少123.45 万元，主要是公司贷款利息收入增加XXX元，XXX公司增加/减少XXX元。
\`\`\`

## Excel 文件要求

- 支持 \`.xls\` 或 \`.xlsx\`。
- excel的第一张表单命名方式若为 字母+数据，则后续表单名称若只有数字会自动读取第一张表单名称的字母，将字母与数字合并。
- 表头必须按 \`指标代码\`、\`指标名称\`、\`本期\`、\`上期数据\`这四列顺序排列。
- 其中本期/上期数据列可以包含\`人民币\`、\`本外币\`、\`美元合计\`，每个数据项可以包括\`余额\`、\`发生额\`。
- 余额发生额的单位默认为万元
- \`人民币\`、\`本外币\`、\`美元合计\`及其对应的\`余额\`、\`发生额\`字段均为可选项，无需全部提供，顺序可以任意。

### 表头写法

下面示例表格展示了多级表头的结构示例（其中：\`人民币\`、\`本外币\`、\`美元合计\`及其对应的\`余额\`、\`发生额\`字段均为可选项，无需全部提供，顺序可以任意）。

`;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  return escapeHtml(text).replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdown(markdown) {
  const lines = String(markdown).trim().split("\n");
  const html = [];
  let inList = false;
  let inCode = false;
  const codeBuffer = [];

  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };

  const closeCode = () => {
    if (inCode) {
      html.push(`<pre class="format-guide-code"><code>${escapeHtml(codeBuffer.join("\n"))}</code></pre>`);
      codeBuffer.length = 0;
      inCode = false;
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      closeList();
      if (inCode) {
        closeCode();
      } else {
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeBuffer.push(line);
      continue;
    }

    if (!trimmed) {
      closeList();
      continue;
    }

    if (trimmed.startsWith("### ")) {
      closeList();
      html.push(`<h3>${renderInlineMarkdown(trimmed.slice(4))}</h3>`);
      continue;
    }

    if (trimmed.startsWith("## ")) {
      closeList();
      html.push(`<h2>${renderInlineMarkdown(trimmed.slice(3))}</h2>`);
      continue;
    }

    if (trimmed.startsWith("# ")) {
      closeList();
      html.push(`<h1>${renderInlineMarkdown(trimmed.slice(2))}</h1>`);
      continue;
    }

    if (trimmed.startsWith("- ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${renderInlineMarkdown(trimmed.slice(2))}</li>`);
      continue;
    }

    closeList();
    html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  }

  closeCode();
  closeList();
  return html.join("");
}

const formatGuideHtml = computed(() => renderMarkdown(formatGuideMarkdown));
</script>

<template>
  <div class="format-guide-entry inline-flex items-center">
    <button
      type="button"
      class="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg border border-slate-200 bg-white transition-colors"
      title="查看操作指引与格式说明"
      aria-label="查看操作指引与格式说明"
      @click="visible = true"
    >
      <FileText class="w-3.5 h-3.5" />
      操作指引
    </button>

    <div v-if="visible" class="guide-modal-overlay" @click.self="visible = false">
      <div class="guide-modal">
        <div class="guide-modal-header">
          <h3>比对格式说明</h3>
          <button class="guide-modal-close" @click="visible = false"><X class="w-4 h-4" /></button>
        </div>
        <div class="guide-modal-body">
          <div class="dialog-tip">上传前可先核对文件结构，说明内容和当前解析规则保持一致。</div>
          <div class="format-guide-markdown" v-html="formatGuideHtml"></div>
          <div class="format-guide-table-block">
        <div class="format-guide-table-title">Excel 表头示例</div>
        <div class="format-guide-table-scroll">
          <table class="format-guide-table">
            <thead>
              <tr>
                <th rowspan="3">指标代码</th>
                <th rowspan="3">指标名称</th>
                <th colspan="6">本期</th>
                <th colspan="6">上期数据</th>
              </tr>
              <tr>
                <th colspan="2">人民币</th>
                <th colspan="2">本外币</th>
                <th colspan="2">美元合计</th>
                <th colspan="2">人民币</th>
                <th colspan="2">本外币</th>
                <th colspan="2">美元合计</th>
              </tr>
              <tr>
                <th>余额</th>
                <th>发生额</th>
                <th>余额</th>
                <th>发生额</th>
                <th>余额</th>
                <th>发生额</th>
                <th>余额</th>
                <th>发生额</th>
                <th>余额</th>
                <th>发生额</th>
                <th>余额</th>
                <th>发生额</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>XXX</td>
                <td>XXX</td>
                <td>123.45</td>
                <td>12.34</td>
                <td>123.45</td>
                <td>12.34</td>
                <td>123.45</td>
                <td>12.34</td>
                <td>120.00</td>
                <td>10.00</td>
                <td>120.00</td>
                <td>10.00</td>
                <td>120.00</td>
                <td>10.00</td>
              </tr>
              <tr>
                <td>XXX</td>
                <td>XXX</td>
                <td>98.76</td>
                <td>8.76</td>
                <td>98.76</td>
                <td>8.76</td>
                <td>98.76</td>
                <td>8.76</td>
                <td>88.00</td>
                <td>6.00</td>
                <td>88.00</td>
                <td>6.00</td>
                <td>88.00</td>
                <td>6.00</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.format-guide-entry {
  display: inline-flex;
  align-items: center;
}

/* 手写弹窗（替代 el-dialog） */
.guide-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
}

.guide-modal {
  width: 92%;
  max-width: 760px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.16);
  overflow: hidden;
}

.guide-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 24px 14px;
  border-bottom: 1px solid #eef2f7;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
}

.guide-modal-header h3 {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: #111827;
  letter-spacing: 0.01em;
}

.guide-modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  color: #94a3b8;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
}

.guide-modal-close:hover {
  background: #f1f5f9;
  color: #475569;
}

.guide-modal-body {
  padding: 18px 24px 24px;
  overflow-y: auto;
  background: #ffffff;
}

.dialog-tip {
  margin-bottom: 20px;
  padding: 14px 16px;
  border: 1px solid #dbe6f5;
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfdff 0%, #f6faff 100%);
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
}

.format-guide-markdown {
  max-height: min(70vh, 720px);
  overflow: auto;
  padding-right: 6px;
  color: #334155;
  line-height: 1.7;
}

.format-guide-markdown :deep(h1),
.format-guide-markdown :deep(h2),
.format-guide-markdown :deep(h3) {
  margin: 20px 0 10px;
  color: #0f172a;
  line-height: 1.35;
}

.format-guide-markdown :deep(h1) {
  margin-top: 0;
  font-size: 22px;
}

.format-guide-markdown :deep(h2) {
  font-size: 17px;
}

.format-guide-markdown :deep(h3) {
  font-size: 15px;
}

.format-guide-markdown :deep(p) {
  margin: 0 0 10px;
}

.format-guide-markdown :deep(ul) {
  margin: 0 0 12px;
  padding-left: 20px;
}

.format-guide-markdown :deep(li) {
  margin-bottom: 6px;
}

.format-guide-markdown :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: #eff4fb;
  color: #1d4ed8;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 13px;
}

.format-guide-markdown :deep(.format-guide-code) {
  margin: 0 0 14px;
  padding: 14px 16px;
  border: 1px solid #dbe6f5;
  border-radius: 14px;
  background: #f8fbff;
  overflow: auto;
}

.format-guide-markdown :deep(.format-guide-code code) {
  padding: 0;
  background: transparent;
  color: #0f172a;
  white-space: pre;
}

.format-guide-table-block {
  margin-top: 18px;
  padding: 16px;
  border: 1px solid #dbe6f5;
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfdff 0%, #f8fbff 100%);
}

.format-guide-table-title {
  margin-bottom: 12px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.format-guide-table-scroll {
  overflow: auto;
}

.format-guide-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  background: #ffffff;
}

.format-guide-table th,
.format-guide-table td {
  padding: 10px 12px;
  border: 1px solid #dbe6f5;
  text-align: center;
  font-size: 13px;
  white-space: nowrap;
}

.format-guide-table thead th {
  background: #eef4fb;
  color: #334155;
  font-weight: 700;
}

.format-guide-table tbody td:first-child,
.format-guide-table tbody td:nth-child(2) {
  background: #f8fbff;
  font-weight: 600;
}

@media (max-width: 768px) {
  .guide-modal {
    width: calc(100vw - 24px);
  }
}
</style>
