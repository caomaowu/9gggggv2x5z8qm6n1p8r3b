import { useAppStore } from '../store/useAppStore';
import type { FutureKlineDataRow } from '../types';
import styles from './FutureKlinePanel.module.css';

export default function FutureKlinePanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { 
        future_kline_chart_base64, 
        future_kline_data,
        latest_price,
        decision: singleDecision
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

    if (firstKline && latestVal) {
        const close = parseFloat(String(firstKline.close));
        firstTrendDiff = ((close - latestVal) / latestVal) * 100;
        
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
    
    if (secondKline && latestVal) {
        const close = parseFloat(String(secondKline.close));
        trendDiff = ((close - latestVal) / latestVal) * 100;
        
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
    
    if (thirdKline && latestVal) {
        const close = parseFloat(String(thirdKline.close));
        thirdTrendDiff = ((close - latestVal) / latestVal) * 100;
        
        if (isLong) {
            thirdTrendPassed = close > latestVal;
        } else if (isShort) {
            thirdTrendPassed = close < latestVal;
        }
    }

    // Helper for Pct Display
    const getPct = (target: number) => {
        if (!latestVal) return '';
        const pct = ((target - latestVal) / latestVal) * 100;
        return (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
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
                                        <div className={styles.priceValue}>{latestVal}</div>
                                        <span className={styles.statusPending}>基准点</span>
                                    </div>

                                    {/* Stop Loss */}
                                    <div className={styles.priceItem}>
                                        <div className={styles.priceLabel}>止损价格</div>
                                        <div className={`${styles.priceValue} ${styles.textDanger}`}>
                                            {!isNaN(slVal) ? slVal : '未设置'}
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
                                            {!isNaN(tpVal) ? tpVal : '未设置'}
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
                                            <span className={styles.priceNum}>{latestVal}</span>
                                        </div>
                                    </div>

                                     {/* Item 2: 1st Future Kline */}
                                     {firstKline ? (
                                        <div className={styles.trendItem}>
                                            <div className={styles.itemLabel}>
                                                <i className="fas fa-clock"></i> 未来第1根K线
                                            </div>
                                            <div className={styles.itemValue}>
                                                <div style={{textAlign: 'right', marginRight: '8px'}}>
                                                    <div className={styles.priceNum}>{Number(firstKline.close).toFixed(2)}</div>
                                                    <small style={{color: firstTrendDiff > 0 ? '#10B981' : '#EF4444', fontSize: '0.75rem'}}>
                                                        {firstTrendDiff > 0 ? '+' : ''}{firstTrendDiff.toFixed(2)}%
                                                    </small>
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
                                                <i className="fas fa-clock"></i> 未来第2根K线
                                            </div>
                                            <div className={styles.itemValue}>
                                                <div style={{textAlign: 'right', marginRight: '8px'}}>
                                                    <div className={styles.priceNum}>{Number(secondKline.close).toFixed(2)}</div>
                                                    <small style={{color: trendDiff > 0 ? '#10B981' : '#EF4444', fontSize: '0.75rem'}}>
                                                        {trendDiff > 0 ? '+' : ''}{trendDiff.toFixed(2)}%
                                                    </small>
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
                                                <i className="fas fa-clock"></i> 未来第3根K线
                                            </div>
                                            <div className={styles.itemValue}>
                                                <div style={{textAlign: 'right', marginRight: '8px'}}>
                                                    <div className={styles.priceNum}>{Number(thirdKline.close).toFixed(2)}</div>
                                                    <small style={{color: thirdTrendDiff > 0 ? '#10B981' : '#EF4444', fontSize: '0.75rem'}}>
                                                        {thirdTrendDiff > 0 ? '+' : ''}{thirdTrendDiff.toFixed(2)}%
                                                    </small>
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

                    {/* Chart Container */}
                    <div className={styles.chartContainer}>
                        <div className={styles.chartTitle}>分析时间点后的实际K线走势</div>
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
                                                    <td>{open.toFixed(2)}</td>
                                                    <td className={styles.textSuccess}>{high.toFixed(2)}</td>
                                                    <td className={styles.textDanger}>{low.toFixed(2)}</td>
                                                    <td>{Number(row.close).toFixed(2)}</td>
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
