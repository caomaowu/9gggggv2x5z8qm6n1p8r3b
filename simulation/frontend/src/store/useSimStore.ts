import { create } from 'zustand';
import type {
  TaskResponse,
  StatsResponse,
  EquityPoint,
  RoundResponse,
  WsMessage,
  BetMode,
} from '../types';
import { listTasks, createTask, startTask, stopTask, deleteTask, getStats, getEquity, getRounds } from '../api/client';

interface SimState {
  tasks: TaskResponse[];
  selectedTaskId: string | null;
  stats: StatsResponse | null;
  equity: EquityPoint[];
  rounds: RoundResponse[];
  roundsTotal: number;

  // 操作
  fetchTasks: () => Promise<void>;
  selectTask: (id: string | null) => void;
  addTask: (req: { asset: string; timeframe: string; bet_mode: BetMode; bet_amount: number; fee_rate: number; initial_capital: number }) => Promise<void>;
  startSelected: () => Promise<void>;
  stopSelected: () => Promise<void>;
  deleteSelected: () => Promise<void>;
  loadTaskData: (id: string) => Promise<void>;
  loadMoreRounds: () => Promise<void>;

  // WebSocket 处理
  handleWsMessage: (msg: WsMessage) => void;
}

export const useSimStore = create<SimState>((set, get) => ({
  tasks: [],
  selectedTaskId: null,
  stats: null,
  equity: [],
  rounds: [],
  roundsTotal: 0,

  async fetchTasks() {
    const tasks = await listTasks();
    set({ tasks });
  },

  selectTask(id: string | null) {
    set({ selectedTaskId: id });
    if (id) get().loadTaskData(id);
  },

  async addTask(req) {
    await createTask(req);
    await get().fetchTasks();
  },

  async startSelected() {
    const id = get().selectedTaskId;
    if (!id) return;
    await startTask(id);
    await get().fetchTasks();
  },

  async stopSelected() {
    const id = get().selectedTaskId;
    if (!id) return;
    await stopTask(id);
    await get().fetchTasks();
  },

  async deleteSelected() {
    const id = get().selectedTaskId;
    if (!id) return;
    await deleteTask(id);
    set({ selectedTaskId: null, stats: null, equity: [], rounds: [] });
    await get().fetchTasks();
  },

  async loadTaskData(id: string) {
    const [stats, equity, rounds] = await Promise.all([
      getStats(id),
      getEquity(id),
      getRounds(id, 0, 50),
    ]);
    set({ stats, equity, rounds: rounds.rounds, roundsTotal: rounds.total });
  },

  async loadMoreRounds() {
    const id = get().selectedTaskId;
    if (!id) return;
    const { rounds } = get();
    const data = await getRounds(id, rounds.length, 50);
    set({ rounds: [...rounds, ...data.rounds], roundsTotal: data.total });
  },

  handleWsMessage(msg: WsMessage) {
    if (msg.type === 'round_completed' && msg.task_id === get().selectedTaskId) {
      get().loadTaskData(msg.task_id);
    }
    // 刷新任务列表以更新状态
    if (['task_started', 'task_stopped', 'task_deleted'].includes(msg.type)) {
      get().fetchTasks();
    }
  },
}));
