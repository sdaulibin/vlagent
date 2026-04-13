/**
 * JWT 认证管理模块
 *
 * 支持两种 token 获取方式：
 * 1. URL 参数：?token=xxx（开发调试和备用方式）
 * 2. postMessage：iframe 嵌入场景下父窗口发送 token
 */

const TOKEN_KEY = "vl_flow_token";

let currentToken: string | null = null;
let authReady = false;

/** 将 JWT payload 部分解码（不做签名验证，仅读取字段） */
function decodePayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    const json = atob(base64);
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
    // 存储 token 后清除 URL 中的参数，避免暴露在地址栏
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
  // token 过期，清除
  currentToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
  return null;
}

/** 是否已认证 */
export function isAuthenticated(): boolean {
  return getToken() !== null;
}

/**
 * 初始化认证流程
 *
 * 优先级：
 * 1. URL 参数 ?token=xxx（开发调试）
 * 2. sessionStorage 中已有 token（页面刷新）
 * 3. postMessage 接收（iframe 场景）
 */
export function initAuth(): Promise<string | null> {
  return new Promise((resolve) => {
    // 优先从 URL 参数获取
    const urlToken = getTokenFromUrl();
    if (urlToken) {
      authReady = true;
      resolve(urlToken);
      return;
    }

    // 尝试从 sessionStorage 恢复 token（处理 iframe 内刷新）
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored && !isTokenExpired(stored)) {
      currentToken = stored;
      authReady = true;
      resolve(stored);
      return;
    }

    // 监听父窗口消息（iframe 场景）
    const handler = (event: MessageEvent) => {
      const data = event.data;
      // 接收格式：{ type: "token", token: "jwt_string" }
      // 或直接发送 token 字符串
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

    // 通知父窗口已准备好接收 token
    if (window.parent !== window) {
      window.parent.postMessage({ type: "vl_flow_ready" }, "*");
    }

    // 超时 10 秒未收到 token，视为认证失败
    setTimeout(() => {
      if (!authReady) {
        window.removeEventListener("message", handler);
        resolve(null);
      }
    }, 10000);
  });
}

/** 清除认证状态 */
export function clearAuth(): void {
  currentToken = null;
  authReady = false;
  sessionStorage.removeItem(TOKEN_KEY);
}
