import { apiClient } from './client';
import type { AnalyzeRequest, AnalysisResult } from '../types';

export const analyzeMarket = async (data: AnalyzeRequest) => {
  const response = await apiClient.post('/analyze/', data);
  return response.data;
};

export const getAnalysisHistory = async (resultId: string) => {
  const response = await apiClient.get<AnalysisResult>(`/analyze/history/${encodeURIComponent(resultId)}`);
  return response.data;
};

export interface HistoryItem {
    result_id: string;
    date: string;
    timestamp: number;
    created_at: string;
}

export const getHistoryList = async (limit: number = 20) => {
    const response = await apiClient.get<HistoryItem[]>('/analyze/history', {
        params: { limit }
    });
    return response.data;
};
