import React, { useState } from 'react';
import { useAuthStore } from '../../store/useAuthStore';

export const LoginOverlay: React.FC = () => {
  const { 
    login, 
    error, 
    setError 
  } = useAuthStore();
  
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;

    setIsSubmitting(true);
    await login(password);
    setIsSubmitting(false);
    setPassword('');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0a0a0c] bg-opacity-95 backdrop-blur-sm">
      <div className="relative w-full max-w-md p-8 mx-4">
        {/* Decorative background effects */}
        <div className="absolute top-0 -left-4 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob"></div>
        <div className="absolute top-0 -right-4 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-20 w-72 h-72 bg-indigo-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>

        <div className="relative bg-gray-900/80 backdrop-blur-xl rounded-2xl border border-gray-700/50 shadow-2xl p-8">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 bg-gradient-to-tr from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                 <i className="fas fa-shield-alt text-2xl text-white"></i>
              </div>
            </div>
            <h2 className="text-3xl font-bold text-white mb-2 tracking-tight">
              Welcome Back
            </h2>
            <p className="text-gray-400 text-sm">
              请输入访问密码以进入 QuantAgent 系统
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-gray-400 uppercase tracking-wider ml-1">Password</label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError(null);
                  }}
                  placeholder="Enter access code"
                  className="w-full px-5 py-4 bg-gray-800/50 text-white placeholder-gray-500 rounded-xl border border-gray-700 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all duration-200 text-lg tracking-wide"
                  autoFocus
                />
              </div>
              
              {error && (
                <div className="flex items-center gap-2 text-red-400 text-sm mt-2 bg-red-400/10 p-3 rounded-lg border border-red-400/20">
                  <i className="fas fa-exclamation-circle"></i>
                  <span>{error}</span>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !password}
              className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-bold rounded-xl shadow-lg shadow-purple-500/20 transform transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <i className="fas fa-circle-notch fa-spin"></i>
                  Verifying...
                </span>
              ) : 'Unlock Access'}
            </button>
          </form>

          <div className="mt-8 text-center">
            <p className="text-xs text-gray-500">
              Authorized Personnel Only
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
