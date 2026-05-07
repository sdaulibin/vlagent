import { ref } from 'vue'
import { getUserPermissions, getModules, type ModuleInfo } from '../api'
import { decodePayload, getToken } from './useAuth'

export interface UserInfo {
  userId: string
  name: string
  orgId: string
  userType: string
}

const userInfo = ref<UserInfo | null>(null)
const permittedModules = ref<string[]>([])
const modules = ref<ModuleInfo[]>([])
const permissionsLoaded = ref(false)

function extractUserInfo(): UserInfo | null {
  const token = getToken()
  if (!token) return null
  const payload = decodePayload(token)
  if (!payload) return null
  return {
    userId: (payload.user_id as string) || '',
    name: (payload.name as string) || '',
    orgId: (payload.org_id as string) || '',
    userType: (payload.user_type as string) || '',
  }
}

async function loadPermissions() {
  userInfo.value = extractUserInfo()
  try {
    const [keys, mods] = await Promise.all([
      getUserPermissions(),
      getModules(),
    ])
    permittedModules.value = keys
    modules.value = mods
  } catch {
    permittedModules.value = modules.value.map(m => m.key)
  }
  permissionsLoaded.value = true
}

function hasPermission(moduleKey: string): boolean {
  if (!permissionsLoaded.value) return true
  return permittedModules.value.includes(moduleKey)
}

export function useUser() {
  return {
    userInfo,
    permittedModules,
    modules,
    permissionsLoaded,
    loadPermissions,
    hasPermission,
  }
}
