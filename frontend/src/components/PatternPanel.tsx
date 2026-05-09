import { useAppStore } from '../store/useAppStore';
import AutoBeautify from './AutoBeautify';
import styles from './PatternPanel.module.css';

export default function PatternPanel() {
  const { analysisResult } = useAppStore();
  if (!analysisResult) return null;

  const structure = analysisResult.structure_summary;
  if (!structure) {
    return (
      <div className={styles.panel}>
        <h3 className={styles.panelTitle}>
          <i className="fas fa-project-diagram"></i> 结构分析 Agent
        </h3>
        <div className={styles.emptyState}>暂无结构分析数据</div>
      </div>
    );
  }

  const scoreColor = structure.movement_score >= 0.3 ? '#10b981'
    : structure.movement_score <= -0.3 ? '#ef4444'
    : '#6b7280';

  return (
    <div className={styles.panel}>
      <h3 className={styles.panelTitle}>
        <i className="fas fa-project-diagram"></i> 结构分析 Agent
        <span style={{ float: 'right', fontSize: '0.9rem', color: scoreColor }}>
          score: {structure.movement_score?.toFixed(2)}
          <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: '#9ca3af' }}>
            conf: {((structure.movement_confidence ?? 0) * 100).toFixed(0)}%
          </span>
        </span>
      </h3>

      <div className={styles.grid}>
        <div className={styles.item}>
          <span className={styles.label}>市场状态</span>
          <span className={`${styles.badge} ${styles[`badge_${structure.regime}`] || ''}`}>{structure.regime}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.label}>最近突破</span>
          <span className={`${styles.badge} ${styles[`badge_${structure.last_break}`] || ''}`}>{structure.last_break}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.label}>结构质量</span>
          <span className={`${styles.badge} ${styles[`badge_${structure.quality}`] || ''}`}>{structure.quality}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.label}>形态</span>
          <span className={`${styles.badge} ${styles[`badge_${structure.pattern}`] || ''}`}>{structure.pattern}</span>
        </div>
      </div>

      {structure.volume_action && (
        <div className={styles.section}>
          <strong>成交量特征</strong>
          <AutoBeautify content={structure.volume_action} />
        </div>
      )}

      {structure.candle_reaction && (
        <div className={styles.section}>
          <strong>K线反应</strong>
          <AutoBeautify content={structure.candle_reaction} />
        </div>
      )}

      {structure.next_focus && (
        <div className={styles.section} style={{ color: '#6b7280', fontSize: '0.85rem' }}>
          <strong>下轮关注</strong>: {structure.next_focus}
        </div>
      )}
    </div>
  );
}
