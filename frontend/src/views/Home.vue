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

                <!-- 询证函识别 -->
                <router-link to="/confirmation-letter" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-green">
                        <FileText class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">询证函识别</h3>
                    <p class="scenario-card-desc">
                        智能识别银行询证函，自动提取编号、事务所、联系方式等关键字段
                    </p>
                    <div class="scenario-card-link group-hover:text-green-300">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 文档比对 -->
                <router-link to="/document-compare" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-orange">
                        <FileDiff class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">文档比对</h3>
                    <p class="scenario-card-desc">
                        智能对比两份文档差异，逐页标注新增、删除、修改的内容
                    </p>
                    <div class="scenario-card-link group-hover:text-orange-300">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 询证函格式比对 -->
                <router-link to="/format-compare" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-purple">
                        <FileSearch class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">询证函格式比对</h3>
                    <p class="scenario-card-desc">
                        上传询证函与标准模板比对，智能识别格式差异并标注不符处
                    </p>
                    <div class="scenario-card-link group-hover:text-purple-300">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 发票识别 -->
                <router-link to="/invoice-recognition" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-red">
                        <Receipt class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">发票识别</h3>
                    <p class="scenario-card-desc">
                        智能识别电子发票PDF，自动提取发票类型、号码、金额、购销方等关键信息
                    </p>
                    <div class="scenario-card-link group-hover:text-red-300">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 类凭证识别 -->
                <router-link to="/credential-recognition" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-blue" style="background: linear-gradient(135deg, #6366f1, #9333ea);">
                        <FileCheck2 class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">类凭证识别</h3>
                    <p class="scenario-card-desc">
                        智能提取身份证、银行卡、网银申请书等多种凭证的关键信息
                    </p>
                    <div class="scenario-card-link group-hover:text-indigo-400">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 通用 PDF 提取 -->
                <router-link to="/pdf-extract" class="scenario-card group">
                    <div class="scenario-card-icon" style="background: linear-gradient(135deg, #06b6d4, #2563eb);">
                        <FileScan class="w-8 h-8 text-white" />
                    </div>
                    <h3 class="scenario-card-title">通用 PDF 提取</h3>
                    <p class="scenario-card-desc">
                        自定义提取字段，AI 自动从任意 PDF 文件中提取结构化信息
                    </p>
                    <div class="scenario-card-link group-hover:text-cyan-300">
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
import { Scan, CreditCard, FileText, FileDiff, FileSearch, Receipt, ArrowRight, FileCheck2, FileScan } from 'lucide-vue-next'
</script>

