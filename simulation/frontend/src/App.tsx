import { useEffect, useState } from 'react';
import './App.css';
import { useSimStore } from './store/useSimStore';
import { useWebSocket } from './hooks/useWebSocket';
import { usePollingFallback } from './hooks/usePollingFallback';
import type { TaskResponse } from './types';
import TaskCard from './components/TaskCard';
import CreateTaskModal from './components/CreateTaskModal';
import EditTaskModal from './components/EditTaskModal';
import EquityChart from './components/EquityChart';
import StatsPanel from './components/StatsPanel';
import RoundTable from './components/RoundTable';
import PositionBar from './components/PositionBar';
import ToastContainer from './components/ToastContainer';
import ConnectionStatus from './components/ConnectionStatus';
import ExportMenu from './components/ExportMenu';

function App() {
  const {
    tasks, selectedTaskId, stats, equity, rounds, roundsTotal,
    fetchTasks, handleWsMessage, setConnectionStatus,
  } = useSimStore();
  const [modalOpen, setModalOpen] = useState(false);
  const [editModalTask, setEditModalTask] = useState<TaskResponse | null>(null);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);
  const { connectionStatus } = useWebSocket(handleWsMessage, setConnectionStatus);
  usePollingFallback();

  return (
    <div className="h-screen flex flex-col bg-surface-950 text-text-primary">
      {/* 顶栏 */}
      <header className="bg-surface-900 border-b border-border shrink-0">
        <div className="flex items-center justify-between px-6 py-3 gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
              <span className="text-accent-300 text-sm font-bold">Q</span>
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-text-primary">
                QuantAgent
              </h1>
              <p className="text-[11px] text-text-muted -mt-0.5">模拟交易系统</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <ConnectionStatus status={connectionStatus} />
            {selectedTaskId && rounds.length > 0 && (
              <ExportMenu
                rounds={rounds}
                taskName={tasks.find(t => t.id === selectedTaskId)?.asset}
              />
            )}
            <button
              className="px-4 py-2 bg-accent hover:bg-accent-400 text-white text-sm font-medium rounded-lg
                         transition-all duration-200 hover:shadow-lg hover:shadow-accent/25 active:scale-[0.97]"
              onClick={() => setModalOpen(true)}
            >
              + 新建任务
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧任务列表 */}
        <aside className="w-72 bg-surface-900 border-r border-border overflow-y-auto p-3 flex flex-col gap-2 shrink-0">
          <div className="px-2 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-text-muted">
              任务列表
            </p>
          </div>
          {tasks.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <div className="w-12 h-12 rounded-full bg-surface-800 flex items-center justify-center mb-3">
                <svg className="w-6 h-6 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
              </div>
              <p className="text-text-muted text-sm">暂无任务</p>
              <p className="text-text-muted/60 text-xs mt-1">点击右上角按钮开始</p>
            </div>
          )}
          {tasks.map(t => (
            <TaskCard key={t.id} task={t} onEdit={setEditModalTask} />
          ))}
        </aside>

        {/* 右侧主区域 */}
        <main className="flex-1 overflow-y-auto">
          {!selectedTaskId ? (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="w-20 h-20 rounded-2xl bg-surface-800 border border-border flex items-center justify-center mb-5">
                <svg className="w-10 h-10 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
                </svg>
              </div>
              <p className="text-text-muted text-lg font-medium">选择一个任务查看详情</p>
              <p className="text-text-muted/60 text-sm mt-1">左侧选择已有任务，或新建一个开始模拟</p>
            </div>
          ) : (
            <div className="p-6 space-y-5 max-w-6xl mx-auto">
              <PositionBar taskId={selectedTaskId} />
              <StatsPanel stats={stats} />
              <EquityChart data={equity} />
              <RoundTable rounds={rounds} total={roundsTotal} />
            </div>
          )}
        </main>
      </div>

      <CreateTaskModal open={modalOpen} onClose={() => setModalOpen(false)} />
      <EditTaskModal
        task={editModalTask}
        open={!!editModalTask}
        onClose={() => setEditModalTask(null)}
      />
      <ToastContainer />
    </div>
  );
}

export default App;
