<template>
    <div class="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <!-- Header -->
        <header class="pt-12 pb-8 text-center">
            <div class="flex items-center justify-center gap-4 mb-4">
                <div class="bg-gradient-to-r from-blue-500 to-purple-600 p-3 rounded-2xl shadow-lg shadow-purple-500/30">
                    <Scan class="w-10 h-10 text-white" />
                </div>
                <h1 class="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                    智能文档识别平台
                </h1>
            </div>
            <p class="text-gray-400 text-lg">基于 AI 大模型的智能文档信息提取解决方案</p>
        </header>

        <!-- Scenario Cards -->
        <main class="max-w-5xl mx-auto px-6 pb-16">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- 银行流水识别 -->
                <router-link to="/bank-statement" class="scenario-card group">
                    <div class="card-icon bg-gradient-to-br from-blue-500 to-blue-600">
                        <CreditCard class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="text-xl font-semibold text-white mb-2">银行流水识别</h3>
                    <p class="text-gray-400 text-sm mb-4">
                        智能解析银行流水PDF，提取交易明细、账户信息和汇总统计
                    </p>
                    <div class="flex items-center text-blue-400 text-sm font-medium group-hover:text-blue-300">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 发票识别 -->
                <div class="scenario-card opacity-60 cursor-not-allowed">
                    <div class="card-icon bg-gradient-to-br from-green-500 to-green-600">
                        <FileText class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="text-xl font-semibold text-white mb-2">发票识别</h3>
                    <p class="text-gray-400 text-sm mb-4">
                        自动识别增值税发票，提取发票代码、金额、税额等关键信息
                    </p>
                    <span class="inline-block px-3 py-1 bg-gray-700 text-gray-400 text-xs rounded-full">
                        敬请期待
                    </span>
                </div>

                <!-- 合同识别 -->
                <div class="scenario-card opacity-60 cursor-not-allowed">
                    <div class="card-icon bg-gradient-to-br from-orange-500 to-orange-600">
                        <FileCheck class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="text-xl font-semibold text-white mb-2">合同识别</h3>
                    <p class="text-gray-400 text-sm mb-4">
                        智能解析合同文本，提取甲乙方、金额、有效期等核心条款
                    </p>
                    <span class="inline-block px-3 py-1 bg-gray-700 text-gray-400 text-xs rounded-full">
                        敬请期待
                    </span>
                </div>
            </div>
        </main>

        <!-- Footer -->
        <footer class="text-center py-8 text-gray-500 text-sm">
            <p>Powered by Qwen-VL Large Model</p>
        </footer>
    </div>
</template>

<script setup lang="ts">
import { Scan, CreditCard, FileText, FileCheck, ArrowRight } from 'lucide-vue-next'
</script>

