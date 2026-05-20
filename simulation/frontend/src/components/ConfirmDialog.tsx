interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  confirmDanger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = '确认',
  confirmDanger = false,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* 遮罩 */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* 模态框 */}
      <div className="relative w-full max-w-sm bg-surface-800 border border-border rounded-2xl shadow-2xl shadow-black/40 overflow-hidden animate-[scaleIn_0.2s_ease-out]">
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface-800/80">
          <h2 className="text-base font-bold text-text-primary tracking-tight">{title}</h2>
          <button
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-700 transition-all duration-150"
            onClick={onCancel}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 内容 */}
        <div className="p-6">
          <p className="text-sm text-text-secondary leading-relaxed">{message}</p>
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-surface-900/50">
          <button
            className="px-5 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary rounded-lg border border-border hover:border-surface-600 transition-all duration-150"
            onClick={onCancel}
          >
            取消
          </button>
          <button
            className={`px-5 py-2.5 text-sm font-semibold text-white rounded-lg shadow-sm transition-all duration-150 active:scale-[0.97] ${
              confirmDanger
                ? 'bg-loss hover:bg-loss-400 shadow-loss/25 hover:shadow-md hover:shadow-loss/30'
                : 'bg-accent hover:bg-accent-400 shadow-accent/25 hover:shadow-md hover:shadow-accent/30'
            }`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
