import { useAppStore } from '../store/useAppStore';
import styles from './DecisionPanel.module.css';

export default function DecisionPanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { 
        decision: singleDecision,
        latest_price,
        result_id,
        data_method_short,
        analysis_time_display
    } = analysisResult;

    // 辅助函数：格式化百分比
    const formatPct = (current: number | undefined, target: number | string | undefined, type: 'stop' | 'profit', decision: string | undefined) => {
        if (!current || !target || typeof target !== 'number' || isNaN(current) || isNaN(target)) return null;
        
        const pct = ((target - current) / current) * 100;
        const pctStr = (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
        
        const isShort = decision?.toLowerCase().includes('short') || decision?.includes('做空');
        
        let isProfitDirection = false;
        
        if (type === 'profit') {
             // 止盈：Long时pct>0为好，Short时pct<0为好
             isProfitDirection = isShort ? (pct < 0) : (pct > 0);
        } else {
            // 止损：通常无论Long/Short，止损位都是为了限制亏损，所以这里我们可能只关心它是pct-up还是pct-down的颜色
            isProfitDirection = false; 
        }

        const badgeClass = isProfitDirection ? styles.pctUp : styles.pctDown;
        
        return <span className={`${styles.pctBadge} ${badgeClass}`}>{pctStr}</span>;
    };

    const getDecisionClass = (d: string) => {
        const lower = d?.toLowerCase() || '';
        if (lower.includes('buy') || lower.includes('long') || lower.includes('做多')) return styles.decisionLong;
        if (lower.includes('sell') || lower.includes('short') || lower.includes('做空')) return styles.decisionShort;
        return styles.decisionHold;
    };

    // isExperimental removed as we only have original version now

    return (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}>
                <i className="fas fa-bullseye"></i> 最终交易决策
            </h4>

            <div className={styles.singleModelResults}>
                <div className="text-center mb-3">
                    <span className={`${styles.decisionBadge} ${getDecisionClass(singleDecision?.action || singleDecision?.decision || 'HOLD')}`}>
                        {singleDecision?.action || singleDecision?.decision || 'HOLD'}
                    </span>
                </div>

                <div className={styles.priceInfoCard}>
                    <div className={styles.priceInfoGrid}>
                        {singleDecision?.market_environment && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>市场环境</div>
                                <div className={styles.priceValue}>
                                    <span className="badge bg-info">{singleDecision.market_environment}</span>
                                </div>
                            </div>
                        )}
                         {singleDecision?.volatility_assessment && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>波动性评估</div>
                                <div className={styles.priceValue}>
                                    <span className="badge bg-warning">{singleDecision.volatility_assessment}</span>
                                </div>
                            </div>
                        )}
                        <div className={styles.priceItem}>
                            <div className={styles.priceLabel}>预测周期</div>
                            <div className={styles.priceValue}>
                                {singleDecision?.forecast_horizon || '未提供'}
                            </div>
                        </div>
                        <div className={styles.priceItem}>
                            <div className={styles.priceLabel}>风险回报比</div>
                            <div className={styles.priceValue}>
                                {singleDecision?.risk_reward_ratio || singleDecision?.risk_reward || '未提供'}
                            </div>
                        </div>
                         {data_method_short && analysis_time_display && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>数据方式/时间</div>
                                <div className={styles.priceValue}>
                                    {data_method_short} ｜ {analysis_time_display}
                                </div>
                            </div>
                        )}
                        <div className={styles.priceItem}>
                            <div className={styles.priceLabel}>结果编号</div>
                            <div className={styles.priceValue}>
                                <span className="badge bg-secondary">{result_id}</span>
                            </div>
                        </div>

                        {latest_price && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>最新价格</div>
                                <div className={`${styles.priceValue} ${styles.current}`}>
                                    <span className="badge bg-primary fs-6">{latest_price}</span>
                                </div>
                            </div>
                        )}

                        {singleDecision?.stop_loss && singleDecision.stop_loss !== '未提供' && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>止损价格</div>
                                <div className={`${styles.priceValue} ${styles.stopLoss}`}>
                                    {singleDecision.stop_loss}
                                    {formatPct(latest_price, singleDecision.stop_loss as number, 'stop', singleDecision.action || singleDecision.decision)}
                                </div>
                            </div>
                        )}

                        {singleDecision?.take_profit && singleDecision.take_profit !== '未提供' && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>止盈价格</div>
                                <div className={`${styles.priceValue} ${styles.takeProfit}`}>
                                    {singleDecision.take_profit}
                                    {formatPct(latest_price, singleDecision.take_profit as number, 'profit', singleDecision.action || singleDecision.decision)}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {singleDecision?.confidence_level && (
                     <div className={styles.confidenceSection}>
                        <div className={styles.confidenceLabel}>
                            <span>置信度</span>
                            <span className={styles.confidenceValue}>{singleDecision.confidence_level}</span>
                        </div>
                        <div className={styles.confidenceBar}>
                            <div className={`${styles.confidenceBarFill} ${singleDecision.confidence_level === '高' ? styles.confidenceHigh : singleDecision.confidence_level === '中' ? styles.confidenceMedium : styles.confidenceLow}`} 
                                 style={{ width: singleDecision.confidence_level === '高' ? '85%' : singleDecision.confidence_level === '中' ? '60%' : '35%' }}>
                                {singleDecision.confidence_level}
                            </div>
                        </div>
                    </div>
                )}

                <div className={styles.reasoningSection}>
                    <div className={styles.reasoningLabel}>决策理由</div>
                    <div className={styles.reasoningContent}>
                        {singleDecision?.justification || singleDecision?.reasoning || '暂无详细决策理由。'}
                    </div>
                </div>
            </div>
        </div>
    );
}
