import { useEffect, useRef } from 'react';
import { useSimStore } from '../store/useSimStore';

const POLL_INTERVAL = 30_000;  // WS 断开后每 30s 轮询一次
const GRACE_PERIOD = 10_000;   // 断开后等待 10s 再开始轮询（给 WS 重连留时间）

/**
 * WS 断开时的 HTTP 轮询回退。
 * 监听 store 中的 connectionStatus：
 *   - disconnected → 10s 宽限期后启动 30s 轮询
 *   - connected     → 立即停止轮询
 */
export function usePollingFallback() {
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const graceRef = useRef<ReturnType<typeof setTimeout>>();

  // 订阅连接状态（仅用于触发 effect）
  const connectionStatus = useSimStore((s) => s.connectionStatus);

  useEffect(() => {
    const cleanup = () => {
      if (graceRef.current) { clearTimeout(graceRef.current); graceRef.current = undefined; }
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = undefined; }
    };

    if (connectionStatus === 'disconnected') {
      // 宽限期：等 10s，若仍未重连则启动轮询
      graceRef.current = setTimeout(() => {
        const { connectionStatus: latest, selectedTaskId } = useSimStore.getState();
        if (latest === 'connected') return; // 已重连，不启动

        const doPoll = () => {
          const state = useSimStore.getState();
          state.fetchTasks();
          const id = state.selectedTaskId;
          if (id) state.loadTaskData(id);
        };

        doPoll(); // 立即执行一次
        pollRef.current = setInterval(doPoll, POLL_INTERVAL);
      }, GRACE_PERIOD);
    } else if (connectionStatus === 'connected') {
      cleanup();
    }

    return cleanup;
  }, [connectionStatus]);
}
