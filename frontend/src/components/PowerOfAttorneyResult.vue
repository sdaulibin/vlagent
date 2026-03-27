<script setup lang="ts">
import { Check, X } from 'lucide-vue-next';

const props = defineProps<{
  data: any;
}>();

const CATEGORY_LABELS: Record<string, string> = {
  opening: '开户类业务',
  change: '变更类业务',
  cancellation: '注销类业务',
  other: '其他业务'
};

const getItems = (category: string) => {
  const items = props.data?.authorized_items_by_category?.[category];
  if (!items) return [];
  return items;
};

const isOtherCategory = (category: string) => category === 'other';
</script>

<template>
  <div class="space-y-6">
    <!-- 基本信息区 -->
    <div class="bg-slate-50 rounded-lg p-4 border border-slate-200">
      <h4 class="font-medium text-slate-700 mb-3 flex items-center gap-2">
        <span class="w-2 h-2 bg-indigo-500 rounded-full"></span>
        基本信息
      </h4>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <div>
          <span class="text-slate-400">委托人：</span>
          <span class="font-medium text-slate-800">{{ data.principal_name || '-' }}</span>
        </div>
        <div>
          <span class="text-slate-400">委托人证件号：</span>
          <span class="font-mono text-slate-800">{{ data.principal_id_number || '-' }}</span>
        </div>
        <div>
          <span class="text-slate-400">被授权人证件号：</span>
          <span class="font-mono text-slate-800">{{ data.authorized_person_id_number || '-' }}</span>
        </div>
        <div>
          <span class="text-slate-400">本单位职工：</span>
          <span :class="data.is_employee ? 'text-green-600' : 'text-slate-500'">
            {{ data.is_employee ? '是' : '否' }}
          </span>
        </div>
        <div>
          <span class="text-slate-400">代表本人日期：</span>
          <span class="text-slate-800">{{ data.authorized_date || '-' }}</span>
        </div>
        <div>
          <span class="text-slate-400">公章日期：</span>
          <span class="text-slate-800">{{ data.seal_date || '-' }}</span>
        </div>
      </div>
    </div>

    <!-- 授权事项分类展示 -->
    <div class="space-y-4">
      <h4 class="font-medium text-slate-700 flex items-center gap-2">
        <span class="w-2 h-2 bg-indigo-500 rounded-full"></span>
        授权事项
      </h4>

      <!-- 四个类别 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <template v-for="(label, category) in CATEGORY_LABELS" :key="category">
          <div class="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <!-- 类别标题 -->
            <div class="px-4 py-2 bg-gradient-to-r from-slate-50 to-white border-b border-slate-100">
              <h5 class="font-medium text-slate-600 text-sm">{{ label }}</h5>
            </div>

            <!-- 项目列表 -->
            <div class="p-3">
              <!-- 其他业务（字符串数组，只要填写了就表示已勾选） -->
              <template v-if="isOtherCategory(category)">
                <div v-if="getItems(category).length > 0" class="space-y-1">
                  <div v-for="(item, idx) in getItems(category)" :key="idx"
                       class="flex items-center justify-between text-sm px-2 py-1.5 rounded bg-green-50 border border-green-100">
                    <span class="text-green-700 font-medium">{{ item }}</span>
                    <span class="flex items-center gap-1 text-green-600">
                      <Check class="w-4 h-4" />
                      <span class="text-xs">已勾选</span>
                    </span>
                  </div>
                </div>
                <div v-else class="text-sm text-slate-400 text-center py-2">
                  无其他业务
                </div>
              </template>

              <!-- 三类已知业务（对象数组，带勾选状态） -->
              <template v-else>
                <div class="space-y-1">
                  <div v-for="(item, idx) in getItems(category)" :key="idx"
                       class="flex items-center justify-between text-sm px-2 py-1.5 rounded transition-colors"
                       :class="item.checked ? 'bg-green-50 border border-green-100' : 'bg-slate-50 border border-slate-100'">
                    <span :class="item.checked ? 'text-green-700 font-medium' : 'text-slate-500'">
                      {{ item.name }}
                    </span>
                    <span v-if="item.checked" class="flex items-center gap-1 text-green-600">
                      <Check class="w-4 h-4" />
                      <span class="text-xs">已勾选</span>
                    </span>
                    <span v-else class="flex items-center gap-1 text-slate-400">
                      <X class="w-4 h-4" />
                      <span class="text-xs">未勾选</span>
                    </span>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 签名信息 -->
    <div class="bg-slate-50 rounded-lg p-4 border border-slate-200">
      <h4 class="font-medium text-slate-700 mb-3 flex items-center gap-2">
        <span class="w-2 h-2 bg-indigo-500 rounded-full"></span>
        签名信息
      </h4>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span class="text-slate-400">被授权人签字：</span>
          <span class="text-slate-800">{{ data.authorized_person_signature || '-' }}</span>
        </div>
        <div>
          <span class="text-slate-400">签字日期：</span>
          <span class="text-slate-800">{{ data.sign_date || '-' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
