import { useState, useMemo, Fragment } from 'react';
import type { RoundResponse, RoundFilter, RoundResult, Direction } from '../types';
import { useSimStore } from '../store/useSimStore';

interface Props {
  rounds: RoundResponse[];
  total: number;
}

function formatTs(ts: string) {
  return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function formatNumber(v: number | null, decimals = 2): string {
  if (v == null) return '—';
  return v.toFixed(decimals);
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

function MarketTag({ label, value }: { label: string; value: string }) {
  const colorMap: Record<string, string> = {
    'expanding': 'bg-cyan-400/10 text-cyan-400 border-cyan-400/20',
    'contracting': 'bg-amber-400/10 text-amber-400 border-amber-400/20',
    'aligned': 'bg-profit/10 text-profit border-profit/20',
    'divergent': 'bg-loss/10 text-loss border-loss/20',
    'low': 'bg-profit/10 text-profit-400 border-profit/20',
    'medium': 'bg-amber-400/10 text-amber-400 border-amber-400/20',
    'high': 'bg-loss/10 text-loss-400 border-loss/20',
  };
  const color = colorMap[value] || 'bg-surface-700 text-text-muted border-surface-600/30';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium border ${color}`}>
      <span className="text-text-muted">{label}</span>
      <span>{value}</span>
    </span>
  );
}

function ScoreBar({ score, color }: { score: number | null; color: 'profit' | 'loss' }) {
  if (score == null) return <span className="text-text-muted text-xs">—</span>;
  const pct = Math.min(Math.abs(score) * 100, 100);
  const barColor = color === 'profit' ? 'bg-profit' : 'bg-loss';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-surface-700 overflow-hidden">
        <div className={`h-full rounded-full ${barColor} transition-all duration-300`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] font-mono font-semibold w-10 text-right text-text-secondary">
        {score.toFixed(2)}
      </span>
    </div>
  );
}

function AgentAnalysis({ label, score, confidence, summary }: {
  label: string;
  score: number | null;
  confidence: number | null;
  summary: string | null;
}) {
  const [showRaw, setShowRaw] = useState(false);

  // Parse summary JSON
  let parsed: Record<string, unknown> | null = null;
  if (summary) {
    try { parsed = JSON.parse(summary); } catch { /* not JSON, show as text */ }
  }

  const isPositive = score != null && score >= 0;

  return (
    <div className="flex flex-col gap-2 p-3 rounded-lg bg-surface-800 border border-border/40">
      {/* Header: label + confidence badge */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary">{label}</span>
        {confidence != null && (
          <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
            confidence >= 0.6 ? 'bg-profit/10 text-profit-400' :
            confidence >= 0.4 ? 'bg-surface-700 text-text-secondary' :
            'bg-loss/10 text-loss-400'
          }`}>
            {(confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {/* Score bar */}
      <ScoreBar score={score} color={isPositive ? 'profit' : 'loss'} />

      {/* Parsed text content */}
      {parsed ? (
        <div className="space-y-1.5">
          {parsed.momentum_detail && (
            <p className="text-[11px] text-text-secondary leading-relaxed">{String(parsed.momentum_detail)}</p>
          )}
          {parsed.conflict_detail && (
            <div className="mt-1.5 pt-1.5 border-t border-border/30">
              <span className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider">矛盾</span>
              <p className="text-[11px] text-text-secondary leading-relaxed mt-0.5">{String(parsed.conflict_detail)}</p>
            </div>
          )}
          {parsed.next_focus && (
            <div className="mt-1.5 pt-1.5 border-t border-border/30">
              <span className="text-[10px] font-semibold text-accent-300/80 uppercase tracking-wider">关注</span>
              <p className="text-[11px] text-text-secondary leading-relaxed mt-0.5">{String(parsed.next_focus)}</p>
            </div>
          )}
          {/* Show any other Chinese text fields that aren't these standard ones */}
          {Object.entries(parsed).map(([k, v]) => {
            if (['movement_score', 'movement_confidence', 'momentum_detail', 'conflict_detail', 'next_focus', 'expansion', 'alignment', 'noise'].includes(k)) return null;
            if (typeof v !== 'string' || v.length < 20) return null;
            return (
              <div key={k} className="mt-1.5 pt-1.5 border-t border-border/30">
                <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">{k}</span>
                <p className="text-[11px] text-text-secondary leading-relaxed mt-0.5">{v}</p>
              </div>
            );
          })}
        </div>
      ) : summary ? (
        <p className="text-[11px] text-text-secondary leading-relaxed">{summary}</p>
      ) : null}

      {/* Toggle raw JSON */}
      {parsed && (
        <button
          className="text-[10px] text-text-muted hover:text-text-secondary transition-colors self-start mt-1"
          onClick={(e) => { e.stopPropagation(); setShowRaw(!showRaw); }}
        >
          {showRaw ? '收起原始数据' : '查看原始数据'}
        </button>
      )}
      {showRaw && parsed && (
        <pre className="p-2 rounded bg-surface-900 border border-border/30 text-[10px] text-text-muted font-mono overflow-auto max-h-32">
          {JSON.stringify(parsed, null, 2)}
        </pre>
      )}
    </div>
  );
}

function FusionPanel({ fusionRaw }: { fusionRaw: unknown }) {
  const [showRaw, setShowRaw] = useState(false);
  let fusion: Record<string, unknown> | null = null;
  try { fusion = typeof fusionRaw === 'string' ? JSON.parse(fusionRaw) : fusionRaw as Record<string, unknown>; } catch {}
  if (!fusion) return null;

  const direction = String(fusion.direction || 'none');
  const score = Number(fusion.score ?? 0);
  const confidence = Number(fusion.confidence ?? 0);
  const expansion = String(fusion.expansion || '—');
  const alignment = String(fusion.alignment || '—');
  const noise = String(fusion.noise || '—');

  return (
    <div className="rounded-lg bg-surface-800 border border-accent/15 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-accent-300">Fusion 共识</span>
        <button
          className="text-[10px] text-text-muted hover:text-text-secondary transition-colors"
          onClick={() => setShowRaw(!showRaw)}
        >
          {showRaw ? '收起原始数据' : '查看原始数据'}
        </button>
      </div>

      {/* Main consensus row */}
      <div className="flex items-center gap-4 mb-3">
        {/* Direction badge */}
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
          direction === 'long' ? 'bg-profit/15 border border-profit/20' :
          direction === 'short' ? 'bg-loss/15 border border-loss/20' :
          'bg-surface-700 border border-surface-600/30'
        }`}>
          {direction === 'long' ? (
            <svg className="w-4 h-4 text-profit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
            </svg>
          ) : direction === 'short' ? (
            <svg className="w-4 h-4 text-loss" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          ) : (
            <svg className="w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
            </svg>
          )}
          <span className={`text-sm font-bold ${
            direction === 'long' ? 'text-profit' : direction === 'short' ? 'text-loss' : 'text-text-muted'
          }`}>
            {direction === 'long' ? '做多' : direction === 'short' ? '做空' : '观望'}
          </span>
        </div>

        {/* Score + Confidence */}
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-center">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">分数</span>
            <span className={`text-base font-mono font-bold ${score >= 0.5 ? 'text-profit' : score >= 0.35 ? 'text-accent-300' : 'text-loss'}`}>
              {score.toFixed(2)}
            </span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">信心</span>
            <span className={`text-base font-mono font-bold ${confidence >= 0.6 ? 'text-profit-400' : confidence >= 0.4 ? 'text-text-secondary' : 'text-loss-400'}`}>
              {(confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* Market state tags */}
      <div className="flex flex-wrap gap-2 mb-3">
        <MarketTag label="扩张" value={expansion} />
        <MarketTag label="一致性" value={alignment} />
        <MarketTag label="噪声" value={noise} />
      </div>

      {/* Key text content from fusion */}
      {fusion.momentum_detail && (
        <div className="mt-2 pt-2 border-t border-border/30">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">动量分析</span>
          <p className="text-[11px] text-text-secondary leading-relaxed mt-1">{String(fusion.momentum_detail)}</p>
        </div>
      )}
      {fusion.conflict_detail && (
        <div className="mt-2 pt-2 border-t border-border/30">
          <span className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider">矛盾</span>
          <p className="text-[11px] text-text-secondary leading-relaxed mt-1">{String(fusion.conflict_detail)}</p>
        </div>
      )}
      {fusion.next_focus && (
        <div className="mt-2 pt-2 border-t border-border/30">
          <span className="text-[10px] font-semibold text-accent-300/80 uppercase tracking-wider">关注</span>
          <p className="text-[11px] text-text-secondary leading-relaxed mt-1">{String(fusion.next_focus)}</p>
        </div>
      )}

      {/* Collapsed raw JSON */}
      {showRaw && (
        <pre className="mt-3 p-3 rounded-lg bg-surface-900 border border-border/50 text-[10px] text-text-muted font-mono overflow-auto max-h-48">
          {JSON.stringify(fusion, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ── K线数据 panel (inside expanded row) ──
function KlinePanel({ round }: { round: RoundResponse }) {
  const hasData = round.trigger_kline_open != null || round.trigger_kline_close != null
    || round.settle_kline_ts != null || round.settle_price != null;
  if (!hasData) return null;

  return (
    <div className="rounded-lg bg-surface-800 border border-border/40 p-3">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">K线数据</span>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 mt-2">
        {round.trigger_kline_open != null && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-muted">开盘价</span>
            <span className="text-[11px] font-mono text-text-secondary">{formatNumber(round.trigger_kline_open, 4)}</span>
          </div>
        )}
        {round.trigger_kline_close != null && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-muted">收盘价</span>
            <span className="text-[11px] font-mono text-text-secondary">{formatNumber(round.trigger_kline_close, 4)}</span>
          </div>
        )}
        {round.settle_kline_ts != null && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-muted">结算时间</span>
            <span className="text-[11px] font-mono text-text-secondary">{formatTs(round.settle_kline_ts)}</span>
          </div>
        )}
        {round.settle_price != null && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-muted">结算价</span>
            <span className="text-[11px] font-mono text-text-secondary">{formatNumber(round.settle_price, 4)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Filter Bar ──
function FilterBar({
  filter, onChange, activeCount,
}: {
  filter: RoundFilter;
  onChange: (f: RoundFilter) => void;
  activeCount: number;
}) {
  return (
    <div className="px-4 py-2 border-b border-border bg-surface-800/40">
      <div className="flex items-center gap-2 flex-wrap">
        {/* Result filter */}
        <div className="flex items-center rounded-md border border-border overflow-hidden">
          {(['', 'WIN', 'LOSE', 'SKIP'] as const).map(val => (
            <button
              key={val}
              className={`px-2 py-1 text-[10px] font-medium transition-colors
                ${filter.result === val
                  ? 'bg-accent/20 text-accent-300'
                  : 'text-text-muted hover:text-text-secondary'
                }`}
              onClick={() => onChange({ ...filter, result: val })}
            >
              {val === '' ? '全部' : val === 'WIN' ? '盈利' : val === 'LOSE' ? '亏损' : '跳过'}
            </button>
          ))}
        </div>

        {/* Direction filter */}
        <div className="flex items-center rounded-md border border-border overflow-hidden">
          {(['', 'long', 'short', 'none'] as const).map(val => (
            <button
              key={val}
              className={`px-2 py-1 text-[10px] font-medium transition-colors
                ${filter.direction === val
                  ? 'bg-accent/20 text-accent-300'
                  : 'text-text-muted hover:text-text-secondary'
                }`}
              onClick={() => onChange({ ...filter, direction: val })}
            >
              {val === '' ? '全部' : val === 'long' ? '做多' : val === 'short' ? '做空' : '观望'}
            </button>
          ))}
        </div>

        {/* Search input */}
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            className="w-32 px-2 py-1 rounded-md border border-border bg-surface-900 text-text-primary text-[10px] font-mono
                       placeholder:text-text-muted/50 outline-none focus:border-accent/40 focus:bg-surface-800 transition-colors"
            placeholder="轮次/日期..."
            value={filter.search || ''}
            onChange={e => onChange({ ...filter, search: e.target.value })}
          />
        </div>

        {/* Clear button */}
        {activeCount > 0 && (
          <button
            className="px-2 py-1 rounded-md text-[10px] font-medium text-text-muted hover:text-text-secondary
                       hover:bg-surface-700 transition-colors"
            onClick={() => onChange({})}
          >
            重置
            <span className="ml-1 px-1 rounded bg-surface-700 text-[9px]">{activeCount}</span>
          </button>
        )}
      </div>
    </div>
  );
}

export default function RoundTable({ rounds, total }: Props) {
  const { loadMoreRounds } = useSimStore();
  const hasMore = rounds.length < total;
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<RoundFilter>({});

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filter.result) count++;
    if (filter.direction) count++;
    if (filter.search && filter.search.trim()) count++;
    return count;
  }, [filter]);

  // Client-side filtering
  const filteredRounds = useMemo(() => {
    let result = rounds;
    if (filter.result) {
      result = result.filter(r => r.result === filter.result);
    }
    if (filter.direction) {
      result = result.filter(r => r.direction === filter.direction);
    }
    if (filter.search && filter.search.trim()) {
      const s = filter.search.trim().toLowerCase();
      result = result.filter(r =>
        String(r.round_seq).includes(s) ||
        r.trigger_kline_ts.toLowerCase().includes(s)
      );
    }
    return result;
  }, [rounds, filter]);

  const filteredCount = filteredRounds.length;
  const totalDisplay = filteredCount !== rounds.length
    ? `${filteredCount}/${total}`
    : `${total}`;

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
          <span className="ml-2 text-text-muted font-normal text-xs">({totalDisplay} 条)</span>
        </h3>
      </div>

      {/* Filter bar */}
      <FilterBar filter={filter} onChange={setFilter} activeCount={activeFilterCount} />

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
            {filteredRounds.map((r, i) => {
              const isExpanded = expandedId === r.id;
              return (
                <Fragment key={r.id}>
                  <tr
                    className={`border-t border-border/50 transition-colors duration-100 cursor-pointer
                      ${isExpanded ? 'bg-surface-750' : i % 2 === 0 ? 'bg-surface-800/20' : 'bg-surface-800/50'}
                      hover:bg-accent/5`}
                    onClick={() => setExpandedId(isExpanded ? null : r.id)}
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
                  {isExpanded && (
                    <tr className="border-t border-border/30 bg-surface-800">
                      <td colSpan={8} className="p-4">
                        <div className="space-y-3">
                          {/* 三 Agent 分析 */}
                          <div className="grid grid-cols-3 gap-3">
                            <AgentAnalysis
                              label="Indicator Agent"
                              score={r.indicator_score}
                              confidence={r.indicator_confidence}
                              summary={r.indicator_summary ?? null}
                            />
                            <AgentAnalysis
                              label="Structure Agent"
                              score={r.structure_score}
                              confidence={r.structure_confidence}
                              summary={r.structure_summary ?? null}
                            />
                            <AgentAnalysis
                              label="Mechanics Agent"
                              score={r.mechanics_score}
                              confidence={r.mechanics_confidence}
                              summary={r.mechanics_summary ?? null}
                            />
                          </div>

                          {/* Fusion Consensus */}
                          {r.fusion_raw != null && <FusionPanel fusionRaw={r.fusion_raw} />}

                          {/* K线数据 */}
                          <KlinePanel round={r} />
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
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
