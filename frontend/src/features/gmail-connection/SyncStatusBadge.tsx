import { Badge, type Tone } from '@/shared/ui/Badge';
import { Spinner } from '@/shared/ui/feedback';
import type { AccountStatus, SyncStatus } from './api';

const SYNC_TONE: Record<SyncStatus, Tone> = {
  PENDING: 'slate', RUNNING: 'blue', COMPLETED: 'green', PARTIAL: 'amber', FAILED: 'red',
};
const SYNC_LABEL: Record<SyncStatus, string> = {
  PENDING: 'Pending', RUNNING: 'Running', COMPLETED: 'Completed', PARTIAL: 'Partial', FAILED: 'Failed',
};

export function SyncStatusBadge({ status }: { status: SyncStatus }) {
  return (
    <Badge tone={SYNC_TONE[status]}>
      {(status === 'RUNNING' || status === 'PENDING') && <Spinner className="h-3 w-3" />}
      {SYNC_LABEL[status]}
    </Badge>
  );
}

const ACCOUNT: Record<AccountStatus, { tone: Tone; label: string }> = {
  ACTIVE: { tone: 'green', label: 'Connected' },
  ERROR: { tone: 'amber', label: 'Connected — last sync failed' },
  REVOKED: { tone: 'red', label: 'Authorization revoked' },
  DISCONNECTED: { tone: 'slate', label: 'Not connected' },
};

export function AccountStatusBadge({ status }: { status: AccountStatus }) {
  const a = ACCOUNT[status];
  return <Badge tone={a.tone}>{a.label}</Badge>;
}
