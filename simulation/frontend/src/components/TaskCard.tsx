import type { TaskResponse } from '../types';
import { useSimStore } from '../store/useSimStore';

interface Props {
  task: TaskResponse;
}

export default function TaskCard({ task }: Props) {
  const { selectTask, selectedTaskId, startSelected, stopSelected, deleteSelected } = useSimStore();
  const isSelected = selectedTaskId === task.id;
  const isRunning = task.status === 'RUNNING';
  const isProfitable = task.current_capital >= task.initial_capital;
  const pnlPercent = ((task.current_capital - task.initial_capital) / task.initial_capital * 100);

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
          <span className="font-bold text-sm text-text-primary tracking-tight">{task.asset}</span>
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
          onClick={() => { selectTask(task.id); deleteSelected(); }}
        >
          删除
        </button>
      </div>
    </div>
  );
}
