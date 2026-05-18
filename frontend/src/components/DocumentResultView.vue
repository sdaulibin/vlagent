<script setup lang="ts">
import { computed, ref, shallowRef, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { ChevronLeft, ChevronRight, ArrowLeft } from 'lucide-vue-next';
import { api } from '../api';
import type { PageDiff } from '../types';
import * as pdfjsLib from 'pdfjs-dist';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

interface Props {
  taskId: number;
  fileAName: string;
  fileBName: string;
  fileAPageCount: number | null;
  fileBPageCount: number | null;
  status: string;
  errorMsg: string | null;
  comparisonDuration: number | null;
  pages: PageDiff[];
}

const props = defineProps<Props>();
const emit = defineEmits<{ (e: 'back'): void }>();

const currentPageIndex = ref(0);
const filter = ref('all');
const pdfLoading = ref(false);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const pdfDocA = shallowRef<any>(null);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const pdfDocB = shallowRef<any>(null);

const containerA = ref<HTMLDivElement | null>(null);
const containerB = ref<HTMLDivElement | null>(null);
const canvasA = ref<HTMLCanvasElement | null>(null);
const canvasB = ref<HTMLCanvasElement | null>(null);
const highlightA = ref<HTMLDivElement | null>(null);
const highlightB = ref<HTMLDivElement | null>(null);

const filteredPages = computed(() => {
  if (filter.value === 'all') return props.pages;
  return props.pages.filter(p => p.diff_type === filter.value);
});

const currentPage = computed(() => {
  return filteredPages.value[currentPageIndex.value] || null;
});

const stats = computed(() => {
  const all = props.pages.length;
  const modified = props.pages.filter(p => p.diff_type === 'modified').length;
  const added = props.pages.filter(p => p.diff_type === 'added').length;
  const deleted = props.pages.filter(p => p.diff_type === 'deleted').length;
  const equal = props.pages.filter(p => p.diff_type === 'equal').length;
  return { all, modified, added, deleted, equal };
});

// 预解析所有页面的 diff_ops_json，避免模板中重复 JSON.parse
const parsedDiffOpsMap = computed(() => {
  const map = new Map<number, ReturnType<typeof parseDiffOps>>();
  for (const page of props.pages) {
    map.set(page.id, parseDiffOps(page.diff_ops_json));
  }
  return map;
});

const hasPrev = computed(() => currentPageIndex.value > 0);
const hasNext = computed(() => currentPageIndex.value < filteredPages.value.length - 1);

const goPrev = () => { if (hasPrev.value) currentPageIndex.value--; };
const goNext = () => { if (hasNext.value) currentPageIndex.value++; };

const goToPage = (index: number) => {
  currentPageIndex.value = index;
};

// ---- PDF loading ----

async function loadPdf(docType: 'a' | 'b') {
  const response = await api.post(
    `/documents/${props.taskId}/file/${docType}`,
    {},
    { responseType: 'arraybuffer' }
  );
  const data = new Uint8Array(response.data);
  return pdfjsLib.getDocument({ data }).promise;
}

async function loadPdfs() {
  pdfLoading.value = true;

  try {
    const [docA, docB] = await Promise.all([loadPdf('a'), loadPdf('b')]);
    pdfDocA.value = docA;
    pdfDocB.value = docB;
  } catch (e) {
    console.error('Failed to load PDFs:', e);
  }

  pdfLoading.value = false;
}

// ---- PDF page rendering with highlight ----

async function renderPdfPage(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfDoc: any,
  pageNum: number,
  canvasEl: HTMLCanvasElement,
  highlightEl: HTMLDivElement,
  containerEl: HTMLDivElement,
  diffOps: { op: number; text: string }[],
  side: 'a' | 'b'
) {
  const page = await pdfDoc.getPage(pageNum);
  const baseViewport = page.getViewport({ scale: 1 });
  const containerWidth = containerEl.clientWidth - 32;
  const scale = containerWidth / baseViewport.width;
  const viewport = page.getViewport({ scale });

  // HiDPI canvas
  const dpr = window.devicePixelRatio || 1;
  canvasEl.width = Math.floor(viewport.width * dpr);
  canvasEl.height = Math.floor(viewport.height * dpr);
  canvasEl.style.width = `${Math.floor(viewport.width)}px`;
  canvasEl.style.height = `${Math.floor(viewport.height)}px`;

  const ctx = canvasEl.getContext('2d')!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  await page.render({ canvasContext: ctx, viewport }).promise;

  // Clear highlight layer
  highlightEl.innerHTML = '';
  highlightEl.style.width = `${viewport.width}px`;
  highlightEl.style.height = `${viewport.height}px`;

  // Get text content items with positions
  const textContent = await page.getTextContent();
  const allItems: { str: string; transform: number[]; width: number }[] = [];
  for (let i = 0; i < textContent.items.length; i++) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const raw = textContent.items[i] as any;
    if (raw.str && raw.str.trim()) {
      allItems.push({ str: raw.str, transform: raw.transform, width: raw.width });
    }
  }

  const targetOp = side === 'a' ? -1 : 1;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const segments = (diffOps as any[]).filter(d => d.op === targetOp && d.text && d.text.trim());

  if (allItems.length === 0 || segments.length === 0) return;

  // Sort items into reading order: top-to-bottom (PDF Y descending), left-to-right (X ascending)
  allItems.sort((a, b) => {
    const ay = a.transform[5]!;
    const by = b.transform[5]!;
    if (Math.abs(ay - by) > 3) return by - ay;
    return a.transform[4]! - b.transform[4]!;
  });

  // Build stripped text — matches backend's _strip_all_whitespace
  // Track original char position within each text item for precise highlighting
  let normText = '';
  const charMap: { itemIdx: number; charInItem: number }[] = [];
  for (let i = 0; i < allItems.length; i++) {
    const item = allItems[i];
    if (!item) continue;
    const str = item.str;
    for (let c = 0; c < str.length; c++) {
      const ch = str[c];
      if (!ch || /\s/.test(ch)) continue;
      charMap.push({ itemIdx: i, charInItem: c });
      normText += ch;
    }
  }

  const offsetKey = side === 'a' ? 'offsetA' : 'offsetB';
  const bgColor = side === 'a' ? 'rgba(239,68,68,0.35)' : 'rgba(34,197,94,0.35)';
  let totalMatches = 0;

  // Collect highlighted character positions per text item
  const itemCharPositions = new Map<number, number[]>();

  for (const seg of segments as any[]) {
    const segNorm = seg.text.replace(/\s/g, '');
    if (!segNorm) continue;

    const expectedOffset: number = seg[offsetKey] ?? 0;

    // Find all occurrences, pick the one closest to the backend offset
    let bestIdx = -1;
    let bestDist = Infinity;
    let searchFrom = 0;
    while (searchFrom < normText.length) {
      const idx = normText.indexOf(segNorm, searchFrom);
      if (idx === -1) break;
      const dist = Math.abs(idx - expectedOffset);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = idx;
      }
      searchFrom = idx + 1;
    }

    if (bestIdx === -1) continue;

    // Record each matched character's original position within its text item
    const endIdx = bestIdx + segNorm.length;
    for (let c = bestIdx; c < endIdx && c < charMap.length; c++) {
      const entry = charMap[c];
      if (!entry) continue;
      const { itemIdx, charInItem } = entry;
      if (!itemCharPositions.has(itemIdx)) {
        itemCharPositions.set(itemIdx, []);
      }
      itemCharPositions.get(itemIdx)!.push(charInItem);
    }
  }

  // Render character-precise highlight rectangles
  for (const [itemIdx, chars] of itemCharPositions) {
    const item = allItems[itemIdx];
    if (!item) continue;
    const tx = item.transform;
    const [vx, vy] = viewport.convertToViewportPoint(tx[4]!, tx[5]!);
    const fontSize = Math.sqrt(tx[0]! ** 2 + tx[1]! ** 2) * viewport.scale;
    const fullW = Math.abs(item.width || fontSize * item.str.length * 0.6) * viewport.scale;
    const h = fontSize * 1.3;
    const strLen = item.str.length;
    if (strLen === 0 || fullW < 1 || h < 1 || chars.length === 0) continue;

    // Sort positions and find contiguous ranges
    chars.sort((a, b) => a - b);
    const ranges: [number, number][] = [];
    let rs = chars[0]!, re = chars[0]!;
    for (let i = 1; i < chars.length; i++) {
      const c = chars[i]!;
      if (c <= re + 1) {
        re = c;
      } else {
        ranges.push([rs, re]);
        rs = c;
        re = c;
      }
    }
    ranges.push([rs, re]);

    // Create a highlight rectangle for each contiguous range
    for (const [start, end] of ranges) {
      const left = vx + (start / strLen) * fullW;
      const width = ((end - start + 1) / strLen) * fullW;
      if (width < 1) continue;
      const rect = document.createElement('div');
      rect.style.cssText = `position:absolute;left:${left}px;top:${vy - h}px;width:${width}px;height:${h}px;background:${bgColor};border-radius:2px;`;
      highlightEl.appendChild(rect);
      totalMatches++;
    }
  }
}

// ---- Render current page ----

async function renderCurrentPage() {
  const page = currentPage.value;
  if (!page) return;

  const diffOps = parseDiffOps(page.diff_ops_json);

  const renderA = async () => {
    if (!pdfDocA.value || !page!.page_a || !canvasA.value || !highlightA.value || !containerA.value) return;
    await renderPdfPage(pdfDocA.value, page!.page_a, canvasA.value, highlightA.value, containerA.value, diffOps, 'a');
  };

  const renderB = async () => {
    if (!pdfDocB.value || !page!.page_b || !canvasB.value || !highlightB.value || !containerB.value) return;
    await renderPdfPage(pdfDocB.value, page!.page_b, canvasB.value, highlightB.value, containerB.value, diffOps, 'b');
  };

  await Promise.all([renderA(), renderB()]);
}

// ---- Parse diff ops ----

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parseDiffOps(json: string | null): any[] {
  if (!json) return [];
  try {
    const raw = JSON.parse(json);
    if (!Array.isArray(raw)) return [];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return raw.map((item: any) => {
      if (Array.isArray(item)) {
        const entry: Record<string, any> = { op: item[0] as number, text: item[1] as string };
        if (item.length >= 4) {
          entry.offsetA = item[2] as number;
          entry.offsetB = item[3] as number;
        }
        return entry;
      }
      return item;
    });
  } catch {
    return [];
  }
}

// ---- Watchers ----

watch(currentPageIndex, () => { nextTick(renderCurrentPage); });

watch(() => props.status, async (s) => {
  if (s === 'done') {
    await loadPdfs();
    nextTick(renderCurrentPage);
  }
});

watch(filter, () => { currentPageIndex.value = 0; });

onMounted(async () => {
  if (props.status === 'done') {
    await loadPdfs();
    nextTick(renderCurrentPage);
  }
});

onUnmounted(() => {
  pdfDocA.value?.destroy();
  pdfDocB.value?.destroy();
});

const typeLabel: Record<string, string> = {
  equal: '相同',
  modified: '有差异',
  added: '新增页',
  deleted: '删除页',
};

const typeBadgeClass: Record<string, string> = {
  equal: 'bg-slate-100 text-slate-600',
  modified: 'bg-orange-100 text-orange-700',
  added: 'bg-green-100 text-green-700',
  deleted: 'bg-red-100 text-red-700',
};
</script>

<template>
  <div class="document-result-container">
    <!-- 工具栏 -->
    <div class="document-toolbar">
      <div class="flex items-center gap-3">
        <button @click="emit('back')" class="flex items-center gap-1 text-slate-500 hover:text-slate-700 text-sm">
          <ArrowLeft class="w-4 h-4" /> 返回
        </button>
        <span class="text-slate-300">|</span>
        <span class="text-sm text-slate-600">{{ fileAName }}</span>
        <span class="text-slate-400 text-xs">vs</span>
        <span class="text-sm text-slate-600">{{ fileBName }}</span>
      </div>

      <div class="flex items-center gap-3">
        <span v-if="comparisonDuration" class="text-xs text-slate-400">耗时 {{ comparisonDuration }}s</span>
        <button @click="goPrev" :disabled="!hasPrev"
          class="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed">
          <ChevronLeft class="w-4 h-4" />
        </button>
        <span class="text-sm text-slate-600 min-w-[80px] text-center">
          {{ currentPage ? `第 ${currentPageIndex + 1} / ${filteredPages.length} 组` : '-' }}
        </span>
        <button @click="goNext" :disabled="!hasNext"
          class="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed">
          <ChevronRight class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- 主体 -->
    <div class="document-result-main">
      <!-- PDF 文档面板 -->
      <div class="document-doc-panes">
        <!-- 处理中 -->
        <template v-if="status === 'processing' || status === 'pending'">
          <div class="flex-1 flex items-center justify-center">
            <div class="text-center">
              <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500 mx-auto mb-3"></div>
              <p class="text-slate-500 text-sm">正在比对中...</p>
            </div>
          </div>
        </template>

        <!-- PDF 加载中 -->
        <template v-else-if="pdfLoading">
          <div class="flex-1 flex items-center justify-center">
            <div class="text-center">
              <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500 mx-auto mb-3"></div>
              <p class="text-slate-500 text-sm">正在加载文档...</p>
            </div>
          </div>
        </template>

        <!-- 文档内容 -->
        <template v-else-if="currentPage">
          <!-- 文档 A -->
          <div class="document-doc-pane">
            <div class="document-doc-header document-doc-header-original">
              <span class="document-doc-badge document-badge-original">原文档</span>
              <span v-if="currentPage.page_a" class="text-xs text-slate-500">第 {{ currentPage.page_a }} 页</span>
              <span v-else class="text-xs text-slate-400">-</span>
            </div>
            <div ref="containerA" class="document-doc-content" style="overflow:auto;display:flex;justify-content:center;align-items:flex-start;padding:16px;background:#f8fafc;">
              <template v-if="currentPage.diff_type === 'added'">
                <div class="flex items-center justify-center h-full text-slate-400 text-sm">
                  比对文档新增页，原文档中无对应内容
                </div>
              </template>
              <template v-else-if="pdfDocA">
                <div style="position:relative;display:inline-block;line-height:1;box-shadow:0 1px 3px rgba(0,0,0,0.12);border-radius:2px;">
                  <canvas ref="canvasA" />
                  <div ref="highlightA" style="position:absolute;top:0;left:0;pointer-events:none;z-index:10;"></div>
                </div>
              </template>
            </div>
          </div>

          <!-- 文档 B -->
          <div class="document-doc-pane">
            <div class="document-doc-header document-doc-header-compare">
              <span class="document-doc-badge document-badge-compare">比对文档</span>
              <span v-if="currentPage.page_b" class="text-xs text-slate-500">第 {{ currentPage.page_b }} 页</span>
              <span v-else class="text-xs text-slate-400">-</span>
            </div>
            <div ref="containerB" class="document-doc-content" style="overflow:auto;display:flex;justify-content:center;align-items:flex-start;padding:16px;background:#f8fafc;">
              <template v-if="currentPage.diff_type === 'deleted'">
                <div class="flex items-center justify-center h-full text-slate-400 text-sm">
                  原文档页面已删除，比对文档中无对应内容
                </div>
              </template>
              <template v-else-if="pdfDocB">
                <div style="position:relative;display:inline-block;line-height:1;box-shadow:0 1px 3px rgba(0,0,0,0.12);border-radius:2px;">
                  <canvas ref="canvasB" />
                  <div ref="highlightB" style="position:absolute;top:0;left:0;pointer-events:none;z-index:10;"></div>
                </div>
              </template>
            </div>
          </div>
        </template>

        <!-- 失败 -->
        <template v-else-if="status === 'failed'">
          <div class="flex-1 flex items-center justify-center">
            <p class="text-red-500 text-sm">{{ errorMsg || '比对失败' }}</p>
          </div>
        </template>
      </div>

      <!-- 差异侧边栏 -->
      <div class="document-diff-sidebar">
        <div class="p-4 border-b border-slate-100">
          <h3 class="text-sm font-semibold text-slate-700 mb-3">比对结果</h3>
          <div class="grid grid-cols-2 gap-2 text-center">
            <div class="bg-slate-50 rounded-lg p-2">
              <div class="text-lg font-bold text-slate-700">{{ stats.all }}</div>
              <div class="text-xs text-slate-400">总页数</div>
            </div>
            <div class="bg-orange-50 rounded-lg p-2">
              <div class="text-lg font-bold text-orange-600">{{ stats.modified }}</div>
              <div class="text-xs text-orange-400">有差异</div>
            </div>
          </div>
        </div>

        <div class="flex gap-1 p-2 bg-slate-50 mx-4 my-3 rounded-lg">
          <button v-for="f in ['all', 'modified', 'added', 'deleted']" :key="f"
            @click="filter = f"
            :class="['document-filter-tab', { active: filter === f }]">
            {{ f === 'all' ? '全部' : f === 'modified' ? '差异' : f === 'added' ? '新增' : '删除' }}
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
          <div
            v-for="(page, idx) in filteredPages"
            :key="page.id"
            @click="goToPage(idx)"
            :class="[
              'diff-item cursor-pointer rounded-lg border p-2.5 transition-colors',
              idx === currentPageIndex ? 'border-orange-300 bg-orange-50/50' : 'border-transparent hover:bg-slate-50'
            ]"
          >
            <div class="flex items-center gap-2 mb-1">
              <span :class="['diff-badge text-xs px-1.5 py-0.5 rounded font-medium', typeBadgeClass[page.diff_type]]">{{ typeLabel[page.diff_type] }}</span>
              <span class="text-xs text-slate-400">
                <template v-if="page.page_a && page.page_b">A:{{ page.page_a }} / B:{{ page.page_b }}</template>
                <template v-else-if="page.page_a">A:{{ page.page_a }}</template>
                <template v-else>B:{{ page.page_b }}</template>
              </span>
            </div>

            <template v-if="page.diff_type === 'modified' && page.diff_ops_json">
              <div class="text-xs leading-relaxed mt-1.5 line-clamp-3">
                <template v-for="(seg, si) in parsedDiffOpsMap.get(page.id) || []" :key="si">
                  <span v-if="seg.op === -1" class="diff-text-del">{{ seg.text }}</span>
                  <span v-else-if="seg.op === 1" class="diff-text-ins">{{ seg.text }}</span>
                  <span v-else class="text-slate-400">{{ seg.text }}</span>
                </template>
              </div>
            </template>

            <p v-else-if="page.diff_type === 'equal'" class="text-xs text-slate-400 mt-1">页面内容一致</p>
            <p v-else-if="page.diff_type === 'added'" class="text-xs text-green-600 mt-1">比对文档中新增的页面</p>
            <p v-else-if="page.diff_type === 'deleted'" class="text-xs text-red-600 mt-1">原文档中已删除的页面</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* PDF viewer */
.document-pdf-content {
  overflow-y: auto;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 16px;
}

.document-pdf-page {
  position: relative;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.06);
  border-radius: 2px;
  line-height: 1;
}

.pdf-highlight-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 1;
}

.pdf-highlight-layer .pdf-highlight-del {
  position: absolute;
  background-color: rgba(254, 202, 202, 0.5);
  border-radius: 2px;
}

.pdf-highlight-layer .pdf-highlight-ins {
  position: absolute;
  background-color: rgba(187, 247, 208, 0.5);
  border-radius: 2px;
}

/* Sidebar diff text */
.diff-text-del {
  background: #fca5a5;
  text-decoration: line-through;
  text-decoration-color: #dc2626;
  border-radius: 2px;
  padding: 0 1px;
}

.diff-text-ins {
  background: #86efac;
  border-radius: 2px;
  padding: 0 1px;
}
</style>
