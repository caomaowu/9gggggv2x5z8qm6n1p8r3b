import { create } from 'zustand';
import { apiClient } from '../api/client';

interface AuthState {
  isAuthenticated: boolean;
  systemEnabled: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  checkStatus: () => Promise<void>;
  login: (password: string) => Promise<boolean>;
  adminToggle: (password: string, enabled: boolean) => Promise<boolean>;
  logout: () => void;
  setError: (error: string | null) => void;
}

const TOKEN_KEY = 'qa_auth_token';
const EXPIRY_KEY = 'qa_auth_expiry';

export const useAuthStore = create<AuthState>((set, get) => ({
  isAuthenticated: false,
  systemEnabled: true,
  isLoading: true,
  error: null,

  checkStatus: async () => {
    // 重置状态
    set({ isLoading: true, error: null }); 
    try {
      // 1. Check Local Token validity
      const token = localStorage.getItem(TOKEN_KEY);
      const expiry = localStorage.getItem(EXPIRY_KEY);
      const now = Date.now() / 1000;
      
      let isLocalValid = false;
      if (token && expiry && parseFloat(expiry) > now) {
        isLocalValid = true;
      }

      // ... (Dev mode check commented out) ...
      if (import.meta.env.DEV) {
        set({ 
          isAuthenticated: true, 
          systemEnabled: false, 
          isLoading: false 
        });
        return;
      }

      const response = await apiClient.get('/auth/status');
      // 忽略后端返回的 is_locked 和 remaining_attempts，前端不再关心
      const { enabled } = response.data;
      
      set({
        systemEnabled: enabled,
        // If system is disabled, we are authenticated by default
        isAuthenticated: !enabled || isLocalValid,
        isLoading: false
      });

    } catch (error) {
      console.error('Auth check failed:', error);
      set({ 
        isLoading: false, 
        error: "无法连接到认证服务器", 
      });
    }
  },

  login: async (password: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.post('/auth/login', { password });
      const { success, token, expires_at } = response.data;
      
      if (success) {
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(EXPIRY_KEY, expires_at.toString());
        set({ isAuthenticated: true, isLoading: false, error: null });
        return true;
      }
      return false;
    } catch (error: any) {
      const data = error.response?.data?.detail;
      if (data) {
        // 只提取错误信息，忽略锁定相关字段
        set({
          error: typeof data === 'string' ? data : data.message,
          isLoading: false
        });
      } else {
        set({ error: "Login failed", isLoading: false });
      }
      return false;
    }
  },

  adminToggle: async (password: string, enabled: boolean) => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.post('/auth/admin/toggle', { 
        admin_password: password, 
        enabled 
      });
      
      if (response.data.success) {
        set({ 
          systemEnabled: response.data.enabled, 
          isAuthenticated: !response.data.enabled || get().isAuthenticated, // If disabled, auto auth
          isLoading: false 
        });
        // Reload status to sync everything
        get().checkStatus();
        return true;
      }
      return false;
    } catch (error: any) {
      set({ 
        error: "Admin action failed", 
        isLoading: false 
      });
      return false;
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRY_KEY);
    set({ isAuthenticated: false });
  },

  setError: (error) => set({ error })
}));
