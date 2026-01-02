import { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import styles from './AssetAndTimeframePanel.module.css';

const DEFAULT_ASSETS = [
  { symbol: 'BTC', icon: 'fa-bitcoin' },
  { symbol: 'ETH', icon: 'fa-ethereum', isFab: true },
  { symbol: 'SOL', icon: 'fa-fire' },
  { symbol: 'BNB', icon: 'fa-coins' },
  { symbol: 'XRP', icon: 'fa-water' },
  { symbol: 'ADA', icon: 'fa-diamond' },
];

const TIMEFRAMES = [
    { label: '1分钟', value: '1m' },
    { label: '15分钟', value: '15m' },
    { label: '1小时', value: '1h' },
    { label: '4小时', value: '4h' },
    { label: '1天', value: '1d' },
    { label: '1周', value: '1w' },
    { label: '1月', value: '1mo' },
];

export default function AssetAndTimeframePanel() {
  const { 
      selectedAsset, setAsset, 
      customAssets, addCustomAsset, removeCustomAsset,
      selectedTimeframe, setTimeframe
  } = useAppStore();
  
  const [isManagementMode, setManagementMode] = useState(false);
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [customInputVal, setCustomInputVal] = useState('');

  const handleCustomSubmit = () => {
    if (customInputVal.trim()) {
        addCustomAsset(customInputVal.trim().toUpperCase());
        setAsset(customInputVal.trim().toUpperCase());
        setCustomInputVal('');
        setShowCustomInput(false);
    }
  };

  return (
    <div className={styles.panel}>
        <h4 className={styles.panelTitle}>
            <i className="fas fa-database"></i> Data Selection
        </h4>
        
        {/* Asset Management Panel */}
        <div className={styles.assetManagementPanel}>
            <div className={styles.managementControls}>
                <div className={styles.batchControls}>
                    <div className={styles.checkboxWrapper}>
                        <input 
                            type="checkbox" 
                            id="managementMode" 
                            checked={isManagementMode}
                            onChange={(e) => setManagementMode(e.target.checked)} 
                        />
                        <label htmlFor="managementMode">管理模式</label>
                    </div>
                </div>
                <small style={{ color: '#6B7280', fontSize: '0.9rem' }}>
                    <i className="fas fa-info-circle"></i>
                    开启管理模式可批量删除自定义币种，鼠标悬停显示单个删除按钮
                </small>
            </div>
        </div>

        {/* Asset Selection */}
        <div className={styles.formGroup}>
            <label className={styles.formLabel}>
                <i className="fas fa-coins"></i> Asset
            </label>
            <div className={styles.assetButtonGrid}>
                {DEFAULT_ASSETS.map(asset => (
                    <button 
                        key={asset.symbol}
                        type="button" 
                        className={`${styles.assetBtn} ${selectedAsset === asset.symbol ? styles.active : ''}`}
                        onClick={() => setAsset(asset.symbol)}
                    >
                        <i className={`${asset.isFab ? 'fab' : 'fas'} ${asset.icon}`}></i> {asset.symbol}
                    </button>
                ))}
                
                {customAssets.map(symbol => (
                    <div key={symbol} className="relative inline-block">
                         {isManagementMode && (
                             <span 
                                className={styles.deleteBtn} 
                                onClick={(e) => { e.stopPropagation(); removeCustomAsset(symbol); }}
                             >×</span>
                         )}
                         <button 
                            type="button" 
                            className={`${styles.assetBtn} ${selectedAsset === symbol ? styles.active : ''}`}
                            onClick={() => setAsset(symbol)}
                        >
                            <i className="fas fa-star"></i> {symbol}
                        </button>
                    </div>
                ))}

                {showCustomInput ? (
                    <div className={styles.assetBtn} style={{ width: 'auto', minWidth: '200px', cursor: 'default' }}>
                        <div className={styles.inputGroup}>
                            <input 
                                type="text" 
                                className={styles.formControl}
                                placeholder="Symbol (e.g. DOGE)"
                                value={customInputVal}
                                onChange={(e) => setCustomInputVal(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
                                autoFocus
                            />
                            <button className={`${styles.btn} ${styles.btnPrimary}`} onClick={handleCustomSubmit} style={{ minWidth: 'auto', padding: '0.5rem' }}>OK</button>
                            <button className={`${styles.btn} ${styles.btnOutlineSecondary}`} onClick={() => setShowCustomInput(false)} style={{ minWidth: 'auto', padding: '0.5rem' }}>X</button>
                        </div>
                    </div>
                ) : (
                    <button 
                        type="button" 
                        className={`${styles.assetBtn} ${styles.customAssetBtn}`}
                        onClick={() => setShowCustomInput(true)}
                    >
                        <i className="fas fa-plus"></i> Custom
                    </button>
                )}
            </div>
        </div>

        {/* Timeframe Selection */}
        <div className={styles.formGroup}>
            <label className={styles.formLabel}>
                <i className="far fa-clock"></i> Timeframe
            </label>
            <div className={styles.timeframeSelector}>
                {TIMEFRAMES.map(tf => (
                    <button 
                        key={tf.value}
                        type="button" 
                        className={`${styles.timeframeBtn} ${selectedTimeframe === tf.value ? styles.active : ''}`}
                        onClick={() => setTimeframe(tf.value)}
                    >
                        {tf.label}
                    </button>
                ))}
            </div>
        </div>
    </div>
  );
}
