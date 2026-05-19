import { useEffect, useRef } from 'react';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import type { EquityPoint } from '../types';

interface Props {
  data: EquityPoint[];
}

const CHART_COLORS = {
  bg: '#0f172a',
  grid: 'rgba(59, 130, 246, 0.06)',
  gridBorder: 'rgba(59, 130, 246, 0.12)',
  text: '#64748b',
  line: '#3b82f6',
  profitArea: 'rgba(16, 185, 129, 0.08)',
  lossArea: 'rgba(239, 68, 68, 0.05)',
};

export default function EquityChart({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: CHART_COLORS.bg },
        textColor: CHART_COLORS.text,
      },
      grid: {
        vertLines: { color: CHART_COLORS.grid },
        horzLines: { color: CHART_COLORS.grid },
      },
      rightPriceScale: {
        borderColor: CHART_COLORS.gridBorder,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: CHART_COLORS.gridBorder,
        timeVisible: false,
      },
      crosshair: {
        vertLine: {
          color: 'rgba(59, 130, 246, 0.3)',
          width: 1,
          style: 2,
        },
        horzLine: {
          color: 'rgba(59, 130, 246, 0.3)',
          width: 1,
          style: 2,
        },
      },
    });

    const series = chart.addSeries(LineSeries, {
      color: CHART_COLORS.line,
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
      crosshairMarkerBorderColor: CHART_COLORS.line,
      crosshairMarkerBackgroundColor: CHART_COLORS.bg,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    if (data.length > 0) {
      const chartData = data.map((p, i) => ({
        time: i as never,
        value: p.cumulative_pnl,
      }));
      series.setData(chartData);

      chart.timeScale().fitContent();
    }

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <h3 className="text-sm font-semibold text-text-primary">权益曲线</h3>
        </div>
        <div className="h-[300px] flex items-center justify-center">
          <div className="text-center">
            <svg className="w-12 h-12 text-text-muted/30 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
            </svg>
            <p className="text-text-muted text-sm">暂无权益数据</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface-900 overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">权益曲线</h3>
        <div className="flex items-center gap-3 text-[10px] text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 rounded-full bg-accent" /> 累计盈亏
          </span>
        </div>
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
