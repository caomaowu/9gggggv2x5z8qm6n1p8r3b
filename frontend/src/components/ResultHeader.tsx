import styles from './ResultHeader.module.css';

export default function ResultHeader() {
    return (
        <header className={styles.header}>
            <div className="text-center">
                <div className={styles.logoContainer}>
                    <img src="/assets/darklogo.png" alt="QuantAgent Logo" loading="lazy" />
                    <span className={styles.titleText}>QuantAgent</span>
                </div>
                <div className="text-center">
                    <span className={styles.titleHighlight}>Multi-Agent Trading System</span>
                </div>
                <div className={styles.backButton}>
                    {/* 使用 window.location.reload() 模拟返回并重置状态，或者调用 store 方法重置 */}
                    <a href="/" className={styles.backBtn} onClick={(e) => {
                        e.preventDefault();
                        window.location.reload();
                    }}>
                        <i className="fas fa-arrow-left"></i>&nbsp;&nbsp; 返回分析页面
                    </a>
                </div>
            </div>
        </header>
    );
}
