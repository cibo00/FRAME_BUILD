import axios from 'axios';

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


// 创建一个 Axios 实例
export const api_vedio = axios.create({
  baseURL: '',
  timeout: 10000,
});
