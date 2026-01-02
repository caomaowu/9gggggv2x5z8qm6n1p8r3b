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
