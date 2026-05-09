import { useAppStore } from '../store/useAppStore';
import AutoBeautify from './AutoBeautify';
import styles from './IndicatorPanel.module.css';

export default function IndicatorPanel() {
  const { analysisResult } = useAppStore();
  if (!analysisResult) return null;

  const indicator = analysisResult.indicator_summary;
  if (!indicator) {
    return (
      <div className={styles.panel}>
        <h3 className={styles.panelTitle}>
          <i className="fas fa-chart-line"></i> 指标分析 Agent
        </h3>
        <div className={styles.emptyState}>暂无指标分析数据</div>
      </div>
    );
  }

  const scoreColor = indicator.movement_score >= 0.3 ? '#10b981'
    : indicator.movement_score <= -0.3 ? '#ef4444'
    : '#6b7280';

  return (
    <div className={styles.panel}>
      <h3 className={styles.panelTitle}>
        <i className="fas fa-chart-line"></i> 指标分析 Agent
        <span style={{ float: 'right', fontSize: '0.9rem', color: scoreColor }}>
          score: {indicator.movement_score?.toFixed(2)}
          <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: '#9ca3af' }}>
            conf: {((indicator.movement_confidence ?? 0) * 100).toFixed(0)}%
          </span>
        </span>
      </h3>

      <div className={styles.grid}>
        <div className={styles.item}>
          <span className={styles.label}>波动扩张</span>
          <span className={`${styles.badge} ${styles[`badge_${indicator.expansion}`] || ''}`}>{indicator.expansion}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.label}>指标对齐</span>
          <span className={`${styles.badge} ${styles[`badge_${indicator.alignment}`] || ''}`}>{indicator.alignment}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.label}>噪音水平</span>
          <span className={`${styles.badge} ${styles[`badge_${indicator.noise}`] || ''}`}>{indicator.noise}</span>
        </div>
      </div>

      {indicator.momentum_detail && (
        <div className={styles.section}>
          <strong>动能分析</strong>
          <AutoBeautify content={indicator.momentum_detail} />
        </div>
      )}

      {indicator.conflict_detail && indicator.conflict_detail !== '无明显冲突' && (
        <div className={styles.section} style={{ borderLeft: '3px solid #f59e0b', paddingLeft: '0.5rem' }}>
          <strong style={{ color: '#d97706' }}>冲突</strong>
          <AutoBeautify content={indicator.conflict_detail} />
        </div>
      )}

      {indicator.next_focus && (
        <div className={styles.section} style={{ color: '#6b7280', fontSize: '0.85rem' }}>
          <strong>下轮关注</strong>: {indicator.next_focus}
        </div>
      )}
    </div>
  );
}
