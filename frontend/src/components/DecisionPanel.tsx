import { useAppStore } from '../store/useAppStore';
import styles from './DecisionPanel.module.css';

export default function DecisionPanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { 
        dual_model_analysis, 
        decision: singleDecision,
        latest_price,
        result_id,
        data_method_short,
        analysis_time_display,
        agent_version_name,
        agent_version_description,
        decision_agent_version
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

    const isExperimental = (name: string) => name && name.includes('宽松');

    return (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}>
                <i className="fas fa-bullseye"></i> 最终交易决策
            </h4>

            {/* AI 版本信息 */}
            {(agent_version_name || decision_agent_version) && (
                <div className={styles.aiVersionInfo}>
                    <div className={styles.icon}>
                        <i className="fas fa-brain fa-2x"></i>
                    </div>
                    <div className={styles.content}>
                        <div className={styles.title}>
                            <i className="fas fa-cog me-1"></i>决策智能体版本
                        </div>
                        {agent_version_name ? (
                            isExperimental(agent_version_name) ? (
                                <span className={`${styles.versionBadge} ${styles.versionExperimental}`}>
                                    <i className="fas fa-magic me-1"></i>{agent_version_name}（实验性）
                                </span>
                            ) : (
                                <span className={`${styles.versionBadge} ${styles.versionStandard}`}>
                                    <i className="fas fa-shield-alt me-1"></i>{agent_version_name}（标准）
                                </span>
                            )
                        ) : decision_agent_version === 'relaxed' ? (
                            <span className={`${styles.versionBadge} ${styles.versionExperimental}`}>
                                <i className="fas fa-magic me-1"></i>宽松版本（实验性）
                            </span>
                        ) : (
                            <span className={`${styles.versionBadge} ${styles.versionStandard}`}>
                                <i className="fas fa-shield-alt me-1"></i>约束版本（标准）
                            </span>
                        )}
                        
                        {agent_version_description && (
                            <div className={styles.versionDescription}>
                                <i className="fas fa-info-circle me-1"></i>{agent_version_description}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 双模型模式 */}
            {dual_model_analysis ? (
                <div className={styles.dualModelResults}>
                    <div className={styles.comparisonStatus}>
                        <h6><i className="fas fa-layer-group"></i> 双模型对比分析</h6>
                        <div className={styles.modelVsContainer}>
                            <span className={`${styles.modelBadge} ${styles.modelA}`}>
                                <i className="fas fa-robot"></i> {dual_model_analysis.model_1_result?.model_name}
                            </span>
                            <span className={styles.vsSeparator}>VS</span>
                            <span className={`${styles.modelBadge} ${styles.modelB}`}>
                                <i className="fas fa-robot"></i> {dual_model_analysis.model_2_result?.model_name}
                            </span>
                        </div>
                        <div className={styles.consensusIndicator}>
                            {dual_model_analysis.comparison?.consensus ? (
                                <span className={`badge ${styles.consensus}`}>
                                    <i className="fas fa-check-circle"></i> 决策一致
                                </span>
                            ) : (
                                <span className={`badge ${styles.divergent}`}>
                                    <i className="fas fa-exclamation-triangle"></i> 决策分歧
                                </span>
                            )}
                        </div>
                    </div>

                    <div className={styles.modelInfoPanel}>
                        <div className={styles.modelInfoGrid}>
                            <div className={styles.modelInfoItem}>
                                <div className={styles.modelInfoLabel}>最新价格</div>
                                <div className={styles.modelInfoValue}>
                                    {latest_price ? <span className="badge bg-primary">{latest_price}</span> : '未提供'}
                                </div>
                            </div>
                            {data_method_short && analysis_time_display && (
                                <div className={styles.modelInfoItem}>
                                    <div className={styles.modelInfoLabel}>数据方式/时间</div>
                                    <div className={styles.modelInfoValue}>
                                        {data_method_short} ｜ {analysis_time_display}
                                    </div>
                                </div>
                            )}
                            <div className={styles.modelInfoItem}>
                                <div className={styles.modelInfoLabel}>结果编号</div>
                                <div className={styles.modelInfoValue}>
                                    <span className="badge bg-secondary">{result_id}</span>
                                </div>
                            </div>
                            <div className={styles.modelInfoItem}>
                                <div className={styles.modelInfoLabel}>市场环境</div>
                                <div className={styles.modelInfoValue}>
                                    {dual_model_analysis.model_1_result?.market_environment || '未知'}
                                </div>
                            </div>
                            <div className={styles.modelInfoItem}>
                                <div className={styles.modelInfoLabel}>波动性评估</div>
                                <div className={styles.modelInfoValue}>
                                    {dual_model_analysis.model_1_result?.volatility_assessment || '未知'}
                                </div>
                            </div>
                            <div className={styles.modelInfoItem}>
                                <div className={styles.modelInfoLabel}>风险等级</div>
                                <div className={styles.modelInfoValue}>
                                    <span className="status-indicator medium">中等风险</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Model A */}
                    <div className={`${styles.modelResult} ${styles.modelA}`}>
                        <div className={styles.modelHeader}>
                            <h6 className={styles.modelTitle}>
                                <i className="fas fa-robot"></i> 模型A分析结果
                            </h6>
                            <span className={styles.modelTag}>{dual_model_analysis.model_1_result?.model_name}</span>
                        </div>
                        <div className={styles.modelDecision}>
                            <span className={styles.modelDecisionBadge}>
                                {dual_model_analysis.model_1_result?.decision}
                            </span>
                        </div>
                        <div className={styles.decisionDetails}>
                            <div className={styles.confidenceSection}>
                                <div className={styles.confidenceLabel}>
                                    <span>置信度</span>
                                    <span className={styles.confidenceValue}>{Math.round((dual_model_analysis.model_1_result?.confidence || 0) * 100)}%</span>
                                </div>
                                <div className={styles.confidenceBar}>
                                    <div className={styles.confidenceFill} style={{ width: `${Math.round((dual_model_analysis.model_1_result?.confidence || 0) * 100)}%` }}>
                                        {Math.round((dual_model_analysis.model_1_result?.confidence || 0) * 100)}%
                                    </div>
                                </div>
                            </div>
                            
                            <div className={styles.decisionMetrics}>
                                <div className={styles.metricItem}>
                                    <div className={styles.metricLabel}>风险回报比</div>
                                    <div className={styles.metricValue}>{dual_model_analysis.model_1_result?.risk_reward}</div>
                                </div>
                                <div className={styles.metricItem}>
                                    <div className={styles.metricLabel}>时间框架</div>
                                    <div className={styles.metricValue}>{dual_model_analysis.model_1_result?.time_horizon}</div>
                                </div>
                            </div>
                            
                            {/* Inline Prices with dynamic badges */}
                            <div className={styles.priceInline}>
                                <div>
                                    <span className={styles.label}>止损</span>
                                    <span className={styles.val}>{dual_model_analysis.model_1_result?.stop_loss}</span>
                                    {formatPct(latest_price, dual_model_analysis.model_1_result?.stop_loss as number, 'stop', dual_model_analysis.model_1_result?.decision)}
                                </div>
                                <div>
                                    <span className={styles.label}>止盈</span>
                                    <span className={styles.val}>{dual_model_analysis.model_1_result?.take_profit}</span>
                                    {formatPct(latest_price, dual_model_analysis.model_1_result?.take_profit as number, 'profit', dual_model_analysis.model_1_result?.decision)}
                                </div>
                            </div>

                            <div className={styles.reasoningSection}>
                                <div className={styles.reasoningLabel}>分析推理</div>
                                <div className={styles.reasoningContent}>
                                    {dual_model_analysis.model_1_result?.reasoning}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Model B */}
                    <div className={`${styles.modelResult} ${styles.modelB}`}>
                        <div className={styles.modelHeader}>
                            <h6 className={styles.modelTitle}>
                                <i className="fas fa-robot"></i> 模型B分析结果
                            </h6>
                            <span className={styles.modelTag}>{dual_model_analysis.model_2_result?.model_name}</span>
                        </div>
                        <div className={styles.modelDecision}>
                            <span className={styles.modelDecisionBadge}>
                                {dual_model_analysis.model_2_result?.decision}
                            </span>
                        </div>
                        <div className={styles.decisionDetails}>
                            <div className={styles.confidenceSection}>
                                <div className={styles.confidenceLabel}>
                                    <span>置信度</span>
                                    <span className={styles.confidenceValue}>{Math.round((dual_model_analysis.model_2_result?.confidence || 0) * 100)}%</span>
                                </div>
                                <div className={styles.confidenceBar}>
                                    <div className={styles.confidenceFill} style={{ width: `${Math.round((dual_model_analysis.model_2_result?.confidence || 0) * 100)}%` }}>
                                        {Math.round((dual_model_analysis.model_2_result?.confidence || 0) * 100)}%
                                    </div>
                                </div>
                            </div>

                            <div className={styles.decisionMetrics}>
                                <div className={styles.metricItem}>
                                    <div className={styles.metricLabel}>风险回报比</div>
                                    <div className={styles.metricValue}>{dual_model_analysis.model_2_result?.risk_reward}</div>
                                </div>
                                <div className={styles.metricItem}>
                                    <div className={styles.metricLabel}>时间框架</div>
                                    <div className={styles.metricValue}>{dual_model_analysis.model_2_result?.time_horizon}</div>
                                </div>
                            </div>

                             {/* Inline Prices with dynamic badges */}
                             <div className={styles.priceInline}>
                                <div>
                                    <span className={styles.label}>止损</span>
                                    <span className={styles.val}>{dual_model_analysis.model_2_result?.stop_loss}</span>
                                    {formatPct(latest_price, dual_model_analysis.model_2_result?.stop_loss as number, 'stop', dual_model_analysis.model_2_result?.decision)}
                                </div>
                                <div>
                                    <span className={styles.label}>止盈</span>
                                    <span className={styles.val}>{dual_model_analysis.model_2_result?.take_profit}</span>
                                    {formatPct(latest_price, dual_model_analysis.model_2_result?.take_profit as number, 'profit', dual_model_analysis.model_2_result?.decision)}
                                </div>
                            </div>

                            <div className={styles.reasoningSection}>
                                <div className={styles.reasoningLabel}>分析推理</div>
                                <div className={styles.reasoningContent}>
                                    {dual_model_analysis.model_2_result?.reasoning}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            ) : (
                /* 单模型模式 */
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
            )}
        </div>
    );
}
