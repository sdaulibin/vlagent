<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { renderAsync } from "docx-preview";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.mjs?url";
import type { ScrollbarInstance } from "element-plus";
import { getHighlightKind } from "../utils/diffUtils";
import {
  bboxToDomRect,
  findDocxTableCellRect,
  findPdfTextBBox,
  findTextRect,
  getSideTextQueries,
  mergeDomRects,
  pickLocForFileType
} from "../utils/anchorUtils";
import type { BBox, DiffHighlightKind, DiffLoc, DiffRecord, SupportedFileType } from "../types";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

const PDF_SCALE = 1.4;
const PDF_CMAP_URL = `${import.meta.env.BASE_URL}pdfjs/cmaps/`;
const PDF_STANDARD_FONT_URL = `${import.meta.env.BASE_URL}pdfjs/standard_fonts/`;

const props = defineProps<{
  title: string;
  file: File | null;
  side: "A" | "B";
  diffs: DiffRecord[];
  activeDiff: DiffRecord | null;
}>();

const emit = defineEmits<{
  highlightsUpdated: [];
  scroll: [ratio: number];
}>();

const loading = ref(false);
const errorMessage = ref("");
const contentRef = ref<HTMLElement | null>(null);
const scrollRef = ref<ScrollbarInstance | null>(null);
const fileBuffer = ref<ArrayBuffer | null>(null);
const pdfPageTextItems = ref<Map<number, Array<{ text: string; bbox: BBox }>>>(new Map());
/** 递增世代号，用于丢弃过期的异步 PDF/DOCX 渲染，避免旧预览覆盖新文件 */
let renderGeneration = 0;
const isStaleRender = (gen: number): boolean => gen !== renderGeneration;

const fileType = computed<SupportedFileType>(() => {
  if (!props.file) return "unknown";
  const name = props.file.name.toLowerCase();
  if (name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".docx")) return "docx";
  return "unknown";
});

const sideDiffs = computed(() =>
  props.diffs.filter((diff) => pickLocForFileType(diff, fileType.value) !== null)
);

const markClass = (kind: DiffHighlightKind, active: boolean): string => {
  const classes = ["diff-mark", kind === "only-in" ? "diff-mark--only-in" : "diff-mark--other"];
  if (active) classes.push("diff-mark--active");
  return classes.join(" ");
};

const bboxClass = (kind: DiffHighlightKind, active: boolean): string => {
  const classes = ["diff-bbox", kind === "only-in" ? "diff-bbox--only-in" : "diff-bbox--other"];
  if (active) classes.push("diff-bbox--active");
  return classes.join(" ");
};

const clearDocxHighlights = (): void => {
  if (!contentRef.value) return;

  contentRef.value.querySelectorAll("mark[data-diff-id]").forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    const textNode = document.createTextNode(mark.textContent ?? "");
    parent.replaceChild(textNode, mark);
    parent.normalize();
  });

  contentRef.value.querySelectorAll("td[data-diff-id]").forEach((cell) => {
    cell.removeAttribute("data-diff-id");
    cell.classList.remove(
      "diff-mark",
      "diff-mark--only-in",
      "diff-mark--other",
      "diff-mark--active"
    );
  });
};

const clearHighlights = (): void => {
  if (!contentRef.value) return;
  clearDocxHighlights();
  contentRef.value.querySelectorAll(".diff-bbox").forEach((node) => node.remove());
};

const getSideLoc = (diff: DiffRecord): DiffLoc | null =>
  pickLocForFileType(diff, fileType.value);

const findTextNodeAndOffset = (
  root: HTMLElement,
  query: string
): { node: Text; start: number } | null => {
  if (!query.trim()) return null;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let current = walker.nextNode();
  while (current) {
    const textNode = current as Text;
    const text = textNode.nodeValue ?? "";
    const idx = text.indexOf(query);
    if (idx >= 0) {
      return { node: textNode, start: idx };
    }
    current = walker.nextNode();
  }
  return null;
};

const wrapTextRange = (
  root: HTMLElement,
  query: string,
  className: string,
  diffId: string
): boolean => {
  const result = findTextNodeAndOffset(root, query);
  if (!result) return false;

  try {
    const range = document.createRange();
    range.setStart(result.node, result.start);
    range.setEnd(result.node, result.start + query.length);
    const mark = document.createElement("mark");
    mark.className = className;
    mark.setAttribute("data-diff-id", diffId);
    range.surroundContents(mark);
    return true;
  } catch {
    return false;
  }
};

const highlightDocxTable = (root: HTMLElement, loc: DiffLoc, className: string, diffId: string): boolean => {
  if (loc.table_index === undefined || loc.table_index < 0 || loc.row === undefined) return false;
  const tables = root.querySelectorAll("table");
  const table = tables.item(loc.table_index);
  if (!table) return false;

  const row = table.rows.item(loc.row);
  if (!row) return false;

  const targets =
    loc.col !== undefined && loc.col >= 0 ? [row.cells.item(loc.col)].filter(Boolean) : Array.from(row.cells);

  if (!targets.length) return false;

  targets.forEach((cell) => {
    if (!cell) return;
    cell.classList.add(...className.split(" "));
    cell.setAttribute("data-diff-id", diffId);
  });
  return true;
};

const applyDocxHighlights = (): void => {
  if (!contentRef.value) return;

  for (const diff of sideDiffs.value) {
    const loc = getSideLoc(diff);
    if (!loc) continue;

    const className = markClass(getHighlightKind(diff), diff.diff_id === props.activeDiff?.diff_id);
    let applied = false;

    if (loc.table_index !== undefined && loc.row !== undefined) {
      applied = highlightDocxTable(contentRef.value, loc, className, diff.diff_id);
    }

    if (!applied) {
      for (const candidate of getSideTextQueries(diff, fileType.value)) {
        if (wrapTextRange(contentRef.value, candidate, className, diff.diff_id)) {
          applied = true;
          break;
        }
      }
    }
  }
};

const extractPageTextItems = async (
  page: pdfjsLib.PDFPageProxy,
  pageHeight: number
): Promise<Array<{ text: string; bbox: BBox }>> => {
  const textContent = await page.getTextContent();
  const items: Array<{ text: string; bbox: BBox }> = [];

  for (const item of textContent.items) {
    if (!("str" in item) || !item.str.trim()) continue;
    const transform = item.transform;
    const fontHeight = Math.hypot(transform[2], transform[3]) || Math.hypot(transform[0], transform[1]) || 12;
    const x0 = transform[4];
    const y0 = pageHeight - transform[5] - fontHeight;
    items.push({
      text: item.str,
      bbox: [x0, y0, x0 + item.width, y0 + fontHeight]
    });
  }

  return items;
};

const createPdfOverlay = (
  overlay: HTMLElement,
  scale: number,
  bbox: BBox,
  className: string,
  diffId: string
): void => {
  const [x0, y0, x1, y1] = bbox;
  const left = x0 * scale;
  const top = y0 * scale;
  const width = (x1 - x0) * scale;
  const height = (y1 - y0) * scale;

  const box = document.createElement("div");
  box.className = className;
  box.setAttribute("data-diff-id", diffId);
  box.style.left = `${left}px`;
  box.style.top = `${top}px`;
  box.style.width = `${Math.max(width, 1)}px`;
  box.style.height = `${Math.max(height, 1)}px`;
  overlay.appendChild(box);
};

const renderPdf = async (buffer: ArrayBuffer, gen: number): Promise<void> => {
  if (!contentRef.value || isStaleRender(gen)) return;
  const pdf = await pdfjsLib.getDocument({
    data: buffer.slice(0),
    cMapUrl: PDF_CMAP_URL,
    cMapPacked: true,
    standardFontDataUrl: PDF_STANDARD_FONT_URL
  }).promise;
  if (!contentRef.value || isStaleRender(gen)) return;
  const root = contentRef.value;
  root.innerHTML = "";
  pdfPageTextItems.value = new Map();

  for (let pageIndex = 1; pageIndex <= pdf.numPages; pageIndex += 1) {
    if (isStaleRender(gen)) return;
    const page = await pdf.getPage(pageIndex);
    const baseViewport = page.getViewport({ scale: 1 });
    pdfPageTextItems.value.set(
      pageIndex,
      await extractPageTextItems(page, baseViewport.height)
    );
    const viewport = page.getViewport({ scale: PDF_SCALE });
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    if (!context) continue;

    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.className = "pdf-canvas";

    await page.render({ canvasContext: context, viewport, canvas, intent: "display" }).promise;
    if (isStaleRender(gen)) return;

    const wrapper = document.createElement("section");
    wrapper.className = "pdf-page";
    wrapper.dataset.page = String(pageIndex);

    const pageTitle = document.createElement("h4");
    pageTitle.textContent = `第 ${pageIndex} 页`;
    wrapper.appendChild(pageTitle);

    const stage = document.createElement("div");
    stage.className = "pdf-stage";
    stage.style.width = `${canvas.width}px`;
    stage.style.height = `${canvas.height}px`;

    stage.appendChild(canvas);

    const overlay = document.createElement("div");
    overlay.className = "pdf-overlay";

    for (const diff of sideDiffs.value) {
      const loc = getSideLoc(diff);
      if (!loc || loc.page !== pageIndex) continue;

      const className = bboxClass(
        getHighlightKind(diff),
        diff.diff_id === props.activeDiff?.diff_id
      );

      if (loc.spans?.length) {
        for (const span of loc.spans) {
          if (span.bbox) {
            createPdfOverlay(overlay, PDF_SCALE, span.bbox, className, diff.diff_id);
          }
        }
      } else if (loc.bbox) {
        createPdfOverlay(overlay, PDF_SCALE, loc.bbox, className, diff.diff_id);
      }
    }

    stage.appendChild(overlay);
    wrapper.appendChild(stage);
    root.appendChild(wrapper);
  }
};

const renderDocx = async (buffer: ArrayBuffer, gen: number): Promise<void> => {
  if (!contentRef.value || isStaleRender(gen)) return;
  contentRef.value.innerHTML = "";
  await renderAsync(buffer, contentRef.value, undefined, {
    className: "docx-preview"
  });
  if (isStaleRender(gen)) return;
};

const updateActiveHighlight = (): void => {
  if (!contentRef.value) return;

  contentRef.value.querySelectorAll(".diff-mark--active, .diff-bbox--active").forEach((node) => {
    node.classList.remove("diff-mark--active", "diff-bbox--active");
  });

  if (!props.activeDiff) return;

  contentRef.value
    .querySelectorAll(`[data-diff-id="${props.activeDiff.diff_id}"]`)
    .forEach((node) => {
      node.classList.add(
        node.classList.contains("diff-bbox") ? "diff-bbox--active" : "diff-mark--active"
      );
    });
};

const scrollToActiveDiff = async (): Promise<void> => {
  await nextTick();
  if (!contentRef.value || !props.activeDiff) return;
  const target = contentRef.value.querySelector(
    `[data-diff-id="${props.activeDiff.diff_id}"]`
  );
  target?.scrollIntoView({ behavior: "auto", block: "center" });
};

const mergeRects = (nodes: NodeListOf<Element>): DOMRect | null => {
  const rects = [...nodes].map((node) => node.getBoundingClientRect());
  return mergeDomRects(rects);
};

const getHighlightAnchor = (diffId: string): DOMRect | null => {
  if (!contentRef.value) return null;

  const diff = props.diffs.find((item) => item.diff_id === diffId);
  if (!diff) return null;

  const loc = getSideLoc(diff);
  if (!loc) return null;

  const queries = getSideTextQueries(diff, fileType.value);
  const nodes = contentRef.value.querySelectorAll(`[data-diff-id="${diffId}"]`);

  const marks = [...nodes].filter((node) => node.tagName === "MARK");
  if (marks.length) {
    const markRect = mergeDomRects(marks.map((node) => node.getBoundingClientRect()));
    if (markRect) return markRect;
  }

  const bboxNodes = [...nodes].filter((node) => node.classList.contains("diff-bbox"));
  if (bboxNodes.length) {
    return mergeDomRects(bboxNodes.map((node) => node.getBoundingClientRect()));
  }

  for (const node of nodes) {
    if (node instanceof HTMLElement && queries.length) {
      const textRect = findTextRect(node, queries);
      if (textRect) return textRect;
    }
  }

  if (fileType.value === "pdf" && loc.page) {
    const stage = contentRef.value.querySelector(
      `.pdf-page[data-page="${loc.page}"] .pdf-stage`
    );
    if (stage instanceof HTMLElement) {
      if (loc.bbox) {
        return bboxToDomRect(stage, loc.bbox, PDF_SCALE);
      }
      const pageItems = pdfPageTextItems.value.get(loc.page) ?? [];
      const textBBox = findPdfTextBBox(pageItems, queries);
      if (textBBox) {
        return bboxToDomRect(stage, textBBox, PDF_SCALE);
      }
    }
  }

  if (fileType.value === "docx") {
    const tableRect = findDocxTableCellRect(contentRef.value, loc);
    if (tableRect) return tableRect;
    const textRect = findTextRect(contentRef.value, queries);
    if (textRect) return textRect;
  }

  if (nodes.length) return mergeRects(nodes);
  return null;
};

const getScrollElement = (): HTMLElement | null => {
  const scrollbar = scrollRef.value;
  if (!scrollbar) return null;
  const wrap = scrollbar.wrapRef;
  if (wrap instanceof HTMLElement) return wrap;
  if (wrap && typeof wrap === "object" && "value" in wrap) {
    const el = (wrap as { value?: HTMLElement | null }).value;
    return el instanceof HTMLElement ? el : null;
  }
  return null;
};

const getScrollRatio = (): number => {
  const el = getScrollElement();
  if (!el) return 0;
  const maxScroll = el.scrollHeight - el.clientHeight;
  if (maxScroll <= 0) return 0;
  return el.scrollTop / maxScroll;
};

const setScrollRatio = (ratio: number): void => {
  const el = getScrollElement();
  if (!el) return;
  const maxScroll = el.scrollHeight - el.clientHeight;
  el.scrollTop = Math.max(0, Math.min(1, ratio)) * maxScroll;
};

let scrollListener: (() => void) | null = null;

const bindScrollListener = (): void => {
  const el = getScrollElement();
  if (!el) return;
  if (scrollListener) {
    el.removeEventListener("scroll", scrollListener);
  }
  scrollListener = (): void => {
    emit("scroll", getScrollRatio());
  };
  el.addEventListener("scroll", scrollListener, { passive: true });
};

const ensureScrollListener = async (): Promise<void> => {
  await nextTick();
  for (let attempt = 0; attempt < 10; attempt += 1) {
    if (getScrollElement()) {
      bindScrollListener();
      return;
    }
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, 80);
    });
  }
};

const unbindScrollListener = (): void => {
  const el = getScrollElement();
  if (el && scrollListener) {
    el.removeEventListener("scroll", scrollListener);
  }
  scrollListener = null;
};

defineExpose({
  getHighlightAnchor,
  getScrollElement,
  getScrollRatio,
  setScrollRatio
});

const renderFile = async (): Promise<void> => {
  const gen = ++renderGeneration;
  await nextTick();
  if (!contentRef.value || isStaleRender(gen)) return;

  errorMessage.value = "";
  clearHighlights();
  contentRef.value.innerHTML = "";

  if (!props.file) {
    fileBuffer.value = null;
    return;
  }
  if (fileType.value === "unknown") {
    errorMessage.value = "当前文件类型不支持预览，请上传 PDF 或 DOCX。";
    return;
  }

  loading.value = true;
  try {
    fileBuffer.value = await props.file.arrayBuffer();
    if (isStaleRender(gen)) return;
    if (fileType.value === "pdf") {
      await renderPdf(fileBuffer.value, gen);
    } else {
      await renderDocx(fileBuffer.value, gen);
      if (isStaleRender(gen)) return;
      applyDocxHighlights();
      updateActiveHighlight();
    }
  } catch (error) {
    if (isStaleRender(gen)) return;
    errorMessage.value = "预览解析失败，请确认文件内容是否正常。";
    console.error(error);
  } finally {
    if (isStaleRender(gen)) return;
    loading.value = false;
    await ensureScrollListener();
  }
};

const refreshHighlights = async (): Promise<void> => {
  if (!props.file || !contentRef.value || loading.value) return;

  updateActiveHighlight();
  await scrollToActiveDiff();
  emit("highlightsUpdated");
};

const reapplyAllHighlights = async (): Promise<void> => {
  if (!props.file || !contentRef.value || loading.value) return;
  const gen = renderGeneration;

  if (fileType.value === "docx") {
    clearDocxHighlights();
    applyDocxHighlights();
    updateActiveHighlight();
  } else if (fileBuffer.value) {
    await renderPdf(fileBuffer.value, gen);
    if (isStaleRender(gen)) return;
    updateActiveHighlight();
  }
  emit("highlightsUpdated");
};

watch(
  () => props.file,
  async () => {
    unbindScrollListener();
    await renderFile();
  },
  { immediate: true }
);

watch(
  () => props.activeDiff?.diff_id ?? null,
  async () => {
    await refreshHighlights();
  }
);

watch(
  () => props.diffs,
  async () => {
    await reapplyAllHighlights();
  },
  { deep: true }
);

watch(
  () => scrollRef.value,
  () => {
    void ensureScrollListener();
  }
);

onBeforeUnmount(() => {
  unbindScrollListener();
  clearHighlights();
});
</script>

<template>
  <div class="doc-pane">
    <div class="doc-pane-title">{{ title }}</div>
    <el-empty v-if="!file" description="请先上传文件" :image-size="72" />
    <div v-else class="doc-viewer">
      <el-alert v-if="errorMessage" :title="errorMessage" type="warning" show-icon />
      <div class="doc-scroll-wrap">
        <el-scrollbar ref="scrollRef" class="doc-scroll">
          <div ref="contentRef" class="doc-content"></div>
        </el-scrollbar>
        <div v-if="loading" class="doc-loading-mask">
          <el-skeleton animated :rows="6" />
        </div>
      </div>
    </div>
  </div>
</template>
