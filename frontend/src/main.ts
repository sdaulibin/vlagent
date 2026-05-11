import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'

const TOKEN_KEY = 'vlagent_token'

// 处理浏览器 bfcache 恢复
window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    const entryUrl = sessionStorage.getItem('vlagent_entry_url')
    if (entryUrl) {
      sessionStorage.removeItem('vlagent_entry_url')
      window.location.replace(entryUrl)
    } else {
      window.location.reload()
    }
  }
})

// postMessage 监听（支持 window.open 和 iframe 场景）
let _tokenReceived = false
window.addEventListener('message', (event) => {
  if (_tokenReceived) return
  let token: string | null = null
  if (typeof event.data === 'string') {
    token = event.data
  } else if (event.data && typeof event.data === 'object' && event.data.type === 'token' && event.data.token) {
    token = event.data.token
  }
  if (token) {
    _tokenReceived = true
    sessionStorage.setItem(TOKEN_KEY, token)
    const url = new URL(window.location.href)
    if (url.searchParams.has('token')) {
      url.searchParams.delete('token')
      window.history.replaceState({}, '', url.pathname + url.hash)
    }
  }
})

// 通知 opener：vlagent 已就绪，可以发送 token
setTimeout(() => {
  if (!_tokenReceived && window.opener) {
    try { window.opener.postMessage({ type: 'vlagent_ready' }, '*') } catch {}
  }
}, 100)

// URL 参数提取（备用）
{
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')
  if (token && !_tokenReceived) {
    sessionStorage.setItem(TOKEN_KEY, token)
    _tokenReceived = true
    const url = new URL(window.location.href)
    url.searchParams.delete('token')
    window.history.replaceState({}, '', url.pathname + url.hash)
  }
}

createApp(App).use(router).mount('#app')
