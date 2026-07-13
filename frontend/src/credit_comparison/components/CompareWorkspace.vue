<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { buildExceptionColorStyle } from "../utils/exceptionColors";

const props = defineProps({
  detail: {
    type: Object,
    required: true,
  },
});
const emit = defineEmits(["active-record-change"]);

const activeSheet = ref(props.detail.excelSheets?.[0]?.sheet || "");
const activeLinkId = ref(null);
const activeWordRecordId = ref(null);
const compareStageRef = ref(null);
const wordScrollRef = ref(null);
const excelScrollRef = ref(null);
const lineCanvasRef = ref(null);

const wordRecordNodeRefs = new Map();
const excelRecordMarkerRefs = new Map();
const excelRecordRowRefs = new Map();

const balanceMissingExceptionNames = new Set(["余额缺失异常", "余额缺失"]);
const wordNormalColorStyle = buildExceptionColorStyle(1, "指标代码异常");
const excelExceptionColorStyle = buildExceptionColorStyle(3, "指标数值异常");
const excelNormalColorStyle = buildExceptionColorStyle(1, "指标代码异常");

const currentSheet = computed(() => {
  return props.detail.excelSheets.find((item) => item.sheet === activeSheet.value) || props.detail.excelSheets[0] || null;
});

const currentWordDocument = computed(() => {
  return props.detail.wordDocument || { fileName: props.detail.title || "", paragraphs: [] };
});

const sheetOptions = computed(() => {
  return (props.detail.excelSheets || []).map((item) => ({
    label: item.sheet,
    value: item.sheet,
  }));
});

const visibleLinks = computed(() => {
  const links = props.detail.linkList || [];
  if (!activeSheet.value) {
    return links;
  }
  return links.filter(
    (item) => String(item.wordSheet || "") === activeSheet.value || String(item.excelSheet || "") === activeSheet.value,
  );
});

const visibleMatchedLinks = computed(() => {
  return visibleLinks.value.filter((item) => item.excelRecordId !== null && item.excelRecordId !== undefined);
});

const currentActiveLink = computed(() => {
  return visibleMatchedLinks.value.find((item) => Number(item.compareLinkId) === Number(activeLinkId.value)) || null;
});

const currentDrawLinks = computed(() => {
  const activeLink = currentActiveLink.value;
  if (!activeLink) {
    return [];
  }
  const sameWordLinks = visibleMatchedLinks.value.filter(
    (item) => Number(item.wordRecordId) === Number(activeLink.wordRecordId),
  );
  return sameWordLinks.length ? sameWordLinks : [activeLink];
});

function scrollNodeIntoView(container, node) {
  if (!container || !node) {
    return;
  }

  const containerRect = container.getBoundingClientRect();
  const nodeRect = node.getBoundingClientRect();
  const offsetTop = nodeRect.top - containerRect.top + container.scrollTop;
  const offsetBottom = offsetTop + nodeRect.height;
  const visibleTop = container.scrollTop;
  const visibleBottom = visibleTop + container.clientHeight;
  const padding = 40;

  if (offsetTop - padding < visibleTop) {
    container.scrollTo({
      top: Math.max(offsetTop - padding, 0),
      behavior: "smooth",
    });
    return;
  }

  if (offsetBottom + padding > visibleBottom) {
    container.scrollTo({
      top: Math.max(offsetBottom - container.clientHeight + padding, 0),
      behavior: "smooth",
    });
  }
}

function scrollExcelRowIntoNonFrozenArea(rowElement) {
  const container = excelScrollRef.value;
  if (!container || !rowElement) {
    return;
  }

  const table = container.querySelector(".excel-table");
  const thead = table && table.tHead;
  if (!thead) {
    rowElement.scrollIntoView({ block: "nearest" });
    return;
  }

  const containerRect = container.getBoundingClientRect();
  const tableWrap = container.querySelector(".excel-table-wrap");
  const tableWrapRect = tableWrap ? tableWrap.getBoundingClientRect() : containerRect;

  let frozenTopHeight = 0;
  for (const row of [...thead.rows]) {
    const rect = row.getBoundingClientRect();
    if (rect.height > 0) {
      frozenTopHeight += rect.height;
    }
  }

  const tableVisibleTop = Math.max(containerRect.top, Math.min(tableWrapRect.top, containerRect.bottom));
  const topGapHeight = Math.max(0, tableVisibleTop - containerRect.top);
  const safeTop = topGapHeight + frozenTopHeight + 12;
  const safeBottom = Math.max(safeTop + 24, container.clientHeight - 12);

  const rowRect = rowElement.getBoundingClientRect();
  const rowTopInContainer = rowRect.top - containerRect.top;
  const rowBottomInContainer = rowRect.bottom - containerRect.top;

  let nextScrollTop = container.scrollTop;
  if (rowTopInContainer < safeTop) {
    nextScrollTop -= safeTop - rowTopInContainer;
  } else if (rowBottomInContainer > safeBottom) {
    nextScrollTop += rowBottomInContainer - safeBottom;
  }

  const maxScrollTop = Math.max(0, container.scrollHeight - container.clientHeight);
  const finalScrollTop = Math.max(0, Math.min(maxScrollTop, nextScrollTop));
  if (Math.abs(finalScrollTop - container.scrollTop) > 1) {
    container.scrollTo({ top: finalScrollTop, behavior: "smooth" });
  }
}

function ensureExcelFrozenColumnsVisible() {
  if (excelScrollRef.value && Math.abs(excelScrollRef.value.scrollLeft) > 1) {
    excelScrollRef.value.scrollLeft = 0;
  }
}

function updateExcelHeaderStickyOffsets() {
  const container = excelScrollRef.value;
  if (!container) {
    return;
  }

  const table = container.querySelector(".excel-table");
  const thead = table && table.tHead;
  if (!thead) {
    return;
  }

  let offset = 0;
  for (const row of [...thead.rows]) {
    const height = row.getBoundingClientRect().height;
    for (const cell of [...row.cells]) {
      cell.style.top = `${offset}px`;
    }
    offset += height;
  }
}

function syncActiveNodes() {
  const activeLink = currentActiveLink.value;
  if (!activeLink) {
    return;
  }

  const wordNode = wordRecordNodeRefs.get(Number(activeLink.wordRecordId));
  const excelRow = excelRecordRowRefs.get(Number(activeLink.excelRecordId));

  scrollNodeIntoView(wordScrollRef.value, wordNode);
  scrollExcelRowIntoNonFrozenArea(excelRow);
  ensureExcelFrozenColumnsVisible();
}

function isRectVisibleInContainer(elementRect, containerRect) {
  return (
    elementRect.bottom >= containerRect.top &&
    elementRect.top <= containerRect.bottom &&
    elementRect.right >= containerRect.left &&
    elementRect.left <= containerRect.right
  );
}

function buildConnectionPath(x1, y1, x2, y2) {
  const controlOffset = Math.max(Math.abs(x2 - x1) * 0.35, 60);
  return `M ${x1} ${y1} C ${x1 + controlOffset} ${y1}, ${x2 - controlOffset} ${y2}, ${x2} ${y2}`;
}

function getLinkColorStyle(link) {
  return link?.hasException ? excelExceptionColorStyle : excelNormalColorStyle;
}

function getParagraphColorStyle(paragraph) {
  if (!paragraph?.tag) {
    return wordNormalColorStyle;
  }
  return buildExceptionColorStyle(paragraph?.primaryExceptionTypeId, paragraph?.primaryExceptionTypeName);
}

function getSegmentColorStyle(segment) {
  if (!segment?.highlight) {
    return null;
  }
  return buildExceptionColorStyle(segment?.typeId, segment?.typeName);
}

function getExcelRowColorStyle(row) {
  return row?.hasException ? excelExceptionColorStyle : excelNormalColorStyle;
}

function getExcelFrozenRegionInStage(stageRect) {
  const container = excelScrollRef.value;
  if (!container) {
    return null;
  }

  const excelDocRect = container.getBoundingClientRect();
  const excelPanel = container.closest(".doc-panel");
  const tableWrap = container.querySelector(".excel-table-wrap");
  const table = container.querySelector(".excel-table");
  const thead = table && table.tHead;
  if (!thead) {
    return null;
  }
  if (excelDocRect.width <= 0 || excelDocRect.height <= 0) {
    return null;
  }

  const rows = [...thead.rows];
  if (!rows.length) {
    return null;
  }

  let frozenTopHeight = 0;
  for (const row of rows) {
    const rect = row.getBoundingClientRect();
    if (rect.height > 0) {
      frozenTopHeight += rect.height;
    }
  }
  frozenTopHeight = Math.min(frozenTopHeight, excelDocRect.height);

  const rowHeaderCell = container.querySelector(".excel-table .excel-row-header");
  const codeCell = container.querySelector(".excel-table .excel-code-col");
  const rowHeaderRight = rowHeaderCell ? rowHeaderCell.getBoundingClientRect().right : excelDocRect.left;
  const codeRight = codeCell ? codeCell.getBoundingClientRect().right : excelDocRect.left;
  const frozenLeftRight = Math.max(rowHeaderRight, codeRight, excelDocRect.left);
  let frozenLeftWidth = frozenLeftRight - excelDocRect.left;
  frozenLeftWidth = Math.max(0, Math.min(frozenLeftWidth, excelDocRect.width));

  const x = excelDocRect.left - stageRect.left;
  const y = excelDocRect.top - stageRect.top;
  const topMaskX = excelPanel ? Math.max(0, excelPanel.getBoundingClientRect().left - stageRect.left) : x;
  const topMaskWidth = Math.max(0, stageRect.width - topMaskX);
  const rects = [];

  if (tableWrap) {
    const tableWrapRect = tableWrap.getBoundingClientRect();
    const tableVisibleTop = Math.max(excelDocRect.top, Math.min(tableWrapRect.top, excelDocRect.bottom));
    const topGapHeight = Math.max(0, tableVisibleTop - excelDocRect.top);
    if (topGapHeight > 0) {
      rects.push({
        kind: "top-gap",
        rect: { x: topMaskX, y, width: topMaskWidth, height: topGapHeight },
      });
    }
  }

  if (frozenTopHeight > 0) {
    rects.push({
      kind: "top",
      rect: { x: topMaskX, y, width: topMaskWidth, height: frozenTopHeight },
    });
  }
  if (frozenLeftWidth > 0) {
    rects.push({
      kind: "left",
      rect: { x, y, width: frozenLeftWidth, height: excelDocRect.height },
    });
  }

  return rects.length ? { rects, meta: { frozenTopHeight, frozenLeftWidth } } : null;
}

function drawConnections() {
  const stage = compareStageRef.value;
  const canvas = lineCanvasRef.value;
  if (!stage || !canvas) {
    return;
  }

  const stageRect = stage.getBoundingClientRect();
  canvas.setAttribute("viewBox", `0 0 ${Math.max(stageRect.width, 1)} ${Math.max(stageRect.height, 1)}`);
  canvas.innerHTML = "";

  const drawLinks = currentDrawLinks.value.filter(
    (item) => item.excelRecordId !== null && item.excelRecordId !== undefined,
  );
  if (!drawLinks.length) {
    return;
  }

  const stageWidth = Math.max(stageRect.width, 1);
  const stageHeight = Math.max(stageRect.height, 1);
  const wordViewportRect = wordScrollRef.value.getBoundingClientRect();
  const excelViewportRect = excelScrollRef.value.getBoundingClientRect();
  const clipTop = Math.max(wordViewportRect.top, excelViewportRect.top) - stageRect.top;
  const clipY = Math.max(0, Math.min(stageHeight, clipTop));
  const excelFrozenRegion = getExcelFrozenRegionInStage(stageRect);
  const minVisibleY = clipY + 2;
  const clipId = "docViewportClip-active";
  const svgNS = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(svgNS, "defs");
  const clipPath = document.createElementNS(svgNS, "clipPath");
  clipPath.setAttribute("id", clipId);
  clipPath.setAttribute("clipPathUnits", "userSpaceOnUse");
  const clipRect = document.createElementNS(svgNS, "rect");
  clipRect.setAttribute("x", "0");
  clipRect.setAttribute("y", String(clipY));
  clipRect.setAttribute("width", String(stageWidth));
  clipRect.setAttribute("height", String(Math.max(0, stageHeight - clipY)));
  clipPath.appendChild(clipRect);
  defs.appendChild(clipPath);

  let maskId = "";
  if (excelFrozenRegion) {
    maskId = "excelFreezeMask-active";
    const mask = document.createElementNS(svgNS, "mask");
    mask.setAttribute("id", maskId);
    mask.setAttribute("maskUnits", "userSpaceOnUse");
    mask.setAttribute("maskContentUnits", "userSpaceOnUse");
    mask.setAttribute("x", "0");
    mask.setAttribute("y", "0");
    mask.setAttribute("width", String(stageWidth));
    mask.setAttribute("height", String(stageHeight));

    const maskBg = document.createElementNS(svgNS, "rect");
    maskBg.setAttribute("x", "0");
    maskBg.setAttribute("y", "0");
    maskBg.setAttribute("width", String(stageWidth));
    maskBg.setAttribute("height", String(stageHeight));
    maskBg.setAttribute("fill", "white");
    mask.appendChild(maskBg);

    const topHolePadUp = 28;
    for (const rectInfo of excelFrozenRegion.rects) {
      if (rectInfo.kind !== "top" && rectInfo.kind !== "top-gap") {
        continue;
      }
      const hole = document.createElementNS(svgNS, "rect");
      const y =
        rectInfo.kind === "top"
          ? Math.max(0, Math.floor(rectInfo.rect.y - topHolePadUp))
          : rectInfo.rect.y;
      const bottom = Math.ceil(rectInfo.rect.y + rectInfo.rect.height);
      const height = rectInfo.kind === "top" ? Math.max(0, bottom - y) : rectInfo.rect.height;
      hole.setAttribute("x", String(rectInfo.rect.x));
      hole.setAttribute("y", String(y));
      hole.setAttribute("width", String(rectInfo.rect.width));
      hole.setAttribute("height", String(height));
      hole.setAttribute("fill", "black");
      mask.appendChild(hole);
    }

    defs.appendChild(mask);
  }

  canvas.appendChild(defs);

  const outerGroup = document.createElementNS(svgNS, "g");
  outerGroup.setAttribute("clip-path", `url(#${clipId})`);
  const frozenTopRect = excelFrozenRegion?.rects.find((item) => item.kind === "top")?.rect || null;
  const frozenBottom = frozenTopRect ? frozenTopRect.y + frozenTopRect.height : null;

  for (const link of drawLinks) {
    const wordNode = wordRecordNodeRefs.get(Number(link.wordRecordId));
    const excelMarker = excelRecordMarkerRefs.get(Number(link.excelRecordId));
    if (!wordNode || !excelMarker) {
      continue;
    }

    const wordRect = wordNode.getBoundingClientRect();
    const excelRect = excelMarker.getBoundingClientRect();
    if (!isRectVisibleInContainer(wordRect, wordViewportRect) || !isRectVisibleInContainer(excelRect, excelViewportRect)) {
      continue;
    }

    const rawX1 = wordRect.right - stageRect.left - 6;
    const rawY1 = wordRect.top - stageRect.top + Math.min(wordRect.height / 2, 42);
    const rawX2 = excelRect.left - stageRect.left + excelRect.width / 2;
    const rawY2 = excelRect.top - stageRect.top + excelRect.height / 2;
    const isExcelTargetAtOrAboveFrozenBottom = frozenBottom !== null && rawY2 <= frozenBottom;
    if (isExcelTargetAtOrAboveFrozenBottom) {
      continue;
    }

    const x1 = rawX1;
    const y1 = Math.max(rawY1, minVisibleY);
    const x2 = rawX2;
    const y2 = Math.max(rawY2, minVisibleY);
    const isPrimaryLink = Number(link.compareLinkId) === Number(activeLinkId.value);

    const targetGroup = document.createElementNS(svgNS, "g");
    if (maskId) {
      targetGroup.setAttribute("mask", `url(#${maskId})`);
    }

    const line = document.createElementNS(svgNS, "path");
    line.setAttribute("d", buildConnectionPath(x1, y1, x2, y2));
    line.setAttribute("class", `svg-link-line${isPrimaryLink ? " active" : ""}`);
    line.style.stroke = getLinkColorStyle(link)["--exception-color"];
    line.style.filter = `drop-shadow(0 0 4px ${getLinkColorStyle(link)["--exception-strong-color"]})`;
    targetGroup.appendChild(line);

    const leftDot = document.createElementNS(svgNS, "circle");
    leftDot.setAttribute("cx", String(x1));
    leftDot.setAttribute("cy", String(y1));
    leftDot.setAttribute("r", "4.5");
    leftDot.setAttribute("class", "svg-link-dot");
    leftDot.style.fill = getLinkColorStyle(link)["--exception-color"];
    targetGroup.appendChild(leftDot);

    const rightDot = document.createElementNS(svgNS, "circle");
    rightDot.setAttribute("cx", String(x2));
    rightDot.setAttribute("cy", String(y2));
    rightDot.setAttribute("r", "4.5");
    rightDot.setAttribute("class", "svg-link-dot");
    rightDot.style.fill = getLinkColorStyle(link)["--exception-color"];
    targetGroup.appendChild(rightDot);

    outerGroup.appendChild(targetGroup);
  }

  canvas.appendChild(outerGroup);
}

function focusLink(linkId) {
  activeWordRecordId.value = null;
  activeLinkId.value = Number(linkId);
}

function findLinkByWordRecordId(wordRecordId, preferredSheet = "") {
  const targetWordRecordId = Number(wordRecordId);
  const links = props.detail.linkList || [];
  return (
    links.find(
      (item) =>
        Number(item.wordRecordId) === targetWordRecordId &&
        preferredSheet &&
        (String(item.wordSheet || "") === preferredSheet || String(item.excelSheet || "") === preferredSheet),
    ) ||
    links.find((item) => Number(item.wordRecordId) === targetWordRecordId) ||
    null
  );
}

async function focusWordRecord(wordRecordId) {
  activeWordRecordId.value = Number(wordRecordId);
  activeLinkId.value = null;
  await nextTick();
  const wordNode = wordRecordNodeRefs.get(Number(wordRecordId));
  scrollNodeIntoView(wordScrollRef.value, wordNode);
  drawConnections();
}

async function focusByExceptionItem(item) {
  const targetSheet = String(item?.sheet || "");
  const link = findLinkByWordRecordId(item?.wordRecordId, targetSheet || activeSheet.value);
  const linkSheet = link ? String(link.wordSheet || link.excelSheet || "") : "";
  const nextSheet = linkSheet || targetSheet;
  if (nextSheet && nextSheet !== activeSheet.value) {
    activeSheet.value = nextSheet;
    await nextTick();
  }

  if (link && link.excelRecordId !== null && link.excelRecordId !== undefined) {
    focusLink(link.compareLinkId);
    await nextTick();
    syncActiveNodes();
    drawConnections();
    return;
  }

  await focusWordRecord(item?.wordRecordId);
}

function findPreferredLinkForParagraph(paragraph) {
  return visibleMatchedLinks.value.find((link) => (paragraph.wordRecordIds || []).includes(Number(link.wordRecordId))) || null;
}

function findPreferredLinkForRow(row) {
  return visibleMatchedLinks.value.find((link) => (row.excelRecordIds || []).includes(Number(link.excelRecordId))) || null;
}

function selectParagraph(paragraph) {
  activeWordRecordId.value = null;
  const targetSheet = String(paragraph.sheet || "");
  if (targetSheet && targetSheet !== activeSheet.value) {
    activeSheet.value = targetSheet;
  }
  if (paragraph.isSheetTitle) {
    return;
  }
  const link = findPreferredLinkForParagraph(paragraph);
  if (link) {
    focusLink(link.compareLinkId);
    return;
  }
  const fallbackWordRecordId = Number((paragraph.wordRecordIds || [])[0] || 0);
  if (fallbackWordRecordId) {
    focusWordRecord(fallbackWordRecordId);
  }
}

function selectExcelRow(row) {
  activeWordRecordId.value = null;
  const link = findPreferredLinkForRow(row);
  if (link) {
    focusLink(link.compareLinkId);
  }
}

function isParagraphActive(paragraph) {
  if (Boolean(currentActiveLink.value)) {
    return (paragraph.wordRecordIds || []).includes(Number(currentActiveLink.value.wordRecordId));
  }
  return (paragraph.wordRecordIds || []).includes(Number(activeWordRecordId.value));
}

function isParagraphException(paragraph) {
  return Boolean(paragraph.tag);
}

function isParagraphBalanceOnly(paragraph) {
  const names = String(paragraph.tag || "")
    .split("|")
    .map((name) => name.trim())
    .filter(Boolean);
  return names.length > 0 && names.every((name) => balanceMissingExceptionNames.has(name));
}

function isExcelRowActive(row) {
  return currentDrawLinks.value.some((link) => (row.excelRecordIds || []).includes(Number(link.excelRecordId)));
}

function handleScroll() {
  drawConnections();
}

function setWordNodeRef(wordRecordIds, element) {
  for (const wordRecordId of wordRecordIds || []) {
    if (element) {
      wordRecordNodeRefs.set(Number(wordRecordId), element);
    } else {
      wordRecordNodeRefs.delete(Number(wordRecordId));
    }
  }
}

function setExcelMarkerRef(excelRecordIds, element) {
  for (const excelRecordId of excelRecordIds || []) {
    if (element) {
      excelRecordMarkerRefs.set(Number(excelRecordId), element);
    } else {
      excelRecordMarkerRefs.delete(Number(excelRecordId));
    }
  }
}

function setExcelRowRef(excelRecordIds, element) {
  for (const excelRecordId of excelRecordIds || []) {
    if (element) {
      excelRecordRowRefs.set(Number(excelRecordId), element);
    } else {
      excelRecordRowRefs.delete(Number(excelRecordId));
    }
  }
}

watch(
  () => props.detail,
  (detail) => {
    activeSheet.value = detail.excelSheets?.[0]?.sheet || "";
    activeLinkId.value = null;
  },
  { immediate: true },
);

watch(
  [activeSheet, visibleMatchedLinks, activeWordRecordId],
  ([sheet, links, wordRecordId]) => {
    const activeLink = links.find((item) => Number(item.compareLinkId) === Number(activeLinkId.value));
    if (!sheet || !links.length) {
      activeLinkId.value = null;
      return;
    }
    if (!activeLink) {
      if (activeLinkId.value === null && Number(wordRecordId || 0) > 0) {
        return;
      }
      activeLinkId.value = Number(links[0].compareLinkId);
    }
  },
  { immediate: true },
);

watch(
  [activeSheet, activeLinkId, currentSheet, currentWordDocument, visibleMatchedLinks],
  async () => {
    await nextTick();
    updateExcelHeaderStickyOffsets();
    syncActiveNodes();
    drawConnections();
  },
  { immediate: true },
);

function handleResize() {
  updateExcelHeaderStickyOffsets();
  drawConnections();
}

onMounted(() => {
  window.addEventListener("resize", handleResize);
  nextTick(() => {
    updateExcelHeaderStickyOffsets();
    syncActiveNodes();
    drawConnections();
  });
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
});

watch(
  [currentActiveLink, activeWordRecordId],
  ([activeLink, wordRecordId]) => {
    emit("active-record-change", {
      wordRecordId: activeLink ? Number(activeLink.wordRecordId) : Number(wordRecordId || 0),
      compareLinkId: activeLink ? Number(activeLink.compareLinkId) : null,
      sheet: activeLink ? String(activeLink.wordSheet || activeLink.excelSheet || "") : String(activeSheet.value || ""),
    });
  },
  { immediate: true },
);

defineExpose({
  focusByExceptionItem,
});
</script>

<template>
  <section class="compare-workspace">
    <div ref="compareStageRef" class="compare-doc-stage">
      <article class="doc-panel">
        <div class="doc-panel-header">
          <h3>Word</h3>
          <span>{{ currentWordDocument.fileName || detail.title }}</span>
        </div>
        <div ref="wordScrollRef" class="document-scroll word-document-scroll" @scroll="handleScroll">
          <div v-if="currentWordDocument.paragraphs.length" class="word-paper">
            <div class="word-paper-content">
              <button
                v-for="paragraph in currentWordDocument.paragraphs"
                :key="paragraph.id"
                type="button"
                class="word-paragraph"
                :style="getParagraphColorStyle(paragraph)"
                :class="{
                  active: isParagraphActive(paragraph),
                  'has-exception': isParagraphException(paragraph),
                  'balance-missing-exception': isParagraphBalanceOnly(paragraph),
                  'sheet-title': paragraph.isSheetTitle,
                }"
                :ref="(element) => setWordNodeRef(paragraph.wordRecordIds, element)"
                @click="selectParagraph(paragraph)"
              >
                <span class="word-paragraph-text">
                  <template
                    v-for="(segment, segmentIndex) in paragraph.textSegments || [{ text: paragraph.text, highlight: false }]"
                    :key="`${paragraph.id}-${segmentIndex}`"
                  >
                    <span
                      :class="{
                        'word-inline-highlight': segment.highlight,
                        'word-inline-highlight--format': segment.highlight && segment.highlightVariant === 'format',
                        'word-inline-highlight--company-name': segment.highlight && segment.highlightVariant === 'company-name',
                      }"
                      :style="getSegmentColorStyle(segment)"
                    >
                      {{ segment.text }}
                    </span>
                  </template>
                </span>
              </button>
            </div>
          </div>
          <div v-else class="flex-1 flex items-center justify-center text-slate-400 text-sm">暂无 Word 数据</div>
        </div>
      </article>

      <article class="doc-panel excel-panel">
        <div class="doc-panel-header">
          <h3>Excel</h3>
          <div class="doc-panel-actions">
            <span>{{ detail.excelFileName || "Excel" }}</span>
            <select v-model="activeSheet" class="sheet-select border border-slate-300 rounded-md px-2 py-1 text-xs bg-white text-slate-700 focus:outline-none focus:border-blue-400">
              <option v-for="item in sheetOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </div>
        </div>
        <div ref="excelScrollRef" class="document-scroll excel-document-scroll" @scroll="handleScroll">
          <div v-if="currentSheet" class="excel-sheet">
            <div class="excel-table-wrap">
              <table class="excel-table">
                <thead>
                  <tr class="excel-sheet-title-row">
                    <th class="excel-row-header excel-corner" rowspan="2"></th>
                    <th
                      v-for="(columnLabel, columnIndex) in currentSheet.columnLabels"
                      :key="`sheet-title-${columnIndex}`"
                      :class="{ 'excel-code-col': columnIndex === currentSheet.codeColumnIndex }"
                    >
                      {{ columnIndex === 0 ? currentSheet.sheet : "" }}
                    </th>
                  </tr>
                  <tr class="excel-column-label-row">
                    <th
                      v-for="(columnLabel, columnIndex) in currentSheet.columnLabels"
                      :key="`column-${columnIndex}`"
                      :class="{ 'excel-code-col': columnIndex === currentSheet.codeColumnIndex }"
                    >
                      {{ columnLabel }}
                    </th>
                  </tr>
                  <tr
                    v-for="headerRow in currentSheet.headerRows"
                    :key="headerRow.id"
                    class="excel-content-header-row"
                  >
                    <th class="excel-row-header">{{ headerRow.rowIndex }}</th>
                    <th
                      v-for="(cell, cellIndex) in headerRow.cells"
                      :key="`${headerRow.id}-${cellIndex}-${cell.colIndex}`"
                      :colspan="cell.colspan"
                      :rowspan="cell.rowspan"
                      :class="{ 'excel-code-col': cell.colIndex - 1 === currentSheet.codeColumnIndex }"
                    >
                      {{ cell.text }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in currentSheet.rows"
                    :key="row.id"
                    class="excel-row"
                    :style="getExcelRowColorStyle(row)"
                    :class="{
                      active: isExcelRowActive(row),
                      'has-exception': row.hasException,
                      'balance-missing-exception': row.hasOnlyBalanceMissing,
                    }"
                    :ref="(element) => setExcelRowRef(row.excelRecordIds, element)"
                    @click="selectExcelRow(row)"
                  >
                    <th
                      class="excel-row-header"
                      :class="{ 'excel-row-header-marker-cell': row.excelRecordIds.length > 0 }"
                    >
                      <span
                        v-if="row.excelRecordIds.length > 0"
                        class="excel-node-marker excel-row-header-marker"
                        :class="{
                          active: isExcelRowActive(row),
                          'has-exception': row.hasException,
                          'balance-missing-exception': row.hasOnlyBalanceMissing,
                        }"
                        :ref="(element) => setExcelMarkerRef(row.excelRecordIds, element)"
                      ></span>
                      {{ row.rowIndex }}
                    </th>
                    <td
                      v-for="(cell, cellIndex) in row.cells"
                      :key="`${row.id}-${cellIndex}-${cell.colIndex}`"
                      :colspan="cell.colspan"
                      :rowspan="cell.rowspan"
                      :class="{
                        'excel-code-col': cell.colIndex - 1 === currentSheet.codeColumnIndex,
                      }"
                    >
                      {{ cell.text }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="flex-1 flex items-center justify-center text-slate-400 text-sm">暂无 Excel 数据</div>
        </div>
      </article>

      <svg ref="lineCanvasRef" class="line-canvas" aria-hidden="true"></svg>
    </div>
  </section>
</template>
