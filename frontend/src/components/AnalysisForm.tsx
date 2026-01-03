import { useAppStore } from '../store/useAppStore';
import { analyzeMarket } from '../api/analyze';
import AssetAndTimeframePanel from './AssetAndTimeframePanel';
import ConfigPanel from './ConfigPanel';
import { useState, useEffect } from 'react';
import type { AnalyzeRequest } from '../types';
import styles from './AnalysisForm.module.css';

export default function AnalysisForm() {
    const { 
        selectedAsset, selectedTimeframe,
        dataMethod, klineCount, futureKlineCount,
        startDate, startTime, endDate, endTime, useCurrentTime,
        aiVersion,
        setAnalysisResult
    } = useAppStore();
    
    const [isLoading, setIsLoading] = useState(false);
    const [progress, setProgress] = useState(0);

    useEffect(() => {
        let interval: any;
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
        return () => clearInterval(interval);
    }, [isLoading]);

    const handleStartAnalysis = async () => {
        if (!selectedAsset) {
            alert('Please select an asset first.');
            return;
        }
        setIsLoading(true);
        setAnalysisResult(null); // Clear previous result
        
        const request: AnalyzeRequest = {
            asset: selectedAsset,
            timeframe: selectedTimeframe,
            data_source: 'quant_api', // Default
            data_method: dataMethod,
            kline_count: klineCount,
            future_kline_count: futureKlineCount,
            use_current_time: useCurrentTime,
            ai_version: aiVersion,
            start_date: startDate || undefined,
            start_time: startTime || undefined,
            end_date: endDate || undefined,
            end_time: endTime || undefined
        };

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
                trend_chart: result.trend_chart || result.trend_image
            };
            
            setAnalysisResult(enrichedResult);
            
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
            alert("Analysis failed. See console for details.");
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

                        {isLoading && (
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
            </div>
        </section>
    );
}
