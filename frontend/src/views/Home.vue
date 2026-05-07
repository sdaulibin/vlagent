<template>
    <div class="home-container">
        <!-- Header -->
        <header class="home-header">
            <div class="flex items-center justify-center gap-3 mb-3">
                <div class="home-logo">
                    <Scan class="w-6 h-6 text-white" />
                </div>
                <h1 class="home-title">智能文档识别平台</h1>
            </div>
            <p class="home-subtitle">基于 AI 大模型的智能文档信息提取解决方案</p>
        </header>

        <!-- Scenario Cards -->
        <main class="max-w-5xl mx-auto px-6 pb-16">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
                <router-link
                    v-for="m in visibleModules"
                    :key="m.key"
                    :to="m.route"
                    class="scenario-card group"
                >
                    <div class="scenario-card-icon" :class="m.gradient">
                        <component :is="iconMap[m.icon]" class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">{{ m.title }}</h3>
                    <p class="scenario-card-desc">{{ m.description }}</p>
                    <div class="scenario-card-link" :class="m.hover_class">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>
            </div>
        </main>

        <!-- Footer -->
        <footer class="home-footer">
            <p>Powered by Qwen-VL Large Model</p>
        </footer>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import {
    Scan, ArrowRight,
    CreditCard, FileText, FileDiff, FileSearch,
    Receipt, FileCheck2, FileScan,
} from 'lucide-vue-next'
import { useUser } from '../composables/useUser'

const { modules, hasPermission } = useUser()

const iconMap: Record<string, Component> = {
    CreditCard, FileText, FileDiff, FileSearch,
    Receipt, FileCheck2, FileScan,
}

const visibleModules = computed(() => modules.value.filter(m => hasPermission(m.key)))
</script>
