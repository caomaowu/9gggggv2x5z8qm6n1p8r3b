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

            {/* 模型配置信息展示 */}
            {analysisResult.llm_config && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-gray-100">
                    <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
                         <div className="flex items-center mb-2 pb-1 border-b border-gray-200">
                            <i className="fas fa-robot text-blue-500 mr-2"></i>
                            <span className="font-semibold text-gray-700 text-sm">分析智能体</span>
                        </div>
                        <div className="text-sm space-y-1">
                            <div className="flex justify-between items-center">
                                <span className="text-gray-500 text-xs">模型</span>
                                <span className="font-medium text-gray-800 text-xs truncate pl-2" title={analysisResult.llm_config.agent.model}>
                                    {analysisResult.llm_config.agent.model.split('/').pop()}
                                </span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-500 text-xs">温度</span>
                                <span className="font-medium text-gray-800 text-xs">{analysisResult.llm_config.agent.temperature}</span>
                            </div>
                        </div>
                    </div>

                    <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
                         <div className="flex items-center mb-2 pb-1 border-b border-gray-200">
                            <i className="fas fa-chart-line text-purple-500 mr-2"></i>
                            <span className="font-semibold text-gray-700 text-sm">图表智能体</span>
                        </div>
                        <div className="text-sm space-y-1">
                            <div className="flex justify-between items-center">
                                <span className="text-gray-500 text-xs">模型</span>
                                <span className="font-medium text-gray-800 text-xs truncate pl-2" title={analysisResult.llm_config.graph.model}>
                                    {analysisResult.llm_config.graph.model.split('/').pop()}
                                </span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-500 text-xs">温度</span>
                                <span className="font-medium text-gray-800 text-xs">{analysisResult.llm_config.graph.temperature}</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
