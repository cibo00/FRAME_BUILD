import axios from 'axios';
import { getOrCreateClientId } from '@/utils/clientId';

const BASE_URL = (import.meta.env as any).VITE_API_BASE_URL || (window as any).__API_BASE_URL__ || '/api';

// 创建一个 Axios 实例
export const api = axios.create({
  // 使用相对路径，生产环境通过 Nginx 代理，开发环境通过 Vite proxy
  baseURL: '',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  }
});

// 自动在所有请求的 query params 中追加 client_id，用于后端 per-client 状态隔离
api.interceptors.request.use((config) => {
  const clientId = getOrCreateClientId();
  if (!config.params) {
    config.params = {};
  }
  config.params.client_id = clientId;
  return config;
});

// 创建一个 Axios 实例
export const api_vedio = axios.create({
  baseURL: '',
  timeout: 10000,
});

api_vedio.interceptors.request.use((config) => {
  const clientId = getOrCreateClientId();
  if (!config.params) {
    config.params = {};
  }
  config.params.client_id = clientId;
  return config;
});
