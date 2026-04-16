const CLIENT_ID_KEY = 'frame_build_client_id';

// 生成 UUID v4（兼容 HTTP 非安全上下文，不依赖 crypto.randomUUID）
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * 获取或创建持久化的客户端 ID（存储在 localStorage，跨标签页共享）。
 * 用于后端 per-client 状态隔离。
 */
export function getOrCreateClientId(): string {
  let clientId = localStorage.getItem(CLIENT_ID_KEY);
  if (!clientId) {
    clientId = generateUUID();
    localStorage.setItem(CLIENT_ID_KEY, clientId);
  }
  return clientId;
}

/**
 * 获取标签页作用域 ID。
 * 结合 clientId + sessionStorage 中的 tabId，确保每个浏览器标签页有独立的 localStorage 命名空间。
 * - localStorage 存储 clientId（跨标签页共享）
 * - sessionStorage 存储 tabId（每个标签页独立）
 */
export function getTabScopedId(): string {
  const clientId = getOrCreateClientId();
  let tabId = sessionStorage.getItem('frame_build_tab_id');
  if (!tabId) {
    tabId = generateUUID().slice(0, 8);
    sessionStorage.setItem('frame_build_tab_id', tabId);
  }
  return `${clientId}_${tabId}`;
}
