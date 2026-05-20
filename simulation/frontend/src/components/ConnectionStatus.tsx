import type { ConnectionStatus as ConnectionStatusType } from '../types';

interface Props {
  status: ConnectionStatusType;
  attempt?: number;
}

export default function ConnectionStatus({ status, attempt = 0 }: Props) {
  const dotColor = status === 'connected'
    ? 'bg-profit'
    : status === 'connecting'
      ? 'bg-amber-400'
      : 'bg-loss';

  const label = status === 'connected'
    ? '已连接'
    : status === 'connecting'
      ? '连接中...'
      : '已断开';

  const retryText = status === 'disconnected' && attempt > 0
    ? ` (重试${attempt})`
    : '';

  const tooltip = status === 'connected'
    ? 'WebSocket 已连接'
    : status === 'connecting'
      ? '正在建立 WebSocket 连接...'
      : `WebSocket 已断开${attempt > 0 ? `，正在重试第 ${attempt} 次` : ''}`;

  return (
    <span
      className="inline-flex items-center gap-1.5 shrink-0"
      title={tooltip}
    >
      <span className={`relative flex h-2.5 w-2.5`}>
        <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${dotColor} ${status === 'connected' ? 'animate-ping' : ''}`} />
        <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${dotColor}`} />
      </span>
      <span className="text-[10px] font-medium text-text-muted">
        {label}{retryText}
      </span>
    </span>
  );
}
