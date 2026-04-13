/**
 * JWT 认证管理模块
 *
 * 支持三种 token 获取方式：
 * 1. URL 参数：?token=xxx（开发调试和备用方式）
 * 2. sessionStorage 中已有 token（页面刷新）
 * 3. postMessage：iframe 嵌入场景下父窗口发送 token
 * 4. 开发模式：非 iframe 时从后端 /dev-token 获取测试 token
 */

const TOKEN_KEY = "vl_flow_token";

let currentToken: string | null = null;
let authReady = false;

/** 模块加载时立即从 sessionStorage 恢复 token，确保路由守卫可以同步获取 */
(function initFromStorage() {
  try {
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored) {
      const payload = decodePayload(stored);
      if (payload && payload.exp && (payload.exp as number) > Math.floor(Date.now() / 1000)) {
        currentToken = stored;
      }
    }
  } catch {
    // ignore
  }
})();

/** 将 JWT payload 部分解码（不做签名验证，仅读取字段） */
function decodePayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** 检查 token 是否过期 */
function isTokenExpired(token: string): boolean {
  const payload = decodePayload(token);
  if (!payload || !payload.exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return (payload.exp as number) < now;
}

/** 尝试从 URL 参数获取 token */
function getTokenFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (token && !isTokenExpired(token)) {
    currentToken = token;
    sessionStorage.setItem(TOKEN_KEY, token);
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.pathname + url.hash);
    return token;
  }
  return null;
}

/** 获取当前存储的 token */
export function getToken(): string | null {
  if (currentToken && !isTokenExpired(currentToken)) {
    return currentToken;
  }
  currentToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
  return null;
}

/** 是否已认证 */
export function isAuthenticated(): boolean {
  return getToken() !== null;
}

/** 从后端获取开发测试 token */
async function fetchDevToken(): Promise<string | null> {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
      ? import.meta.env.VITE_API_BASE_URL.replace(/\/api$/, "")
      : "http://localhost:8000";
    const res = await fetch(`${baseUrl}/dev-token`, { method: "POST" });
    if (!res.ok) return null;
    const data = await res.json();
    return data.token || null;
  } catch {
    return null;
  }
}

/**
 * 初始化认证流程
 *
 * 优先级：
 * 1. URL 参数 ?token=xxx
 * 2. sessionStorage 中已有 token（页面刷新）
 * 3. postMessage 接收（iframe 场景）
 * 4. 非 iframe 时从后端 /dev-token 获取测试 token
 */
export function initAuth(): Promise<string | null> {
  return new Promise((resolve) => {
    // 1. 优先从 URL 参数获取
    const urlToken = getTokenFromUrl();
    if (urlToken) {
      authReady = true;
      resolve(urlToken);
      return;
    }

    // 2. 尝试从 sessionStorage 恢复 token
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored && !isTokenExpired(stored)) {
      currentToken = stored;
      authReady = true;
      resolve(stored);
      return;
    }

    // 3. iframe 场景：监听父窗口 postMessage
    if (window.parent !== window) {
      const handler = (event: MessageEvent) => {
        const data = event.data;
        let token: string | null = null;

        if (typeof data === "string") {
          token = data;
        } else if (data && typeof data === "object") {
          if (data.type === "token" && data.token) {
            token = data.token;
          }
        }

        if (token && !isTokenExpired(token)) {
          currentToken = token;
          sessionStorage.setItem(TOKEN_KEY, token);
          authReady = true;
          window.removeEventListener("message", handler);
          resolve(token);
        }
      };

      window.addEventListener("message", handler);
      window.parent.postMessage({ type: "vl_flow_ready" }, "*");

      // 超时 10 秒
      setTimeout(() => {
        if (!authReady) {
          window.removeEventListener("message", handler);
          resolve(null);
        }
      }, 10000);
      return;
    }

    // 4. 非 iframe：从后端获取开发测试 token
    fetchDevToken().then((token) => {
      if (token) {
        currentToken = token;
        sessionStorage.setItem(TOKEN_KEY, token);
        authReady = true;
        resolve(token);
      } else {
        resolve(null);
      }
    });
  });
}

/** 清除认证状态 */
export function clearAuth(): void {
  currentToken = null;
  authReady = false;
  sessionStorage.removeItem(TOKEN_KEY);
}
