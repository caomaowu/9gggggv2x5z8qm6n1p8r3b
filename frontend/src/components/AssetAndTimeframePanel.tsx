import { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import styles from './AssetAndTimeframePanel.module.css';

// Asset metadata configuration (Icons, Styles)
// Keep this for priority/preset rendering
const ASSET_METADATA: Record<string, { icon: string, isFab?: boolean }> = {
  'BTC': { icon: 'fa-bitcoin' },
  'ETH': { icon: 'fa-ethereum', isFab: true },
  'SOL': { icon: 'fa-fire' },
  'BNB': { icon: 'fa-coins' },
  'XRP': { icon: 'fa-water' },
  'ADA': { icon: 'fa-diamond' },
};

const DEFAULT_ASSET_ICON = 'fa-star';

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
      assets, addAssets, removeAssets, assetIcons,
      selectedTimeframe, setTimeframe
  } = useAppStore();
  
  const [isManagementMode, setManagementMode] = useState(false);
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [customInputVal, setCustomInputVal] = useState('');
  const [selectedToDelete, setSelectedToDelete] = useState<Set<string>>(new Set());

  // Reset selection when exiting management mode
  useEffect(() => {
    if (!isManagementMode) {
        setSelectedToDelete(new Set());
    }
  }, [isManagementMode]);

  const handleCustomSubmit = () => {
    if (customInputVal.trim()) {
        // Split by comma, semicolon (both English and Chinese)
        const newAssets = customInputVal
            .split(/[;,，；]/)
            .map(s => s.trim().toUpperCase())
            .filter(s => s.length > 0);

        if (newAssets.length > 0) {
            addAssets(newAssets);
            // Auto select the first one if no asset is selected, or just select the first new one
            setAsset(newAssets[0]);
            setCustomInputVal('');
            setShowCustomInput(false);
        }
    }
  };

  const toggleSelection = (symbol: string) => {
    const newSelection = new Set(selectedToDelete);
    if (newSelection.has(symbol)) {
        newSelection.delete(symbol);
    } else {
        newSelection.add(symbol);
    }
    setSelectedToDelete(newSelection);
  };

  const handleBatchDelete = () => {
    if (selectedToDelete.size > 0) {
        removeAssets(Array.from(selectedToDelete));
        setSelectedToDelete(new Set());
    }
  };

  const getAssetIcon = (symbol: string) => {
      // 1. Priority: Preset Metadata (e.g. BTC, ETH specific branding)
      if (ASSET_METADATA[symbol]) {
          return { 
              icon: ASSET_METADATA[symbol].icon, 
              iconClass: ASSET_METADATA[symbol].isFab ? 'fab' : 'fas' 
          };
      }
      
      // 2. Priority: Custom assigned random icon from Store
      if (assetIcons[symbol]) {
          return {
              icon: assetIcons[symbol],
              iconClass: 'fas' // Random icons are all solid 'fas'
          };
      }

      // 3. Fallback: Default Star
      return {
          icon: DEFAULT_ASSET_ICON,
          iconClass: 'fas'
      };
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
                     {isManagementMode && selectedToDelete.size > 0 && (
                        <button 
                            className={`${styles.btn} ${styles.btnDanger}`}
                            onClick={handleBatchDelete}
                            style={{ marginLeft: '1rem' }}
                        >
                            <i className="fas fa-trash-alt me-1"></i> 删除选中 ({selectedToDelete.size})
                        </button>
                    )}
                </div>
                <small style={{ color: '#6B7280', fontSize: '0.9rem' }}>
                    <i className="fas fa-info-circle"></i>
                    {isManagementMode 
                        ? '点击卡片选中，然后点击“删除选中”按钮进行批量删除'
                        : '开启管理模式可批量删除币种'}
                </small>
            </div>
        </div>

        {/* Asset Selection */}
        <div className={styles.formGroup}>
            <label className={styles.formLabel}>
                <i className="fas fa-coins"></i> Asset
            </label>
            <div className={styles.assetButtonGrid}>
                {assets.map(symbol => {
                    const isSelectedToDelete = selectedToDelete.has(symbol);
                    const { icon, iconClass } = getAssetIcon(symbol);
                    
                    return (
                        <div key={symbol} className="relative inline-block">
                             <button 
                                type="button" 
                                className={`
                                    ${styles.assetBtn} 
                                    ${(!isManagementMode && selectedAsset === symbol) ? styles.active : ''}
                                    ${(isManagementMode && isSelectedToDelete) ? styles.deleteActive : ''}
                                `}
                                onClick={() => isManagementMode ? toggleSelection(symbol) : setAsset(symbol)}
                            >
                                <i className={`${iconClass} ${icon}`}></i> {symbol}
                                {isManagementMode && isSelectedToDelete && (
                                    <div style={{ position: 'absolute', top: 5, right: 5, color: '#DC2626' }}>
                                        <i className="fas fa-check-circle"></i>
                                    </div>
                                )}
                            </button>
                        </div>
                    );
                })}

                {showCustomInput ? (
                    <div className={styles.assetBtn} style={{ width: 'auto', minWidth: '200px', cursor: 'default' }}>
                        <div className={styles.inputGroup}>
                            <input 
                                type="text" 
                                className={styles.formControl}
                                placeholder="Symbol (e.g. DOGE, SHIB)"
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
                        style={isManagementMode ? { display: 'none' } : {}}
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
