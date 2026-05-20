import { useEffect, useRef, useCallback, useState } from 'react';
import type { WsMessage, ConnectionStatus } from '../types';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

export function useWebSocket(
  onMessage: (msg: WsMessage) => void,
  onStatusChange?: (status: ConnectionStatus) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setConnectionStatus('connecting');
    onStatusChange?.('connecting');

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      retryRef.current = 0;
      setConnectionStatus('connected');
      setReconnectAttempt(0);
      onStatusChange?.('connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        onMessage(msg);
      } catch {
        // 忽略解析失败的消息
      }
    };

    ws.onclose = () => {
      setConnectionStatus('disconnected');
      onStatusChange?.('disconnected');
      const delay = RECONNECT_DELAYS[Math.min(retryRef.current, RECONNECT_DELAYS.length - 1)];
      retryRef.current++;
      setReconnectAttempt(retryRef.current);
      timerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onMessage, onStatusChange]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connectionStatus, reconnectAttempt };
}
