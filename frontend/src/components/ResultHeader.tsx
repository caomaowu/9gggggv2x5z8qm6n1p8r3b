import { useAppStore } from '../store/useAppStore';
import styles from './ResultHeader.module.css';

export default function ResultHeader() {
    const { analysisResult, setAnalysisResult, setLatestResultId } = useAppStore();

    const handleBack = (e: React.MouseEvent) => {
        e.preventDefault();
        // 清除状态，返回表单页
        setAnalysisResult(null);
        setLatestResultId(null);
    };

    return (
        <header className={styles.header}>
            <div className="text-center">
                <div className={styles.logoContainer}>
                    <img src="/assets/darklogo.png" alt="QuantAgent Logo" loading="lazy" />
                    <span className={styles.titleText}>QuantAgent</span>
                </div>
                <div className="text-center">
                    <span className={styles.titleHighlight}>Multi-Agent Trading System</span>
                </div>
                {/* Result ID Display */}
                {analysisResult?.result_id && (
                    <div className={styles.resultIdBadge}>
                        <i className="fas fa-fingerprint"></i> ID: {analysisResult.result_id}
                    </div>
                )}
                {/* Analysis Time Display */}
                {analysisResult?.analysis_time_display && (
                    <div style={{ fontSize: '0.85rem', color: '#6B7280', marginTop: '4px' }}>
                        <i className="fas fa-clock me-1"></i> 
                        <span style={{ fontWeight: 500 }}>{analysisResult.analysis_time_display}</span>
                    </div>
                )}
                <div className={styles.backButton}>
                    <a href="/" className={styles.backBtn} onClick={handleBack}>
                        <i className="fas fa-arrow-left"></i>&nbsp;&nbsp; 返回分析页面
                    </a>
                </div>
            </div>
        </header>
    );
}
