import { create } from 'zustand';
import type {
  TaskResponse,
  StatsResponse,
  EquityPoint,
  RoundResponse,
  WsMessage,
  BetMode,
  TaskCreateRequest,
  ConnectionStatus,
} from '../types';
import {
  listTasks, createTask, startTask, stopTask, deleteTask,
  getStats, getEquity, getRounds, updateTask as updateTaskClient,
  clearTaskRounds,
} from '../api/client';

interface ToastItem {
  id: string;
  type: string;
  message: string;
  taskId: string;
  data?: Record<string, unknown>;
}

interface SimState {
  tasks: TaskResponse[];
  selectedTaskId: string | null;
  stats: StatsResponse | null;
  equity: EquityPoint[];
  rounds: RoundResponse[];
  roundsTotal: number;
  latestRound: RoundResponse | null;
  toasts: ToastItem[];
  connectionStatus: ConnectionStatus;
  reconnectAttempt: number;

  // 操作
  fetchTasks: () => Promise<void>;
  selectTask: (id: string | null) => void;
  addTask: (req: { asset: string; timeframe: string; bet_mode: BetMode; bet_amount: number; fee_rate: number; initial_capital: number }) => Promise<void>;
  startSelected: () => Promise<void>;
  stopSelected: () => Promise<void>;
  deleteSelected: () => Promise<void>;
  updateTask: (id: string, req: Partial<TaskCreateRequest>) => Promise<void>;
  loadTaskData: (id: string) => Promise<void>;
  loadMoreRounds: () => Promise<void>;
  addToast: (msg: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
  setConnectionStatus: (status: ConnectionStatus, attempt?: number) => void;
  clearSelectedRounds: () => Promise<void>;

  // WebSocket 处理
  handleWsMessage: (msg: WsMessage) => void;
}

let toastCounter = 0;

export const useSimStore = create<SimState>((set, get) => ({
  tasks: [],
  selectedTaskId: null,
  stats: null,
  equity: [],
  rounds: [],
  roundsTotal: 0,
  latestRound: null,
  toasts: [],
  connectionStatus: 'connecting',
  reconnectAttempt: 0,

  async fetchTasks() {
    const tasks = await listTasks();
    set({ tasks });
  },

  selectTask(id: string | null) {
    set({ selectedTaskId: id, latestRound: null });
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
    set({ selectedTaskId: null, stats: null, equity: [], rounds: [], latestRound: null });
    await get().fetchTasks();
  },

  async clearSelectedRounds() {
    const id = get().selectedTaskId;
    if (!id) return;
    await clearTaskRounds(id);
    set({ stats: null, equity: [], rounds: [], roundsTotal: 0, latestRound: null });
    await get().fetchTasks();
    if (get().selectedTaskId === id) await get().loadTaskData(id);
  },

  async updateTask(id: string, req: Partial<TaskCreateRequest>) {
    await updateTaskClient(id, req);
    await get().fetchTasks();
    if (get().selectedTaskId === id) await get().loadTaskData(id);
  },

  async loadTaskData(id: string) {
    const [stats, equity, rounds] = await Promise.all([
      getStats(id),
      getEquity(id),
      getRounds(id, 0, 50),
    ]);
    set({
      stats,
      equity,
      rounds: rounds.rounds,
      roundsTotal: rounds.total,
      latestRound: rounds.rounds[0] || null,
    });
  },

  async loadMoreRounds() {
    const id = get().selectedTaskId;
    if (!id) return;
    const { rounds } = get();
    const data = await getRounds(id, rounds.length, 50);
    set({ rounds: [...rounds, ...data.rounds], roundsTotal: data.total });
  },

  addToast(msg) {
    const id = `toast-${++toastCounter}-${Date.now()}`;
    set((s) => ({ toasts: [...s.toasts, { ...msg, id }] }));
  },

  removeToast(id: string) {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  },

  setConnectionStatus(status: ConnectionStatus, attempt?: number) {
    set({ connectionStatus: status, ...(attempt !== undefined ? { reconnectAttempt: attempt } : {}) });
  },

  handleWsMessage(msg: WsMessage) {
    const taskId = msg.task_id;
    const data = msg.data as Record<string, unknown> | undefined;

    if (msg.type === 'round_completed') {
      const prevResult = data?.prev_result as Record<string, unknown> | undefined;
      const result = prevResult?.result as string | undefined;
      const pnl = prevResult?.pnl as number | undefined;

      if (result === 'WIN') {
        get().addToast({
          type: 'WIN',
          message: `盈利 +$${typeof pnl === 'number' ? pnl.toFixed(2) : '0.00'}`,
          taskId,
          data: prevResult,
        });
      } else if (result === 'LOSE') {
        get().addToast({
          type: 'LOSE',
          message: `亏损 -$${typeof pnl === 'number' ? Math.abs(pnl).toFixed(2) : '0.00'}`,
          taskId,
          data: prevResult,
        });
      }

      // 刷新任务列表（更新 last_kline_ts 等字段）+ 选中任务详情
      get().fetchTasks();
      if (taskId === get().selectedTaskId) {
        get().loadTaskData(taskId);
      }
    }

    if (msg.type === 'task_started') {
      get().addToast({ type: 'task_started', message: '任务已启动', taskId });
      get().fetchTasks();
    }

    if (msg.type === 'task_stopped') {
      get().addToast({ type: 'task_stopped', message: '任务已停止', taskId });
      get().fetchTasks();
    }

    if (msg.type === 'task_deleted') {
      get().addToast({ type: 'task_deleted', message: '任务已删除', taskId });
      get().fetchTasks();
    }

    if (msg.type === 'stats_updated') {
      if (taskId === get().selectedTaskId) {
        Promise.all([getStats(taskId), getEquity(taskId)]).then(([stats, equity]) => {
          set({ stats, equity });
        });
      }
    }

    if (msg.type === 'task_updated') {
      get().fetchTasks();
      if (taskId === get().selectedTaskId) {
        get().loadTaskData(taskId);
      }
    }
  },
}));
