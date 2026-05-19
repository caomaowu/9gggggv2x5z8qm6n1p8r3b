import { useSimStore } from '../store/useSimStore';

interface Props {
  taskId: string;
}

export default function PositionBar(_props: Props) {
  const latestRound = useSimStore((s) => s.latestRound);

  if (!latestRound) {
    return (
      <div className="rounded-xl border border-border bg-surface-800 p-4 flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-surface-700 flex items-center justify-center">
            <svg className="w-5 h-5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <span className="text-text-muted font-medium text-sm">暂无持仓</span>
        </div>
      </div>
    );
  }

  const isLong = latestRound.direction === 'long';
  const isShort = latestRound.direction === 'short';
  const isPlaced = latestRound.status === 'BET_PLACED';
  const score = latestRound.score ?? 0;
  const confidence = latestRound.confidence ?? 0;

  return (
    <div className="rounded-xl border border-border bg-surface-800 p-4 flex items-center gap-6">
      {/* 方向徽章 */}
      <div className="flex items-center gap-3">
        {isLong ? (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-profit/15 border border-profit/20">
            <svg className="w-5 h-5 text-profit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
            </svg>
            <span className="text-lg font-bold text-profit">做多</span>
          </div>
        ) : isShort ? (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-loss/15 border border-loss/20">
            <svg className="w-5 h-5 text-loss" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
            <span className="text-lg font-bold text-loss">做空</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-700 border border-surface-600/30">
            <svg className="w-5 h-5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
            <span className="text-lg font-bold text-text-muted">观望</span>
          </div>
        )}

        {/* 押注金额 */}
        {latestRound.bet_amount != null && (
          <div className="text-sm">
            <span className="text-text-muted text-[11px] uppercase tracking-wide">押注</span>
            <span className="ml-2 font-mono font-semibold text-text-primary">
              ${latestRound.bet_amount.toFixed(2)}
            </span>
          </div>
        )}

        {/* BET_PLACED 浮盈提示 */}
        {isPlaced && (
          <div className="px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <span className="text-amber-400 text-xs font-medium flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              持仓中
            </span>
          </div>
        )}
      </div>

      {/* 分隔线 */}
      <div className="w-px h-8 bg-border shrink-0" />

      {/* 分数和信心 */}
      <div className="flex items-center gap-8">
        <div className="flex flex-col">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">综合分数</span>
          <span className={`font-mono font-bold text-sm ${
            score > 0 ? 'text-profit' : score < 0 ? 'text-loss' : 'text-text-secondary'
          }`}>
            {score.toFixed(2)}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">信心</span>
          <span className={`font-mono font-bold text-sm ${
            confidence >= 0.6 ? 'text-profit-400' : confidence >= 0.4 ? 'text-text-secondary' : 'text-loss-400'
          }`}>
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* 分隔线 */}
      <div className="w-px h-8 bg-border shrink-0" />

      {/* 轮次信息 */}
      <div className="flex items-center gap-4 ml-auto">
        <span className="text-[10px] text-text-muted">
          Round <span className="font-mono text-text-secondary font-semibold">#{latestRound.round_seq}</span>
        </span>
      </div>
    </div>
  );
}
