import { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { getHistoryList } from '../api/analyze';
import { clearHistoryData } from '../api/system';
import type { HistoryItem } from '../api/analyze';
import styles from './HistoryPanel.module.css';

export default function HistoryPanel() {
    const { setLatestResultId, historyRefreshTrigger, autoFocusResult, setAutoFocusResult } = useAppStore();
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
        const url = `/?id=${resultId}`;
        if (autoFocusResult) {
            // Focus: Open in new tab and switch to it
            window.open(url, '_blank');
        } else {
            // No Focus: Open in background tab (or attempt to)
            // Note: Browsers block programmatic opening in background for security/UX.
            // Best effort: Open in new window/tab, but since we can't easily force "background" 
            // without extension permissions, we might just open it. 
            // HOWEVER, the user requirement is "don't jump to that page".
            // A common trick is window.open then window.focus(), but that often fails.
            // Alternatively, user might mean "Open in new tab but keep me here".
            // "Ctrl+Click" behavior.
            
            // Let's try the standard approach. If browser forces focus, we can't do much.
            // But we can try to refocus current window.
            const newWindow = window.open(url, '_blank');
            if (newWindow) {
                // Attempt to blur new window and focus current
                // This is often blocked by browsers but it's the standard attempt
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <button 
                        className={styles.refreshBtn} 
                        onClick={() => setAutoFocusResult(!autoFocusResult)}
                        title={autoFocusResult ? "点击切换：后台打开新页面" : "点击切换：直接跳转新页面"}
                        style={{ color: autoFocusResult ? '#2563eb' : '#9ca3af', fontSize: '0.9em', marginRight: '5px' }}
                    >
                        <i className={`fas ${autoFocusResult ? 'fa-external-link-alt' : 'fa-columns'}`}></i>
                    </button>
                    <button onClick={fetchHistory} className={styles.refreshBtn} title="Refresh list">
                        <i className={`fas fa-sync-alt ${isLoading ? 'fa-spin' : ''}`}></i>
                    </button>
                </div>
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
