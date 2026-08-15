import axios from 'axios';
import { toast } from 'sonner';

// Platform admin API client - separate from tenant API
const platformApi = axios.create({
  baseURL: '/api/platform',
});

// Auto-attach platform token from localStorage
platformApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('platform_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors and auth redirects
platformApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    
    if (status === 401) {
      // Clear platform token and redirect to platform login
      localStorage.removeItem('platform_token');
      window.location.href = '/platform/login';
      return Promise.reject(error);
    }
    
    if (status === 403) {
      toast.error('Platform admin access required');
    } else if (!error.config?.skipErrorToast) {
      toast.error(message);
    }
    
    return Promise.reject(error);
  }
);

export const setPlatformAuthToken = (token) => {
  if (token) {
    platformApi.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    localStorage.setItem('platform_token', token);
  } else {
    delete platformApi.defaults.headers.common['Authorization'];
    localStorage.removeItem('platform_token');
  }
};

// ============================================
// Auth endpoints
// ============================================

export const platformLogin = (email, password) => {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);
  return platformApi.post('/auth/login', formData);
};

export const getPlatformMe = () => platformApi.get('/auth/me');

export const platformLogout = () => platformApi.post('/auth/logout');

// ============================================
// Dashboard endpoints
// ============================================

export const getDashboardStats = () => platformApi.get('/dashboard/stats');

// ============================================
// Tenants endpoints
// ============================================

export const getTenants = () => platformApi.get('/tenants');

export const createTenant = (data) => platformApi.post('/tenants', data);

export const updateTenant = (slug, data) => platformApi.patch(`/tenants/${slug}`, data);

export const deleteTenant = (slug) => platformApi.delete(`/tenants/${slug}`);

export const getTenantModules = (slug) => platformApi.get(`/tenants/${slug}/modules`);

export const toggleTenantModule = (slug, moduleKey, enabled) => 
  platformApi.put(`/tenants/${slug}/modules/${moduleKey}?enabled=${enabled}`);

export const bulkUpdateTenantModules = (slug, modules) => 
  platformApi.put(`/tenants/${slug}/modules`, { modules });

export const getTenantUsers = (slug) => platformApi.get(`/tenants/${slug}/users`);

export const impersonateTenant = (slug) => platformApi.post(`/tenants/${slug}/impersonate`);

// ============================================
// Modules catalog
// ============================================

export const getModulesCatalog = () => platformApi.get('/modules');

// ============================================
// Audit log
// ============================================

export const getAuditLog = (params) => platformApi.get('/audit-log', { params });

export default platformApi;
