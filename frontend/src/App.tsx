import { useAppStore } from './store/useAppStore';
import HomeHeader from './components/HomeHeader';
import AnalysisForm from './components/AnalysisForm';
import AnalysisResult from './components/AnalysisResult';

function App() {
  const { analysisResult } = useAppStore();

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
