import { useState, useRef, useEffect } from 'react';
import type { RoundResponse } from '../types';

interface Props {
  rounds: RoundResponse[];
  taskName?: string;
}

const CSV_HEADERS = [
  '轮次', '触发时间', '信号方向', '综合分数', '信心度',
  '押注方向', '押注金额', '结果', '盈亏', '结算价',
];

function escapeCsvField(field: string | number | null): string {
  if (field == null) return '';
  const str = String(field);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function roundsToCsv(rounds: RoundResponse[]): string {
  const lines: string[] = [CSV_HEADERS.join(',')];
  for (const r of rounds) {
    const row = [
      r.round_seq,
      r.trigger_kline_ts,
      r.direction ?? '',
      r.score != null ? r.score.toFixed(4) : '',
      r.confidence != null ? (r.confidence * 100).toFixed(1) + '%' : '',
      r.bet_direction ?? '',
      r.bet_amount != null ? r.bet_amount.toFixed(2) : '',
      r.result ?? '',
      r.pnl != null ? r.pnl.toFixed(2) : '',
      r.settle_price != null ? r.settle_price.toFixed(4) : '',
    ];
    lines.push(row.map(escapeCsvField).join(','));
  }
  return lines.join('\n');
}

function getTimestamp(): string {
  const now = new Date();
  const y = now.getFullYear();
  const mo = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const h = String(now.getHours()).padStart(2, '0');
  const mi = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  return `${y}${mo}${d}_${h}${mi}${s}`;
}

function downloadFile(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ExportMenu({ rounds, taskName }: Props) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const baseName = taskName || 'trades';
  const ts = getTimestamp();

  const handleCsv = () => {
    const csv = roundsToCsv(rounds);
    downloadFile(csv, `${baseName}_export_${ts}.csv`, 'text/csv;charset=utf-8');
    setOpen(false);
  };

  const handleJson = () => {
    const json = JSON.stringify(rounds, null, 2);
    downloadFile(json, `${baseName}_export_${ts}.json`, 'application/json;charset=utf-8');
    setOpen(false);
  };

  return (
    <div className="relative inline-block" ref={menuRef}>
      <button
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium
                   text-text-muted hover:text-text-secondary hover:bg-surface-700/50
                   border border-border hover:border-border-strong transition-all duration-150"
        onClick={() => setOpen(!open)}
        title="导出数据"
      >
        {/* Download icon */}
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        导出
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-36 rounded-lg border border-border bg-surface-800 shadow-xl
                        shadow-black/30 z-50 overflow-hidden animate-[scaleIn_120ms_ease-out]">
          <button
            className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-text-secondary
                       hover:bg-accent/10 hover:text-accent-300 transition-colors"
            onClick={handleCsv}
          >
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m.75 12l3 3m0 0l3-3m-3 3v-6m-1.5-9H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            导出 CSV
          </button>
          <button
            className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-text-secondary
                       hover:bg-accent/10 hover:text-accent-300 transition-colors border-t border-border/50"
            onClick={handleJson}
          >
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.25 9.75L16.5 12l-2.25 2.25m-4.5 0L7.5 12l2.25-2.25M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z" />
            </svg>
            导出 JSON
          </button>
        </div>
      )}
    </div>
  );
}
