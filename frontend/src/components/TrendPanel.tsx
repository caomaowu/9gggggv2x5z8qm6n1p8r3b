import { useAppStore } from '../store/useAppStore';
import AutoBeautify from './AutoBeautify';
import styles from './TrendPanel.module.css';

export default function TrendPanel() {
  const { analysisResult } = useAppStore();
  if (!analysisResult) return null;

  const mechanics = analysisResult.mechanics_summary;
  if (!mechanics) {
    return (
      <div className={styles.panel}>
        <h3 className={styles.panelTitle}>
          <i className="fas fa-cogs"></i> 机制分析 Agent
        </h3>
        <div className={styles.emptyState}>暂无机制分析数据</div>
      </div>
    );
  }

  const scoreColor = mechanics.movement_score >= 0.3 ? '#10b981'
    : mechanics.movement_score <= -0.3 ? '#ef4444'
    : '#6b7280';

  return (
    <div className={styles.panel}>
      <h3 className={styles.panelTitle}>
        <i className="fas fa-cogs"></i> 机制分析 Agent
        <span style={{ float: 'right', fontSize: '0.9rem', color: scoreColor }}>
          score: {mechanics.movement_score?.toFixed(2)}
          <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: '#9ca3af' }}>
            conf: {((mechanics.movement_confidence ?? 0) * 100).toFixed(0)}%
          </span>
        </span>
      </h3>

      <div className={styles.grid}>
        <div className={styles.item}>
          <span className={styles.label}>杠杆状态</span>
          <span className={`${styles.badge} ${styles[`badge_${mechanics.leverage_state}`] || ''}`}>{mechanics.leverage_state}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.label}>持仓拥挤</span>
          <span className={`${styles.badge} ${styles[`badge_${mechanics.crowding}`] || ''}`}>{mechanics.crowding}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.label}>风险等级</span>
          <span className={`${styles.badge} ${styles[`badge_${mechanics.risk_level}`] || ''}`}>{mechanics.risk_level}</span>
        </div>
      </div>

      {mechanics.open_interest_context && (
        <div className={styles.section}>
          <strong>OI / 资金费率</strong>
          <AutoBeautify content={mechanics.open_interest_context} />
        </div>
      )}

      {mechanics.anomaly_detail && mechanics.anomaly_detail !== '无明显异常' && (
        <div className={styles.section} style={{ borderLeft: '3px solid #ef4444', paddingLeft: '0.5rem' }}>
          <strong style={{ color: '#dc2626' }}>异常信号</strong>
          <AutoBeautify content={mechanics.anomaly_detail} />
        </div>
      )}

      {mechanics.next_focus && (
        <div className={styles.section} style={{ color: '#6b7280', fontSize: '0.85rem' }}>
          <strong>下轮关注</strong>: {mechanics.next_focus}
        </div>
      )}
    </div>
  );
}
