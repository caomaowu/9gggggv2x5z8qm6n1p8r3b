import type { StatsResponse } from '../types';

interface Props {
  stats: StatsResponse | null;
}

interface StatCardProps {
  label: string;
  value: string;
  accent?: 'profit' | 'loss' | 'neutral' | 'accent';
  subtitle?: string;
}

function StatCard({ label, value, accent = 'neutral', subtitle }: StatCardProps) {
  const accentStyles = {
    profit: {
      gradient: 'from-profit/10 via-profit/5 to-transparent',
      border: 'border-profit/20',
      text: 'text-profit',
      glow: 'shadow-profit/5',
    },
    loss: {
      gradient: 'from-loss/10 via-loss/5 to-transparent',
      border: 'border-loss/20',
      text: 'text-loss',
      glow: 'shadow-loss/5',
    },
    accent: {
      gradient: 'from-accent/10 via-accent/5 to-transparent',
      border: 'border-accent/20',
      text: 'text-accent-300',
      glow: 'shadow-accent/5',
    },
    neutral: {
      gradient: 'from-surface-700/50 to-transparent',
      border: 'border-border',
      text: 'text-text-primary',
      glow: 'shadow-transparent',
    },
  };

  const s = accentStyles[accent];

  return (
    <div className={`relative rounded-xl border ${s.border} bg-gradient-to-b ${s.gradient} p-4
      transition-all duration-200 hover:border-border-strong hover:shadow-lg ${s.glow}`}>
      <div className="text-[10px] font-semibold uppercase tracking-widest text-text-muted mb-2">{label}</div>
      <div className={`text-xl font-bold font-mono tracking-tight ${s.text}`}>{value}</div>
      {subtitle && (
        <div className="text-[10px] text-text-muted mt-1 font-medium">{subtitle}</div>
      )}
    </div>
  );
}

export default function StatsPanel({ stats }: Props) {
  if (!stats) {
    return (
      <div className="rounded-xl border border-border bg-surface-900 p-8 text-center">
        <div className="w-14 h-14 rounded-full bg-surface-800 flex items-center justify-center mx-auto mb-4">
          <svg className="w-7 h-7 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </div>
        <p className="text-text-muted text-sm font-medium">选择任务查看统计</p>
      </div>
    );
  }

  const roiStr = `${stats.roi >= 0 ? '+' : ''}${(stats.roi * 100).toFixed(1)}%`;
  const ddStr = `${(stats.max_drawdown * 100).toFixed(2)}%`;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">交易统计</h3>
        <div className="flex items-center gap-3 text-[10px] text-text-muted">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-profit" /> {stats.wins}W
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-loss" /> {stats.losses}L
          </span>
          <span>{stats.skips} skips</span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          label="总盈亏"
          value={`${stats.total_pnl >= 0 ? '+' : ''}$${stats.total_pnl.toFixed(2)}`}
          accent={stats.total_pnl >= 0 ? 'profit' : 'loss'}
          subtitle="累计"
        />
        <StatCard
          label="胜率"
          value={`${(stats.win_rate * 100).toFixed(1)}%`}
          accent={stats.win_rate >= 0.5 ? 'profit' : 'neutral'}
          subtitle={`${stats.wins}/${stats.wins + stats.losses + stats.skips} 回合`}
        />
        <StatCard
          label="当前资金"
          value={`$${stats.current_capital.toFixed(2)}`}
          accent="accent"
          subtitle={`ROI ${roiStr}`}
        />
        <StatCard
          label="最大回撤"
          value={ddStr}
          accent="loss"
          subtitle="最大亏损幅度"
        />
        <StatCard
          label="夏普比率"
          value={stats.sharpe_ratio.toFixed(2)}
          accent={stats.sharpe_ratio >= 1 ? 'profit' : stats.sharpe_ratio >= 0 ? 'neutral' : 'loss'}
          subtitle="风险调整收益"
        />
        <StatCard
          label="盈亏因子"
          value={stats.profit_factor.toFixed(2)}
          accent={stats.profit_factor >= 1.5 ? 'profit' : stats.profit_factor >= 1 ? 'neutral' : 'loss'}
          subtitle="盈利/亏损比"
        />
        <StatCard
          label="连胜"
          value={`${stats.best_win_streak}W`}
          accent="profit"
          subtitle={`最佳连胜`}
        />
        <StatCard
          label="连败"
          value={`${stats.worst_lose_streak}L`}
          accent="loss"
          subtitle={`最差连败`}
        />
      </div>
    </div>
  );
}
