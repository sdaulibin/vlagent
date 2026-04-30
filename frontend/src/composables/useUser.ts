import { ref } from 'vue'
import { getUserPermissions } from '../api'
import { decodePayload, getToken } from './useAuth'

export interface UserInfo {
  userId: string
  name: string
  orgId: string
  userType: string
}

const ALL_MODULES = [
  'bank-statement',
  'confirmation-letter',
  'document-compare',
  'format-compare',
  'invoice-recognition',
  'credential-recognition',
  'pdf-extract',
]

const userInfo = ref<UserInfo | null>(null)
const permittedModules = ref<string[]>([])
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
    const modules = await getUserPermissions()
    permittedModules.value = modules
  } catch {
    permittedModules.value = ALL_MODULES
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
    permissionsLoaded,
    loadPermissions,
    hasPermission,
  }
}
