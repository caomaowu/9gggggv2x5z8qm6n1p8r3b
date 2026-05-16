import { useAppStore } from '../store/useAppStore';
import type { FutureKlineDataRow, AgentVerification } from '../types';
import styles from './FutureKlinePanel.module.css';

export default function FutureKlinePanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { 
        future_kline_chart_base64, 
        future_kline_data,
        future_15m_chart_base64,
        latest_price,
        decision: singleDecision,
        timeframe, // Get timeframe
        agent_verification,
        adverse_excursion
    } = analysisResult;

    const stopLoss = singleDecision?.stop_loss;
    const takeProfit = singleDecision?.take_profit;
    const action = singleDecision?.action || singleDecision?.decision || '';
    
    // Normalize Action
    const isLong = action.toLowerCase().includes('buy') || action.toLowerCase().includes('long') || action.includes('做多');
    const isShort = action.toLowerCase().includes('sell') || action.toLowerCase().includes('short') || action.includes('做空');

    // 3. Verification Logic
    let slTriggered = false;
    let tpTriggered = false;
    
    const slVal = typeof stopLoss === 'number' ? stopLoss : parseFloat(stopLoss as string);
    const tpVal = typeof takeProfit === 'number' ? takeProfit : parseFloat(takeProfit as string);
    const latestVal = latest_price || 0;

    if (future_kline_data && future_kline_data.length > 0) {
        for (const kline of future_kline_data) {
            const high = parseFloat(String(kline.high));
            const low = parseFloat(String(kline.low));
            
            if (isLong) {
                if (!isNaN(tpVal) && high >= tpVal) tpTriggered = true;
                if (!isNaN(slVal) && low <= slVal) slTriggered = true;
            } else if (isShort) {
                if (!isNaN(tpVal) && low <= tpVal) tpTriggered = true;
                if (!isNaN(slVal) && high >= slVal) slTriggered = true;
            }
        }
    }

    // 4. Trend Verification
    // Future Kline 1
    const firstKline = future_kline_data && future_kline_data.length >= 1 ? future_kline_data[0] : null;
    let firstTrendPassed = false;
    let firstTrendDiff = 0;
    let firstKlinePct = 0;

    if (firstKline && latestVal) {
        const close = parseFloat(String(firstKline.close));
        const open = parseFloat(String(firstKline.open));
        firstTrendDiff = ((close - latestVal) / latestVal) * 100;
        
        if (open > 0) {
            firstKlinePct = ((close - open) / open) * 100;
        }
        
        if (isLong) {
            firstTrendPassed = close > latestVal;
        } else if (isShort) {
            firstTrendPassed = close < latestVal;
        }
    }

    // Future Kline 2
    const secondKline = future_kline_data && future_kline_data.length >= 2 ? future_kline_data[1] : null;
    let trendPassed = false;
    let trendDiff = 0;
    let secondKlinePct = 0;
    
    if (secondKline && latestVal) {
        const close = parseFloat(String(secondKline.close));
        const open = parseFloat(String(secondKline.open));
        trendDiff = ((close - latestVal) / latestVal) * 100;
        
        if (open > 0) {
            secondKlinePct = ((close - open) / open) * 100;
        }

        if (isLong) {
            trendPassed = close > latestVal;
        } else if (isShort) {
            trendPassed = close < latestVal;
        }
    }

    // Future Kline 3
    const thirdKline = future_kline_data && future_kline_data.length >= 3 ? future_kline_data[2] : null;
    let thirdTrendPassed = false;
    let thirdTrendDiff = 0;
    let thirdKlinePct = 0;
    
    if (thirdKline && latestVal) {
        const close = parseFloat(String(thirdKline.close));
        const open = parseFloat(String(thirdKline.open));
        thirdTrendDiff = ((close - latestVal) / latestVal) * 100;
        
        if (open > 0) {
            thirdKlinePct = ((close - open) / open) * 100;
        }

        if (isLong) {
            thirdTrendPassed = close > latestVal;
        } else if (isShort) {
            thirdTrendPassed = close < latestVal;
        }
    }

    // Helper for Price Formatting
    const formatPrice = (price: number | string | undefined) => {
        if (price === undefined || price === null) return '';
        const num = typeof price === 'string' ? parseFloat(price) : price;
        if (isNaN(num)) return String(price);
        
        if (num === 0) return '0.00';

        const absNum = Math.abs(num);
        
        // Intelligent precision based on price magnitude
        // For very small values (Meme coins etc.)
        if (absNum < 0.000001) return num.toFixed(10);
        if (absNum < 0.0001) return num.toFixed(8);
        if (absNum < 1) return num.toFixed(6);
        if (absNum < 10) return num.toFixed(5);
        if (absNum < 1000) return num.toFixed(4); // Even for BTC/ETH, 4 decimals is often useful
        
        return num.toFixed(2);
    };

    // Helper for Pct Display
    const getPct = (target: number) => {
        if (!latestVal) return '';
        const pct = ((target - latestVal) / latestVal) * 100;
        return (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
    };

    // Inline style constants for new verification sections
    const thStyle: React.CSSProperties = {
        padding: '8px 10px',
        textAlign: 'left',
        fontWeight: 600,
        color: '#374151',
        fontSize: '0.78rem',
        borderBottom: '1px solid #e5e7eb'
    };
    const tdStyle: React.CSSProperties = {
        padding: '7px 10px',
        color: '#4b5563',
        fontSize: '0.83rem'
    };
    const infoRowStyle: React.CSSProperties = {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        marginBottom: '6px',
        fontSize: '0.83rem'
    };

    return (
        <section className={styles.section}>
            <div className={styles.panel}>
                <div className={styles.panelHeader}>
                    <h3 className={styles.panelTitle}>
                        <i className="fas fa-history"></i> 未来走势回测验证
                        {isLong && (
                            <span className={`${styles.directionBadge} ${styles.directionLong}`}>
                                <i className="fas fa-arrow-up me-1"></i> 预测做多
                            </span>
                        )}
                        {isShort && (
                            <span className={`${styles.directionBadge} ${styles.directionShort}`}>
                                <i className="fas fa-arrow-down me-1"></i> 预测做空
                            </span>
                        )}
                    </h3>
                </div>
                <div className={styles.panelBody}>
                    
                    {/* Contrast Analysis Panel - Only if we have future data */}
                    {future_kline_data && future_kline_data.length > 0 && (
                        <div className={styles.analysisGrid}>
                            {/* Card 1: Data Contrast */}
                            <div className={styles.dataCard}>
                                <div className={styles.cardHeader}>
                                    <i className="fas fa-balance-scale me-2"></i> 数据对比分析
                                </div>
                                <div className={styles.priceGrid}>
                                    {/* Latest Price */}
                                    <div className={styles.priceItem}>
                                        <div className={styles.priceLabel}>预测时价格</div>
                                        <div className={styles.priceValue}>{formatPrice(latestVal)}</div>
                                        <span className={styles.statusPending}>基准点</span>
                                    </div>

                                    {/* Stop Loss */}
                                    <div className={styles.priceItem}>
                                        <div className={styles.priceLabel}>止损价格</div>
                                        <div className={`${styles.priceValue} ${styles.textDanger}`}>
                                            {!isNaN(slVal) ? formatPrice(slVal) : '未设置'}
                                        </div>
                                        {!isNaN(slVal) && (
                                            <>
                                                <div style={{fontSize: '0.8rem', marginBottom: '4px'}}>{getPct(slVal)}</div>
                                                <span className={`${styles.priceStatus} ${slTriggered ? styles.statusTriggeredBad : styles.statusPending}`}>
                                                    {slTriggered ? '已触发' : '未触发'}
                                                </span>
                                            </>
                                        )}
                                    </div>

                                    {/* Take Profit */}
                                    <div className={styles.priceItem}>
                                        <div className={styles.priceLabel}>止盈价格</div>
                                        <div className={`${styles.priceValue} ${styles.textSuccess}`}>
                                            {!isNaN(tpVal) ? formatPrice(tpVal) : '未设置'}
                                        </div>
                                        {!isNaN(tpVal) && (
                                            <>
                                                <div style={{fontSize: '0.8rem', marginBottom: '4px'}}>{getPct(tpVal)}</div>
                                                <span className={`${styles.priceStatus} ${tpTriggered ? styles.statusTriggered : styles.statusPending}`}>
                                                    {tpTriggered ? '已触及' : '未触及'}
                                                </span>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Card 2: Trend Verification */}
                            <div className={styles.dataCard}>
                                <div className={styles.cardHeader}>
                                    <i className="fas fa-check-double me-2"></i> K线走势验证
                                </div>
                                <div className={styles.trendList}>
                                    {/* Item 1: Latest Price */}
                                    <div className={styles.trendItem}>
                                        <div className={styles.itemLabel}>
                                            <i className="fas fa-map-marker-alt"></i> 预测时点
                                        </div>
                                        <div className={styles.itemValue}>
                                            <span className="text-muted">最新价</span>
                                            <span className={styles.priceNum}>{formatPrice(latestVal)}</span>
                                        </div>
                                    </div>

                                    {/* Item 2: 1st Future Kline */}
                                    {firstKline ? (
                                        <div className={styles.trendItem}>
                                            <div className={styles.itemLabel}>
                                                <i className="fas fa-clock"></i> 未来第1根K线 ({timeframe})
                                            </div>
                                            <div className={styles.itemValue}>
                                                <div style={{textAlign: 'right', marginRight: '8px'}}>
                                                    <div className={styles.priceNum}>{formatPrice(firstKline.close)}</div>
                                                    <div style={{color: firstKlinePct > 0 ? '#10B981' : (firstKlinePct < 0 ? '#EF4444' : '#6B7280'), fontSize: '0.75rem', fontWeight: 'bold'}}>
                                                        {firstKlinePct > 0 ? '+' : ''}{firstKlinePct.toFixed(2)}%
                                                    </div>
                                                    <div style={{color: '#6B7280', fontSize: '0.7rem'}}>
                                                        (vs预测: {firstTrendDiff > 0 ? '+' : ''}{firstTrendDiff.toFixed(2)}%)
                                                    </div>
                                                </div>
                                                {firstTrendPassed ? (
                                                    <span className={`${styles.verifyBadge} ${styles.verifyPass}`}>
                                                        <i className="fas fa-check"></i> 符合
                                                    </span>
                                                ) : (
                                                    <span className={`${styles.verifyBadge} ${styles.verifyFail}`}>
                                                        <i className="fas fa-times"></i> 不符
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className={styles.trendItem}>
                                            <div className={styles.itemLabel}>未来第1根K线</div>
                                            <div className="text-muted small">数据不足</div>
                                        </div>
                                    )}

                                    {/* Item 3: 2nd Future Kline */}
                                    {secondKline ? (
                                        <div className={`${styles.trendItem} ${styles.active}`}>
                                            <div className={styles.itemLabel}>
                                                <i className="fas fa-clock"></i> 未来第2根K线 ({timeframe})
                                            </div>
                                            <div className={styles.itemValue}>
                                                <div style={{textAlign: 'right', marginRight: '8px'}}>
                                                    <div className={styles.priceNum}>{formatPrice(secondKline.close)}</div>
                                                    <div style={{color: secondKlinePct > 0 ? '#10B981' : (secondKlinePct < 0 ? '#EF4444' : '#6B7280'), fontSize: '0.75rem', fontWeight: 'bold'}}>
                                                        {secondKlinePct > 0 ? '+' : ''}{secondKlinePct.toFixed(2)}%
                                                    </div>
                                                    <div style={{color: '#6B7280', fontSize: '0.7rem'}}>
                                                        (vs预测: {trendDiff > 0 ? '+' : ''}{trendDiff.toFixed(2)}%)
                                                    </div>
                                                </div>
                                                {trendPassed ? (
                                                    <span className={`${styles.verifyBadge} ${styles.verifyPass}`}>
                                                        <i className="fas fa-check"></i> 符合
                                                    </span>
                                                ) : (
                                                    <span className={`${styles.verifyBadge} ${styles.verifyFail}`}>
                                                        <i className="fas fa-times"></i> 不符
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className={styles.trendItem}>
                                            <div className={styles.itemLabel}>未来第2根K线</div>
                                            <div className="text-muted small">数据不足，无法验证</div>
                                        </div>
                                    )}

                                    {/* Item 4: 3rd Future Kline */}
                                    {thirdKline ? (
                                        <div className={styles.trendItem}>
                                            <div className={styles.itemLabel}>
                                                <i className="fas fa-clock"></i> 未来第3根K线 ({timeframe})
                                            </div>
                                            <div className={styles.itemValue}>
                                                <div style={{textAlign: 'right', marginRight: '8px'}}>
                                                    <div className={styles.priceNum}>{formatPrice(thirdKline.close)}</div>
                                                    <div style={{color: thirdKlinePct > 0 ? '#10B981' : (thirdKlinePct < 0 ? '#EF4444' : '#6B7280'), fontSize: '0.75rem', fontWeight: 'bold'}}>
                                                        {thirdKlinePct > 0 ? '+' : ''}{thirdKlinePct.toFixed(2)}%
                                                    </div>
                                                    <div style={{color: '#6B7280', fontSize: '0.7rem'}}>
                                                        (vs预测: {thirdTrendDiff > 0 ? '+' : ''}{thirdTrendDiff.toFixed(2)}%)
                                                    </div>
                                                </div>
                                                {thirdTrendPassed ? (
                                                    <span className={`${styles.verifyBadge} ${styles.verifyPass}`}>
                                                        <i className="fas fa-check"></i> 符合
                                                    </span>
                                                ) : (
                                                    <span className={`${styles.verifyBadge} ${styles.verifyFail}`}>
                                                        <i className="fas fa-times"></i> 不符
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className={styles.trendItem}>
                                            <div className={styles.itemLabel}>未来第3根K线</div>
                                            <div className="text-muted small">数据不足</div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Agent Independent Verification & 逆势波动验证 */}
                    {(agent_verification || adverse_excursion) && (
                        <div className={styles.analysisGrid} style={{ marginTop: '1.25rem' }}>
                            {/* Card A: Agent Independent Verification */}
                            {agent_verification && (
                                <div className={styles.dataCard}>
                                    <div className={styles.cardHeader}>
                                        <i className="fas fa-brain me-2"></i> Agent 独立方向验证
                                    </div>
                                    <div style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: '12px' }}>
                                        三个分析 Agent + Fusion 共识各自的方向判断 vs 第一根未来K线实际方向
                                    </div>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                                                <th style={thStyle}>Agent</th>
                                                <th style={thStyle}>Score</th>
                                                <th style={thStyle}>预测方向</th>
                                                <th style={thStyle}>实际方向</th>
                                                <th style={thStyle}>结果</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(['indicator', 'structure', 'mechanics', 'fusion'] as const).map((key) => {
                                                const agent = agent_verification.agents[key];
                                                const isFusion = key === 'fusion';
                                                const agentNames: Record<string, string> = {
                                                    indicator: 'Indicator',
                                                    structure: 'Structure',
                                                    mechanics: 'Mechanics',
                                                    fusion: 'Fusion'
                                                };
                                                const dirArrow = agent.direction === 'up' ? '↑' : agent.direction === 'down' ? '↓' : '—';
                                                const dirColor = agent.direction === 'up' ? '#10b981' : agent.direction === 'down' ? '#ef4444' : '#6b7280';
                                                const actualArrow = agent_verification.actual_direction === 'up' ? '↑' : agent_verification.actual_direction === 'down' ? '↓' : '—';
                                                const actualColor = agent_verification.actual_direction === 'up' ? '#10b981' : agent_verification.actual_direction === 'down' ? '#ef4444' : '#6b7280';
                                                const scoreColor = agent.score > 0 ? '#10b981' : agent.score < 0 ? '#ef4444' : '#6b7280';
                                                return (
                                                    <tr key={key} style={{
                                                        borderBottom: '1px solid #f3f4f6',
                                                        backgroundColor: isFusion ? '#f8fafc' : 'transparent',
                                                        fontWeight: isFusion ? 600 : 400
                                                    }}>
                                                        <td style={tdStyle}>
                                                            {isFusion && <i className="fas fa-star" style={{ color: '#f59e0b', marginRight: '4px', fontSize: '0.7rem' }}></i>}
                                                            {agentNames[key]}
                                                        </td>
                                                        <td style={{ ...tdStyle, color: scoreColor, fontWeight: 600 }}>
                                                            {agent.score > 0 ? '+' : ''}{agent.score.toFixed(1)}
                                                        </td>
                                                        <td style={{ ...tdStyle, color: dirColor, fontSize: '1.1rem' }}>
                                                            {dirArrow}
                                                        </td>
                                                        <td style={{ ...tdStyle, color: actualColor, fontSize: '1.1rem' }}>
                                                            {actualArrow}
                                                        </td>
                                                        <td style={tdStyle}>
                                                            {agent.matched ? (
                                                                <span style={{
                                                                    display: 'inline-flex', alignItems: 'center', gap: '3px',
                                                                    color: '#10b981', fontWeight: 600
                                                                }}>
                                                                    <i className="fas fa-check-circle"></i> 正确
                                                                </span>
                                                            ) : (
                                                                <span style={{
                                                                    display: 'inline-flex', alignItems: 'center', gap: '3px',
                                                                    color: '#ef4444', fontWeight: 600
                                                                }}>
                                                                    <i className="fas fa-times-circle"></i> 错误
                                                                </span>
                                                            )}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            {/* Card B: 逆势波动验证 — 仅预测正确时展示 */}
                            {adverse_excursion && (
                                <div className={styles.dataCard}>
                                    <div className={styles.cardHeader}>
                                        <i className="fas fa-shield-alt me-2"></i> 逆势波动验证
                                    </div>
                                    <div style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: '12px' }}>
                                        预测方向正确时，检查15m K线是否出现逆向偏移（反向突破阈值即记录）
                                    </div>
                                    <div style={{ marginBottom: '12px' }}>
                                        <div style={infoRowStyle}>
                                            <span style={{ color: '#6b7280' }}>偏差阈值:</span>
                                            <span style={{ fontWeight: 600, color: '#f59e0b' }}>
                                                {(adverse_excursion.threshold * 100).toFixed(1)}%
                                            </span>
                                            <span style={{ fontSize: '0.7rem', color: '#9ca3af' }}>（逆向偏移超过此比例即记录）</span>
                                        </div>
                                        <div style={infoRowStyle}>
                                            <span style={{ color: '#6b7280' }}>基准价格:</span>
                                            <span style={{ fontWeight: 600 }}>{formatPrice(adverse_excursion.baseline_price)}</span>
                                        </div>
                                        <div style={infoRowStyle}>
                                            <span style={{ color: '#6b7280' }}>验证窗口:</span>
                                            <span style={{ fontWeight: 600 }}>
                                                首个{adverse_excursion.timeframe}周期内 {adverse_excursion.candles_checked} 根15m K线
                                            </span>
                                        </div>
                                    </div>

                                    {/* Big Result Indicator */}
                                    <div style={{
                                        padding: '14px 16px',
                                        borderRadius: '8px',
                                        marginBottom: '14px',
                                        backgroundColor: adverse_excursion.is_clean ? '#ecfdf5' : '#fef2f2',
                                        border: `1px solid ${adverse_excursion.is_clean ? '#a7f3d0' : '#fecaca'}`,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '10px'
                                    }}>
                                        <i className={`fas fa-${adverse_excursion.is_clean ? 'check' : 'exclamation'}-circle`}
                                            style={{ fontSize: '1.5rem', color: adverse_excursion.is_clean ? '#10b981' : '#f59e0b' }}></i>
                                        <div>
                                            <div style={{
                                                fontWeight: 700,
                                                fontSize: '0.95rem',
                                                color: adverse_excursion.is_clean ? '#059669' : '#dc2626'
                                            }}>
                                                走势{adverse_excursion.is_clean ? '干净' : '存在逆向偏移'} {adverse_excursion.is_clean ? '✓' : '✗'}
                                            </div>
                                            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>
                                                {adverse_excursion.is_clean
                                                    ? '所有15m收盘价均未逆向突破基准价'
                                                    : `发现 ${adverse_excursion.violations.length} 次逆向偏移`}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Violations Table */}
                                    {adverse_excursion.violations.length > 0 && (
                                        <div>
                                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
                                                <thead>
                                                    <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                                                        <th style={thStyle}>#</th>
                                                        <th style={thStyle}>收盘价</th>
                                                        <th style={thStyle}>逆向偏离</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {adverse_excursion.violations.map((v) => (
                                                        <tr key={v.index} style={{ borderBottom: '1px solid #f3f4f6' }}>
                                                            <td style={tdStyle}>{v.index + 1}</td>
                                                            <td style={tdStyle}>{formatPrice(v.close)}</td>
                                                            <td style={{ ...tdStyle, color: '#ef4444', fontWeight: 600 }}>
                                                                {v.deviation_pct > 0 ? '+' : ''}{v.deviation_pct.toFixed(2)}%
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                            <div style={{
                                                fontSize: '0.7rem',
                                                color: '#9ca3af',
                                                marginTop: '6px',
                                                fontStyle: 'italic'
                                            }}>
                                                逆向偏离 = 该K线收盘价与基准价的差值越过阈值，代表方向性预测受到了反向干扰
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Chart Container */}
                    <div className={styles.chartContainer}>
                        <div className={styles.chartTitle}>分析时间点后的实际K线走势 ({timeframe}周期)</div>
                        <div className={styles.chartImageWrapper}>
                            {future_kline_chart_base64 ? (
                                <img 
                                    src={`data:image/png;base64,${future_kline_chart_base64}`} 
                                    alt="Future Kline Verification" 
                                    className={styles.chartImage}
                                />
                            ) : (
                                <div className={styles.chartPlaceholder}>
                                    <div className="text-center">
                                        <p>暂无回测数据</p>
                                        <small className="text-muted">仅在选择"到指定时间为止的N根K线"模式并设置了未来K线数量时可用</small>
                                    </div>
                                </div>
                            )}
                            <div className={styles.chartCaption}>展示分析时间点之后实际发生的市场走势，用于验证AI决策的准确性（非预测生成）</div>
                        </div>
                    </div>

                    {/* 
                        15m Chart Container (New) 
                        User Requirement (2025-01-20): Always show 36 candles of 15m future data for short-term verification.
                    */}
                    {future_15m_chart_base64 && (
                        <div className={styles.chartContainer} style={{ marginTop: '1.5rem' }}>
                            <div className={styles.chartTitle}>分析时间点后的15分钟K线走势 (36根)</div>
                            <div className={styles.chartImageWrapper}>
                                <img 
                                    src={`data:image/png;base64,${future_15m_chart_base64}`} 
                                    alt="Future 15m Kline Verification" 
                                    className={styles.chartImage}
                                />
                                <div className={styles.chartCaption}>展示分析时间点之后15分钟级别的实际走势，用于短线验证</div>
                            </div>
                        </div>
                    )}

                    {/* Table Container */}
                    {future_kline_data && future_kline_data.length > 0 && (
                        <div className={styles.tableContainer}>
                            <div className={styles.tableTitle}>实际行情数据详情</div>
                            <div className="overflow-x-auto">
                                <table className={styles.table}>
                                    <thead>
                                        <tr>
                                            <th>时间</th>
                                            <th>开盘价</th>
                                            <th>最高价</th>
                                            <th>最低价</th>
                                            <th>收盘价</th>
                                            <th>振幅</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {future_kline_data.map((row: FutureKlineDataRow, idx: number) => {
                                            const open = Number(row.open);
                                            const high = Number(row.high);
                                            const low = Number(row.low);
                                            const amplitude = open ? ((high - low) / open * 100).toFixed(2) : '0.00';
                                            
                                            return (
                                                <tr key={idx}>
                                                    <td>{row.datetime || row.date}</td>
                                                    <td>{formatPrice(open)}</td>
                                                    <td className={styles.textSuccess}>{formatPrice(high)}</td>
                                                    <td className={styles.textDanger}>{formatPrice(low)}</td>
                                                    <td>{formatPrice(Number(row.close))}</td>
                                                    <td>{amplitude}%</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}
