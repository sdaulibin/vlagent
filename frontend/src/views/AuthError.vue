<template>
    <div class="min-h-screen bg-slate-900 flex items-center justify-center px-4">
        <div class="text-center max-w-md">
            <div class="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                <ShieldX class="w-10 h-10 text-red-400" />
            </div>
            <h1 class="text-2xl font-bold text-white mb-3">认证失败</h1>
            <p class="text-slate-400 mb-2">未能获取有效的认证凭证，无法访问系统。</p>
            <p class="text-slate-500 text-sm mb-8">请通过智能助手重新进入本系统。</p>
            <button
                v-if="isInIframe"
                @click="retryAuth"
                class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
                重新认证
            </button>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ShieldX } from 'lucide-vue-next'
import { initAuth, clearAuth } from '../composables/useAuth'

const isInIframe = window.parent !== window

async function retryAuth() {
    clearAuth()
    const token = await initAuth()
    if (token) {
        window.location.href = import.meta.env.BASE_URL
    }
}
</script>
