<script setup lang="ts">
import { computed } from 'vue';
import { Check, X, Minus } from 'lucide-vue-next';

const props = defineProps<{
  data: any;
}>();

// 三个待比对字段：(标签, 左联键, 右联键, 比对状态键)
const FIELDS: Array<{ label: string; leftKey: string; rightKey: string; statusKey: string }> = [
  { label: '收款人户名', leftKey: 'left_payee_name', rightKey: 'right_payee_name', statusKey: 'payee_name' },
  { label: '收款人账号', leftKey: 'left_payee_account', rightKey: 'right_payee_account', statusKey: 'payee_account' },
  { label: '金额', leftKey: 'left_amount', rightKey: 'right_amount', statusKey: 'amount' },
];

const comparison = computed(() => props.data?.comparison_result || {});

const rightHasContent = computed(() => comparison.value.right_has_content === true);

const isMono = (key: string) => key === 'left_payee_account' || key === 'right_payee_account';

const displayVal = (v: any) => {
  if (v === null || v === undefined || v === '') return '';
  return String(v);
};

const statusMeta = (status: string) => {
  switch (status) {
    case 'consistent':
      return { icon: Check, text: '一致', cls: 'text-green-600 bg-green-100 border-green-200', iconCls: 'text-green-600' };
    case 'inconsistent':
      return { icon: X, text: '不一致', cls: 'text-red-600 bg-red-100 border-red-200', iconCls: 'text-red-600' };
    case 'one_side_empty':
      return { icon: Minus, text: '仅一侧有内容', cls: 'text-amber-600 bg-amber-100 border-amber-200', iconCls: 'text-amber-600' };
    case 'both_empty':
    default:
      return { icon: Minus, text: '两侧均无内容', cls: 'text-slate-500 bg-slate-100 border-slate-200', iconCls: 'text-slate-400' };
  }
};

// 整体一致性：所有比对字段均为 consistent 或 both_empty 才算全部一致
const allConsistent = computed(() => {
  const statuses = FIELDS.map(f => comparison.value[f.statusKey]);
  return statuses.length > 0 && statuses.every(s => s === 'consistent' || s === 'both_empty');
});
</script>

<template>
  <div class="space-y-5">
    <!-- 顶部摘要 -->
    <div class="rounded-lg p-4 border flex items-start gap-3"
         :class="rightHasContent
           ? (allConsistent ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200')
           : 'bg-amber-50 border-amber-200'">
      <component
        :is="rightHasContent ? (allConsistent ? Check : X) : Minus"
        class="w-5 h-5 mt-0.5 flex-shrink-0"
        :class="rightHasContent
          ? (allConsistent ? 'text-green-600' : 'text-red-600')
          : 'text-amber-600'"
      />
      <div class="text-sm">
        <p class="font-medium"
           :class="rightHasContent
             ? (allConsistent ? 'text-green-800' : 'text-red-800')
             : 'text-amber-800'">
          右联（银行受理通知联）字段内容：{{ rightHasContent ? '已提取' : '无内容' }}
        </p>
        <p class="text-slate-500 mt-0.5">
          <template v-if="!rightHasContent">右联未检测到内容，已停止左右比对。</template>
          <template v-else-if="allConsistent">左联与右联字段内容全部一致。</template>
          <template v-else>左联与右联存在不一致或单侧缺失项，详见下表。</template>
        </p>
      </div>
    </div>

    <!-- 版式判断 -->
    <div class="bg-slate-50 rounded-lg p-4 border border-slate-200">
      <h4 class="font-medium text-slate-700 mb-3 flex items-center gap-2">
        <span class="w-2 h-2 bg-indigo-500 rounded-full"></span>
        版式判断
      </h4>
      <div class="text-sm">
        <span class="text-slate-400">是否为结算业务申请书：</span>
        <span :class="data.is_settlement_application ? 'text-green-600' : 'text-slate-500'">
          {{ data.is_settlement_application ? '是' : '否' }}
        </span>
      </div>
    </div>

    <!-- 左右比对表格 -->
    <div>
      <h4 class="font-medium text-slate-700 mb-3 flex items-center gap-2">
        <span class="w-2 h-2 bg-indigo-500 rounded-full"></span>
        左右两联字段比对
      </h4>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border-collapse">
          <thead>
            <tr class="bg-slate-100">
              <th class="border border-slate-300 px-3 py-2 text-left font-medium text-slate-600 w-28">字段</th>
              <th class="border border-slate-300 px-3 py-2 text-left font-medium text-slate-600">左联（申请书主体）</th>
              <th class="border border-slate-300 px-3 py-2 text-left font-medium text-slate-600">右联（银行受理通知联）</th>
              <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600 w-32">比对状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in FIELDS" :key="f.statusKey" class="hover:bg-slate-50">
              <td class="border border-slate-300 px-3 py-2 font-medium text-slate-700">{{ f.label }}</td>
              <td class="border border-slate-300 px-3 py-2"
                  :class="isMono(f.leftKey) ? 'font-mono text-xs break-all' : ''">
                <span v-if="displayVal(data[f.leftKey])">{{ data[f.leftKey] }}</span>
                <span v-else class="text-slate-300">—</span>
              </td>
              <td class="border border-slate-300 px-3 py-2"
                  :class="isMono(f.rightKey) ? 'font-mono text-xs break-all' : ''">
                <span v-if="displayVal(data[f.rightKey])">{{ data[f.rightKey] }}</span>
                <span v-else class="text-slate-300">—</span>
              </td>
              <td class="border border-slate-300 px-3 py-2 text-center">
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border"
                      :class="statusMeta(comparison[f.statusKey]).cls">
                  <component :is="statusMeta(comparison[f.statusKey]).icon"
                             class="w-3.5 h-3.5"
                             :class="statusMeta(comparison[f.statusKey]).iconCls" />
                  {{ statusMeta(comparison[f.statusKey]).text }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-xs text-slate-400 mt-2">
        注：金额与账号已做规范化比对（忽略空格、千分位逗号、货币符号与大小写差异）。
      </p>
    </div>
  </div>
</template>
