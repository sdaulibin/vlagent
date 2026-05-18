/**
 * JWT 认证管理模块
 *
 * 支持三种 token 获取方式：
 * 1. URL 参数：?token=xxx（开发调试和备用方式）
 * 2. sessionStorage 中已有 token（页面刷新）
 * 3. postMessage：iframe 嵌入场景下父窗口发送 token
 * 4. 开发模式：非 iframe 时从后端 /dev-token 获取测试 token
 */

const TOKEN_KEY = "vlagent_token";

let currentToken: string | null = null;

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

/** 将 JWT payload 部分解码（不做签名验证，仅读取字段），支持 UTF-8 中文 */
export function decodePayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1]!;
    const binary = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
    const json = new TextDecoder().decode(bytes);
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
  if (token) {
    if (isTokenExpired(token)) {
      console.warn("[AUTH] URL token 已过期");
      return null;
    }
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
  // 兜底：从 sessionStorage 恢复（应对 router guard 在 IIFE 之后执行的时序问题）
  if (!currentToken) {
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored && !isTokenExpired(stored)) {
      currentToken = stored;
      return stored;
    }
  }
  currentToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
  return null;
}

/** 是否已认证 */
export function isAuthenticated(): boolean {
  // 先尝试从 sessionStorage 恢复（应对 router guard 在 IIFE 之后执行的时序问题）
  if (!currentToken) {
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored && !isTokenExpired(stored)) {
      currentToken = stored;
    }
  }
  return getToken() !== null;
}

/** 从后端获取开发测试 token */
async function fetchDevToken(): Promise<string | null> {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
      ? import.meta.env.VITE_API_BASE_URL
      : "http://localhost:8000/api";
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
 * 1. sessionStorage 中已有 token（main.ts 预提取/postMessage 保存的）
 * 2. URL 参数 ?token=xxx（备用）
 * 3. 从后端 /dev-token 获取测试 token（开发模式）
 */
export function initAuth(): Promise<string | null> {
  return new Promise((resolve) => {
    // 1. 优先从 sessionStorage 恢复 token（main.ts 提前保存的）
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored && !isTokenExpired(stored)) {
      currentToken = stored;
      resolve(stored);
      return;
    }

    // 2. 从 URL 参数获取（备用）
    const urlToken = getTokenFromUrl();
    if (urlToken) {
      resolve(urlToken);
      return;
    }

    // 3. 从后端获取开发测试 token
    fetchDevToken().then((token) => {
      if (token) {
        console.log("[AUTH] 使用 dev-token 兜底登录");
        currentToken = token;
        sessionStorage.setItem(TOKEN_KEY, token);
        resolve(token);
      } else {
        console.warn("[AUTH] 无有效 token");
        resolve(null);
      }
    });
  });
}

/** 清除认证状态 */
export function clearAuth(): void {
  currentToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
}
