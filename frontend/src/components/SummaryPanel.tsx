import { useAppStore } from '../store/useAppStore';
import styles from './SummaryPanel.module.css';

export default function SummaryPanel() {
    const { analysisResult } = useAppStore();
    
    // 如果没有数据，虽然在主流程中通常会控制，但作为组件也需要处理
    if (!analysisResult) return null;

    const { 
        data_length, 
        timeframe, 
        asset_name 
    } = analysisResult;

    return (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}>
                <i className="fas fa-chart-pie"></i> 分析摘要
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch">
                <div className="flex">
                    <div className={`${styles.statsCard} w-full`}>
                        <div className={styles.statsNumber}>{data_length || '--'}</div>
                        <div className={styles.statsLabel}>数据点</div>
                    </div>
                </div>
                <div className="flex">
                    <div className={`${styles.statsCard} w-full`}>
                        <div className={styles.statsNumber}>{timeframe || '--'}</div>
                        <div className={styles.statsLabel}>时间框架</div>
                    </div>
                </div>
                <div className="flex">
                    <div className={`${styles.statsCard} w-full`}>
                        <div className={styles.statsNumber}>{asset_name || '--'}</div>
                        <div className={styles.statsLabel}>资产</div>
                    </div>
                </div>
            </div>
        </div>
    );
}
