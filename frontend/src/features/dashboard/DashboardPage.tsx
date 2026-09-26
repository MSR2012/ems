import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useMe } from '@/features/auth/api';
import { EmailRow } from '@/features/inbox/EmailRow';
import { PriorityBadge, CategoryBadge } from '@/features/email-analysis/AnalysisBadges';
import { SyncStatusBadge } from '@/features/gmail-connection/SyncStatusBadge';
import type { SyncStatus } from '@/features/gmail-connection/api';
import type { Category, DashboardSummary, Priority } from '@/shared/api/types';
import { Badge } from '@/shared/ui/Badge';
import { EmptyState, ErrorState, LoadingState, PageHeader, Spinner } from '@/shared/ui/feedback';
import { IconAlert, IconInbox, IconMail, IconSparkles } from '@/shared/ui/icons';
import { formatDateTime, formatReceived, formatRelative } from '@/shared/lib/format';
import { useDashboardSummary, useNeedsAttention } from './api';

function StatCard({ label, value, to, hint, tone = 'slate', icon }: {
  label: string; value: number; to: string; hint?: string; tone?: 'slate' | 'red' | 'orange' | 'indigo'; icon?: ReactNode;
}) {
  const tones = { slate: 'text-slate-900', red: 'text-rose-600', orange: 'text-orange-600', indigo: 'text-indigo-600' };
  return (
    <Link to={to} className="card group block p-4 transition hover:border-indigo-200 hover:shadow">
      <div className="flex items-center justify-between text-slate-500">
        <p className="text-xs font-medium uppercase tracking-wide">{label}</p>
        {icon}
      </div>
      <p className={`mt-2 text-3xl font-semibold tabular-nums ${tones[tone]}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500 group-hover:text-indigo-600">{hint}</p>}
    </Link>
  );
}

function StatusCard({ data }: { data: DashboardSummary }) {
  const sync = data.sync;
  const latest = sync?.latest_sync as { status?: SyncStatus; type?: string; completed_at?: string | null } | null | undefined;
  const a = data.analysis;
  const total = a.analyzed + a.in_progress + a.failed + a.skipped || 1;
  return (
    <section className="card self-start p-5" aria-labelledby="status-title">
      <h2 id="status-title" className="text-sm font-semibold text-slate-800">Sync &amp; analysis status</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-slate-500">Gmail</dt>
          <dd>{!sync || !sync.connected ? (
            <Link to="/integrations" className={`font-medium ${sync?.status === 'REVOKED' ? 'text-rose-600' : 'text-indigo-600'} hover:underline`}>
              {sync?.status === 'REVOKED' ? 'Reconnect required' : 'Connect Gmail'}
            </Link>
          ) : <span className="font-medium text-slate-800">{sync.email}</span>}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-slate-500">Latest sync</dt>
          <dd>{latest?.status ? <SyncStatusBadge status={latest.status} /> : '—'}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-slate-500">Last successful sync</dt>
          <dd className="font-medium text-slate-800" title={formatDateTime(sync?.last_synced_at)}>{formatRelative(sync?.last_synced_at)}</dd>
        </div>
      </dl>
      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">AI analysis</span>
          <span className="flex items-center gap-1.5 font-medium text-slate-800">
            {a.in_progress > 0 && <Spinner className="h-3.5 w-3.5" />}
            {a.analyzed} of {a.analyzed + a.in_progress + a.failed + a.skipped} analyzed
          </span>
        </div>
        <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
          <div className="bg-indigo-500" style={{ width: `${(a.analyzed / total) * 100}%` }} />
          <div className="animate-pulse bg-sky-300" style={{ width: `${(a.in_progress / total) * 100}%` }} />
          <div className="bg-amber-400" style={{ width: `${(a.failed / total) * 100}%` }} />
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {a.in_progress} in progress · {a.failed} failed · {a.skipped} not eligible
        </p>
      </div>
    </section>
  );
}

function NeedsAttentionCard() {
  const { data, isLoading, isError, refetch } = useNeedsAttention();
  return (
    <section className="card overflow-hidden" aria-labelledby="na-title">
      <div className="border-b border-slate-100 px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="na-title" className="text-base font-semibold text-slate-900">Needs attention</h2>
          <Badge tone="indigo"><IconSparkles className="h-3 w-3" /> AI-based suggestion</Badge>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {data?.description ?? 'Suggested by AI. Not an objective measure of importance.'}
        </p>
      </div>
      {isLoading ? <LoadingState /> : isError || !data ? <div className="p-4"><ErrorState onRetry={() => refetch()} /></div> : data.results.length === 0 ? (
        <EmptyState icon={<IconSparkles className="h-10 w-10" />} title="Nothing needs your attention right now"
          description="Emails with high reply urgency or high priority will appear here once analyzed." />
      ) : (
        <>
          <ol className="divide-y divide-slate-100">
            {data.results.map((item, i) => (
              <li key={item.email.id}>
                <Link to={`/emails/${item.email.id}`} state={{ backTo: '/' }} className="flex gap-3 px-5 py-3 hover:bg-slate-50">
                  <span className="mt-0.5 w-5 shrink-0 text-right text-xs font-semibold text-slate-400 tabular-nums">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className={`truncate text-sm ${item.email.is_read ? 'font-medium text-slate-700' : 'font-semibold text-slate-900'}`}>
                        {item.email.sender_name || item.email.sender_email}
                      </p>
                      <time className="shrink-0 text-xs text-slate-500">{formatReceived(item.email.received_at)}</time>
                    </div>
                    <p className="truncate text-sm text-slate-700">{item.email.subject || '(no subject)'}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                      <PriorityBadge priority={item.analysis.priority as Priority} />
                      <CategoryBadge category={item.analysis.category as Category} />
                      <Badge tone={item.analysis.reply_urgency >= (data.thresholds.urgency as number) ? 'orange' : 'slate'}>↩ {item.analysis.reply_urgency}%</Badge>
                      <span className="text-xs text-slate-400">· {item.reasons.join(' · ')}</span>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ol>
          {data.total > data.results.length && (
            <div className="border-t border-slate-100 px-5 py-3 text-sm">
              <Link className="font-medium text-indigo-600 hover:underline" to="/inbox?priority=CRITICAL,HIGH&hide_potential_spam=true">
                View all {data.total} in the inbox →
              </Link>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default function DashboardPage() {
  const { data: me } = useMe();
  const { data, isLoading, isError, refetch } = useDashboardSummary();
  const greeting = me?.name ? `Welcome back, ${me.name.split(' ')[0]}` : 'Dashboard';
  if (isLoading) return <LoadingState label="Loading dashboard…" />;
  if (isError || !data) return <><PageHeader title="Dashboard" /><ErrorState onRetry={() => refetch()} /></>;
  const t = data.thresholds as { spam: number; urgency: number };
  const c = data.counts;
  const noAccount = !data.sync || data.sync.status === 'DISCONNECTED';
  return (
    <>
      <PageHeader title={greeting} description="What deserves your attention, based on AI analysis of your synced inbox." />
      {noAccount && c.total === 0 ? (
        <div className="card"><EmptyState icon={<IconMail className="h-10 w-10" />} title="Connect Gmail to get started"
          description="We'll import your recent inbox and analyze it for priority, urgency and spam."
          action={<Link to="/integrations" className="btn-primary">Connect Gmail</Link>} /></div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
            <StatCard label="Inbox" value={c.total} to="/inbox" hint="All synced emails" icon={<IconInbox className="h-4 w-4" />} />
            <StatCard label="Unread" value={c.unread} to="/inbox?is_read=false" hint="Not yet read" tone="indigo" />
            <StatCard label="Critical / high" value={c.high_priority} to="/inbox?priority=CRITICAL,HIGH" hint="AI priority" tone="red" />
            <StatCard label="High urgency" value={c.high_urgency} to={`/inbox?reply_urgency_min=${t.urgency}`} hint={`Reply urgency ≥ ${t.urgency}%`} tone="orange" />
            <StatCard label="Potential spam" value={c.potential_spam} to={`/inbox?spam_likelihood_min=${t.spam}`} hint={`Spam likelihood ≥ ${t.spam}%`} icon={<IconAlert className="h-4 w-4" />} />
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <NeedsAttentionCard />
            <StatusCard data={data} />
          </div>
          <section className="card overflow-hidden" aria-labelledby="recent-title">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 id="recent-title" className="text-base font-semibold text-slate-900">Recent emails</h2>
              <Link to="/inbox" className="text-sm font-medium text-indigo-600 hover:underline">Open inbox →</Link>
            </div>
            {data.recent.length === 0 ? <EmptyState title="No emails yet" /> : (
              <ul className="divide-y divide-slate-100">{data.recent.map((e) => <EmailRow key={e.id} email={e} backTo="/" />)}</ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}
