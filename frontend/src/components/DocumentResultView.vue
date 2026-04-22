<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { ChevronLeft, ChevronRight, ArrowLeft } from 'lucide-vue-next';
import DiffTextView from './DiffTextView.vue';

interface PageDiff {
  id: number;
  page_a: number | null;
  page_b: number | null;
  diff_type: string;
  text_a: string | null;
  text_b: string | null;
  diff_ops_json: string | null;
}

interface Props {
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

const emit = defineEmits<{
  (e: 'back'): void;
}>();

const currentPageIndex = ref(0);
const filter = ref('all');
const syncScroll = ref(true);
const docContentA = ref<HTMLDivElement | null>(null);
const docContentB = ref<HTMLDivElement | null>(null);

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

const hasPrev = computed(() => currentPageIndex.value > 0);
const hasNext = computed(() => currentPageIndex.value < filteredPages.value.length - 1);

const goPrev = () => { if (hasPrev.value) currentPageIndex.value--; };
const goNext = () => { if (hasNext.value) currentPageIndex.value++; };

const goToPage = (index: number) => {
  currentPageIndex.value = index;
};

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

// 同步滚动
const handleScrollA = () => {
  if (!syncScroll.value || !docContentA.value || !docContentB.value) return;
  const ratio = docContentA.value.scrollTop / (docContentA.value.scrollHeight - docContentA.value.clientHeight || 1);
  docContentB.value.scrollTop = ratio * (docContentB.value.scrollHeight - docContentB.value.clientHeight);
};
const handleScrollB = () => {
  if (!syncScroll.value || !docContentA.value || !docContentB.value) return;
  const ratio = docContentB.value.scrollTop / (docContentB.value.scrollHeight - docContentB.value.clientHeight || 1);
  docContentA.value.scrollTop = ratio * (docContentA.value.scrollHeight - docContentA.value.clientHeight);
};

// 切换过滤时重置页码
watch(filter, () => { currentPageIndex.value = 0; });
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
          {{ currentPage ? `第 ${currentPageIndex + 1} / ${filteredPages.length} 页` : '-' }}
        </span>
        <button @click="goNext" :disabled="!hasNext"
          class="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed">
          <ChevronRight class="w-4 h-4" />
        </button>

        <button @click="syncScroll = !syncScroll"
          :class="['document-sync-btn', { active: syncScroll }]">
          同步滚动
        </button>
      </div>
    </div>

    <!-- 主体 -->
    <div class="document-result-main">
      <!-- 文档面板 -->
      <div class="document-doc-panes">
        <template v-if="currentPage">
        <!-- 文档 A -->
        <div class="document-doc-pane">
          <div class="document-doc-header document-doc-header-original">
            <span class="document-doc-badge document-badge-original">原文档</span>
            <span v-if="currentPage.page_a" class="text-xs text-slate-500">第 {{ currentPage.page_a }} 页</span>
            <span v-else class="text-xs text-slate-400">-</span>
          </div>
          <div ref="docContentA" @scroll="handleScrollA" class="document-doc-content">
            <template v-if="currentPage.diff_type === 'added'">
              <div class="flex items-center justify-center h-full text-slate-400 text-sm">
                比对文档新增页，原文档中无对应内容
              </div>
            </template>
            <template v-else-if="currentPage.diff_type === 'equal'">
              <div class="text-slate-500">{{ currentPage.text_a || '（空白页）' }}</div>
            </template>
            <template v-else>
              <DiffTextView
                :diff-ops-json="currentPage.diff_ops_json"
                :raw-text="currentPage.text_a"
                side="a" />
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
          <div ref="docContentB" @scroll="handleScrollB" class="document-doc-content">
            <template v-if="currentPage.diff_type === 'deleted'">
              <div class="flex items-center justify-center h-full text-slate-400 text-sm">
                原文档页面已删除，比对文档中无对应内容
              </div>
            </template>
            <template v-else-if="currentPage.diff_type === 'equal'">
              <div class="text-slate-500">{{ currentPage.text_b || '（空白页）' }}</div>
            </template>
            <template v-else>
              <DiffTextView
                :diff-ops-json="currentPage.diff_ops_json"
                :raw-text="currentPage.text_b"
                side="b" />
            </template>
          </div>
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
              'diff-item cursor-pointer',
              idx === currentPageIndex ? 'border-orange-300 bg-orange-50/30' : ''
            ]"
          >
            <div class="flex items-center gap-2 mb-1">
              <span :class="['diff-badge', typeBadgeClass[page.diff_type]]">{{ typeLabel[page.diff_type] }}</span>
              <span class="text-xs text-slate-400">
                <template v-if="page.page_a && page.page_b">A:{{ page.page_a }} / B:{{ page.page_b }}</template>
                <template v-else-if="page.page_a">A:{{ page.page_a }}</template>
                <template v-else>B:{{ page.page_b }}</template>
              </span>
            </div>
            <p v-if="page.diff_type === 'modified' && page.diff_ops_json" class="text-xs text-slate-500 truncate">
              页面内容有修改
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
