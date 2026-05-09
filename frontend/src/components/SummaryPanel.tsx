import { useAppStore } from '../store/useAppStore';
import styles from './SummaryPanel.module.css';

export default function SummaryPanel() {
  const { analysisResult } = useAppStore();
  if (!analysisResult) return null;

  const { 
    data_length,
    timeframe,
    asset_name,
    multi_timeframe_mode,
    timeframes,
    fusion_result
  } = analysisResult;

  const directionLabel = fusion_result?.direction === 'long' ? '做多'
    : fusion_result?.direction === 'short' ? '做空'
    : '持有/观望';

  const scoreColor = (fusion_result?.score ?? 0) >= 0.35 ? '#10b981'
    : (fusion_result?.score ?? 0) <= -0.35 ? '#ef4444'
    : '#6b7280';

  return (
    <div className={styles.panel}>
      <h4 className={styles.panelTitle}>
        <i className="fas fa-chart-pie"></i> 分析摘要
      </h4>

      <div className={styles.summaryGrid}>
        <div className={styles.summaryCard}>
          <div className={styles.cardNumber}>{data_length || '-'}</div>
          <div className={styles.cardLabel}>数据点</div>
        </div>
        <div className={styles.summaryCard}>
          <div className={styles.cardNumber}>
            {multi_timeframe_mode && timeframes ? timeframes.join('+') : (timeframe || '-')}
          </div>
          <div className={styles.cardLabel}>时间框架</div>
        </div>
        <div className={styles.summaryCard}>
          <div className={styles.cardNumber}>{asset_name || '-'}</div>
          <div className={styles.cardLabel}>资产</div>
        </div>
      </div>

      {fusion_result && (
        <div className={styles.fusionPanel}>
          <div className={styles.fusionDirection} style={{ color: scoreColor }}>
            <span style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
              {directionLabel}
            </span>
            <span style={{ marginLeft: '0.5rem', fontSize: '0.9rem', color: '#9ca3af' }}>
              score: {fusion_result.score?.toFixed(3)}
            </span>
          </div>
          <div className={styles.fusionDetails}>
            <div className={styles.fusionItem}>
              <span>confidence</span>
              <span style={{ color: (fusion_result.confidence ?? 0) >= 0.52 ? '#10b981' : '#f59e0b' }}>
                {((fusion_result.confidence ?? 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className={styles.fusionItem}>
              <span>agreement</span>
              <span>{((fusion_result.agreement ?? 0) * 100).toFixed(0)}%</span>
            </div>
            <div className={styles.fusionItem}>
              <span>coverage</span>
              <span>{((fusion_result.coverage ?? 0) * 100).toFixed(0)}%</span>
            </div>
            {fusion_result.resonance && (
              <div className={styles.fusionItem}>
                <span>resonance</span>
                <span style={{ color: fusion_result.resonance.active ? '#10b981' : '#6b7280' }}>
                  {fusion_result.resonance.active
                    ? `${fusion_result.resonance.aligned_count} agents +${(fusion_result.resonance.bonus).toFixed(3)}`
                    : 'inactive'}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
