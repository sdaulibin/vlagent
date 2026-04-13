<template>
    <div v-if="loading" class="min-h-screen bg-slate-900 flex items-center justify-center">
        <div class="text-center">
            <div class="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto mb-4"></div>
            <p class="text-slate-400">正在验证认证信息...</p>
        </div>
    </div>
    <router-view v-else />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { initAuth } from './composables/useAuth'

const router = useRouter()
const loading = ref(true)

onMounted(async () => {
    const token = await initAuth()

    if (token) {
        loading.value = false
    } else {
        loading.value = false
        router.replace('/auth-error')
    }
})
</script>
