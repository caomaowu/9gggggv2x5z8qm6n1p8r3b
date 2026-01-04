import { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { getHistoryList } from '../api/analyze';
import { clearHistoryData } from '../api/system';
import type { HistoryItem } from '../api/analyze';
import styles from './HistoryPanel.module.css';

export default function HistoryPanel() {
    const { setLatestResultId, historyRefreshTrigger } = useAppStore();
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isCleaning, setIsCleaning] = useState(false);

    const fetchHistory = async () => {
        setIsLoading(true);
        try {
            const data = await getHistoryList(12);
            setHistory(data);
        } catch (error) {
            console.error("Failed to fetch history:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [historyRefreshTrigger]); // Refetch when trigger changes

    const handleSelectHistory = (resultId: string) => {
        // Open in new tab without confirmation
        window.open(`/?id=${resultId}`, '_blank');
    };

    const handleClearHistory = async () => {
        if (!confirm('确定要清除历史记录列表吗？\n(注：这只会删除 data/history 下的索引文件，不会影响 exports 目录下的导出报告)')) {
            return;
        }

        setIsCleaning(true);
        try {
            // Call the system API to clear history data only
            const res = await clearHistoryData();
            // Also refresh the list (which should be empty now)
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
                <button onClick={fetchHistory} className={styles.refreshBtn} title="Refresh list">
                    <i className={`fas fa-sync-alt ${isLoading ? 'fa-spin' : ''}`}></i>
                </button>
            </div>
            
            {history.length === 0 && !isLoading ? (
                <div className={styles.emptyState}>
                    No history found. Run an analysis to see it here.
                </div>
            ) : (
                <div className={styles.historyList}>
                    {history.map((item) => (
                        <div 
                            key={item.result_id} 
                            className={styles.historyItem}
                            onClick={() => handleSelectHistory(item.result_id)}
                        >
                            <div className={styles.itemHeader}>
                                <span className={styles.itemId}>{item.result_id}</span>
                            </div>
                            <div className={styles.itemDate}>
                                {item.created_at}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
