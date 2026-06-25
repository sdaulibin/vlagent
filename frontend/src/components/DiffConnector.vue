<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { isPairedDiff } from "../utils/diffUtils";
import type { DiffRecord, ScrollLinkMode } from "../types";

export interface PaneConnectorApi {
  getHighlightAnchor: (diffId: string) => DOMRect | null;
  getScrollElement: () => HTMLElement | null;
  getScrollRatio: () => number;
  setScrollRatio: (ratio: number) => void;
}

const props = defineProps<{
  activeDiff: DiffRecord | null;
  paneA: PaneConnectorApi | null;
  paneB: PaneConnectorApi | null;
  containerEl: HTMLElement | null;
  scrollLinkMode: ScrollLinkMode;
}>();

const pathD = ref("");
const startPoint = ref({ x: 0, y: 0 });
const endPoint = ref({ x: 0, y: 0 });
const svgSize = ref({ width: 0, height: 0 });

const showConnector = computed(
  () => props.activeDiff !== null && isPairedDiff(props.activeDiff)
);

const isAnchorVisible = (
  anchorX: number,
  anchorY: number,
  scrollEl: HTMLElement | null
): boolean => {
  if (!scrollEl) return true;
  const viewport = scrollEl.getBoundingClientRect();
  return (
    anchorX >= viewport.left &&
    anchorX <= viewport.right &&
    anchorY >= viewport.top &&
    anchorY <= viewport.bottom
  );
};

const paintConnector = (): boolean => {
  if (!showConnector.value || !props.containerEl || !props.activeDiff || !props.paneA || !props.paneB) {
    pathD.value = "";
    return false;
  }

  const containerRect = props.containerEl.getBoundingClientRect();
  svgSize.value = { width: containerRect.width, height: containerRect.height };

  const rectA = props.paneA.getHighlightAnchor(props.activeDiff.diff_id);
  const rectB = props.paneB.getHighlightAnchor(props.activeDiff.diff_id);
  if (!rectA || !rectB) {
    pathD.value = "";
    return false;
  }

  const anchorX_A = rectA.right;
  const anchorY_A = rectA.top + rectA.height / 2;
  const anchorX_B = rectB.left;
  const anchorY_B = rectB.top + rectB.height / 2;

  if (props.scrollLinkMode === "independent") {
    const visibleA = isAnchorVisible(anchorX_A, anchorY_A, props.paneA.getScrollElement());
    const visibleB = isAnchorVisible(anchorX_B, anchorY_B, props.paneB.getScrollElement());
    if (!visibleA || !visibleB) {
      pathD.value = "";
      return false;
    }
  }

  const x1 = anchorX_A - containerRect.left;
  const y1 = anchorY_A - containerRect.top;
  const x2 = anchorX_B - containerRect.left;
  const y2 = anchorY_B - containerRect.top;
  const cx1 = x1 + (x2 - x1) * 0.35;
  const cx2 = x1 + (x2 - x1) * 0.65;

  startPoint.value = { x: x1, y: y1 };
  endPoint.value = { x: x2, y: y2 };
  pathD.value = `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`;
  return true;
};

const updateConnector = async (retries = 12): Promise<void> => {
  await nextTick();
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      const painted = paintConnector();
      if (!painted && retries > 0) {
        window.setTimeout(() => {
          void updateConnector(retries - 1).then(resolve);
        }, 80);
        return;
      }
      resolve();
    });
  });
};

type ListenerTarget = HTMLElement | Window;
const listeners: Array<{ target: ListenerTarget; type: string; handler: () => void }> = [];
let rafScheduled = false;

const scheduleUpdate = (): void => {
  if (rafScheduled) return;
  rafScheduled = true;
  requestAnimationFrame(() => {
    rafScheduled = false;
    void updateConnector(4);
  });
};

const unbindListeners = (): void => {
  for (const { target, type, handler } of listeners) {
    target.removeEventListener(type, handler);
  }
  listeners.length = 0;
};

const bindListeners = (): void => {
  unbindListeners();

  window.addEventListener("resize", scheduleUpdate);
  listeners.push({ target: window, type: "resize", handler: scheduleUpdate });

  for (const pane of [props.paneA, props.paneB]) {
    const scrollEl = pane?.getScrollElement();
    if (!scrollEl) continue;
    scrollEl.addEventListener("scroll", scheduleUpdate, { passive: true });
    listeners.push({ target: scrollEl, type: "scroll", handler: scheduleUpdate });
  }
};

const rebindListeners = async (retries = 10): Promise<void> => {
  await nextTick();
  bindListeners();
  if (!listeners.some(({ type }) => type === "scroll") && retries > 0) {
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, 80);
    });
    await rebindListeners(retries - 1);
    return;
  }
  void updateConnector();
};

watch(
  () => props.activeDiff?.diff_id ?? null,
  () => {
    void rebindListeners();
  }
);

watch(
  () => props.scrollLinkMode,
  () => {
    void updateConnector();
  }
);

watch(
  () => [props.paneA, props.paneB, props.containerEl],
  () => {
    void rebindListeners();
  }
);

onMounted(() => {
  void rebindListeners();
});

onBeforeUnmount(() => {
  unbindListeners();
});

defineExpose({ updateConnector, scheduleUpdate, rebindListeners });
</script>

<template>
  <svg
    v-if="showConnector && pathD"
    class="diff-connector"
    :width="svgSize.width"
    :height="svgSize.height"
  >
    <path :d="pathD" class="diff-connector-line" />
    <circle :cx="startPoint.x" :cy="startPoint.y" r="4" class="diff-connector-dot diff-connector-dot--a" />
    <circle :cx="endPoint.x" :cy="endPoint.y" r="4" class="diff-connector-dot diff-connector-dot--b" />
  </svg>
</template>
