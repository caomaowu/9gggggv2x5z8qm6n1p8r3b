import { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { getHistoryList } from '../api/analyze';
import type { HistoryItem } from '../api/analyze';
import styles from './HistoryPanel.module.css';

export default function HistoryPanel() {
    const { setLatestResultId } = useAppStore();
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);

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
    }, []);

    const handleSelectHistory = (resultId: string) => {
        if (confirm(`Load analysis result ${resultId}? Current unsaved data will be lost.`)) {
            // This will trigger the restoration logic in App.tsx
            // because App.tsx listens for changes in latestResultId
            // However, we need to ensure analysisResult is cleared first or handle the transition
            // Actually, setting latestResultId and reloading page might be safer/cleaner
            // to trigger the full restore flow we built
            
            setLatestResultId(resultId);
            window.location.reload(); 
        }
    };

    return (
        <div className={styles.historyPanel}>
            <div className={styles.historyTitle}>
                <span>
                    <i className="fas fa-history"></i> Recent Analysis
                </span>
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
