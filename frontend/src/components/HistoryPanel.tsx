import { useState, useEffect, useMemo } from 'react';
import { useAppStore } from '../store/useAppStore';
import { getHistoryList } from '../api/analyze';
import { clearHistoryData } from '../api/system';
import type { HistoryItem } from '../api/analyze';
import styles from './HistoryPanel.module.css';

// 辅助函数：从 Result ID 解析信息
// Format: R-{ID}-{YYMMDD}-{HHMM}-{ASSET}-{TF}
// Example: R-A011-260109-1440-SOL-1H
const parseResultId = (resultId: string) => {
    const parts = resultId.split('-');
    if (parts.length >= 6) {
        return {
            asset: parts[parts.length - 2],
            timeframe: parts[parts.length - 1],
            timestamp: parts[2] + '-' + parts[3] // 简单的时间戳标识
        };
    }
    return { asset: 'Unknown', timeframe: 'Unknown', timestamp: '' };
};

export default function HistoryPanel() {
    const { historyRefreshTrigger, autoFocusResult, setAutoFocusResult } = useAppStore();
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isCleaning, setIsCleaning] = useState(false);

    // 筛选状态
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedAsset, setSelectedAsset] = useState('');
    const [selectedTimeframe, setSelectedTimeframe] = useState('');
    const [selectedDate, setSelectedDate] = useState('');

    const fetchHistory = async () => {
        setIsLoading(true);
        try {
            // 获取更多历史记录以供筛选，这里暂时设为 50
            const data = await getHistoryList(50);
            setHistory(data);
        } catch (error) {
            console.error("Failed to fetch history:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [historyRefreshTrigger]);

    // 处理数据：解析并添加元数据
    const enrichedHistory = useMemo(() => {
        return history.map(item => {
            const { asset, timeframe } = parseResultId(item.result_id);
            return {
                ...item,
                asset,
                timeframe,
                // 确保日期格式便于比较 (YYYY-MM-DD)
                dateStr: item.date ? item.date.split(' ')[0] : '' 
            };
        });
    }, [history]);

    // 提取唯一的选项供下拉框使用
    const uniqueAssets = useMemo(() => {
        const assets = new Set(enrichedHistory.map(item => item.asset));
        return Array.from(assets).sort();
    }, [enrichedHistory]);

    const uniqueTimeframes = useMemo(() => {
        const tfs = new Set(enrichedHistory.map(item => item.timeframe));
        return Array.from(tfs).sort();
    }, [enrichedHistory]);

    // 过滤逻辑
    const filteredHistory = useMemo(() => {
        return enrichedHistory.filter(item => {
            // 1. 搜索词 (模糊匹配 ID 或 Asset)
            const searchLower = searchTerm.toLowerCase();
            const matchesSearch = 
                item.result_id.toLowerCase().includes(searchLower) || 
                item.asset.toLowerCase().includes(searchLower);

            // 2. 资产筛选
            const matchesAsset = selectedAsset ? item.asset === selectedAsset : true;

            // 3. 时间周期筛选
            const matchesTimeframe = selectedTimeframe ? item.timeframe === selectedTimeframe : true;

            // 4. 日期筛选
            const matchesDate = selectedDate ? item.dateStr === selectedDate : true;

            return matchesSearch && matchesAsset && matchesTimeframe && matchesDate;
        });
    }, [enrichedHistory, searchTerm, selectedAsset, selectedTimeframe, selectedDate]);

    const handleSelectHistory = (resultId: string) => {
        const url = `/?id=${resultId}`;
        if (autoFocusResult) {
            window.open(url, '_blank');
        } else {
            const newWindow = window.open(url, '_blank');
            if (newWindow) {
                newWindow.blur();
                window.focus();
            }
        }
    };

    const handleClearHistory = async () => {
        if (!confirm('确定要清除历史记录列表吗？\n(注：这只会删除 data/history 下的索引文件，不会影响 exports 目录下的导出报告)')) {
            return;
        }

        setIsCleaning(true);
        try {
            const res = await clearHistoryData();
            await fetchHistory();
            alert(res.message || '历史记录已清除');
        } catch (error) {
            console.error("Failed to clear history:", error);
            alert("清除历史记录失败，请检查控制台");
        } finally {
            setIsCleaning(false);
        }
    };

    return (
        <div className={styles.historyPanel}>
            <div className={styles.historyTitle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span>
                        <i className="fas fa-history"></i> Recent Analysis
                    </span>
                    {history.length > 0 && (
                        <button 
                            onClick={handleClearHistory} 
                            disabled={isCleaning}
                            className={styles.refreshBtn} 
                            style={{ color: '#ef4444', fontSize: '0.9em' }}
                            title="Clear all history"
                        >
                            {isCleaning ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-trash-alt"></i>}
                        </button>
                    )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <button 
                        className={styles.refreshBtn} 
                        onClick={() => setAutoFocusResult(!autoFocusResult)}
                        title={autoFocusResult ? "点击切换：后台打开新页面" : "点击切换：直接跳转新页面"}
                        style={{ color: autoFocusResult ? '#2563eb' : '#9ca3af', fontSize: '0.9em', marginRight: '5px' }}
                    >
                        <i className={`fas ${autoFocusResult ? 'fa-external-link-alt' : 'fa-columns'}`}></i>
                    </button>
                    <button onClick={fetchHistory} disabled={isLoading} className={styles.refreshBtn}>
                        <i className={`fas fa-sync-alt ${isLoading ? 'fa-spin' : ''}`}></i>
                    </button>
                </div>
            </div>

            {/* 筛选与搜索工具栏 */}
            <div className={styles.filterContainer}>
                <div className={styles.searchBox}>
                    <input 
                        type="text" 
                        placeholder="🔍 搜索编号或币种 (模糊搜索)..." 
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className={styles.searchInput}
                    />
                </div>
                <div className={styles.filterGroup}>
                    <select 
                        value={selectedAsset} 
                        onChange={(e) => setSelectedAsset(e.target.value)}
                        className={styles.filterSelect}
                    >
                        <option value="">所有币种</option>
                        {uniqueAssets.map(asset => (
                            <option key={asset} value={asset}>{asset}</option>
                        ))}
                    </select>

                    <select 
                        value={selectedTimeframe} 
                        onChange={(e) => setSelectedTimeframe(e.target.value)}
                        className={styles.filterSelect}
                    >
                        <option value="">所有周期</option>
                        {uniqueTimeframes.map(tf => (
                            <option key={tf} value={tf}>{tf}</option>
                        ))}
                    </select>

                    <input 
                        type="date" 
                        value={selectedDate}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        className={styles.filterDate}
                        title="按日期筛选"
                    />
                    
                    {(searchTerm || selectedAsset || selectedTimeframe || selectedDate) && (
                        <button 
                            onClick={() => {
                                setSearchTerm('');
                                setSelectedAsset('');
                                setSelectedTimeframe('');
                                setSelectedDate('');
                            }}
                            className={styles.refreshBtn}
                            style={{ color: '#6b7280' }}
                            title="重置筛选"
                        >
                            <i className="fas fa-times"></i> 重置
                        </button>
                    )}
                </div>
            </div>

            <div className={styles.historyList}>
                {filteredHistory.length === 0 ? (
                    <div className={styles.emptyState}>
                        {history.length === 0 ? "暂无分析记录" : "未找到匹配的记录"}
                    </div>
                ) : (
                    filteredHistory.map((item) => (
                        <div 
                            key={item.result_id} 
                            className={styles.historyItem}
                            onClick={() => handleSelectHistory(item.result_id)}
                        >
                            <div className={styles.itemHeader}>
                                <span className={styles.itemId}>{item.result_id}</span>
                            </div>
                            <div className={styles.itemDate}>
                                <i className="far fa-clock"></i> {item.date}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
