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

// ---- Brale LLM Configuration Types ----

export interface LLMProviderInfo {
    name: string;
    agent_models: string[];
    graph_models: string[];
}

export interface BraleAgentConfig {
    provider: string;
    model: string;
    temperature: number;
}

export interface LLMConfigCurrent {
    agent_provider: string;
    agent_model: string;
    agent_temperature: number;
    // brale per-agent
    indicator_provider?: string;
    indicator_model?: string;
    indicator_temperature?: number;
    structure_provider?: string;
    structure_model?: string;
    structure_temperature?: number;
    mechanics_provider?: string;
    mechanics_model?: string;
    mechanics_temperature?: number;
}

export interface LLMConfigResponse {
    current: LLMConfigCurrent;
    options: {
        providers: Record<string, LLMProviderInfo>;
    };
}

export interface LLMConfigUpdate {
    agent_provider?: string;
    agent_model?: string;
    agent_temperature?: number;
    indicator_provider?: string;
    indicator_model?: string;
    indicator_temperature?: number;
    structure_provider?: string;
    structure_model?: string;
    structure_temperature?: number;
    mechanics_provider?: string;
    mechanics_model?: string;
    mechanics_temperature?: number;
}

export const getLLMConfig = async (): Promise<LLMConfigResponse> => {
    const response = await apiClient.get<LLMConfigResponse>('/system/llm-config');
    return response.data;
};

export const updateLLMConfig = async (config: LLMConfigUpdate): Promise<any> => {
    const response = await apiClient.post('/system/llm-config', config);
    return response.data;
};
