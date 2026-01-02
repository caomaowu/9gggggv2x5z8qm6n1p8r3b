import { useAppStore } from '../store/useAppStore';
import { AVAILABLE_MODELS } from '../types';
import type { AnalyzeRequest } from '../types';
import styles from './ConfigPanel.module.css';

export default function ConfigPanel() {
  const { 
      dataMethod, setDataMethod,
      startDate, startTime, endDate, endTime, useCurrentTime, setDateConfig,
      aiVersion, setAiVersion, dualModelConfig, setDualModelConfig,
      klineCount, setKlineCount, futureKlineCount, setFutureKlineCount
  } = useAppStore();

  type DataMethod = AnalyzeRequest['data_method'];

  const handleDataMethodChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      setDataMethod(e.target.value as DataMethod);
  };

  return (
    <>
    {/* Date & Time Configuration */}
    <div className={styles.panel}>
        <h4 className={styles.panelTitle}>
            <i className="fas fa-calendar-alt"></i> Date & Time Configuration
        </h4>

        <div className={styles.formGroup}>
            <label className={styles.formLabel}>
                <i className="fas fa-cog"></i> 数据获取方式
            </label>
            <select 
                className={styles.formControl} 
                value={dataMethod}
                onChange={handleDataMethodChange}
            >
                <option value="latest">最新N根K线（默认）</option>
                <option value="date_range">指定日期范围的数据</option>
                <option value="to_end">到指定时间为止的N根K线</option>
            </select>
            <small className={styles.textMuted}>
                <i className="fas fa-info-circle me-1"></i>
                {dataMethod === 'latest' && "获取最新的市场数据进行分析，适合实时交易决策。"}
                {dataMethod === 'date_range' && "获取指定开始和结束时间之间的数据，适合历史回测。"}
                {dataMethod === 'to_end' && "获取截止到指定时间点的历史数据，适合复盘分析。"}
            </small>
        </div>

        {dataMethod !== 'latest' && (
            <div className={styles.datetimeConfigSection}>
                {dataMethod === 'date_range' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                         <div>
                            <label className="text-sm font-semibold text-gray-700 mb-2 block">开始日期</label>
                            <input type="date" className={styles.formControl} value={startDate} onChange={e => setDateConfig({ startDate: e.target.value })} />
                        </div>
                        <div>
                            <label className="text-sm font-semibold text-gray-700 mb-2 block">开始时间</label>
                            <input type="time" className={styles.formControl} value={startTime} onChange={e => setDateConfig({ startTime: e.target.value })} />
                        </div>
                    </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                     <div>
                        <label className="text-sm font-semibold text-gray-700 mb-2 block">结束日期</label>
                        <input type="date" className={styles.formControl} value={endDate} onChange={e => setDateConfig({ endDate: e.target.value })} disabled={useCurrentTime} />
                    </div>
                    <div>
                        <label className="text-sm font-semibold text-gray-700 mb-2 block">结束时间</label>
                        <input type="time" className={styles.formControl} value={endTime} onChange={e => setDateConfig({ endTime: e.target.value })} disabled={useCurrentTime} />
                    </div>
                </div>

                <div className="flex items-center gap-2 mt-3">
                    <input 
                        className={styles.formCheckInput} 
                        type="checkbox" 
                        id="useCurrentTime"
                        checked={useCurrentTime}
                        onChange={e => setDateConfig({ useCurrentTime: e.target.checked })}
                    />
                    <label className="text-sm text-gray-600 cursor-pointer" htmlFor="useCurrentTime">
                        使用当前系统时间作为结束时间
                    </label>
                </div>
            </div>
        )}

        {/* Kline Count Configuration */}
        <div className={`${styles.formGroup} mt-4`}>
            <label className={styles.formLabel}>
                <i className="fas fa-chart-bar"></i> K线分析数量
            </label>
            <div className="flex items-center gap-4">
                {/* Slider */}
                <div className="flex-1">
                    <input 
                        type="range" 
                        className={styles.formRange}
                        min="20" 
                        max="200" 
                        step="5"
                        value={klineCount}
                        onChange={(e) => setKlineCount(Number(e.target.value))}
                    />
                    <div className="flex justify-between mt-1 text-xs text-gray-500">
                        <span>20</span>
                        <span>100</span>
                        <span>200</span>
                    </div>
                </div>
                {/* Number Input */}
                <div className="w-20">
                    <input 
                        type="number" 
                        className={`${styles.formControl} text-center font-semibold`}
                        min="20" 
                        max="200" 
                        step="5"
                        value={klineCount}
                        onChange={(e) => setKlineCount(Number(e.target.value))}
                    />
                </div>
                {/* Presets */}
                <div className="flex gap-2">
                    {[30, 50, 100].map(count => (
                        <button 
                            key={count}
                            type="button" 
                            className={`${styles.btn} ${klineCount === count ? styles.btnPrimary : styles.btnOutlinePrimary}`}
                            onClick={() => setKlineCount(count)}
                            style={{ padding: '0.375rem 0.75rem', fontSize: '0.875rem' }}
                        >
                            {count}
                        </button>
                    ))}
                </div>
            </div>
            <small className={styles.textMuted}>
                <i className="fas fa-info-circle me-1"></i>
                更多K线提供更全面的技术分析，但会增加处理时间。推荐：30-100条
            </small>
        </div>

        {/* Future Kline Count (only for to_end method) */}
        {dataMethod === 'to_end' && (
             <div className={`${styles.formGroup} mt-4`}>
                <label className={styles.formLabel}>
                    <i className="fas fa-chart-line"></i> 未来K线数量
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <input 
                            type="number" 
                            className={styles.formControl}
                            min="1" 
                            max="60" 
                            step="1"
                            value={futureKlineCount}
                            onChange={(e) => setFutureKlineCount(Number(e.target.value))}
                        />
                    </div>
                    <div>
                         <small className={styles.textMuted}>
                            仅用于“到指定时间为止的N根K线”，默认20
                        </small>
                    </div>
                </div>
            </div>
        )}
    </div>

    {/* AI Agent Configuration */}
    <div className={styles.panel}>
        <h4 className={styles.panelTitle}>
            <i className="fas fa-robot"></i> AI Agent Configuration
        </h4>
        
        <div className={styles.aiConfigGrid}>
            {/* AI Version Selection */}
            <div>
                 <label className={styles.formLabel}>
                    <i className="fas fa-code-branch"></i> AI Strategy Version
                </label>
                <select 
                    className={styles.formControl}
                    value={aiVersion}
                    onChange={e => setAiVersion(e.target.value)}
                >
                    <option value="constrained">Constrained (Conservative)</option>
                    <option value="liberal">Liberal (Aggressive)</option>
                </select>
                <small className={styles.textMuted}>
                    Select the risk appetite for the decision agent.
                </small>
            </div>

            {/* Dual Model Config */}
            <div>
                <div className="flex items-center justify-between mb-3">
                    <label className={`${styles.formLabel} mb-0`}>
                        <i className="fas fa-project-diagram"></i> Dual Model System
                    </label>
                    <div className={styles.formSwitch}>
                        <input 
                            className={styles.formCheckInput} 
                            type="checkbox" 
                            id="dualModelToggle"
                            checked={dualModelConfig.dual_model}
                            onChange={e => setDualModelConfig({ dual_model: e.target.checked })}
                        />
                    </div>
                </div>

                {dualModelConfig.dual_model && (
                    <div className={styles.dualModelSettings}>
                        <div className="mb-4">
                            <label className="text-sm font-semibold text-gray-700 mb-2 block">Primary Model (Analysis)</label>
                            <select 
                                className={styles.formControl}
                                value={dualModelConfig.model_1 || ''}
                                onChange={e => setDualModelConfig({ model_1: e.target.value })}
                            >
                                <option value="">Select Model A...</option>
                                {AVAILABLE_MODELS.map(m => (
                                    <option key={m.id} value={m.id}>{m.name}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-sm font-semibold text-gray-700 mb-2 block">Secondary Model (Decision)</label>
                             <select 
                                className={styles.formControl}
                                value={dualModelConfig.model_2 || ''}
                                onChange={e => setDualModelConfig({ model_2: e.target.value })}
                            >
                                <option value="">Select Model B...</option>
                                {AVAILABLE_MODELS.map(m => (
                                    <option key={m.id} value={m.id}>{m.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>
                )}
            </div>
        </div>
    </div>
    </>
  );
}
