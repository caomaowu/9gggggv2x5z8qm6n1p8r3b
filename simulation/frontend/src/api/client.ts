import axios from 'axios';
import type {
  TaskCreateRequest,
  TaskResponse,
  StatsResponse,
  EquityPoint,
  RoundListResponse,
} from '../types';

const api = axios.create({ baseURL: '/api' });

// ── 任务 CRUD ──
export async function createTask(req: TaskCreateRequest): Promise<TaskResponse> {
  const { data } = await api.post('/tasks', req);
  return data;
}

export async function listTasks(): Promise<TaskResponse[]> {
  const { data } = await api.get('/tasks');
  return data;
}

export async function getTask(id: string): Promise<TaskResponse> {
  const { data } = await api.get(`/tasks/${id}`);
  return data;
}

export async function startTask(id: string): Promise<TaskResponse> {
  const { data } = await api.post(`/tasks/${id}/start`);
  return data;
}

export async function stopTask(id: string): Promise<TaskResponse> {
  const { data } = await api.post(`/tasks/${id}/stop`);
  return data;
}

export async function deleteTask(id: string): Promise<void> {
  await api.delete(`/tasks/${id}`);
}

// ── 统计 ──
export async function getStats(id: string): Promise<StatsResponse> {
  const { data } = await api.get(`/tasks/${id}/stats`);
  return data;
}

export async function getEquity(id: string): Promise<EquityPoint[]> {
  const { data } = await api.get(`/tasks/${id}/equity`);
  return data;
}

export async function getRounds(id: string, offset = 0, limit = 50): Promise<RoundListResponse> {
  const { data } = await api.get(`/tasks/${id}/rounds`, { params: { offset, limit } });
  return data;
}
