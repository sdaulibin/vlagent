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
                <!-- 流水识别 -->
                <router-link to="/bank-statement" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-blue">
                        <CreditCard class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">流水识别</h3>
                    <p class="scenario-card-desc">
                        AI 识别银行流水 PDF，提取交易明细、账户信息和汇总数据，支持光大、招商、工商等多家银行格式
                    </p>
                    <div class="scenario-card-link group-hover:text-blue-700">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 询证函识别 -->
                <router-link to="/confirmation-letter" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-green">
                        <FileText class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">询证函识别</h3>
                    <p class="scenario-card-desc">
                        AI 识别银行询证函 PDF，自动提取编号、事务所、联系方式、账户等 13 个关键字段
                    </p>
                    <div class="scenario-card-link group-hover:text-emerald-700">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 文档比对 -->
                <router-link to="/document-compare" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-orange">
                        <FileDiff class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">文档比对</h3>
                    <p class="scenario-card-desc">
                        逐页对比两份文档（PDF / Word），逐行标注新增、删除、修改内容，支持表格结构化比对
                    </p>
                    <div class="scenario-card-link group-hover:text-orange-600">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 询证函格式比对 -->
                <router-link to="/format-compare" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-purple">
                        <FileSearch class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">询证函格式比对</h3>
                    <p class="scenario-card-desc">
                        将询证函与标准模板比对，检查格式类型、章节标题、表头字段是否符合规范
                    </p>
                    <div class="scenario-card-link group-hover:text-violet-700">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 发票识别 -->
                <router-link to="/invoice-recognition" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-red">
                        <Receipt class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">发票识别</h3>
                    <p class="scenario-card-desc">
                        识别电子发票 PDF 及图片，提取发票类型、号码、金额、购销方名称及税号等信息
                    </p>
                    <div class="scenario-card-link group-hover:text-rose-600">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 类凭证识别 -->
                <router-link to="/credential-recognition" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-indigo">
                        <FileCheck2 class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">类凭证识别</h3>
                    <p class="scenario-card-desc">
                        识别身份证、银行卡、电子印章、网银申请书、授权书等多种凭证类型的关键信息
                    </p>
                    <div class="scenario-card-link group-hover:text-indigo-700">
                        立即使用
                        <ArrowRight class="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                </router-link>

                <!-- 通用 PDF 提取 -->
                <router-link to="/pdf-extract" class="scenario-card group">
                    <div class="scenario-card-icon icon-gradient-cyan">
                        <FileScan class="w-5 h-5 text-white" />
                    </div>
                    <h3 class="scenario-card-title">通用 PDF 提取</h3>
                    <p class="scenario-card-desc">
                        自定义提取字段（最多 10 个），AI 从任意 PDF 中提取结构化数据，支持导出 Excel / CSV
                    </p>
                    <div class="scenario-card-link group-hover:text-cyan-700">
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
