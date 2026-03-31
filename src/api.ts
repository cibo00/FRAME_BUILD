import axios from 'axios';

const BASE_URL = (import.meta.env as any).VITE_API_BASE_URL || (window as any).__API_BASE_URL__ || '/api';

// 创建一个 Axios 实例
export const api = axios.create({
  // 设置基础URL，这样你就不需要在每个请求中都写 "http://localhost:8080" 192.168.5.182:8080
  baseURL: 'http://localhost:8080', 
  timeout: 10000, // 请求超时时间
  headers: {
    'Content-Type': 'application/json',
  }
});

// 关键：创建请求拦截器 (Request Interceptor)
// 在每个请求被发送出去之前，这个函数都会被调用
api.interceptors.request.use(
  (config) => {
    // 1. 从 localStorage 中获取 token
    const token = localStorage.getItem('session_token');
    
    // 2. 如果 token 存在，则为请求头添加 Authorization 字段
    if (token) {
      // 这里的格式是 "Bearer <token>"，是行业标准
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // 3. 必须返回 config 对象，否则请求会被阻塞
    return config;
  }, 
  (error) => {
    // 处理请求错误
    return Promise.reject(error);
  }
);

// 你还可以添加响应拦截器 (Response Interceptor) 来统一处理错误
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
      // 例如，如果收到 401 (Unauthorized) 错误，说明 token 失效
      // 在这里可以做一些全局操作，比如清除 token 并跳转到登录页
      localStorage.removeItem('session_token');
      // window.location.href = '/login';
      console.error("认证失败或Token已过期，请重新登录。");
    }
    return Promise.reject(error);
  }
);


// 创建一个 Axios 实例
export const api_vedio = axios.create({
  // 设置基础URL，这样你就不需要在每个请求中都写 "http://localhost:8080"
  baseURL: 'http://localhost:8080', 
  timeout: 10000, // 请求超时时间
  
});

// 关键：创建请求拦截器 (Request Interceptor)
// 在每个请求被发送出去之前，这个函数都会被调用
api_vedio.interceptors.request.use(
  (config) => {
    // 1. 从 localStorage 中获取 token
    const token = localStorage.getItem('session_token');
    
    // 2. 如果 token 存在，则为请求头添加 Authorization 字段
    if (token) {
      // 这里的格式是 "Bearer <token>"，是行业标准
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // 3. 必须返回 config 对象，否则请求会被阻塞
    return config;
  }, 
  (error) => {
    // 处理请求错误
    return Promise.reject(error);
  }
);

// 你还可以添加响应拦截器 (Response Interceptor) 来统一处理错误
api_vedio.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
      // 例如，如果收到 401 (Unauthorized) 错误，说明 token 失效
      // 在这里可以做一些全局操作，比如清除 token 并跳转到登录页
      localStorage.removeItem('session_token');
      // window.location.href = '/login';
      console.error("认证失败或Token已过期，请重新登录。");
    }
    return Promise.reject(error);
  }
);
