<template>
    <div class="home-container">
        <!-- Header -->
        <header class="home-header">
            <span class="home-label">AI DOCUMENT RECOGNITION PLATFORM</span>
            <h1 class="home-title">智能文档识别平台</h1>
            <p class="home-subtitle">基于大模型的银行文档智能识别，涵盖流水、发票、凭证、询证函等多种文档类型</p>
        </header>

        <!-- Filter Tabs -->
        <div class="home-filter">
            <button
                v-for="cat in categories"
                :key="cat.key"
                :class="{ active: filter === cat.key }"
                @click="filter = cat.key"
            >
                {{ cat.label }}
            </button>
        </div>

        <!-- Card Grid -->
        <div class="home-grid">
            <router-link
                v-for="m in filteredModules"
                :key="m.key"
                :to="m.route"
                class="home-card"
            >
                <div class="home-card-image" :style="{ background: m.bg_color }">
                    <span class="home-card-tag" :style="{ color: m.category_color, borderColor: m.category_color }">{{ m.category_label }}</span>
                    <component :is="iconMap[m.icon]" class="home-card-svg" />
                </div>
                <div class="home-card-body">
                    <h3 class="home-card-title">{{ m.title }}</h3>
                    <p class="home-card-name">{{ m.name_en }}</p>
                    <p class="home-card-desc">{{ m.description }}</p>
                </div>
            </router-link>
        </div>

        <!-- Footer -->
        <footer class="home-footer">Powered by Qwen-VL Large Model</footer>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, type Component } from 'vue'
import {
    CreditCard, FileText, FileDiff, FileSearch,
    Receipt, FileCheck2, FileScan,
} from 'lucide-vue-next'
import { useUser } from '../composables/useUser'

const { modules, hasPermission } = useUser()

const iconMap: Record<string, Component> = {
    CreditCard, FileText, FileDiff, FileSearch,
    Receipt, FileCheck2, FileScan,
}

const filter = ref('all')

const visibleModules = computed(() =>
    modules.value.filter(m => hasPermission(m.key))
)

const categories = computed(() => {
    const cats = [{ key: 'all', label: '全部' }]
    const seen = new Set<string>()
    for (const m of visibleModules.value) {
        if (m.category && !seen.has(m.category)) {
            seen.add(m.category)
            cats.push({ key: m.category, label: m.category_label || m.category })
        }
    }
    return cats
})

const filteredModules = computed(() =>
    filter.value === 'all'
        ? visibleModules.value
        : visibleModules.value.filter(m => m.category === filter.value)
)
</script>
