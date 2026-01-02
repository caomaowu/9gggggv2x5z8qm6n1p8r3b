import { useEffect, useState } from 'react';
import styles from './Footer.module.css';

export default function Footer() {
    const [timeString, setTimeString] = useState('');

    useEffect(() => {
        // 设置初始分析时间 (如果有)
        // output.html 的逻辑是显示当前时间，并每秒更新
        // 但也有一个 id="analysis-time" 的 span，似乎既用于显示分析时间，也用于显示当前时间？
        // 仔细看 output.html 的 JS:
        // 1. DOMContentLoaded 时设置 analysis-time 为当前时间
        // 2. setInterval 每秒更新 analysis-time
        // 3. footer 文本: 分析时间: <span id="analysis-time"></span>
        
        // 实际上 "分析时间" 通常应该是静态的（结果生成时间），但在 output.html 的实现里它被做成了即时时钟。
        // 我们复刻这个行为。

        const updateTime = () => {
            setTimeString(new Date().toLocaleString('zh-CN'));
        };

        updateTime();
        const timer = setInterval(updateTime, 1000);

        return () => clearInterval(timer);
    }, []);

    return (
        <footer className={styles.pageFooter}>
            <div className="container mx-auto px-4">
                <p>
                    <i className="fas fa-robot"></i>
                    QuantAgent - AI驱动的量化交易分析系统 |
                    <small> 分析时间: <span id="analysis-time">{timeString}</span></small>
                </p>
            </div>
        </footer>
    );
}
