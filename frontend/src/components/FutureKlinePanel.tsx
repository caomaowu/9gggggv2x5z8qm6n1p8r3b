import { useAppStore } from '../store/useAppStore';
import styles from './FutureKlinePanel.module.css';

export default function FutureKlinePanel() {
    const { analysisResult } = useAppStore();
    if (!analysisResult) return null;

    const { future_kline_chart_base64, future_kline_data } = analysisResult;

    return (
        <section className={styles.section}>
            <div className={styles.panel}>
                <div className={styles.panelHeader}>
                    <h3 className={styles.panelTitle}>
                        <i className="fas fa-history"></i> 未来走势回测验证
                    </h3>
                </div>
                <div className={styles.panelBody}>
                    {/* 图表展示 */}
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

                    {/* 数据表格 */}
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
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {future_kline_data.map((row: any, idx: number) => (
                                            <tr key={idx}>
                                                <td>{row.datetime || row.date}</td>
                                                <td>{Number(row.open).toFixed(2)}</td>
                                                <td className={styles.textSuccess}>{Number(row.high).toFixed(2)}</td>
                                                <td className={styles.textDanger}>{Number(row.low).toFixed(2)}</td>
                                                <td>{Number(row.close).toFixed(2)}</td>
                                            </tr>
                                        ))}
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
