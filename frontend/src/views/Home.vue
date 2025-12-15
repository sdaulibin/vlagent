<template>
    <div class="home-container">
        <!-- Header -->
        <header class="home-header">
            <div class="flex items-center justify-center gap-4 mb-4">
                <div class="home-logo">
                    <Scan class="w-10 h-10 text-white" />
                </div>
                <h1 class="home-title">智能文档识别平台</h1>
            </div>
            <p class="home-subtitle">基于 AI 大模型的智能文档信息提取解决方案</p>
        </header>

        <!-- Scenario Cards -->
        <main class="max-w-5xl mx-auto px-6 pb-16">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- 流水识别 -->
                <router-link to="/bank-statement" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-blue">
                        <CreditCard class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">流水识别</h3>
                    <p class="scenario-card-desc">
                        智能解析银行流水PDF，提取交易明细、账户信息和汇总统计
                    </p>
                    <div class="scenario-card-link group-hover:text-blue-300">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 发票识别 -->
                <div class="scenario-card scenario-card-disabled">
                    <div class="scenario-card-icon icon-gradient-green">
                        <FileText class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">发票识别</h3>
                    <p class="scenario-card-desc">
                        自动识别增值税发票，提取发票代码、金额、税额等关键信息
                    </p>
                    <span class="scenario-badge-coming">敬请期待</span>
                </div>

                <!-- 合同比对 -->
                <router-link to="/contract-compare" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-orange">
                        <FileDiff class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">合同比对</h3>
                    <p class="scenario-card-desc">
                        智能对比两份文档差异，自动识别新增、删除、修改的内容
                    </p>
                    <div class="scenario-card-link group-hover:text-orange-300">
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
import { Scan, CreditCard, FileText, FileDiff, ArrowRight } from 'lucide-vue-next'
</script>

