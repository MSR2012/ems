import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ApiError } from '@/shared/api/client';
import { Alert, ErrorState, LoadingState, PageHeader, Spinner } from '@/shared/ui/feedback';
import { IconMail, IconRefresh } from '@/shared/ui/icons';
import { formatDateTime, formatRelative } from '@/shared/lib/format';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import {
  CONNECT_URL, useDemoAction, useDisconnect, useGmailConnection, useSyncHistory, useSyncNow,
  type GmailAccount,
} from './api';
import { AccountStatusBadge, SyncStatusBadge } from './SyncStatusBadge';
import { AiDemoTools } from './AiDemoTools';

const CALLBACK_MESSAGES: Record<string, { tone: 'success' | 'warning' | 'error'; text: string }> = {
  connected: { tone: 'success', text: 'Gmail connected. Your inbox is syncing in the background — you can keep using the app.' },
  denied: { tone: 'warning', text: 'Gmail access was not granted. You can try again whenever you are ready.' },
  error: { tone: 'error', text: 'We could not connect Gmail. Please try again.' },
};
const REASONS: Record<string, string> = {
  state_mismatch: 'The sign-in request expired or did not match (security check). Please start again.',
  exchange_failed: 'Google did not accept the authorization code.',
  missing_code: 'Google did not return an authorization code.',
};

function CallbackBanner() {
  const [params, setParams] = useSearchParams();
  const [shown, setShown] = useState<{ key: string; reason: string | null } | null>(null);
  useEffect(() => {
    const key = params.get('gmail');
    if (key) {
      setShown({ key, reason: params.get('reason') });
      setParams({}, { replace: true });
    }
  }, [params, setParams]);
  useEffect(() => {
    if (!shown) return;
    const t = setTimeout(() => setShown(null), 12_000);
    return () => clearTimeout(t);
  }, [shown]);
  if (!shown || !CALLBACK_MESSAGES[shown.key]) return null;
  const m = CALLBACK_MESSAGES[shown.key];
  return (
    <div className="mb-6">
      <Alert tone={m.tone}>
        {m.text} {shown.reason && REASONS[shown.reason]}
      </Alert>
    </div>
  );
}

function NotConnected() {
  return (
    <section className="card p-6 sm:p-8">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-600"><IconMail /></span>
          <div>
            <h2 className="text-lg font-semibold">Connect your Gmail inbox</h2>
            <p className="mt-1 max-w-xl text-sm text-slate-600">
              You'll be sent to Google to approve <strong>read-only</strong> access. We never see or store your Gmail password,
              and OAuth tokens are encrypted on our server — they never reach your browser.
            </p>
          </div>
        </div>
        <a href={CONNECT_URL} className="btn-primary shrink-0">Connect Gmail</a>
      </div>
    </section>
  );
}

function AccountCard({ account }: { account: GmailAccount }) {
  const syncNow = useSyncNow();
  const disconnect = useDisconnect();
  const [confirm, setConfirm] = useState(false);
  const latest = account.latest_sync;
  const revoked = account.status === 'REVOKED';
  const syncError = syncNow.error instanceof ApiError ? syncNow.error.message : null;

  return (
    <section className="card p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-600"><IconMail /></span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-base font-semibold">{account.email}</h2>
              <AccountStatusBadge status={account.status} />
            </div>
            <p className="mt-1 text-sm text-slate-500">Gmail · connected {formatDateTime(account.created_at)}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {revoked ? (
            <a href={CONNECT_URL} className="btn-primary">Reconnect Gmail</a>
          ) : (
            <button type="button" className="btn-secondary" disabled={account.sync_in_progress || syncNow.isPending}
              onClick={() => syncNow.mutate(account.id)}>
              {account.sync_in_progress ? <Spinner className="h-4 w-4" /> : <IconRefresh className="h-4 w-4" />}
              {account.sync_in_progress ? 'Syncing…' : 'Sync now'}
            </button>
          )}
          <button type="button" className="btn-ghost text-rose-600 hover:bg-rose-50" onClick={() => setConfirm(true)}>Disconnect</button>
        </div>
      </div>

      {revoked && (
        <div className="mt-5">
          <Alert tone="error" title="Reconnect required">
            Google reports that access for this account was revoked or expired, so scheduled syncs are paused.
            Reconnect Gmail to resume syncing — your existing emails stay available.
          </Alert>
        </div>
      )}
      {account.status === 'ERROR' && account.last_error && (
        <div className="mt-5"><Alert tone="warning">{account.last_error}</Alert></div>
      )}
      {syncError && <div className="mt-5"><Alert tone="warning">{syncError}</Alert></div>}

      <dl className="mt-6 grid gap-4 border-t border-slate-100 pt-5 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">Current sync</dt>
          <dd className="mt-1 flex flex-wrap items-center gap-2" data-testid="current-sync-status">
            {latest ? <SyncStatusBadge status={latest.status} /> : <span className="text-slate-400">No syncs yet</span>}
            {latest && <span className="text-slate-500">{latest.type === 'INITIAL' ? 'Initial' : 'Incremental'}</span>}
          </dd>
          {latest && latest.status === 'RUNNING' && (
            <p className="mt-1 text-xs text-slate-500">{latest.fetched_count} fetched · {latest.imported_count} new</p>
          )}
        </div>
        <div>
          <dt className="text-slate-500">Last successful sync</dt>
          <dd className="mt-1 font-medium text-slate-800" title={formatDateTime(account.last_synced_at)}>{formatRelative(account.last_synced_at)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Next scheduled sync</dt>
          <dd className="mt-1 font-medium text-slate-800">{revoked ? 'Paused' : account.next_sync_at ? formatDateTime(account.next_sync_at) : '—'}</dd>
        </div>
      </dl>

      <ConfirmDialog
        open={confirm}
        title="Disconnect Gmail?"
        confirmLabel="Disconnect"
        tone="danger"
        busy={disconnect.isPending}
        onCancel={() => setConfirm(false)}
        onConfirm={() => disconnect.mutate(account.id, { onSettled: () => setConfirm(false) })}
      >
        We'll revoke access and delete the stored Google credentials. Emails already imported remain visible in the app.
      </ConfirmDialog>
    </section>
  );
}

function SyncHistory({ account }: { account: GmailAccount }) {
  const { data, isLoading, isError, refetch } = useSyncHistory(account.id, account.sync_in_progress);
  return (
    <section className="card overflow-hidden">
      <div className="border-b border-slate-100 px-5 py-4">
        <h2 className="text-base font-semibold">Sync history</h2>
        <p className="text-sm text-slate-500">Most recent synchronization runs. Failed runs are retried automatically with backoff.</p>
      </div>
      {isLoading ? <LoadingState /> : isError ? <div className="p-4"><ErrorState onRetry={() => refetch()} /></div> : (
        <div className="overflow-x-auto">
          <p className="px-5 pt-2 text-xs text-slate-400 sm:hidden">Swipe sideways to see all columns →</p>
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-2 font-medium">Started</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">Fetched</th>
                <th className="px-3 py-2 text-right font-medium">New</th>
                <th className="px-3 py-2 text-right font-medium">Failed</th>
                <th className="px-5 py-2 font-medium">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.results.length === 0 && (
                <tr><td colSpan={7} className="px-5 py-6 text-center text-slate-500">No syncs yet.</td></tr>
              )}
              {data?.results.map((s) => (
                <tr key={s.id}>
                  <td className="whitespace-nowrap px-5 py-2.5 text-slate-700">{formatDateTime(s.started_at ?? s.created_at)}</td>
                  <td className="px-3 py-2.5 text-slate-600">{s.type === 'INITIAL' ? 'Initial' : 'Incremental'}</td>
                  <td className="px-3 py-2.5"><SyncStatusBadge status={s.status} /></td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{s.fetched_count}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{s.imported_count}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{s.failed_count}</td>
                  <td className="max-w-xs truncate px-5 py-2.5 text-slate-500" title={s.error}>{s.error || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function DemoTools({ account }: { account: GmailAccount | null }) {
  const demo = useDemoAction();
  const syncNow = useSyncNow();
  // New mail is picked up by a sync: trigger one right away so the demo shows it immediately.
  const deliver = (id: number) => demo.mutate({ accountId: id, action: 'new-messages' }, {
    onSuccess: () => { if (!account?.sync_in_progress) syncNow.mutate(id); },
  });
  return (
    <section className="card border-dashed border-indigo-200 bg-indigo-50/40 p-5 sm:p-6">
      <h2 className="text-base font-semibold text-indigo-900">Demo tools</h2>
      <p className="mt-1 text-sm text-indigo-900/70">Demo mode uses a simulated Gmail mailbox and AI. Use these controls to exercise real-world scenarios.</p>
      {demo.data && <div className="mt-3"><Alert tone="info">{demo.data.detail}</Alert></div>}
      {demo.error && <div className="mt-3"><Alert tone="error">{(demo.error as Error).message}</Alert></div>}
      {account && account.status !== 'DISCONNECTED' ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className="btn-secondary" disabled={demo.isPending}
            onClick={() => deliver(account.id)}>Deliver 3 new emails &amp; sync</button>
          <button type="button" className="btn-secondary" disabled={demo.isPending}
            onClick={() => demo.mutate({ accountId: account.id, action: 'rate-limit' })}>Simulate Gmail rate limit (429)</button>
          <button type="button" className="btn-secondary" disabled={demo.isPending || account.status === 'REVOKED'}
            onClick={() => demo.mutate({ accountId: account.id, action: 'revoke' })}>Simulate revoked authorization</button>
        </div>
      ) : (
        <p className="mt-3 text-sm text-indigo-900/70">Connect Gmail to use the mailbox simulations.</p>
      )}
      {account && account.status !== 'DISCONNECTED' && (
        <p className="mt-2 text-xs text-indigo-900/70">Rate-limit and revocation simulations take effect on the next sync — click <strong>Sync now</strong> or wait for the scheduled sync.</p>
      )}
      <AiDemoTools />
    </section>
  );
}

export default function IntegrationsPage() {
  const { data, isLoading, isError, refetch } = useGmailConnection();
  return (
    <>
      <PageHeader title="Integrations" description="Gmail connection, synchronization status and history." />
      <CallbackBanner />
      {isLoading ? <LoadingState /> : isError || !data ? <ErrorState onRetry={() => refetch()} /> : (
        <div className="grid gap-6">
          {data.account ? <AccountCard account={data.account} /> : <NotConnected />}
          {data.account && <SyncHistory account={data.account} />}
          {data.demo_mode && <DemoTools account={data.account} />}
        </div>
      )}
    </>
  );
}
