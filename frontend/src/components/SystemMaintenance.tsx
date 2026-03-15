import { useState } from 'react';
import { clearSystemCache, clearExportsFiles } from '../api/system';
import styles from './ConfigPanel.module.css';

export default function SystemMaintenance() {
    const [isCleaning, setIsCleaning] = useState(false);
    const [isCleaningExports, setIsCleaningExports] = useState(false);

    const handleClearCache = async () => {
        if (!confirm('确定要清理所有临时图表和缓存文件吗？')) {
            return;
        }
        
        setIsCleaning(true);
        try {
            const res = await clearSystemCache();
            alert(`${res.message}`);
        } catch (error) {
            console.error("Failed to clear cache:", error);
            alert("清理失败，请检查控制台");
        } finally {
            setIsCleaning(false);
        }
    };

    const handleClearExports = async () => {
        if (!confirm('警告：这将永久删除 exports 文件夹下的所有分析报告和文件！\n\n确定要继续吗？')) {
            return;
        }
        
        setIsCleaningExports(true);
        try {
            const res = await clearExportsFiles();
            alert(`${res.message}`);
        } catch (error) {
            console.error("Failed to clear exports:", error);
            alert("清理失败，请检查控制台");
        } finally {
            setIsCleaningExports(false);
        }
    };

    return (
        <div className="flex items-center justify-center gap-4 mt-4 text-xs">
            <button 
                type="button" 
                onClick={handleClearCache}
                disabled={isCleaning}
                className="text-gray-500 hover:text-red-600 transition-colors flex items-center gap-1"
                title="Clean Temp Files"
            >
                {isCleaning ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-trash-alt"></i>}
                <span>Clean Cache</span>
            </button>
            <span className="text-gray-300">|</span>
            <button 
                type="button" 
                onClick={handleClearExports}
                disabled={isCleaningExports}
                className="text-gray-500 hover:text-red-600 transition-colors flex items-center gap-1"
                title="Clean Exports Files"
            >
                {isCleaningExports ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-folder-minus"></i>}
                <span>Clean Exports</span>
            </button>
        </div>
    );
}
