import type { RoundResponse } from '../types';
import { useSimStore } from '../store/useSimStore';

interface Props {
  rounds: RoundResponse[];
  total: number;
}

function formatTs(ts: string) {
  return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function DirectionBadge({ dir }: { dir: string | null }) {
  if (!dir || dir === 'none') return <span className="text-text-muted">—</span>;
  const isLong = dir === 'long';
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-semibold
      ${isLong ? 'bg-profit/10 text-profit' : 'bg-loss/10 text-loss'}`}>
      <span className={`w-0 h-0 border-[4px] border-transparent ${isLong ? 'border-b-profit mb-0.5' : 'border-t-loss mt-0.5'}`} />
      {isLong ? '多' : '空'}
    </span>
  );
}

function ResultBadge({ result }: { result: string | null }) {
  if (!result) return <span className="text-text-muted text-xs">待定</span>;

  const styles: Record<string, string> = {
    WIN: 'bg-profit/10 text-profit border-profit/20',
    LOSE: 'bg-loss/10 text-loss border-loss/20',
    SKIP: 'bg-surface-700 text-text-muted border-surface-600/30',
  };

  const labels: Record<string, string> = {
    WIN: '盈利',
    LOSE: '亏损',
    SKIP: '跳过',
  };

  const s = styles[result] || styles.SKIP;
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border ${s}`}>
      {labels[result] || result}
    </span>
  );
}

export default function RoundTable({ rounds, total }: Props) {
  const { loadMoreRounds } = useSimStore();
  const hasMore = rounds.length < total;

  if (rounds.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <h3 className="text-sm font-semibold text-text-primary">交易记录</h3>
        </div>
        <div className="py-12 text-center">
          <svg className="w-12 h-12 text-text-muted/20 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <p className="text-text-muted text-sm">暂无交易记录</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface-900 overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">
          交易记录
          <span className="ml-2 text-text-muted font-normal text-xs">({total} 条)</span>
        </h3>
      </div>

      <div className="overflow-auto max-h-[480px]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-surface-800/80 sticky top-0 z-10 backdrop-blur-sm">
              <th className="text-left p-3 text-text-muted font-medium uppercase tracking-wider text-[10px] w-12">#</th>
              <th className="text-left p-3 text-text-muted font-medium uppercase tracking-wider text-[10px]">时间</th>
              <th className="text-left p-3 text-text-muted font-medium uppercase tracking-wider text-[10px]">方向</th>
              <th className="text-right p-3 text-text-muted font-medium uppercase tracking-wider text-[10px]">分数</th>
              <th className="text-right p-3 text-text-muted font-medium uppercase tracking-wider text-[10px]">信心</th>
              <th className="text-right p-3 text-text-muted font-medium uppercase tracking-wider text-[10px]">押注</th>
              <th className="text-center p-3 text-text-muted font-medium uppercase tracking-wider text-[10px]">结果</th>
              <th className="text-right p-3 text-text-muted font-medium uppercase tracking-wider text-[10px]">盈亏</th>
            </tr>
          </thead>
          <tbody>
            {rounds.map((r, i) => (
              <tr
                key={r.id}
                className={`border-t border-border/50 transition-colors duration-100
                  ${i % 2 === 0 ? 'bg-surface-800/20' : 'bg-surface-800/50'}
                  hover:bg-accent/5`}
              >
                <td className="p-3 text-text-muted font-mono text-[11px]">{r.round_seq}</td>
                <td className="p-3 text-text-secondary font-mono text-[11px]">{formatTs(r.trigger_kline_ts)}</td>
                <td className="p-3"><DirectionBadge dir={r.direction} /></td>
                <td className="p-3 text-right font-mono text-text-secondary">
                  {r.score != null ? r.score.toFixed(2) : '—'}
                </td>
                <td className="p-3 text-right font-mono">
                  {r.confidence != null ? (
                    <span className={r.confidence >= 0.6 ? 'text-profit-400' : r.confidence >= 0.4 ? 'text-text-secondary' : 'text-loss-400'}>
                      {(r.confidence * 100).toFixed(0)}%
                    </span>
                  ) : '—'}
                </td>
                <td className="p-3 text-right font-mono text-text-secondary">
                  {r.bet_amount != null ? `$${r.bet_amount.toFixed(0)}` : '—'}
                </td>
                <td className="p-3 text-center"><ResultBadge result={r.result} /></td>
                <td className={`p-3 text-right font-mono font-semibold text-[11px] ${
                  r.pnl == null ? 'text-text-muted' : r.pnl >= 0 ? 'text-profit' : 'text-loss'
                }`}>
                  {r.pnl != null ? `${r.pnl >= 0 ? '+' : ''}$${r.pnl.toFixed(2)}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMore && (
        <div className="px-5 py-3 border-t border-border bg-surface-800/30">
          <button
            className="w-full py-2 text-sm font-medium text-accent-400 hover:text-accent-300 rounded-lg
                       hover:bg-accent/5 transition-all duration-150 active:scale-[0.99]"
            onClick={loadMoreRounds}
          >
            加载更多 ({rounds.length}/{total})
          </button>
        </div>
      )}
    </div>
  );
}
