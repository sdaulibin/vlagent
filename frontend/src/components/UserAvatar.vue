<script setup lang="ts">
import { useUser } from '../composables/useUser'

const { userInfo } = useUser()
</script>

<template>
  <div v-if="userInfo" class="fixed top-4 right-6 z-50 flex items-center gap-3">
    <span class="text-sm text-slate-600 font-medium">{{ userInfo.name }}</span>
    <div class="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-semibold select-none">
      {{ userInfo.name?.charAt(0) || '' }}
    </div>
  </div>
</template>
