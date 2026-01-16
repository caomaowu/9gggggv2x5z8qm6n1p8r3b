import { useAppStore } from '../store/useAppStore';
import { analyzeMarket } from '../api/analyze';
import AssetAndTimeframePanel from './AssetAndTimeframePanel';
import ConfigPanel from './ConfigPanel';
import HistoryPanel from './HistoryPanel';
import { useState, useEffect } from 'react';
import type { AnalyzeRequest } from '../types';
import styles from './AnalysisForm.module.css';

export default function AnalysisForm() {
    const { 
        selectedAsset, selectedTimeframe,
        dataMethod, klineCount, futureKlineCount,
        startDate, startTime, endDate, endTime, useCurrentTime,
        multiTimeframeMode, selectedTimeframes,
        setAnalysisResult,
        setLatestResultId,
        continuousMode, setContinuousMode, triggerHistoryRefresh
    } = useAppStore();
    
    const [isLoading, setIsLoading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [statusMessage, setStatusMessage] = useState<string | null>(null);

    useEffect(() => {
        let interval: ReturnType<typeof setInterval> | undefined;
        if (isLoading) {
            setProgress(0);
            interval = setInterval(() => {
                setProgress(prev => {
                    if (prev >= 95) return prev;
                    // Slower progress as it approaches 95%
                    const increment = Math.max(0.5, (95 - prev) / 20); 
                    return Math.min(95, prev + increment);
                });
            }, 200);
        } else {
            setProgress(100);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [isLoading]);

    const handleStartAnalysis = async () => {
        if (!selectedAsset) {
            alert('Please select an asset first.');
            return;
        }
        
        // 检查多时间框架模式是否有选择时间框架
        if (multiTimeframeMode && selectedTimeframes.length === 0) {
            alert('请至少选择一个时间框架。');
            return;
        }
        
        setStatusMessage(null);
        
        const request: AnalyzeRequest = {
            asset: selectedAsset,
            timeframe: multiTimeframeMode ? selectedTimeframes[0] : selectedTimeframe,
            data_source: 'quant_api', // Default
            data_method: dataMethod,
            kline_count: klineCount,
            future_kline_count: futureKlineCount,
            use_current_time: useCurrentTime,
            start_date: startDate || undefined,
            start_time: startTime || undefined,
            end_date: endDate || undefined,
            end_time: endTime || undefined,
            multi_timeframe_mode: multiTimeframeMode,
            timeframes: multiTimeframeMode ? selectedTimeframes : undefined
        };

        if (continuousMode) {
            // Continuous Mode: Non-blocking
            setIsLoading(true); // Short loading for feedback
            
            // Fire and forget (from UI perspective)
            analyzeMarket(request).then(() => {
                console.log(`[Continuous] Analysis for ${request.asset} finished.`);
                triggerHistoryRefresh();
                setStatusMessage(`✅ ${request.asset} 分析完成! 请查看历史记录。`);
                
                // Optional: Auto-clear success message after 5 seconds
                setTimeout(() => {
                    setStatusMessage(prev => (prev && prev.includes('分析完成') ? null : prev));
                }, 5000);
            }).catch(error => {
                console.error(`[Continuous] Analysis for ${request.asset} failed:`, error);
                setStatusMessage(`❌ ${request.asset} 分析失败。请检查控制台。`);
            });

            // Release UI immediately after a short delay
            setTimeout(() => {
                setIsLoading(false);
                setStatusMessage(`⏳ ${request.asset} 正在后台分析中... 您可以继续操作。`);
            }, 500);

            return; // Exit function, do not execute blocking logic
        }

        // Normal Mode: Blocking & Redirect
        setIsLoading(true);
        setAnalysisResult(null); // Clear previous result
        
        try {
            console.log("Sending analysis request:", request);
            const result = await analyzeMarket(request);
            console.log("Analysis result:", result);
            
            // 注入用户选择的参数，供前端展示使用
            const enrichedResult = {
                ...result,
                asset_name: selectedAsset,
                timeframe: selectedTimeframe,
                data_length: klineCount, // 或者使用后端返回的实际数据点数
                pattern_chart: result.pattern_chart || result.pattern_image,
                trend_chart: result.trend_chart || result.trend_image,
                multi_timeframe_mode: multiTimeframeMode,
                timeframes: selectedTimeframes
            };
            
            setAnalysisResult(enrichedResult);
            if (enrichedResult.result_id) {
                setLatestResultId(enrichedResult.result_id);
            }
            
            // Scroll to results
            setTimeout(() => {
                const resultsElement = document.getElementById('results');
                if (resultsElement) {
                    resultsElement.scrollIntoView({ behavior: 'smooth' });
                } else {
                    console.warn("Results element not found for scrolling");
                }
            }, 300);
        } catch (error) {
            console.error("Analysis failed:", error);
            // alert("Analysis failed. See console for details.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <section id="analysis" className={styles.analysisSection}>
            <div className={styles.formContainer}>
                <div className={styles.formSection}>
                    <h3 className={styles.sectionTitle}>
                        <i className="fas fa-cog"></i> 分析配置
                    </h3>
                    
                    <div className={styles.panelGroup}>
                        <AssetAndTimeframePanel />
                        <ConfigPanel />
                    </div>

                    <div className={styles.runControlsContainer}>
                        {/* Continuous Mode Toggle */}
                        <div style={{ 
                            marginBottom: '1rem', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center', 
                            gap: '10px',
                            padding: '10px',
                            backgroundColor: 'var(--gray-50)',
                            borderRadius: '8px'
                        }}>
                            <input 
                                type="checkbox" 
                                id="continuousMode"
                                checked={continuousMode}
                                onChange={(e) => setContinuousMode(e.target.checked)}
                                style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: 'var(--etrade-purple)' }}
                            />
                            <label htmlFor="continuousMode" style={{ cursor: 'pointer', fontWeight: 500, userSelect: 'none', color: 'var(--gray-700)' }}>
                                连续分析模式 (后台运行，不跳转)
                            </label>
                        </div>

                         <button 
                            className={styles.startAnalysisBtn}
                            onClick={handleStartAnalysis}
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <>
                                    <i className="fas fa-spinner fa-spin"></i> Analyzing...
                                </>
                            ) : (
                                <>
                                    <i className="fas fa-play"></i> Start Analysis
                                </>
                            )}
                        </button>

                        {/* Status Message for Continuous Mode */}
                        {statusMessage && (
                             <div style={{ marginTop: '1rem', textAlign: 'center', color: statusMessage.includes('❌') ? '#dc2626' : '#2563eb', fontWeight: 600 }}>
                                 {statusMessage}
                             </div>
                        )}

                        {isLoading && !continuousMode && (
                            <div className={styles.progressContainer}>
                                <div className={styles.progressLabel}>
                                    <span className={styles.progressText}>Analysis Progress</span>
                                    <span className={styles.progressText}>{Math.round(progress)}%</span>
                                </div>
                                <div className={styles.progressBarTrack}>
                                    <div 
                                        className={styles.progressBarFill} 
                                        style={{ width: `${progress}%` }}
                                    ></div>
                                </div>
                                <div className={styles.progressSteps}>
                                    <span className={progress > 10 ? styles.stepActive : ""}>Fetching Data</span>
                                    <span className={progress > 40 ? styles.stepActive : ""}>AI Processing</span>
                                    <span className={progress > 80 ? styles.stepActive : ""}>Generating Report</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* History Panel */}
                <HistoryPanel />

            </div>
        </section>
    );
}
