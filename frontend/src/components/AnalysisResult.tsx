import { useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import ResultHeader from './ResultHeader';
import Footer from './Footer';
import SummaryPanel from './SummaryPanel';
import DecisionPanel from './DecisionPanel';
import FutureKlinePanel from './FutureKlinePanel';
import IndicatorPanel from './IndicatorPanel';
import PatternPanel from './PatternPanel';
import TrendPanel from './TrendPanel';
import styles from './AnalysisResult.module.css';

export default function AnalysisResult() {
    const { analysisResult } = useAppStore();
    const history_chart_base64 = analysisResult?.history_chart_base64;

    useEffect(() => {
        // 主题检测 (复刻 output.html 的 head script)
        const theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', theme);
    }, []);

    if (!analysisResult) return null;

    return (
        <div className={styles.outputPageContainer}>
            <main className={styles.mainContainer}>
                {/* 头部区域 */}
                <ResultHeader />

                {/* 结果展示区域 */}
                <section className={styles.resultsSection}>
                    {/* 分析摘要、最终决策 */}
                    <div className={styles.panelGroup}>
                        <SummaryPanel />
                        <DecisionPanel />
                    </div>

                    {/* 未来K线预测面板 */}
                    <FutureKlinePanel />

                    {/* 技术指标面板 */}
                    <IndicatorPanel />

                    {/* 模式识别面板 */}
                    <PatternPanel />

                    {/* 趋势分析面板 */}
                    <TrendPanel />
                </section>

                {/* 历史K线走势图（底部小尺寸） */}
                {history_chart_base64 && (
                    <section className={styles.resultsSection} style={{ marginTop: '1rem' }}>
                        <img
                            src={`data:image/png;base64,${history_chart_base64}`}
                            alt="历史K线走势"
                            style={{
                                maxWidth: '780px',
                                width: '100%',
                                borderRadius: '6px',
                                border: '1px solid #374151',
                                display: 'block',
                                margin: '0 auto'
                            }}
                        />
                    </section>
                )}

                <Footer />
            </main>
        </div>
    );
}
