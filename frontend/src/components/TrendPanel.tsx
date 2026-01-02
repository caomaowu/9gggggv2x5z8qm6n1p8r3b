import { useAppStore } from '../store/useAppStore';
import AutoBeautify from './AutoBeautify';
import styles from './TrendPanel.module.css';

export default function TrendPanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { trend_analysis, trend_report, trend_chart } = analysisResult;
    const content = trend_analysis || trend_report;

    return (
        <div className={styles.largePanel}>
            <h3 className={styles.largePanelTitle}>
                <i className="fas fa-chart-line"></i> 趋势分析智能体
            </h3>
            <div className={styles.largePanelContent}>
                <div className={styles.panelGroup}>
                    <div className={styles.panel}>
                        <h4 className={styles.panelTitle}>
                            <i className="fas fa-analytics"></i> 趋势分析
                        </h4>
                        <div className={styles.formGroup} id="trend-analysis-content">
                            {content ? (
                                <AutoBeautify content={content} />
                            ) : (
                                <div className={styles.emptyState}>
                                    <i className="fas fa-chart-line"></i>
                                    <h5>趋势分析结果不可用</h5>
                                    <p>请重新运行分析以获取趋势分析结果</p>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className={styles.panel}>
                        <h4 className={styles.panelTitle}>
                            <i className="fas fa-chart-line"></i> 趋势可视化
                        </h4>
                        <div className={styles.chartContainer}>
                            <div className={styles.chartWrapper}>
                                {trend_chart ? (
                                    <div className={styles.chartImageWrapper}>
                                        <img 
                                            src={`data:image/png;base64,${trend_chart}`}
                                            alt="趋势分析图表"
                                            className={styles.chartImage}
                                            loading="lazy" 
                                        />
                                        <div className={styles.chartCaption}>支撑线与阻力线分析</div>
                                    </div>
                                ) : (
                                    <div className={styles.chartPlaceholder}>
                                        <div className={styles.loadingSpinner}></div>
                                        <h5>加载趋势图表中...</h5>
                                        <p>正在生成趋势分析图表和支撑阻力线</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
