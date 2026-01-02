import { apiClient } from './client';
import type { AnalyzeRequest } from '../types';

export const analyzeMarket = async (data: AnalyzeRequest) => {
  const response = await apiClient.post('/analyze/', data);
  return response.data;
};
