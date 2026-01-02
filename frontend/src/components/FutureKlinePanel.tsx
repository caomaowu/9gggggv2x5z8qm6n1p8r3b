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
                        <i className="fas fa-chart-line"></i> 未来价格预测
                    </h3>
                </div>
                <div className={styles.panelBody}>
                    {/* 图表展示 */}
                    <div className={styles.chartContainer}>
                        <div className={styles.chartTitle}>未来K线预测图</div>
                        <div className={styles.chartImageWrapper}>
                            {future_kline_chart_base64 ? (
                                <img 
                                    src={`data:image/png;base64,${future_kline_chart_base64}`} 
                                    alt="Future Kline Prediction" 
                                    className={styles.chartImage}
                                />
                            ) : (
                                <div className={styles.chartPlaceholder}>暂无预测图表数据</div>
                            )}
                            <div className={styles.chartCaption}>基于多重模型集成的未来价格走势预测（仅供参考）</div>
                        </div>
                    </div>

                    {/* 数据表格 */}
                    {future_kline_data && future_kline_data.length > 0 && (
                        <div className={styles.tableContainer}>
                            <div className={styles.tableTitle}>预测数据详情</div>
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
