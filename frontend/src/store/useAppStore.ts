import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AnalysisResult } from '../types';

interface AppState {
  selectedAsset: string;
  selectedTimeframe: string;
  
  // Unified Assets Management
  assets: string[];
  // Store custom assigned icons for assets
  assetIcons: Record<string, string>; 
  
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
  
  // History Result Behavior
  autoFocusResult: boolean;

  // Actions
  setAsset: (asset: string) => void;
  setTimeframe: (tf: string) => void;
  
  addAssets: (assets: string[]) => void;
  removeAssets: (assets: string[]) => void;
  
  setDataMethod: (method: "latest" | "date_range" | "to_end") => void;
  setKlineCount: (count: number) => void;
  setFutureKlineCount: (count: number) => void;
  setDateConfig: (config: Partial<AppState>) => void;
  setAiVersion: (version: string) => void;
  setAnalysisResult: (result: AnalysisResult | null) => void;
  setLatestResultId: (id: string | null) => void;
  setContinuousMode: (mode: boolean) => void;
  triggerHistoryRefresh: () => void;
  setAutoFocusResult: (autoFocus: boolean) => void;
}

const DEFAULT_ASSETS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA'];

// Predefined iconic icons for default assets to avoid overriding them with random ones in store logic
const PRESET_ASSET_ICONS: Record<string, string> = {
    'BTC': 'fa-bitcoin',
    'ETH': 'fa-ethereum',
    'SOL': 'fa-fire',
    'BNB': 'fa-coins',
    'XRP': 'fa-water',
    'ADA': 'fa-diamond'
};

const RANDOM_ICONS = [
    'fa-bolt', 'fa-gem', 'fa-rocket', 'fa-leaf', 'fa-paw', 'fa-anchor', 
    'fa-bicycle', 'fa-bomb', 'fa-car', 'fa-carrot', 'fa-cat', 'fa-crow', 
    'fa-crown', 'fa-dog', 'fa-dove', 'fa-dragon', 'fa-feather', 'fa-fighter-jet', 
    'fa-fire', 'fa-flask', 'fa-gamepad', 'fa-ghost', 'fa-gift', 'fa-globe', 
    'fa-hammer', 'fa-heart', 'fa-hippo', 'fa-horse', 'fa-ice-cream', 'fa-key', 
    'fa-lightbulb', 'fa-meteor', 'fa-moon', 'fa-music', 'fa-otter', 'fa-paper-plane', 
    'fa-plane', 'fa-puzzle-piece', 'fa-robot', 'fa-satellite', 'fa-shield-alt', 
    'fa-snowflake', 'fa-space-shuttle', 'fa-spider', 'fa-star', 'fa-sun', 'fa-tag', 
    'fa-tree', 'fa-trophy', 'fa-umbrella', 'fa-utensils', 'fa-virus', 'fa-wallet', 
    'fa-wine-glass'
];

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      selectedAsset: '',
      selectedTimeframe: '1h',
      
      // Initialize with default assets
      assets: DEFAULT_ASSETS,
      assetIcons: {},
      
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
      
      autoFocusResult: true, // Default to jumping to new tab
      
      setAsset: (asset) => set({ selectedAsset: asset }),
      setTimeframe: (tf) => set({ selectedTimeframe: tf }),
      
      addAssets: (newAssets) => set((state) => {
        // Filter out duplicates that already exist
        const uniqueNew = newAssets.filter(a => !state.assets.includes(a));
        if (uniqueNew.length === 0) return state;

        // Assign random icons to new assets if they don't have a preset one
        const newIcons = { ...state.assetIcons };
        uniqueNew.forEach(asset => {
            if (!PRESET_ASSET_ICONS[asset] && !newIcons[asset]) {
                const randomIcon = RANDOM_ICONS[Math.floor(Math.random() * RANDOM_ICONS.length)];
                newIcons[asset] = randomIcon;
            }
        });

        return { 
            assets: [...state.assets, ...uniqueNew],
            assetIcons: newIcons
        };
      }),
      
      removeAssets: (assetsToRemove) => set((state) => ({
        assets: state.assets.filter(a => !assetsToRemove.includes(a))
        // Note: We intentionally keep the icon in assetIcons even if removed,
        // so if the user re-adds the same asset, it gets the same icon back.
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
      setAutoFocusResult: (autoFocus) => set({ autoFocusResult: autoFocus }),
    }),
    {
      name: 'quantagent-storage',
      partialize: (state) => ({ 
        assets: state.assets, 
        assetIcons: state.assetIcons, // Persist custom icons
        selectedTimeframe: state.selectedTimeframe,
        klineCount: state.klineCount,
        latestResultId: state.latestResultId,
        continuousMode: state.continuousMode,
        autoFocusResult: state.autoFocusResult,
      }),
    }
  )
);
