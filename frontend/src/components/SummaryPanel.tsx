import { useAppStore } from '../store/useAppStore';
import styles from './SummaryPanel.module.css';

export default function SummaryPanel() {
    const { analysisResult } = useAppStore();
    
    // 如果没有数据，虽然在主流程中通常会控制，但作为组件也需要处理
    if (!analysisResult) return null;

    const { 
        data_length, 
        timeframe, 
        asset_name,
        multi_timeframe_mode,
        timeframes
    } = analysisResult;

    // 处理多时间框架显示
    let displayTimeframe = timeframe || '--';
    let isLongText = false;
    
    if (multi_timeframe_mode && timeframes && timeframes.length > 0) {
        displayTimeframe = timeframes.join(' + ');
        // 如果文本较长，适当缩小字体
        if (displayTimeframe.length > 5) {
            isLongText = true;
        }
    }

    return (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}>
                <i className="fas fa-chart-pie"></i> 分析摘要
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch mb-3">
                <div className="flex">
                    <div className={`${styles.statsCard} w-full`}>
                        <div className={styles.statsNumber}>{data_length || '--'}</div>
                        <div className={styles.statsLabel}>数据点</div>
                    </div>
                </div>
                <div className="flex">
                    <div className={`${styles.statsCard} w-full`}>
                        <div className={`${styles.statsNumber} ${isLongText ? 'text-2xl' : ''}`}>
                            {displayTimeframe}
                        </div>
                        <div className={styles.statsLabel}>时间框架</div>
                    </div>
                </div>
                <div className="flex">
                    <div className={`${styles.statsCard} w-full`}>
                        <div className={styles.statsNumber}>{asset_name || 'BTC'}</div>
                        <div className={styles.statsLabel}>资产</div>
                    </div>
                </div>
            </div>

        </div>
    );
}
