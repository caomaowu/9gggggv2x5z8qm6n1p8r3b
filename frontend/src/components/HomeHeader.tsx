import { useState } from 'react';
import styles from './HomeHeader.module.css';
import { useAuthStore } from '../store/useAuthStore';
import { AdminModal } from './Admin/AdminModal';

export default function HomeHeader() {
    const { logout, isAuthenticated } = useAuthStore();
    const [isAdminOpen, setIsAdminOpen] = useState(false);

    return (
        <section className={styles.heroSection}>
            <div className={styles.container}>
                <div className={styles.headerTop}>
                    <div className={styles.logoWrapper}>
                        <img 
                            src="/assets/darklogo.png" 
                            alt="QuantAgent Logo" 
                            className={styles.logo}
                        />
                        <h1 className={styles.title}>QuantAgent</h1>
                    </div>

                    {/* Admin & Auth Controls */}
                    <div className="flex items-center gap-4">
                        <button 
                            onClick={() => setIsAdminOpen(true)}
                            className="text-gray-400 hover:text-white transition-colors p-2 rounded-full hover:bg-white/10"
                            title="Admin Settings"
                        >
                            <i className="fas fa-cog text-lg"></i>
                        </button>
                        
                        {isAuthenticated && (
                            <button 
                                onClick={logout}
                                className="text-gray-400 hover:text-red-400 transition-colors p-2 rounded-full hover:bg-white/10"
                                title="Logout / Clear Session"
                            >
                                <i className="fas fa-sign-out-alt text-lg"></i>
                            </button>
                        )}
                    </div>
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

            {/* Admin Modal */}
            <AdminModal isOpen={isAdminOpen} onClose={() => setIsAdminOpen(false)} />
        </section>
    );
}
