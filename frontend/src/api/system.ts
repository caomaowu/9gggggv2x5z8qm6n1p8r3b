import { apiClient } from './client';

export interface SystemCleanResponse {
    status: string;
    message: string;
    cleaned_count: number;
}

export const clearSystemCache = async (): Promise<SystemCleanResponse> => {
    const response = await apiClient.post<SystemCleanResponse>('/system/clear-cache');
    return response.data;
};

export const clearExportsFiles = async (): Promise<SystemCleanResponse> => {
    const response = await apiClient.post<SystemCleanResponse>('/system/clear-exports');
    return response.data;
};

export const clearHistoryData = async (): Promise<SystemCleanResponse> => {
    const response = await apiClient.post<SystemCleanResponse>('/system/clear-history');
    return response.data;
};

