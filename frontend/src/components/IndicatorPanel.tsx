import { useAppStore } from '../store/useAppStore';
import AutoBeautify from './AutoBeautify';
import styles from './IndicatorPanel.module.css';
import autoBeautifyStyles from './AutoBeautify.module.css';

export default function IndicatorPanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { technical_indicators, indicator_report } = analysisResult;

    // 优先展示 HTML 格式的 technical_indicators，如果为空则展示 fallback 内容
    const content = technical_indicators || indicator_report;

    return (
        <div className={styles.largePanel}>
            <h3 className={styles.largePanelTitle}>
                <i className="fas fa-chart-bar"></i> 技术指标智能体
            </h3>
            <div className={styles.largePanelSection}>
                {content ? (
                    <AutoBeautify content={content} />
                ) : (
                    <div className={`${autoBeautifyStyles.autoBeautify} ${styles.fallbackList}`}>
                        <ul>
                            <li><strong>RSI (14):</strong> 暂无数据</li>
                            <li><strong>MACD:</strong> 暂无数据</li>
                            <li><strong>移动平均线:</strong> 暂无数据</li>
                            <li><strong>布林带:</strong> 暂无数据</li>
                            <li><strong>成交量:</strong> 暂无数据</li>
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
}
