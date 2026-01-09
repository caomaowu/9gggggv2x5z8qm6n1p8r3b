import { useAppStore } from '../store/useAppStore';
import AutoBeautify from './AutoBeautify';
import styles from './PatternPanel.module.css';

export default function PatternPanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { 
        pattern_analysis, 
        pattern_report, 
        pattern_chart, 
        pattern_image,
        pattern_images,
        multi_timeframe_mode
    } = analysisResult;
    
    const content = pattern_analysis || pattern_report;
    const hasContent = content && content.trim() !== 'None' && content.trim() !== '';
    
    // 判断是否为多时间框架模式
    const isMultiTF = multi_timeframe_mode && pattern_images && Object.keys(pattern_images).length > 0;
    // 单时间框架图表（兼容多个字段名）
    const singleChart = pattern_chart || pattern_image;

    return (
        <div className={styles.largePanel}>
            <h3 className={styles.largePanelTitle}>
                <i className="fas fa-brain"></i> 模式识别智能体
            </h3>
            <div className={styles.panelGroup}>
                <div className={styles.panel}>
                    <h4 className={styles.panelTitle}>
                        <i className="fas fa-search"></i> 模式识别
                    </h4>
                    <div className={styles.formGroup}>
                        <h5>识别模式:</h5>
                        {hasContent ? (
                            <AutoBeautify content={content} />
                        ) : (
                            <div className={styles.emptyState}>
                                <i className="fas fa-spinner fa-spin"></i>
                                <h5>模式识别分析中...</h5>
                                <p>智能分析引擎正在处理K线图表数据，请稍等片刻或重新分析。</p>
                            </div>
                        )}
                    </div>

                    {hasContent && (
                        <div className={styles.formGroup}>
                            <h5>模式可靠性:</h5>
                            <div className={styles.alert}>
                                <i className="fas fa-chart-line"></i>
                                <span>模式可靠性评估基于历史统计数据和技术分析理论，请结合其他指标综合判断。</span>
                            </div>
                        </div>
                    )}
                </div>

                <div className={styles.panel}>
                    <h4 className={styles.panelTitle}>
                        <i className="fas fa-chart-bar"></i> 模式可视化
                    </h4>
                    <div className={styles.chartContainer}>
                        {isMultiTF ? (
                            // 多时间框架模式：网格布局同时展示多张图表
                            <div className={styles.multiChartGrid}>
                                {Object.entries(pattern_images).map(([tf, img]) => (
                                    <div key={tf} className={styles.chartGridItem}>
                                        <div className={styles.timeframeLabel}>{tf}</div>
                                        <img 
                                            src={`data:image/png;base64,${img}`}
                                            alt={`${tf} K线图`}
                                            className={styles.chartImage}
                                            loading="lazy" 
                                        />
                                    </div>
                                ))}
                            </div>
                        ) : (
                            // 单时间框架模式：保持原有布局
                            <div className={styles.chartWrapper}>
                                {singleChart ? (
                                    <div className={styles.chartImageWrapper}>
                                        <img 
                                            src={`data:image/png;base64,${singleChart}`}
                                            alt="模式分析图表"
                                            className={styles.chartImage}
                                            loading="lazy" 
                                        />
                                        <div className={styles.chartCaption}>模式识别可视化图表</div>
                                    </div>
                                ) : (
                                    <div className={styles.chartPlaceholder}>
                                        <div className={styles.loadingSpinner}></div>
                                        <h5>加载模式图表中...</h5>
                                        <p>正在生成K线图表和模式识别分析</p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
