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

export interface LLMProviderInfo {
    name: string;
    agent_models: string[];
    graph_models: string[];
}

export interface LLMConfigCurrent {
    agent_provider: string;
    agent_model: string;
    agent_temperature: number;
    graph_provider: string;
    graph_model: string;
    graph_temperature: number;
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
    graph_provider?: string;
    graph_model?: string;
    graph_temperature?: number;
}

export const getLLMConfig = async (): Promise<LLMConfigResponse> => {
    const response = await apiClient.get<LLMConfigResponse>('/system/llm-config');
    return response.data;
};

export const updateLLMConfig = async (config: LLMConfigUpdate): Promise<any> => {
    const response = await apiClient.post('/system/llm-config', config);
    return response.data;
};

// Thinking Mode Types

export interface ThinkingModeConfig {
    indicator: boolean;
    pattern: boolean;
    trend: boolean;
    decision: boolean;
}

export interface ThinkingModeUpdate {
    indicator_thinking_mode?: boolean;
    pattern_thinking_mode?: boolean;
    trend_thinking_mode?: boolean;
    decision_thinking_mode?: boolean;
}

export const getThinkingModeConfig = async (): Promise<ThinkingModeConfig> => {
    const response = await apiClient.get<ThinkingModeConfig>('/system/thinking-mode');
    return response.data;
};

export const updateThinkingModeConfig = async (config: ThinkingModeUpdate): Promise<any> => {
    const response = await apiClient.post('/system/thinking-mode', config);
    return response.data;
};
