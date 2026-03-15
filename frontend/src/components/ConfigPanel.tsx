import { useAppStore } from '../store/useAppStore';
import type { AnalyzeRequest } from '../types';
import styles from './ConfigPanel.module.css';
import { 
    getLLMConfig, 
    updateLLMConfig,
    getThinkingModeConfig,
    updateThinkingModeConfig
} from '../api/system';
import type { 
    LLMConfigCurrent, 
    LLMProviderInfo,
    ThinkingModeConfig
} from '../api/system';
import { useState, useEffect } from 'react';

export default function ConfigPanel() {
  const { 
      dataMethod, setDataMethod,
      startDate, startTime, endDate, endTime, useCurrentTime, setDateConfig,
      klineCount, setKlineCount, futureKlineCount, setFutureKlineCount,
      decisionAgentVersion, setDecisionAgentVersion
  } = useAppStore();

  
  // LLM Config State
  const [llmConfig, setLLMConfig] = useState<LLMConfigCurrent | null>(null);
  const [availableProviders, setAvailableProviders] = useState<Record<string, LLMProviderInfo>>({});
  const [decisionVersions, setDecisionVersions] = useState<Array<{ id: string; name: string }>>([]);
  const [isSavingLLM, setIsSavingLLM] = useState(false);
  
  // Thinking Mode State
  const [thinkingConfig, setThinkingConfig] = useState<ThinkingModeConfig | null>(null);

  useEffect(() => {
      const fetchConfig = async () => {
          try {
              const data = await getLLMConfig();
              setLLMConfig(data.current);
              
              // Sync backend version to store if not set locally or different
              // Ideally we want to prioritize backend config or sync them
              if (data.current.decision_agent_version && data.current.decision_agent_version !== decisionAgentVersion) {
                  setDecisionAgentVersion(data.current.decision_agent_version);
              }

              setAvailableProviders(data.options.providers);
              if (data.options.decision_versions) {
                  setDecisionVersions(data.options.decision_versions);
              }
              
              // Fetch Thinking Mode
              const thinkingData = await getThinkingModeConfig();
              setThinkingConfig(thinkingData);
          } catch (error) {
              console.error("Failed to fetch LLM config:", error);
          }
      };
      fetchConfig();
  }, []);

  const handleThinkingToggle = async (key: keyof ThinkingModeConfig) => {
      if (!thinkingConfig) return;
      
      const newValue = !thinkingConfig[key];
      const newConfig = { ...thinkingConfig, [key]: newValue };
      setThinkingConfig(newConfig); // Optimistic update
      
      try {
          await updateThinkingModeConfig({
              [`${key}_thinking_mode`]: newValue
          });
      } catch (error) {
          console.error("Failed to update thinking mode:", error);
          setThinkingConfig(thinkingConfig); // Revert on error
          alert("更新思考模式失败");
      }
  };

  const handleReasoningEffortChange = async (key: string, value: string) => {
    if (!thinkingConfig) return;
    
    // Map key (e.g., "indicator") to config key (e.g., "indicator_effort")
    const configKey = `${key}_effort` as keyof ThinkingModeConfig;
    const newConfig = { ...thinkingConfig, [configKey]: value };
    setThinkingConfig(newConfig); // Optimistic update
    
    try {
        await updateThinkingModeConfig({
            [`${key}_reasoning_effort`]: value
        });
    } catch (error) {
        console.error("Failed to update reasoning effort:", error);
        setThinkingConfig(thinkingConfig); // Revert on error
        alert("更新推理深度失败");
    }
  };

  const handleSaveLLMConfig = async () => {
      if (!llmConfig) return;
      setIsSavingLLM(true);
      try {
          // Sync local decision version to config before saving
          const configToSave = {
              ...llmConfig,
              decision_agent_version: decisionAgentVersion
          };
          
          await updateLLMConfig(configToSave);
          alert("LLM 配置已保存并更新！");
      } catch (error) {
          console.error("Failed to save LLM config:", error);
          alert("保存配置失败，请检查控制台");
      } finally {
          setIsSavingLLM(false);
      }
  };

  const handleAgentProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      if (!llmConfig) return;
      const newProvider = e.target.value;
      // 当切换 Provider 时，默认选择第一个可用模型
      const firstModel = availableProviders[newProvider]?.agent_models?.[0] || '';
      setLLMConfig({ ...llmConfig, agent_provider: newProvider, agent_model: firstModel });
  };

  const handleGraphProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      if (!llmConfig) return;
      const newProvider = e.target.value;
      // 当切换 Provider 时，默认选择第一个可用模型
      const firstModel = availableProviders[newProvider]?.graph_models?.[0] || '';
      setLLMConfig({ ...llmConfig, graph_provider: newProvider, graph_model: firstModel });
  };

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

    {/* LLM Configuration */}
    {llmConfig && (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}>
                <i className="fas fa-robot"></i> LLM Configuration
            </h4>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Agent Model */}
                <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                    <label className={styles.formLabel} style={{ fontSize: '0.85rem' }}>
                        Agent (Logic)
                    </label>
                    <div className="flex gap-2">
                        <select 
                            className={styles.formControl}
                            value={llmConfig.agent_provider}
                            onChange={handleAgentProviderChange}
                            style={{ width: '35%', fontSize: '0.8rem', padding: '0.25rem' }}
                        >
                            {Object.entries(availableProviders).map(([key, info]) => (
                                <option key={key} value={key}>{info.name}</option>
                            ))}
                        </select>
                        <select 
                            className={styles.formControl}
                            value={llmConfig.agent_model}
                            onChange={(e) => setLLMConfig({ ...llmConfig, agent_model: e.target.value })}
                            style={{ width: '65%', fontSize: '0.8rem', padding: '0.25rem' }}
                        >
                            {availableProviders[llmConfig.agent_provider]?.agent_models?.map(model => (
                                <option key={model} value={model}>{model}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Graph Model */}
                <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                    <label className={styles.formLabel} style={{ fontSize: '0.85rem' }}>
                        Graph (Vision)
                    </label>
                    <div className="flex gap-2">
                        <select 
                            className={styles.formControl}
                            value={llmConfig.graph_provider}
                            onChange={handleGraphProviderChange}
                            style={{ width: '35%', fontSize: '0.8rem', padding: '0.25rem' }}
                        >
                            {Object.entries(availableProviders).map(([key, info]) => (
                                <option key={key} value={key}>{info.name}</option>
                            ))}
                        </select>
                        <select 
                            className={styles.formControl}
                            value={llmConfig.graph_model}
                            onChange={(e) => setLLMConfig({ ...llmConfig, graph_model: e.target.value })}
                            style={{ width: '65%', fontSize: '0.8rem', padding: '0.25rem' }}
                        >
                            {availableProviders[llmConfig.graph_provider]?.graph_models?.map(model => (
                                <option key={model} value={model}>{model}</option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* Decision Agent Version */}
            {decisionVersions.length > 0 && (
                <div className={styles.formGroup} style={{ marginTop: '1rem' }}>
                    <label className={styles.formLabel} style={{ fontSize: '0.85rem' }}>
                        Decision Agent Version
                    </label>
                    <select 
                        className={styles.formControl}
                        value={decisionAgentVersion}
                        onChange={(e) => {
                            const newVersion = e.target.value;
                            setDecisionAgentVersion(newVersion);
                            if (llmConfig) {
                                setLLMConfig({ ...llmConfig, decision_agent_version: newVersion });
                            }
                        }}
                        style={{ fontSize: '0.8rem', padding: '0.25rem' }}
                    >
                        {decisionVersions.map(v => (
                            <option key={v.id} value={v.id}>{v.name}</option>
                        ))}
                    </select>
                    <small className={styles.textMuted}>
                        <i className="fas fa-info-circle me-1"></i>
                        Original: 经典HFT逻辑 (慢，严谨); Lite: 快速直觉模式 (快，灵活)
                    </small>
                </div>
            )}

            <div className="mt-4 flex justify-end">
                <button 
                    type="button" 
                    className={styles.btnPrimary}
                    onClick={handleSaveLLMConfig}
                    disabled={isSavingLLM}
                    style={{ padding: '0.5rem 1rem' }}
                >
                    {isSavingLLM ? (
                        <>
                            <i className="fas fa-spinner fa-spin me-2"></i> Saving...
                        </>
                    ) : (
                        <>
                            <i className="fas fa-save me-2"></i> Save Configuration
                        </>
                    )}
                </button>
            </div>
        </div>
    )}

    {/* Thinking Mode Configuration */}
    {thinkingConfig && (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}>
                <i className="fas fa-brain"></i> Thinking Mode (CoT)
            </h4>
            
            <div className={styles.formGroup}>
                <label className={styles.formLabel}>
                    Enable Thinking Mode for Agents
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {[
                        { key: 'indicator', label: 'Indicator (技术)' },
                        { key: 'pattern', label: 'Pattern (形态)' },
                        { key: 'trend', label: 'Trend (趋势)' },
                        { key: 'decision', label: 'Decision (决策)' }
                    ].map(item => {
                        const key = item.key as keyof ThinkingModeConfig;
                        const isEnabled = thinkingConfig[key] as boolean;
                        const effortKey = `${key}_effort` as keyof ThinkingModeConfig;
                        const effortValue = thinkingConfig[effortKey] as string;

                        return (
                            <div key={key} className="p-2 border rounded hover:bg-gray-50 flex flex-col justify-between" style={{ minHeight: '60px' }}>
                                <div className="flex items-center gap-2">
                                    <input 
                                        type="checkbox" 
                                        id={`${key}-thinking`}
                                        checked={isEnabled}
                                        onChange={() => handleThinkingToggle(key)}
                                        className="w-3 h-3 text-blue-600 rounded focus:ring-blue-500"
                                    />
                                    <label htmlFor={`${key}-thinking`} className="text-xs font-medium text-gray-700 cursor-pointer select-none flex-1 truncate" title={item.label}>
                                        {item.label}
                                    </label>
                                </div>
                                {isEnabled && (
                                    <div className="mt-1 flex items-center justify-end gap-1">
                                        <select 
                                            className="text-[10px] border rounded px-1 py-0.5 font-medium"
                                            style={{ color: 'red' }}
                                            value={effortValue || "medium"}
                                            onChange={(e) => handleReasoningEffortChange(item.key, e.target.value)}
                                        >
                                            <option value="low">Low</option>
                                            <option value="medium">Medium</option>
                                            <option value="high">High</option>
                                            <option value="extra_high">Max</option>
                                        </select>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
                <small className={styles.textMuted}>
                    <i className="fas fa-info-circle me-1"></i>
                    开启思考模式会让模型在回答前进行更深度的推理（Chain of Thought）。<br/>
                    支持 OpenRouter (extra_body) 和 OpenAI o1/o3 (reasoning_effort)。
                </small>
            </div>
        </div>
    )}


    </>
  );
}
