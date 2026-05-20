import { useState, useEffect, useMemo } from 'react';
import type { TaskResponse } from '../types';
import { useSimStore } from '../store/useSimStore';
import ConfirmDialog from './ConfirmDialog';

interface Props {
  task: TaskResponse;
  onEdit: (task: TaskResponse) => void;
}

const TIMEFRAME_SECONDS: Record<string, number> = {
  '1m': 60,
  '3m': 180,
  '5m': 300,
  '15m': 900,
  '1h': 3600,
  '4h': 14400,
  '1d': 86400,
};

export default function TaskCard({ task, onEdit }: Props) {
  const { selectTask, selectedTaskId, startSelected, stopSelected, deleteSelected, clearSelectedRounds } = useSimStore();
  const isSelected = selectedTaskId === task.id;
  const isRunning = task.status === 'RUNNING';
  const isProfitable = task.current_capital >= task.initial_capital;
  const pnlPercent = ((task.current_capital - task.initial_capital) / task.initial_capital * 100);

  // ── 连胜/连败 badge ──
  const streakBadge = useMemo(() => {
    if (!task.current_streak) return null;
    const streak = task.current_streak;
    if (streak.startsWith('W')) {
      const count = streak.slice(1);
      return { emoji: '\uD83D\uDD25', label: `连胜${count}`, color: 'bg-profit/10 text-profit border-profit/20' };
    }
    if (streak.startsWith('L')) {
      const count = streak.slice(1);
      return { label: `连败${count}`, color: 'bg-loss/10 text-loss border-loss/20' };
    }
    return null;
  }, [task.current_streak]);

  // ── K线倒计时 ──
  const timeframeSeconds = useMemo(
    () => TIMEFRAME_SECONDS[task.timeframe] ?? 0,
    [task.timeframe],
  );

  const [countdown, setCountdown] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!task.last_kline_ts || task.status !== 'RUNNING' || !timeframeSeconds) {
      setCountdown(null);
      return;
    }

    const calcCountdown = () => {
      const lastTs = new Date(task.last_kline_ts!).getTime();
      const nextTrigger = lastTs + timeframeSeconds * 1000;
      const now = Date.now();
      const remaining = Math.max(0, Math.floor((nextTrigger - now) / 1000));

      if (remaining <= 0) {
        setCountdown('触发中...');
        return;
      }

      const minutes = Math.floor(remaining / 60);
      const seconds = remaining % 60;
      if (minutes > 0) {
        setCountdown(`下次触发: ${minutes}m ${seconds.toString().padStart(2, '0')}s`);
      } else {
        setCountdown(`下次触发: ${seconds}s`);
      }
    };

    calcCountdown();
    const timer = setInterval(calcCountdown, 1000);
    return () => clearInterval(timer);
  }, [task.last_kline_ts, task.status, timeframeSeconds]);

  const klineDisplay = useMemo(() => {
    if (!task.last_kline_ts) return null;
    if (task.status !== 'RUNNING') {
      return <span className="text-[10px] text-text-muted">已停止</span>;
    }
    if (countdown == null) return null;
    return (
      <span className={`text-[10px] font-mono ${countdown === '触发中...' ? 'text-accent-300 animate-pulse' : 'text-text-muted'}`}>
        {countdown}
      </span>
    );
  }, [task.last_kline_ts, task.status, countdown]);

  return (
    <div
      className={`rounded-xl border cursor-pointer transition-all duration-200 overflow-hidden
        ${isSelected
          ? 'border-accent/40 bg-surface-800 shadow-lg shadow-accent/5 ring-1 ring-accent/20'
          : 'border-border bg-surface-800/50 hover:bg-surface-800 hover:border-border-strong'
        }`}
      onClick={() => selectTask(task.id)}
    >
      {/* 顶部资产信息 */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-text-primary tracking-tight">{task.asset}</span>
            <button
              className="px-2 py-0.5 rounded text-[10px] font-medium text-accent-300 hover:text-white hover:bg-accent/20 border border-accent/20 hover:border-accent/40 transition-all duration-150"
              onClick={(e) => { e.stopPropagation(); onEdit(task); }}
              title="编辑参数"
            >
              编辑
            </button>
          </div>
          <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide
            ${isRunning
              ? 'bg-profit/15 text-profit border border-profit/20'
              : 'bg-surface-700 text-text-muted border border-surface-600/50'
            }`}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle ${isRunning ? 'bg-profit animate-pulse' : 'bg-text-muted'}`} />
            {task.status}
          </span>
        </div>
        <div className="text-[11px] text-text-muted font-medium">{task.timeframe}</div>
      </div>

      {/* 资金信息 */}
      <div className={`px-4 py-2 border-t ${isSelected ? 'border-accent/10' : 'border-border'}`}>
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-1.5">
            <span className={`text-lg font-bold font-mono tracking-tight
              ${isProfitable ? 'text-profit' : 'text-loss'}`}>
              ${task.current_capital.toFixed(2)}
            </span>
            <span className={`text-[11px] font-mono ${isProfitable ? 'text-profit/60' : 'text-loss/60'}`}>
              {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
            </span>
          </div>
          <span className="text-[10px] text-text-muted font-mono">
            {task.total_rounds}R
          </span>
        </div>
      </div>

      {/* 战绩条 */}
      <div className={`px-4 py-2 border-t ${isSelected ? 'border-accent/10' : 'border-border'}`}>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="flex items-center gap-1 text-profit-400 font-medium">
            <span className="w-1 h-1 rounded-full bg-profit" />
            {task.wins}W
          </span>
          <span className="flex items-center gap-1 text-loss-400 font-medium">
            <span className="w-1 h-1 rounded-full bg-loss" />
            {task.losses}L
          </span>
          {task.skips > 0 && (
            <span className="text-text-muted ml-auto">{task.skips} skips</span>
          )}
          {task.wins + task.losses > 0 && (
            <span className="ml-auto text-text-muted">
              {((task.wins / (task.wins + task.losses)) * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {/* 连胜/连败 + K线倒计时 */}
        <div className="flex items-center justify-between mt-1.5 min-h-[18px]">
          {streakBadge && (
            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${streakBadge.color}`}>
              {streakBadge.emoji} {streakBadge.label}
            </span>
          )}
          {klineDisplay}
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-1.5 px-3 py-2.5 border-t border-border bg-surface-950/40" onClick={e => e.stopPropagation()}>
        {!isRunning ? (
          <button
            className="flex-1 px-2 py-1.5 bg-profit/15 hover:bg-profit/25 text-profit text-[11px] font-semibold rounded-lg
                       transition-all duration-150 hover:shadow-sm hover:shadow-profit/10 active:scale-[0.97]"
            onClick={() => { selectTask(task.id); startSelected(); }}
          >
            启动
          </button>
        ) : (
          <button
            className="flex-1 px-2 py-1.5 bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 text-[11px] font-semibold rounded-lg
                        transition-all duration-150 hover:shadow-sm hover:shadow-amber-500/10 active:scale-[0.97]"
            onClick={() => { selectTask(task.id); stopSelected(); }}
          >
            停止
          </button>
        )}
        <button
          className="px-2 py-1.5 bg-loss/10 hover:bg-loss/20 text-loss/70 hover:text-loss text-[11px] font-semibold rounded-lg
                     transition-all duration-150 active:scale-[0.97]"
          onClick={(e) => { e.stopPropagation(); selectTask(task.id); setConfirmDelete(true); }}
        >
          删除
        </button>
        {task.total_rounds > 0 && (
          <button
            className="px-2 py-1.5 bg-surface-700 hover:bg-surface-600 text-text-muted hover:text-text-secondary text-[11px] font-medium rounded-lg
                       transition-all duration-150 active:scale-[0.97]"
            onClick={(e) => { e.stopPropagation(); selectTask(task.id); setConfirmClear(true); }}
            title="清空交易记录和分析数据"
          >
            清空
          </button>
        )}
      </div>

      {/* 删除确认 */}
      <ConfirmDialog
        open={confirmDelete}
        title="删除任务"
        message={`确定要删除任务「${task.asset} ${task.timeframe}」吗？该操作不可撤销，所有关联的交易记录也将被删除。`}
        confirmLabel="删除"
        confirmDanger
        onConfirm={() => { deleteSelected(); setConfirmDelete(false); }}
        onCancel={() => setConfirmDelete(false)}
      />

      {/* 清空确认 */}
      <ConfirmDialog
        open={confirmClear}
        title="清空交易记录"
        message={`确定要清空任务「${task.asset} ${task.timeframe}」的所有交易记录和分析数据吗？该操作不可撤销。`}
        confirmLabel="清空"
        confirmDanger
        onConfirm={() => { clearSelectedRounds(); setConfirmClear(false); }}
        onCancel={() => setConfirmClear(false)}
      />
    </div>
  );
}
