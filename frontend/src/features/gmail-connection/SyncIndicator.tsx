import { Link } from 'react-router-dom';
import { Spinner } from '@/shared/ui/feedback';
import { formatRelative } from '@/shared/lib/format';
import { useGmailConnection } from './api';

/** Global sync status (sidebar). Mounting it app-wide also refreshes mail when a sync finishes. */
export function SyncIndicator() {
  const { data } = useGmailConnection();
  const a = data?.account;
  if (!data) return null;
  let content;
  if (!a) content = <span className="text-slate-500">Gmail not connected</span>;
  else if (a.status === 'REVOKED') content = <span className="font-medium text-rose-600">Reconnect Gmail</span>;
  else if (a.sync_in_progress) content = <span className="flex items-center gap-2 text-indigo-700"><Spinner className="h-3.5 w-3.5" /> Syncing inbox…</span>;
  else content = <span className="text-slate-500">Synced {formatRelative(a.last_synced_at)}</span>;
  return (
    <Link to="/integrations" className="mt-4 block rounded-lg bg-slate-50 px-3 py-2 text-xs hover:bg-slate-100" data-testid="sync-indicator">
      {content}
    </Link>
  );
}
