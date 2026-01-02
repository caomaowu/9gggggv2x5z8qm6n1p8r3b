import styles from './HomeHeader.module.css';

export default function HomeHeader() {
    return (
        <section className={styles.heroSection}>
            <div className={styles.container}>
                <div className={styles.logoWrapper}>
                    <img 
                        src="/assets/darklogo.png" 
                        alt="QuantAgent Logo" 
                        className={styles.logo}
                    />
                    <h1 className={styles.title}>QuantAgent</h1>
                </div>
                
                <div className={styles.subtitle}>
                    <span className={styles.subtitleHighlight}>Multi-Agent Trading System</span>
                </div>

                <p className={styles.description}>
                    Advanced multi-agent system combining technical indicators, pattern recognition, and trend analysis for comprehensive market insights.
                </p>

                <div className={styles.actions}>
                    <a className={styles.heroBtn} href="#analysis">
                        <span>Start Analysis</span>
                        <span className={styles.heroBtnIcon}>
                            <i className="fas fa-arrow-right"></i>
                        </span>
                    </a>
                </div>
            </div>
        </section>
    );
}
