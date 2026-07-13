<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { ChevronDown, ChevronRight } from "lucide-vue-next";
import { buildExceptionColorStyle } from "../utils/exceptionColors";

const props = defineProps({
  groups: {
    type: Array,
    default: () => [],
  },
  activeItemKey: {
    type: String,
    default: "",
  },
  activeWordRecordId: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits(["select-item"]);
const itemElementRefs = new Map();
const expandedGroupNames = ref([]);

function buildItemKey(item) {
  if (item?.itemKey) {
    return String(item.itemKey);
  }
  return `${item.id}-${item.wordRecordId}-${item.sheet}-${item.code}`;
}

function setItemRef(item, element) {
  const key = buildItemKey(item);
  if (element) {
    itemElementRefs.set(key, element);
  } else {
    itemElementRefs.delete(key);
  }
}

function handleSelectItem(item) {
  emit("select-item", item);
}

function isItemActive(item) {
  if (props.activeItemKey && props.activeItemKey === buildItemKey(item)) {
    return true;
  }
  return Number(props.activeWordRecordId || 0) > 0 && Number(item.wordRecordId) === Number(props.activeWordRecordId);
}

function isCompanyExceptionGroup(group) {
  const typeId = Number(group?.typeId || group?.type_id || 0);
  if (typeId === 13 || typeId === 15) {
    return false;
  }
  return Array.isArray(group?.companyGroups) && group.companyGroups.length > 0;
}

function getGroupColorStyle(group) {
  return buildExceptionColorStyle(group?.typeId, group?.typeName);
}

function resetExpandedGroups() {
  expandedGroupNames.value = [];
}

function isGroupExpanded(group) {
  return expandedGroupNames.value.includes(String(group.typeId));
}

function toggleGroup(group) {
  if (group.items.length === 0) {
    return;
  }
  const name = String(group.typeId);
  if (isGroupExpanded(group)) {
    expandedGroupNames.value = expandedGroupNames.value.filter((n) => n !== name);
  } else {
    expandedGroupNames.value = [...expandedGroupNames.value, name];
  }
}

function findActiveItemKey() {
  if (props.activeItemKey) {
    return props.activeItemKey;
  }
  for (const group of props.groups || []) {
    const sourceItems = isCompanyExceptionGroup(group)
      ? group.companyGroups.flatMap((companyGroup) => companyGroup.items || [])
      : group.items || [];
    const matchedItem = sourceItems.find((item) => Number(item.wordRecordId) === Number(props.activeWordRecordId || 0));
    if (matchedItem) {
      return buildItemKey(matchedItem);
    }
  }
  return "";
}

function findActiveGroupNames() {
  const groupNames = [];
  for (const group of props.groups || []) {
    const sourceItems = isCompanyExceptionGroup(group)
      ? group.companyGroups.flatMap((companyGroup) => companyGroup.items || [])
      : group.items || [];
    const hasMatchedItem = sourceItems.some((item) => {
      if (props.activeItemKey) {
        return buildItemKey(item) === props.activeItemKey;
      }
      return Number(props.activeWordRecordId || 0) > 0 && Number(item.wordRecordId) === Number(props.activeWordRecordId || 0);
    });
    if (hasMatchedItem) {
      groupNames.push(String(group.typeId));
    }
  }
  return [...new Set(groupNames)];
}

watch(
  () => [props.activeItemKey, props.activeWordRecordId, props.groups],
  async () => {
    const activeGroupNames = findActiveGroupNames();
    if (activeGroupNames.length) {
      expandedGroupNames.value = activeGroupNames;
    }
    await nextTick();
    const activeKey = findActiveItemKey();
    if (!activeKey) {
      return;
    }
    const element = itemElementRefs.get(activeKey);
    element?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  },
  { deep: true },
);

watch(
  () => props.groups,
  () => {
    resetExpandedGroups();
  },
  { immediate: true, deep: true },
);

defineExpose({
  resetExpandedGroups,
});
</script>

<template>
  <section class="flex flex-col h-full bg-white">
    <div class="px-4 py-4 border-b border-slate-100">
      <h2 class="m-0 text-base font-semibold text-slate-900">异常记录</h2>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-3 custom-scrollbar">
      <div v-for="group in groups" :key="group.typeId" class="mb-2" :style="getGroupColorStyle(group)">
        <!-- 折叠头 -->
        <button
          type="button"
          class="w-full flex items-center justify-between gap-3 px-2 py-3 text-left rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
          :disabled="group.items.length === 0"
          :class="{ 'opacity-50': group.items.length === 0 }"
          @click="toggleGroup(group)"
        >
          <span class="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            <component :is="isGroupExpanded(group) ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
            {{ group.typeName }}
          </span>
          <span
            class="text-xs px-2 py-0.5 rounded-full"
            :style="{
              borderColor: 'var(--exception-border-color)',
              color: 'var(--exception-text-color)',
              background: 'var(--exception-soft-color)',
            }"
          >
            {{ group.items.length }}
          </span>
        </button>

        <!-- 折叠内容 -->
        <div v-if="isGroupExpanded(group) && group.items.length" class="grid gap-2.5 px-1 pt-1 pb-2">
          <template v-if="isCompanyExceptionGroup(group)">
            <div
              v-for="companyGroup in group.companyGroups"
              :key="companyGroup.company"
              class="grid gap-2 p-2.5 border border-slate-200 rounded-xl bg-slate-50"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-sm font-semibold text-slate-900">{{ companyGroup.company }}</span>
                <span
                  class="text-xs px-2 py-0.5 rounded-full"
                  :style="getGroupColorStyle(group)"
                  :class="{ 'border': true }"
                  style="border-color: var(--exception-border-color); color: var(--exception-text-color); background: var(--exception-soft-color);"
                >
                  {{ companyGroup.entryCount }}
                </span>
              </div>
              <div class="grid gap-2">
                <button
                  v-for="item in companyGroup.items"
                  :key="item.itemKey || item.id"
                  type="button"
                  class="w-full p-2.5 border rounded-lg bg-white text-left cursor-pointer transition-colors hover:border-slate-300 hover:bg-slate-50"
                  :class="isItemActive(item) ? 'border-red-300 bg-red-50 shadow-[0_0_0_3px_rgba(239,68,68,0.12)]' : 'border-slate-200'"
                  :ref="(element) => setItemRef(item, element)"
                  @click="handleSelectItem(item)"
                >
                  <div class="text-[13px] text-slate-700 leading-relaxed">
                    {{ item.sheet || "-" }} | {{ item.code || "-" }} | {{ item.name || "-" }}
                  </div>
                  <div class="mt-1 text-xs text-slate-500">公司增减金额：{{ item.amountText || "-" }}</div>
                </button>
              </div>
            </div>
          </template>
          <template v-else>
            <button
              v-for="item in group.items"
              :key="item.id"
              type="button"
              class="w-full p-2.5 border rounded-lg bg-slate-50 text-left cursor-pointer transition-colors hover:border-slate-300 hover:bg-slate-100"
              :class="isItemActive(item) ? 'border-red-300 bg-red-50 shadow-[0_0_0_3px_rgba(239,68,68,0.12)]' : 'border-slate-200'"
              :ref="(element) => setItemRef(item, element)"
              @click="handleSelectItem(item)"
            >
              <div class="text-[13px] text-slate-700 leading-relaxed">
                {{ item.sheet || "-" }} | {{ item.code || "-" }} | {{ item.name || "-" }}
              </div>
              <div
                v-if="(group.typeId === 12 || group.typeId === 13 || group.typeId === 15) && item.value"
                class="mt-1 text-xs text-slate-500 break-words"
              >
                {{ item.value }}
              </div>
              <div v-if="group.typeId !== 12 && item.excelRowIndexes?.length > 1" class="mt-1 text-xs text-slate-500">
                Excel 行号：{{ item.excelRowIndexes.join(" | ") }}
              </div>
            </button>
          </template>
        </div>
        <div v-else-if="isGroupExpanded(group)" class="px-2 py-1 text-xs text-slate-400">暂无</div>
      </div>
    </div>
  </section>
</template>
