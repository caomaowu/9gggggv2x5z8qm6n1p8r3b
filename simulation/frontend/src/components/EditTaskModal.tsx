import { useState, useEffect } from 'react';
import { useSimStore } from '../store/useSimStore';
import type { TaskResponse, BetMode, TaskCreateRequest } from '../types';

interface Props {
  task: TaskResponse | null;
  open: boolean;
  onClose: () => void;
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[11px] font-semibold uppercase tracking-wider text-text-secondary mb-1.5">{label}</span>
      {children}
    </label>
  );
}

const inputClass = "w-full bg-surface-900 border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all duration-150";

export default function EditTaskModal({ task, open, onClose }: Props) {
  const { updateTask } = useSimStore();
  const [betMode, setBetMode] = useState<BetMode>('fixed');
  const [betAmount, setBetAmount] = useState(100);
  const [betPercent, setBetPercent] = useState<number | null>(null);
  const [feeRate, setFeeRate] = useState(0.002);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (task && open) {
      setBetMode(task.bet_mode || 'fixed');
      setBetAmount(task.bet_amount || 100);
      setBetPercent(task.bet_percent ?? null);
      setFeeRate(task.fee_rate || 0.002);
    }
  }, [task, open]);

  if (!open || !task) return null;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const req: Partial<TaskCreateRequest> = {
        bet_mode: betMode,
        bet_amount: betAmount,
        fee_rate: feeRate,
      };
      if (betMode === 'percent') {
        req.bet_percent = betPercent;
      } else {
        req.bet_percent = null;
      }
      await updateTask(task.id, req);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* 遮罩 */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* 模态框 */}
      <div className="relative w-full max-w-md bg-surface-800 border border-border rounded-2xl shadow-2xl shadow-black/40 overflow-hidden animate-[scaleIn_0.2s_ease-out]">
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface-800/80">
          <h2 className="text-base font-bold text-text-primary tracking-tight">
            修改任务参数 - {task.asset}
          </h2>
          <button
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-700 transition-all duration-150"
            onClick={onClose}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 表单内容 */}
        <div className="p-6 space-y-4">
          <FormField label="押注模式">
            <div className="flex gap-2">
              <button
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  betMode === 'fixed'
                    ? 'bg-accent text-white shadow-sm shadow-accent/25'
                    : 'bg-surface-900 text-text-secondary hover:text-text-primary border border-border'
                }`}
                onClick={() => setBetMode('fixed')}
              >
                固定金额
              </button>
              <button
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  betMode === 'percent'
                    ? 'bg-accent text-white shadow-sm shadow-accent/25'
                    : 'bg-surface-900 text-text-secondary hover:text-text-primary border border-border'
                }`}
                onClick={() => setBetMode('percent')}
              >
                百分比
              </button>
            </div>
          </FormField>

          <div className="grid grid-cols-2 gap-4">
            <FormField label={betMode === 'fixed' ? '押注金额 (USDT)' : '押注比例 (%)'}>
              <div className="relative">
                <input
                  type="number"
                  className={`${inputClass} pr-8 font-mono`}
                  value={betMode === 'fixed' ? betAmount : (betPercent ?? 0)}
                  onChange={e => {
                    const v = +e.target.value;
                    if (betMode === 'fixed') setBetAmount(v);
                    else setBetPercent(v);
                  }}
                  min={1}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-text-muted">
                  {betMode === 'fixed' ? 'USDT' : '%'}
                </span>
              </div>
            </FormField>

            <FormField label="手续费率">
              <div className="relative">
                <input
                  type="number"
                  className={`${inputClass} pr-8 font-mono`}
                  value={feeRate}
                  onChange={e => setFeeRate(+e.target.value)}
                  step={0.001}
                  min={0}
                  max={1}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-text-muted">%</span>
              </div>
            </FormField>
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-surface-900/50">
          <button
            className="px-5 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary rounded-lg border border-border hover:border-surface-600 transition-all duration-150"
            onClick={onClose}
          >
            取消
          </button>
          <button
            className="px-5 py-2.5 text-sm font-semibold text-white bg-accent hover:bg-accent-400 rounded-lg shadow-sm shadow-accent/25 hover:shadow-md hover:shadow-accent/30 transition-all duration-150 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? '保存中...' : '保存修改'}
          </button>
        </div>
      </div>
    </div>
  );
}
