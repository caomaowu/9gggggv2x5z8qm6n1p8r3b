import { useAppStore } from '../store/useAppStore';
import type { AnalyzeRequest } from '../types';
import styles from './ConfigPanel.module.css';
import { clearSystemCache, clearExportsFiles, getLLMConfig, updateLLMConfig } from '../api/system';
import type { LLMConfigResponse } from '../api/system';
import { useState, useEffect } from 'react';

export default function ConfigPanel() {
  const { 
      dataMethod, setDataMethod,
      startDate, startTime, endDate, endTime, useCurrentTime, setDateConfig,
      aiVersion, setAiVersion,
      klineCount, setKlineCount, futureKlineCount, setFutureKlineCount
  } = useAppStore();

  const [isCleaning, setIsCleaning] = useState(false);
  const [isCleaningExports, setIsCleaningExports] = useState(false);
  
  // LLM Config State
  const [llmConfig, setLlmConfig] = useState<LLMConfigResponse | null>(null);
  const [isLoadingLLM, setIsLoadingLLM] = useState(false);
  const [isSavingLLM, setIsSavingLLM] = useState(false);
  
  // Local state for LLM selections
  const [agentProvider, setAgentProvider] = useState('');
  const [agentModel, setAgentModel] = useState('');
  const [agentTemperature, setAgentTemperature] = useState(0.1);
  const [graphProvider, setGraphProvider] = useState('');
  const [graphModel, setGraphModel] = useState('');
  const [graphTemperature, setGraphTemperature] = useState(0.1);

  useEffect(() => {
    fetchLLMConfig();
  }, []);

  const fetchLLMConfig = async () => {
    setIsLoadingLLM(true);
    try {
      const config = await getLLMConfig();
      setLlmConfig(config);
      setAgentProvider(config.agent.provider);
      setAgentModel(config.agent.model);
      setAgentTemperature(config.agent.temperature || 0.1);
      setGraphProvider(config.graph.provider);
      setGraphModel(config.graph.model);
      setGraphTemperature(config.graph.temperature || 0.1);
    } catch (error) {
      console.error("Failed to fetch LLM config:", error);
    } finally {
      setIsLoadingLLM(false);
    }
  };

  // 监听模型变化，自动加载偏好温度
  useEffect(() => {
    if (llmConfig?.model_preferences && agentModel) {
      const prefTemp = llmConfig.model_preferences[agentModel];
      if (prefTemp !== undefined) {
        setAgentTemperature(prefTemp);
      } else {
        // 如果没有偏好记录，重置为默认值
        setAgentTemperature(0.1);
      }
    }
  }, [agentModel, llmConfig]);

  useEffect(() => {
    if (llmConfig?.model_preferences && graphModel) {
      const prefTemp = llmConfig.model_preferences[graphModel];
      if (prefTemp !== undefined) {
        setGraphTemperature(prefTemp);
      } else {
        // 如果没有偏好记录，重置为默认值
        setGraphTemperature(0.1);
      }
    }
  }, [graphModel, llmConfig]);

  const handleSaveLLMConfig = async () => {
    if (!llmConfig) return;
    
    setIsSavingLLM(true);
    try {
      const res = await updateLLMConfig(
        agentProvider, 
        agentModel, 
        graphProvider, 
        graphModel,
        agentTemperature,
        graphTemperature
      );
      alert('配置已更新并保存到服务器！');
      
      // 更新本地配置缓存，包括新的偏好
      if (res.model_preferences) {
        setLlmConfig(prev => prev ? {
            ...prev,
            model_preferences: res.model_preferences,
            agent: { ...prev.agent, provider: agentProvider, model: agentModel, temperature: agentTemperature },
            graph: { ...prev.graph, provider: graphProvider, model: graphModel, temperature: graphTemperature }
        } : null);
      } else {
        await fetchLLMConfig();
      }
    } catch (error) {
      console.error("Failed to save LLM config:", error);
      alert('保存失败，请检查控制台');
    } finally {
      setIsSavingLLM(false);
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

    {/* AI Agent Configuration */}
    <div className={styles.panel}>
        <h4 className={styles.panelTitle}>
            <i className="fas fa-robot"></i> AI Agent Configuration
        </h4>
        
        {isLoadingLLM ? (
             <div className="text-center py-4 text-gray-500">
                <i className="fas fa-spinner fa-spin mr-2"></i> Loading configuration...
             </div>
        ) : llmConfig ? (
            <div className={styles.aiConfigGrid}>
                {/* 紧凑布局：一行显示两个配置卡片 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                    {/* Agent LLM */}
                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-100 relative">
                         <div className="absolute top-2 right-2 text-xs text-gray-400">
                            <i className="fas fa-brain text-purple-400"></i>
                        </div>
                        <h5 className="font-bold text-xs text-gray-600 uppercase mb-2 tracking-wider">
                            Decision Agent
                        </h5>
                        
                        <div className="space-y-2">
                            <div>
                                <select 
                                    className={`${styles.formControl} text-xs py-1`}
                                    value={agentProvider}
                                    onChange={(e) => {
                                        setAgentProvider(e.target.value);
                                        // 智能切换：如果新 provider 有模型，默认选中第一个
                                        const models = llmConfig.agent_models_map?.[e.target.value] || [];
                                        if (models.length > 0) {
                                            setAgentModel(models[0]);
                                        } else {
                                            setAgentModel(''); 
                                        }
                                    }}
                                >
                                    {llmConfig.available_providers.map(p => (
                                        <option key={p.id} value={p.id}>{p.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                {(llmConfig.agent_models_map?.[agentProvider] || []).length > 0 ? (
                                    <select
                                        className={`${styles.formControl} text-xs py-1`}
                                        value={agentModel}
                                        onChange={(e) => setAgentModel(e.target.value)}
                                    >
                                        {(llmConfig.agent_models_map?.[agentProvider] || []).map(m => (
                                            <option key={m} value={m}>{m}</option>
                                        ))}
                                        {/* 如果当前值不在列表里，也显示出来，防止数据丢失 */}
                                        {agentModel && !(llmConfig.agent_models_map?.[agentProvider] || []).includes(agentModel) && (
                                            <option value={agentModel}>{agentModel}</option>
                                        )}
                                    </select>
                                ) : (
                                    <input 
                                        type="text" 
                                        className={`${styles.formControl} text-xs py-1`}
                                        value={agentModel}
                                        onChange={(e) => setAgentModel(e.target.value)}
                                        placeholder="Enter model name..."
                                    />
                                )}
                            </div>
                            
                            {/* Temperature Control */}
                            <div>
                                <label className="text-xs text-gray-500 font-semibold mb-1 block">
                                    Temperature
                                </label>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="number"
                                        className={`${styles.formControl} text-xs py-1 text-center`}
                                        min="0"
                                        max="1.5"
                                        step="0.01"
                                        value={agentTemperature}
                                        onChange={(e) => setAgentTemperature(Math.min(1.5, Math.max(0, parseFloat(e.target.value) || 0)))}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Graph LLM */}
                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-100 relative">
                        <div className="absolute top-2 right-2 text-xs text-gray-400">
                            <i className="fas fa-chart-line text-blue-400"></i>
                        </div>
                        <h5 className="font-bold text-xs text-gray-600 uppercase mb-2 tracking-wider">
                            Graph Agent
                        </h5>
                        <div className="space-y-2">
                             <div>
                                <select 
                                    className={`${styles.formControl} text-xs py-1`}
                                    value={graphProvider}
                                    onChange={(e) => {
                                        setGraphProvider(e.target.value);
                                        const models = llmConfig.graph_models_map?.[e.target.value] || [];
                                        if (models.length > 0) {
                                            setGraphModel(models[0]);
                                        } else {
                                            setGraphModel('');
                                        }
                                    }}
                                >
                                    {llmConfig.available_providers.map(p => (
                                        <option key={p.id} value={p.id}>{p.name}</option>
                                    ))}
                                </select>
                            </div>
                             <div>
                                 {(llmConfig.graph_models_map?.[graphProvider] || []).length > 0 ? (
                                     <select
                                         className={`${styles.formControl} text-xs py-1`}
                                         value={graphModel}
                                         onChange={(e) => setGraphModel(e.target.value)}
                                     >
                                         {(llmConfig.graph_models_map?.[graphProvider] || []).map(m => (
                                             <option key={m} value={m}>{m}</option>
                                         ))}
                                          {/* 如果当前值不在列表里，也显示出来 */}
                                         {graphModel && !(llmConfig.graph_models_map?.[graphProvider] || []).includes(graphModel) && (
                                             <option value={graphModel}>{graphModel}</option>
                                         )}
                                     </select>
                                 ) : (
                                     <input 
                                         type="text" 
                                         className={`${styles.formControl} text-xs py-1`}
                                         value={graphModel}
                                         onChange={(e) => setGraphModel(e.target.value)}
                                         placeholder="Enter model name..."
                                     />
                                )}
                            </div>

                            {/* Temperature Control */}
                            <div>
                                <label className="text-xs text-gray-500 font-semibold mb-1 block">
                                    Temperature
                                </label>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="number"
                                        className={`${styles.formControl} text-xs py-1 text-center`}
                                        min="0"
                                        max="1.5"
                                        step="0.01"
                                        value={graphTemperature}
                                        onChange={(e) => setGraphTemperature(Math.min(1.5, Math.max(0, parseFloat(e.target.value) || 0)))}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <button 
                    className={`${styles.btn} ${styles.btnPrimary} w-full text-sm py-1`}
                    onClick={handleSaveLLMConfig}
                    disabled={isSavingLLM}
                >
                    {isSavingLLM ? (
                        <><i className="fas fa-spinner fa-spin mr-2"></i> Saving...</>
                    ) : (
                        <><i className="fas fa-save mr-2"></i> Save Configuration</>
                    )}
                </button>
            </div>
        ) : (
            <div className="text-center text-red-500 py-4">
                Failed to load configuration.
            </div>
        )}
        
        <div className={styles.aiConfigGrid + " mt-4 pt-4 border-t"}>
            {/* AI Version Selection */}
            <div>
                 <label className={styles.formLabel}>
                    <i className="fas fa-code-branch"></i> AI Strategy Version
                </label>
                <select 
                    className={styles.formControl}
                    value={aiVersion}
                    onChange={e => setAiVersion(e.target.value)}
                    disabled={true}
                >
                    <option value="original">Original (Classic HFT)</option>
                </select>
                <small className={styles.textMuted}>
                    Select the risk appetite for the decision agent.
                </small>
            </div>
        </div>
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
