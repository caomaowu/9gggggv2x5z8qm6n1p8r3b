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
        analysis_time_display,
        llm_config
    } = analysisResult;

    const formatPct = (current: number | undefined, target: number | string | undefined, type: 'stop' | 'profit', decision: string | undefined) => {
        if (!current || !target || typeof target !== 'number' || isNaN(current) || isNaN(target)) return null;
        const pct = ((target - current) / current) * 100;
        const pctStr = (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
        return <span className={`${styles.pctBadge} ${pct > 0 ? styles.pctUp : styles.pctDown}`}>{pctStr}</span>;
    };

    const getDecisionClass = (d: string) => {
        const lower = d?.toLowerCase() || '';
        if (lower.includes('long') || lower.includes('buy') || lower.includes('做多')) return styles.decisionLong;
        if (lower.includes('short') || lower.includes('sell') || lower.includes('做空')) return styles.decisionShort;
        return styles.decisionHold;
    };

    const score = singleDecision?.score ?? 0;
    const direction = singleDecision?.direction ?? (singleDecision?.action?.toLowerCase() ?? 'hold');
    const resonance = singleDecision?.resonance;
    const agentScores = singleDecision?.agent_scores;

    return (
        <div className={styles.panel}>
            <h4 className={styles.panelTitle}>
                <i className="fas fa-bullseye"></i> Brale Consensus Fusion
            </h4>

            {/* Fusion info */}
            <div className={styles.aiVersionInfo}>
                <div className={styles.icon}>
                    <i className="fas fa-layer-group fa-2x"></i>
                </div>
                <div className={styles.content}>
                    <div className={styles.title}>融合共识</div>
                    <span className={`${styles.versionBadge} ${styles.versionStandard}`}>
                        direction: {direction} | score: {score.toFixed(2)}
                        {singleDecision?.confidence !== undefined && ` | conf: ${(singleDecision.confidence * 100).toFixed(0)}%`}
                    </span>
                    {singleDecision?.agreement !== undefined && (
                        <div className={styles.versionDescription}>
                            agreement: {(singleDecision.agreement * 100).toFixed(0)}%
                            {singleDecision?.coverage !== undefined && ` | coverage: ${((singleDecision.coverage ?? 0) * 100).toFixed(0)}%`}
                        </div>
                    )}
                </div>
            </div>

            {/* Resonance */}
            {resonance && (
                <div className={styles.llmInfo} style={{ borderLeft: resonance.active ? '3px solid #10b981' : '3px solid #6b7280' }}>
                    <div className={styles.llmInfoTitle}>
                        共振: {resonance.active ? '活跃' : '未激活'}
                        {resonance.active && ` (${resonance.aligned_count} agents, bonus +${(resonance.bonus).toFixed(3)})`}
                    </div>
                </div>
            )}

            {/* Agent scores */}
            {agentScores && (
                <div className={styles.llmInfo}>
                    <div className={styles.llmInfoTitle}>Agent 分项</div>
                    <div className={styles.llmInfoGrid}>
                        {Object.entries(agentScores).map(([name, s]: [string, any]) => (
                            <div key={name} className={styles.llmInfoItem}>
                                <div className={styles.llmLabel}>{name}</div>
                                <div className={styles.llmValue}>
                                    <span className={styles.llmModel}>score: {s.score?.toFixed(2) ?? '-'}</span>
                                    <span className={styles.llmTemp}>conf: {((s.confidence ?? 0) * 100).toFixed(0)}%</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* LLM info */}
            {llm_config && (
                <div className={styles.llmInfo}>
                    <div className={styles.llmInfoTitle}>LLM 模型</div>
                    <div className={styles.llmInfoGrid}>
                        {(['indicator', 'structure', 'mechanics'] as const).map(agent => {
                            const info = llm_config[agent];
                            if (!info) return null;
                            return (
                                <div key={agent} className={styles.llmInfoItem}>
                                    <div className={styles.llmLabel}>{agent}</div>
                                    <div className={styles.llmValue}>
                                        <span className={styles.llmModel}>{info.model || '-'}</span>
                                        {typeof info.temperature === 'number' && (
                                            <span className={styles.llmTemp}>T={info.temperature}</span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            <div className={styles.singleModelResults}>
                <div className="text-center mb-3">
                    <span className={`${styles.decisionBadge} ${getDecisionClass(singleDecision?.action || direction || 'HOLD')}`}>
                        {singleDecision?.action || 'HOLD'}
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
                                <div className={styles.priceLabel}>波动性</div>
                                <div className={styles.priceValue}>
                                    <span className="badge bg-warning">{singleDecision.volatility_assessment}</span>
                                </div>
                            </div>
                        )}
                        <div className={styles.priceItem}>
                            <div className={styles.priceLabel}>信号类型</div>
                            <div className={styles.priceValue}>
                                {singleDecision?.signal_type || singleDecision?.forecast_horizon || 'next 1-2 bars'}
                            </div>
                        </div>
                        {data_method_short && analysis_time_display && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>数据方式/时间</div>
                                <div className={styles.priceValue}>
                                    {data_method_short} | {analysis_time_display}
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

                        {singleDecision?.entry_point && singleDecision.entry_point !== latest_price && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>入场点</div>
                                <div className={styles.priceValue}>{singleDecision.entry_point}</div>
                            </div>
                        )}

                        {singleDecision?.stop_loss != null && singleDecision.stop_loss !== '未提供' && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>止损价格</div>
                                <div className={`${styles.priceValue} ${styles.stopLoss}`}>
                                    {String(singleDecision.stop_loss)}
                                    {formatPct(latest_price, singleDecision.stop_loss as number, 'stop', singleDecision.action || singleDecision.decision)}
                                </div>
                            </div>
                        )}

                        {singleDecision?.take_profit != null && singleDecision.take_profit !== '未提供' && (
                            <div className={styles.priceItem}>
                                <div className={styles.priceLabel}>止盈价格</div>
                                <div className={`${styles.priceValue} ${styles.takeProfit}`}>
                                    {String(singleDecision.take_profit)}
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
                            <div className={`${styles.confidenceBarFill} ${Number(singleDecision.confidence) > 0.7 ? styles.confidenceHigh : Number(singleDecision.confidence) > 0.4 ? styles.confidenceMedium : styles.confidenceLow}`} 
                                 style={{ width: `${Math.round(Number(singleDecision.confidence) * 100)}%` }}>
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
