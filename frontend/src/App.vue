<template>
    <div v-if="loading" class="min-h-screen bg-slate-900 flex items-center justify-center">
        <div class="text-center">
            <div class="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto mb-4"></div>
            <p class="text-slate-400">正在验证认证信息...</p>
        </div>
    </div>
    <router-view v-else />
    <UserAvatar v-if="!loading" />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { initAuth } from './composables/useAuth'
import { useUser } from './composables/useUser'
import { api } from './api/index'
import UserAvatar from './components/UserAvatar.vue'

const router = useRouter()
const loading = ref(true)

const { loadPermissions } = useUser()

onMounted(async () => {
    const token = await initAuth()

    if (token) {
        try {
            await api.post('/auth/me')
            await loadPermissions()
        } catch {
            loading.value = false
            router.replace('/auth-error')
            return
        }
        loading.value = false
        if (router.currentRoute.value.name === 'AuthError') {
            router.replace('/')
        }
    } else {
        loading.value = false
        router.replace('/auth-error')
    }
})
</script>
