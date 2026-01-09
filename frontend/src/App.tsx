import { useEffect, useState } from 'react';
import { useAppStore } from './store/useAppStore';
import { getAnalysisHistory } from './api/analyze';
import HomeHeader from './components/HomeHeader';
import AnalysisForm from './components/AnalysisForm';
import AnalysisResult from './components/AnalysisResult';

function App() {
  const { analysisResult, latestResultId, setAnalysisResult } = useAppStore();
  const [isRestoring, setIsRestoring] = useState(false);

  useEffect(() => {
    const restoreHistory = async () => {
      // 1. Check for URL parameter (Priority)
      const urlParams = new URLSearchParams(window.location.search);
      const urlId = urlParams.get('id');

      // 2. Determine which ID to use
      // Modified: Only restore if explicit ID in URL (User request)
      // We do NOT want to auto-restore latestResultId on fresh load/refresh anymore.
      const targetId = urlId;

      // Only restore if we have a target ID and no result is currently loaded (or if we are forcing a load via URL)
      // Note: If urlId is present, we always want to load it, even if analysisResult is already set?
      // Actually, if analysisResult is set, it might be from a previous effect run.
      // But for a fresh page load with ?id=..., analysisResult starts as null.
      
      if (targetId && !isRestoring) {
        // Optimization: If the current result is already the target result, skip.
        if (analysisResult && analysisResult.result_id === targetId) {
            return;
        }

        setIsRestoring(true);
        try {
            console.log("Attempting to restore analysis history:", targetId);
            const result = await getAnalysisHistory(targetId);
            if (result) {
                // Map backend fields to frontend expected fields
                // Ensure compatibility with AnalysisResult components
                const enrichedResult = {
                    ...result,
                    asset_name: result.asset || result.asset_name,
                    timeframe: result.timeframe,
                    data_length: result.data_length || (result.kline_data ? result.kline_data.length : 0),
                    // Ensure charts are mapped if they exist in result
                    pattern_chart: result.pattern_chart || result.pattern_image,
                    trend_chart: result.trend_chart || result.trend_image
                };
                
                setAnalysisResult(enrichedResult);
            }
        } catch (error) {
            console.error("Failed to restore history:", error);
            // If 404, maybe we should clear the ID?
            // For now, let's just log it.
        } finally {
            setIsRestoring(false);
        }
      }
    };
    
    restoreHistory();
  }, [latestResultId, analysisResult, setAnalysisResult]);

  if (isRestoring) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
            <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-lg">Restoring previous analysis...</p>
                <p className="text-sm text-gray-400 mt-2">ID: {latestResultId}</p>
            </div>
        </div>
      );
  }

  if (analysisResult) {
    return <AnalysisResult />;
  }

  return (
    <div className="flex flex-col min-h-screen overflow-hidden bg-gray-900 text-white">
      <main className="grow">
         <HomeHeader />
         <AnalysisForm />
      </main>
    </div>
  )
}

export default App
