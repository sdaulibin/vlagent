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
    userId: String(payload.name ?? payload.user_id ?? ''),
    name: String(payload.user_name ?? payload.name ?? ''),
    orgId: String(payload.org_id ?? ''),
    userType: String(payload.user_type ?? ''),
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
