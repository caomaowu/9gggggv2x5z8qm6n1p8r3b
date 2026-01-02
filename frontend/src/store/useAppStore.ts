import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { DualModelConfig, AnalysisResult } from '../types';

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
  dualModelConfig: DualModelConfig;
  
  // Analysis Result
  analysisResult: AnalysisResult | null;

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
  setDualModelConfig: (config: Partial<DualModelConfig>) => void;
  setAnalysisResult: (result: AnalysisResult | null) => void;
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
      dualModelConfig: {
        dual_model: false,
        model_1: '',
        model_2: ''
      },
      
      analysisResult: null,
      
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
      setDualModelConfig: (config) => set((state) => ({
        dualModelConfig: { ...state.dualModelConfig, ...config }
      })),
      setAnalysisResult: (result) => set({ analysisResult: result }),
    }),
    {
      name: 'quantagent-storage',
      partialize: (state) => ({ 
        customAssets: state.customAssets,
        // selectedAsset: state.selectedAsset, // Optional: persist selection
        // selectedTimeframe: state.selectedTimeframe
      }),
    }
  )
);
