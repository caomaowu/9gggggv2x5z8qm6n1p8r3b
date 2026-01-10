import React, { useState } from 'react';
import { useAuthStore } from '../../store/useAuthStore';

interface AdminModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminModal: React.FC<AdminModalProps> = ({ isOpen, onClose }) => {
  const { adminToggle, systemEnabled } = useAuthStore();
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  if (!isOpen) return null;

  const handleToggle = async (targetState: boolean) => {
    if (!password.trim()) {
      setMessage({ type: 'error', text: 'Please enter admin password' });
      return;
    }

    setIsSubmitting(true);
    const success = await adminToggle(password, targetState);
    setIsSubmitting(false);

    if (success) {
      setMessage({ type: 'success', text: `System authentication ${targetState ? 'enabled' : 'disabled'} successfully` });
      setTimeout(() => {
        onClose();
        setPassword('');
        setMessage(null);
      }, 1500);
    } else {
      setMessage({ type: 'error', text: 'Invalid admin password' });
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-gray-900/80 backdrop-blur-sm">
      <div className="bg-gray-800 rounded-xl shadow-2xl w-full max-w-md overflow-hidden border border-gray-700 animate-fade-in-up">
        {/* Header */}
        <div className="bg-gray-900/50 px-6 py-4 flex justify-between items-center border-b border-gray-700">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <i className="fas fa-user-shield text-purple-400"></i>
            System Administration
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-300 mb-2">Admin Password</label>
            <div className="relative">
              <input
                type="password"
                value={password}
                onChange={(e) => {
                    setPassword(e.target.value);
                    setMessage(null); // Clear error on typing
                }}
                className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none transition-all placeholder-gray-500"
                placeholder="Enter admin password"
                autoFocus
              />
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="p-4 bg-gray-900/30 rounded-lg border border-gray-700">
              <div className="flex justify-between items-center mb-2">
                <span className="font-medium text-gray-300">Auth System Status</span>
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${systemEnabled ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                  {systemEnabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
              <p className="text-xs text-gray-400">
                {systemEnabled 
                  ? 'System is currently protecting all access. Users must log in.' 
                  : 'System protection is disabled. Access is open to everyone.'}
              </p>
            </div>

            {message && (
              <div className={`p-3 rounded-lg text-sm flex items-center gap-2 border ${message.type === 'success' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>
                <i className={`fas ${message.type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}`}></i>
                {message.text}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 mt-2">
               <button
                onClick={() => handleToggle(true)}
                disabled={isSubmitting || systemEnabled}
                className={`py-3 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2
                  ${systemEnabled 
                    ? 'bg-gray-700 text-gray-500 cursor-not-allowed border border-gray-600' 
                    : 'bg-green-600 hover:bg-green-700 text-white shadow-lg shadow-green-500/20 border border-transparent'}`}
              >
                <i className="fas fa-lock"></i> Enable Auth
              </button>

              <button
                onClick={() => handleToggle(false)}
                disabled={isSubmitting || !systemEnabled}
                className={`py-3 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2
                  ${!systemEnabled 
                    ? 'bg-gray-700 text-gray-500 cursor-not-allowed border border-gray-600' 
                    : 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/20 border border-transparent'}`}
              >
                <i className="fas fa-lock-open"></i> Disable Auth
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
