import { useEffect } from 'react';
import { useSimStore } from '../store/useSimStore';

const TOAST_STYLES: Record<string, { border: string; bg: string; icon: string }> = {
  WIN: {
    border: 'border-l-profit',
    bg: 'bg-profit/10',
    icon: 'M4.5 12.75l6 6 9-13.5',
  },
  LOSE: {
    border: 'border-l-loss',
    bg: 'bg-loss/10',
    icon: 'M6 18L18 6M6 6l12 12',
  },
  task_started: {
    border: 'border-l-accent',
    bg: 'bg-accent/10',
    icon: 'M5.25 5.653c-.44-.059-1.53 0-2.25 0-.156 0-.25.15-.25.36v12.48c0 .21.094.36.25.36h2.25M16.5 5.653c.44-.059 1.53 0 2.25 0 .156 0 .25.15.25.36v12.48c0 .21-.094.36-.25.36H16.5',
  },
  task_created: {
    border: 'border-l-accent',
    bg: 'bg-accent/10',
    icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  task_stopped: {
    border: 'border-l-surface-600',
    bg: 'bg-surface-800',
    icon: 'M5.25 7.5A2.25 2.25 0 017.5 5.25h9a2.25 2.25 0 012.25 2.25v9a2.25 2.25 0 01-2.25 2.25h-9a2.25 2.25 0 01-2.25-2.25v-9z',
  },
  task_deleted: {
    border: 'border-l-surface-600',
    bg: 'bg-surface-800',
    icon: 'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0',
  },
};

export default function ToastContainer() {
  const toasts = useSimStore((s) => s.toasts);
  const removeToast = useSimStore((s) => s.removeToast);

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => {
        const style = TOAST_STYLES[toast.type] || TOAST_STYLES.task_deleted;
        return (
          <ToastItem key={toast.id} toast={toast} style={style} onRemove={() => removeToast(toast.id)} />
        );
      })}
    </div>
  );
}

function ToastItem({ toast, style, onRemove }: {
  toast: { id: string; type: string; message: string; taskId: string; data?: Record<string, unknown> };
  style: { border: string; bg: string; icon: string };
  onRemove: () => void;
}) {
  useEffect(() => {
    const timer = setTimeout(onRemove, 4000);
    return () => clearTimeout(timer);
  }, [onRemove]);

  return (
    <div
      className={`rounded-lg p-3 pr-8 shadow-lg border-l-4 ${style.border} ${style.bg}
        text-sm font-medium max-w-sm relative
        animate-[slideInRight_0.3s_ease-out] transition-all duration-300`}
      style={{}}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 text-current opacity-70">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d={style.icon} />
          </svg>
        </span>
        <div>
          <p className="text-text-primary text-[11px] leading-tight font-semibold uppercase tracking-wide opacity-60">
            {toast.type === 'WIN' || toast.type === 'LOSE' ? 'ROUND' : toast.type.replace(/_/g, ' ')}
          </p>
          <p className="text-text-primary text-sm mt-0.5">{toast.message}</p>
        </div>
      </div>
      <button
        className="absolute top-2 right-2 w-5 h-5 flex items-center justify-center rounded text-text-muted hover:text-text-primary transition-colors"
        onClick={onRemove}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
