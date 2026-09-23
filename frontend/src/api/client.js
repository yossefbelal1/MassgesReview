import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('reviewflow_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const reqUrl = error.config?.url || '';
      const isAuthEndpoint = reqUrl.includes('/auth/login') || reqUrl.includes('/auth/register');
      if (!isAuthEndpoint) {
        localStorage.removeItem('reviewflow_token');
        localStorage.removeItem('reviewflow_user');
        const isWinback = window.location.pathname.startsWith('/winback') || 
                          window.location.pathname.startsWith('/retention') ||
                          window.location.hostname.startsWith('winback') || 
                          window.location.hostname.startsWith('retention');
        const targetLogin = isWinback 
          ? (window.location.hostname.startsWith('winback') ? '/login' : '/winback/login')
          : '/login';
        if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
          window.location.href = targetLogin;
        }
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
