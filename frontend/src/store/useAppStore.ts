import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AnalysisResult } from '../types';

interface AppState {
  selectedAsset: string;
  selectedTimeframe: string;
  customAssets: string[];
  
  // Data Method
  dataMethod: "latest" | "date_range" | "to_end";
  klineCount: number;
  futureKlineCount: number;
  
  // Date Range
  startDate: string;
  startTime: string;
  endDate: string;
  endTime: string;
  useCurrentTime: boolean;
  
  // AI Config
  aiVersion: string;
  
  // Analysis Result
  analysisResult: AnalysisResult | null;
  latestResultId: string | null;

  // Continuous Analysis Mode
  continuousMode: boolean;
  historyRefreshTrigger: number;

  // Actions
  setAsset: (asset: string) => void;
  setTimeframe: (tf: string) => void;
  addCustomAsset: (asset: string) => void;
  removeCustomAsset: (asset: string) => void;
  setDataMethod: (method: "latest" | "date_range" | "to_end") => void;
  setKlineCount: (count: number) => void;
  setFutureKlineCount: (count: number) => void;
  setDateConfig: (config: Partial<AppState>) => void;
  setAiVersion: (version: string) => void;
  setAnalysisResult: (result: AnalysisResult | null) => void;
  setLatestResultId: (id: string | null) => void;
  setContinuousMode: (mode: boolean) => void;
  triggerHistoryRefresh: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      selectedAsset: '',
      selectedTimeframe: '1h',
      customAssets: [],
      
      dataMethod: 'latest',
      klineCount: 100,
      futureKlineCount: 13,
      
      startDate: '',
      startTime: '00:00',
      endDate: '',
      endTime: '23:59',
      useCurrentTime: false,
      
      aiVersion: 'constrained',
      
      analysisResult: null,
      latestResultId: null,

      continuousMode: false,
      historyRefreshTrigger: 0,
      
      setAsset: (asset) => set({ selectedAsset: asset }),
      setTimeframe: (tf) => set({ selectedTimeframe: tf }),
      addCustomAsset: (asset) => set((state) => {
        if (state.customAssets.includes(asset)) return state;
        return { customAssets: [...state.customAssets, asset] };
      }),
      removeCustomAsset: (asset) => set((state) => ({ 
        customAssets: state.customAssets.filter(a => a !== asset) 
      })),
      
      setDataMethod: (method) => set({ dataMethod: method }),
      setKlineCount: (count) => set({ klineCount: count }),
      setFutureKlineCount: (count) => set({ futureKlineCount: count }),
      
      setDateConfig: (config) => set((state) => ({ ...state, ...config })),
      
      setAiVersion: (version) => set({ aiVersion: version }),
      setAnalysisResult: (result) => set({ analysisResult: result }),
      setLatestResultId: (id) => set({ latestResultId: id }),
      setContinuousMode: (mode) => set({ continuousMode: mode }),
      triggerHistoryRefresh: () => set((state) => ({ historyRefreshTrigger: state.historyRefreshTrigger + 1 })),
    }),
    {
      name: 'quantagent-storage',
      partialize: (state) => ({ 
        customAssets: state.customAssets,
        selectedTimeframe: state.selectedTimeframe,
        klineCount: state.klineCount,
        latestResultId: state.latestResultId,
        continuousMode: state.continuousMode // Persist user preference
      }),
    }
  )
);
