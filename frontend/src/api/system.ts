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

// LLM Configuration Types
export interface ProviderInfo {
    id: string;
    name: string;
}

export interface LLMConfigResponse {
    agent: {
        provider: string;
        name: string;
        model: string;
        temperature: number;
        base_url: string;
    };
    graph: {
        provider: string;
        name: string;
        model: string;
        temperature: number;
        base_url: string;
    };
    available_providers: ProviderInfo[];
    agent_models: string[]; // Legacy
    graph_models: string[]; // Legacy
    agent_models_map: Record<string, string[]>; // New: Provider -> Models
    graph_models_map: Record<string, string[]>; // New: Provider -> Models
    model_preferences: {
        agent: Record<string, number>;
        graph: Record<string, number>;
    }; // New: Role -> (Model -> Temperature)
}

export const getLLMConfig = async (): Promise<LLMConfigResponse> => {
    const response = await apiClient.get<LLMConfigResponse>('/system/llm-config');
    return response.data;
};

export const updateLLMConfig = async (
    agent_provider: string,
    agent_model: string,
    graph_provider: string,
    graph_model: string,
    agent_temperature: number = 0.1,
    graph_temperature: number = 0.1
): Promise<LLMConfigResponse> => {
    const response = await apiClient.post<LLMConfigResponse>('/system/llm-config', {
        agent_provider,
        agent_model,
        graph_provider,
        graph_model,
        agent_temperature,
        graph_temperature
    });
    return response.data;
};
