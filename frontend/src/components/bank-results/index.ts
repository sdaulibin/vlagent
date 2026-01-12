// 银行汇总组件索引
export { default as ShandongSummary } from './ShandongSummary.vue';
export { default as EverbrightSummary } from './EverbrightSummary.vue';
export { default as CmbSummary } from './CmbSummary.vue';
export { default as JiningSummary } from './JiningSummary.vue';
export { default as CgbSummary } from './CgbSummary.vue';
export { default as PsbcSummary } from './PsbcSummary.vue';
export { default as IcbcSummary } from './IcbcSummary.vue';
export { default as CcbSummary } from './CcbSummary.vue';

import type { BankType } from '../../types';
import type { Component } from 'vue';
import ShandongSummary from './ShandongSummary.vue';
import EverbrightSummary from './EverbrightSummary.vue';
import CmbSummary from './CmbSummary.vue';
import JiningSummary from './JiningSummary.vue';
import CgbSummary from './CgbSummary.vue';
import PsbcSummary from './PsbcSummary.vue';
import IcbcSummary from './IcbcSummary.vue';
import CcbSummary from './CcbSummary.vue';

// 银行类型到汇总组件的映射
export const SummaryComponents: Record<BankType, Component> = {
    'shandong_local': ShandongSummary,
    'everbright': EverbrightSummary,
    'cmb': CmbSummary,
    'jining': JiningSummary,
    'cgb': CgbSummary,
    'psbc': PsbcSummary,
    'icbc': IcbcSummary,
    'ccb': CcbSummary,
};

// 根据银行类型获取汇总组件
export function getSummaryComponent(bankType: BankType): Component {
    return SummaryComponents[bankType] || ShandongSummary;
}
