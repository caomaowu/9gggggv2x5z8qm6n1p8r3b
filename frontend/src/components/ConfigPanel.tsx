import { useAppStore } from '../store/useAppStore';
import type { AnalyzeRequest } from '../types';
import styles from './ConfigPanel.module.css';
import { getLLMConfig, updateLLMConfig } from '../api/system';
import type { LLMConfigCurrent, LLMProviderInfo } from '../api/system';
import { useState, useEffect } from 'react';

export default function ConfigPanel() {
  const { 
      dataMethod, setDataMethod,
      startDate, startTime, endDate, endTime, useCurrentTime, setDateConfig,
      klineCount, setKlineCount, futureKlineCount, setFutureKlineCount,
  } = useAppStore();

  const [llmConfig, setLLMConfig] = useState<LLMConfigCurrent | null>(null);
  const [availableProviders, setAvailableProviders] = useState<Record<string, LLMProviderInfo>>({});
  const [isSavingLLM, setIsSavingLLM] = useState(false);

  useEffect(() => {
      const fetchConfig = async () => {
          try {
              const data = await getLLMConfig();
              setLLMConfig(data.current);
              setAvailableProviders(data.options.providers);
          } catch (error) {
              console.error("Failed to fetch LLM config:", error);
          }
      };
      fetchConfig();
  }, []);

  const handleSaveLLMConfig = async () => {
      if (!llmConfig) return;
      setIsSavingLLM(true);
      try {
          await updateLLMConfig(llmConfig);
          alert("LLM 配置已保存！重启后端后生效。");
      } catch (error) {
          console.error("Failed to save LLM config:", error);
          alert("保存配置失败，请检查控制台");
      } finally {
          setIsSavingLLM(false);
      }
  };

  const handleProviderChange = (agent: string, provider: string) => {
      if (!llmConfig) return;
      const firstModel = availableProviders[provider]?.agent_models?.[0] || '';
      setLLMConfig({ ...llmConfig, [`${agent}_provider`]: provider, [`${agent}_model`]: firstModel } as any);
  };

  const handleModelChange = (agent: string, model: string) => {
      if (!llmConfig) return;
      setLLMConfig({ ...llmConfig, [`${agent}_model`]: model } as any);
  };

  const handleTempChange = (agent: string, temp: number) => {
      if (!llmConfig) return;
      setLLMConfig({ ...llmConfig, [`${agent}_temperature`]: temp } as any);
  };

  const [quickDate, setQuickDate] = useState('');
  const [quickTime, setQuickTime] = useState('');

  const handleQuickDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      if (val.length <= 6 && /^\d*$/.test(val)) {
          setQuickDate(val);
          if (val.length === 6) {
              const yy = val.substring(0, 2), mm = val.substring(2, 4), dd = val.substring(4, 6);
              setDateConfig({ endDate: `20${yy}-${mm}-${dd}`, useCurrentTime: false });
          }
      }
  };

  const handleQuickTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      if (val.length <= 4 && /^\d*$/.test(val)) {
          setQuickTime(val);
          if (val.length === 4) {
              const hh = val.substring(0, 2), mm = val.substring(2, 4);
              setDateConfig({ endTime: `${hh}:${mm}`, useCurrentTime: false });
          }
      }
  };

  type DataMethod = AnalyzeRequest['data_method'];
  const handleDataMethodChange = (e: React.ChangeEvent<HTMLSelectElement>) => setDataMethod(e.target.value as DataMethod);

  const braleAgents = [
    { key: 'indicator', label: 'Indicator Agent', temp: 0.2 },
    { key: 'structure', label: 'Structure Agent', temp: 0.1 },
    { key: 'mechanics', label: 'Mechanics Agent', temp: 0.2 },
  ];

  return (
    <>
    <div className={styles.panel}>
        <h4 className={styles.panelTitle}><i className="fas fa-calendar-alt"></i> Date & Time Configuration</h4>
        <div className={styles.formGroup}>
            <label className={styles.formLabel}><i className="fas fa-cog"></i> 数据获取方式</label>
            <select className={styles.formControl} value={dataMethod} onChange={handleDataMethodChange}>
                <option value="latest">最新N根K线（默认）</option>
                <option value="date_range">指定日期范围的数据</option>
                <option value="to_end">到指定时间为止的N根K线</option>
            </select>
            <small className={styles.textMuted}><i className="fas fa-info-circle me-1"></i>
                {dataMethod === 'latest' && "获取最新的市场数据进行分析，适合实时交易决策。"}
                {dataMethod === 'date_range' && "获取指定开始和结束时间之间的数据，适合历史回测。"}
                {dataMethod === 'to_end' && "获取截止到指定时间点的历史数据，适合复盘分析。"}
            </small>
        </div>

        {dataMethod !== 'latest' && (
            <div className={styles.datetimeConfigSection}>
                {dataMethod === 'date_range' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                         <div><label className="text-sm font-semibold text-gray-700 mb-2 block">开始日期</label>
                         <input type="date" className={styles.formControl} value={startDate} onChange={e => setDateConfig({ startDate: e.target.value })} /></div>
                        <div><label className="text-sm font-semibold text-gray-700 mb-2 block">开始时间</label>
                        <input type="time" className={styles.formControl} value={startTime} onChange={e => setDateConfig({ startTime: e.target.value })} /></div>
                    </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                     <div><label className="text-sm font-semibold text-gray-700 mb-2 block">结束日期</label>
                     <input type="date" className={styles.formControl} value={endDate} onChange={e => setDateConfig({ endDate: e.target.value })} disabled={useCurrentTime} /></div>
                    <div><label className="text-sm font-semibold text-gray-700 mb-2 block">结束时间</label>
                    <input type="time" className={styles.formControl} value={endTime} onChange={e => setDateConfig({ endTime: e.target.value })} disabled={useCurrentTime} /></div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
                    <div><input type="text" className={`${styles.formControl} text-sm`} placeholder="快速日期: YYMMDD (e.g. 250623)" value={quickDate} onChange={handleQuickDateChange} disabled={useCurrentTime} /></div>
                    <div><input type="text" className={`${styles.formControl} text-sm`} placeholder="快速时间: HHMM (e.g. 0524)" value={quickTime} onChange={handleQuickTimeChange} disabled={useCurrentTime} /></div>
                </div>
                <div className="flex items-center gap-2 mt-3">
                    <input className={styles.formCheckInput} type="checkbox" id="useCurrentTime" checked={useCurrentTime} onChange={e => setDateConfig({ useCurrentTime: e.target.checked })} />
                    <label className="text-sm text-gray-600 cursor-pointer" htmlFor="useCurrentTime">使用当前系统时间作为结束时间</label>
                </div>
            </div>
        )}

        <div className={`${styles.formGroup} mt-4`}>
            <label className={styles.formLabel}><i className="fas fa-chart-bar"></i> K线分析数量</label>
            <div className="flex items-center gap-4">
                <div className="flex-1">
                    <input type="range" className={styles.formRange} min="20" max="200" step="5" value={klineCount} onChange={(e) => setKlineCount(Number(e.target.value))} />
                    <div className="flex justify-between mt-1 text-xs text-gray-500"><span>20</span><span>100</span><span>200</span></div>
                </div>
                <div className="w-20"><input type="number" className={`${styles.formControl} text-center font-semibold`} min="20" max="200" step="5" value={klineCount} onChange={(e) => setKlineCount(Number(e.target.value))} /></div>
                <div className="flex gap-2">
                    {[40, 50, 60].map(count => (
                        <button key={count} type="button" className={`${styles.btn} ${klineCount === count ? styles.btnPrimary : styles.btnOutlinePrimary}`} onClick={() => setKlineCount(count)} style={{ padding: '0.375rem 0.75rem', fontSize: '0.875rem' }}>{count}</button>
                    ))}
                </div>
            </div>
            <small className={styles.textMuted}><i className="fas fa-info-circle me-1"></i>更多K线提供更全面的技术分析，但会增加处理时间。推荐：30-100条</small>
        </div>

        {dataMethod === 'to_end' && (
             <div className={`${styles.formGroup} mt-4`}>
                <label className={styles.formLabel}><i className="fas fa-chart-line"></i> 未来K线数量</label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><input type="number" className={styles.formControl} min="1" max="60" step="1" value={futureKlineCount} onChange={(e) => setFutureKlineCount(Number(e.target.value))} /></div>
                    <div><small className={styles.textMuted}>仅用于"到指定时间为止的N根K线"，默认20</small></div>
                </div>
            </div>
        )}
    </div>

    {llmConfig && (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}><i className="fas fa-robot"></i> Brale Agent LLM</h4>

            <div className={styles.formGroup} style={{ marginBottom: '0.75rem' }}>
                <label className={styles.formLabel} style={{ fontSize: '0.8rem', color: '#6b7280' }}>Default (fallback)</label>
                <div className="flex gap-2">
                    <select className={styles.formControl} style={{ width: '35%', fontSize: '0.75rem', padding: '0.2rem' }}
                        value={llmConfig.agent_provider}
                        onChange={e => { const p = e.target.value; const m = availableProviders[p]?.agent_models?.[0] || ''; setLLMConfig({ ...llmConfig, agent_provider: p, agent_model: m }); }}>
                        {Object.entries(availableProviders).map(([k, i]) => (<option key={k} value={k}>{i.name}</option>))}
                    </select>
                    <select className={styles.formControl} style={{ width: '65%', fontSize: '0.75rem', padding: '0.2rem' }}
                        value={llmConfig.agent_model}
                        onChange={e => setLLMConfig({ ...llmConfig, agent_model: e.target.value })}>
                        {availableProviders[llmConfig.agent_provider]?.agent_models?.map(m => (<option key={m} value={m}>{m}</option>))}
                    </select>
                </div>
            </div>

            {braleAgents.map(agent => {
                const pKey = `${agent.key}_provider` as keyof LLMConfigCurrent;
                const mKey = `${agent.key}_model` as keyof LLMConfigCurrent;
                const tKey = `${agent.key}_temperature` as keyof LLMConfigCurrent;
                const provider = (llmConfig[pKey] as string) || '';
                const model = (llmConfig[mKey] as string) || '';
                const temperature = (llmConfig[tKey] as number) ?? agent.temp;
                return (
                    <div key={agent.key} className={styles.formGroup} style={{ marginBottom: '0.5rem', padding: '0.5rem', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
                        <div className="flex items-center justify-between mb-1">
                            <label className={styles.formLabel} style={{ fontSize: '0.85rem', marginBottom: 0 }}>{agent.label}</label>
                            <span style={{ fontSize: '0.7rem', color: '#9ca3af' }}>temp: {temperature}</span>
                        </div>
                        <div className="flex gap-2 items-center">
                            <select className={styles.formControl} style={{ width: '35%', fontSize: '0.75rem', padding: '0.2rem' }}
                                value={provider} onChange={e => handleProviderChange(agent.key, e.target.value)}>
                                <option value="">(use default)</option>
                                {Object.entries(availableProviders).map(([k, i]) => (<option key={k} value={k}>{i.name}</option>))}
                            </select>
                            <select className={styles.formControl} style={{ width: '45%', fontSize: '0.75rem', padding: '0.2rem' }}
                                value={model} onChange={e => handleModelChange(agent.key, e.target.value)}>
                                <option value="">(use default model)</option>
                                {availableProviders[provider || llmConfig.agent_provider]?.agent_models?.map(m => (<option key={m} value={m}>{m}</option>))}
                            </select>
                            <input type="number" className={styles.formControl} style={{ width: '20%', fontSize: '0.75rem', padding: '0.2rem', textAlign: 'center' }}
                                min="0" max="2" step="0.1" value={temperature}
                                onChange={e => handleTempChange(agent.key, parseFloat(e.target.value) || agent.temp)} />
                        </div>
                    </div>
                );
            })}

            <div className="mt-3 flex justify-end">
                <button type="button" className={styles.btnPrimary} onClick={handleSaveLLMConfig} disabled={isSavingLLM} style={{ padding: '0.5rem 1rem' }}>
                    {isSavingLLM ? (<><i className="fas fa-spinner fa-spin me-2"></i> Saving...</>) : (<><i className="fas fa-save me-2"></i> Save Configuration</>)}
                </button>
            </div>
        </div>
    )}
    </>
  );
}
