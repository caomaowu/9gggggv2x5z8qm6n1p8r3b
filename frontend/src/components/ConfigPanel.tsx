import { useAppStore } from '../store/useAppStore';
import type { AnalyzeRequest } from '../types';
import styles from './ConfigPanel.module.css';
import { clearSystemCache, clearExportsFiles } from '../api/system';
import { useState } from 'react';

export default function ConfigPanel() {
  const { 
      dataMethod, setDataMethod,
      startDate, startTime, endDate, endTime, useCurrentTime, setDateConfig,
      klineCount, setKlineCount, futureKlineCount, setFutureKlineCount
  } = useAppStore();

  const [isCleaning, setIsCleaning] = useState(false);
  const [isCleaningExports, setIsCleaningExports] = useState(false);
  
  // Quick Input State
  const [quickDate, setQuickDate] = useState('');
  const [quickTime, setQuickTime] = useState('');

  const handleQuickDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      if (val.length <= 6 && /^\d*$/.test(val)) {
          setQuickDate(val);
          if (val.length === 6) {
              // YYMMDD -> YYYY-MM-DD
              const yy = val.substring(0, 2);
              const mm = val.substring(2, 4);
              const dd = val.substring(4, 6);
              setDateConfig({ endDate: `20${yy}-${mm}-${dd}`, useCurrentTime: false });
          }
      }
  };

  const handleQuickTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      if (val.length <= 4 && /^\d*$/.test(val)) {
          setQuickTime(val);
          if (val.length === 4) {
              // HHMM -> HH:mm
              const hh = val.substring(0, 2);
              const mm = val.substring(2, 4);
              setDateConfig({ endTime: `${hh}:${mm}`, useCurrentTime: false });
          }
      }
  };

  type DataMethod = AnalyzeRequest['data_method'];

  const handleDataMethodChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      setDataMethod(e.target.value as DataMethod);
  };

  const handleClearCache = async () => {
      if (!confirm('确定要清理所有临时图表和缓存文件吗？')) {
          return;
      }
      
      setIsCleaning(true);
      try {
          const res = await clearSystemCache();
          alert(`${res.message}`);
      } catch (error) {
          console.error("Failed to clear cache:", error);
          alert("清理失败，请检查控制台");
      } finally {
          setIsCleaning(false);
      }
  };

  const handleClearExports = async () => {
      if (!confirm('警告：这将永久删除 exports 文件夹下的所有分析报告和文件！\n\n确定要继续吗？')) {
          return;
      }
      
      setIsCleaningExports(true);
      try {
          const res = await clearExportsFiles();
          alert(`${res.message}`);
      } catch (error) {
          console.error("Failed to clear exports:", error);
          alert("清理失败，请检查控制台");
      } finally {
          setIsCleaningExports(false);
      }
  };

  // ------------------------------------------
  // UI Render
  // ------------------------------------------

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

                {/* Quick Input Section */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
                    <div>
                        <input 
                            type="text" 
                            className={`${styles.formControl} text-sm`} 
                            placeholder="快速日期: YYMMDD (e.g. 250623)" 
                            value={quickDate}
                            onChange={handleQuickDateChange}
                            disabled={useCurrentTime}
                        />
                    </div>
                    <div>
                        <input 
                            type="text" 
                            className={`${styles.formControl} text-sm`} 
                            placeholder="快速时间: HHMM (e.g. 0524)" 
                            value={quickTime}
                            onChange={handleQuickTimeChange}
                            disabled={useCurrentTime}
                        />
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
                    {[40, 50, 60].map(count => (
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



    {/* System Maintenance */}
    <div className={styles.panel}>
        <h4 className={styles.panelTitle}>
            <i className="fas fa-tools"></i> System Maintenance
        </h4>
        
        <div className={styles.formGroup}>
            <div className="flex gap-4">
                <button 
                    type="button" 
                    className={styles.cleanBtn}
                    onClick={handleClearCache}
                    disabled={isCleaning}
                >
                    {isCleaning ? (
                        <>
                            <i className="fas fa-spinner fa-spin"></i> Cleaning Cache...
                        </>
                    ) : (
                        <>
                            <i className="fas fa-trash-alt"></i> Clean Temp Files
                        </>
                    )}
                </button>

                <button 
                    type="button" 
                    className={styles.cleanExportsBtn}
                    onClick={handleClearExports}
                    disabled={isCleaningExports}
                >
                    {isCleaningExports ? (
                        <>
                            <i className="fas fa-spinner fa-spin"></i> Cleaning...
                        </>
                    ) : (
                        <>
                            <i className="fas fa-folder-minus"></i> Clean Exports Files
                        </>
                    )}
                </button>
            </div>
            <small className={styles.textMuted}>
                清理缓存图表和导出的报告文件。
            </small>
        </div>
    </div>
    </>
  );
}
