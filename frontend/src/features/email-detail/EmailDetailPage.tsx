import { Link, useLocation, useParams } from 'react-router-dom';
import { ApiError } from '@/shared/api/client';
import { EmptyState, ErrorState, LoadingState } from '@/shared/ui/feedback';
import { Badge } from '@/shared/ui/Badge';
import { IconChevronLeft, IconPaperclip } from '@/shared/ui/icons';
import { formatBytes, formatDateTime } from '@/shared/lib/format';
import { AnalysisPanel } from '@/features/email-analysis/AnalysisPanel';
import { ReanalyzeButton } from '@/features/email-analysis/ReanalyzeButton';
import type { EmailDetail } from '@/shared/api/types';
import { useEmail } from './api';
import { SafeEmailBody } from './SafeEmailBody';

function Recipients({ email }: { email: EmailDetail }) {
  const groups = ['to', 'cc'].map((type) => ({ type, list: email.recipients.filter((r) => r.type === type) })).filter((g) => g.list.length);
  if (!groups.length) return null;
  return (
    <div className="space-y-0.5 text-xs text-slate-500">
      {groups.map((g) => (
        <p key={g.type}><span className="font-medium uppercase">{g.type}:</span> {g.list.map((r) => r.name || r.email).join(', ')}</p>
      ))}
    </div>
  );
}

export function BackLink() {
  const location = useLocation();
  const backTo = (location.state as { backTo?: string } | null)?.backTo ?? '/inbox';
  return (
    <Link to={backTo} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900">
      <IconChevronLeft className="h-4 w-4" /> Back
    </Link>
  );
}

export default function EmailDetailPage() {
  const { id } = useParams();
  const emailId = Number(id);
  const location = useLocation();
  const { data: email, isLoading, isError, error, refetch } = useEmail(emailId);

  if (isLoading) return <LoadingState label="Loading email…" />;
  if (isError || !email) {
    if (error instanceof ApiError && error.status === 404) {
      return <><BackLink /><div className="card"><EmptyState title="Email not found" description="It may have been removed, or it isn't in your mailbox." /></div></>;
    }
    return <><BackLink /><ErrorState onRetry={() => refetch()} /></>;
  }

  return (
    <>
      <BackLink />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <article className="card min-w-0 overflow-hidden">
          <header className="border-b border-slate-100 p-5">
            <h1 className="break-words text-xl font-semibold text-slate-900">{email.subject || '(no subject)'}</h1>
            {email.labels.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">{email.labels.map((l) => <Badge key={l}>{l}</Badge>)}</div>
            )}
            <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm"><span className="font-semibold text-slate-900">{email.sender_name || email.sender_email}</span>{' '}
                  {email.sender_name && <span className="break-all text-slate-500">&lt;{email.sender_email}&gt;</span>}</p>
                <Recipients email={email} />
              </div>
              <time className="shrink-0 text-xs text-slate-500" dateTime={email.received_at}>{formatDateTime(email.received_at)}</time>
            </div>
          </header>
          <div className="p-5">
            <SafeEmailBody html={email.body_html_sanitized} text={email.body_text} />
          </div>
          {email.body_html_sanitized && (
            <p className="border-t border-slate-100 px-5 py-2 text-xs text-slate-400">Remote images and scripts are blocked to protect your privacy.</p>
          )}
          {email.attachments.length > 0 && (
            <div className="border-t border-slate-100 p-5">
              <h2 className="mb-2 text-sm font-semibold text-slate-800">Attachments ({email.attachments.length})</h2>
              <ul className="grid gap-2 sm:grid-cols-2">
                {email.attachments.map((a) => (
                  <li key={a.id} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2">
                    <IconPaperclip className="h-4 w-4 shrink-0 text-slate-400" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-800">{a.filename}</p>
                      <p className="text-xs text-slate-500">{a.mime_type || 'file'} · {formatBytes(a.size)}</p>
                    </div>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-400">Attachment metadata only — files stay in Gmail.</p>
            </div>
          )}
        </article>

        <aside className="min-w-0 space-y-6">
          <AnalysisPanel analysis={email.analysis} actions={<ReanalyzeButton emailId={email.id} analysis={email.analysis} />} />
          {email.thread.length > 1 && (
            <section className="card p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-800">Thread · {email.thread.length} messages</h2>
                <Link className="text-xs font-medium text-indigo-600 hover:underline" to={`/threads/${encodeURIComponent(email.thread_id)}`}
                  state={location.state}>View all</Link>
              </div>
              <ol className="mt-3 space-y-1">
                {email.thread.map((m) => (
                  <li key={m.id}>
                    <Link to={`/emails/${m.id}`} state={location.state} aria-current={m.id === email.id ? 'true' : undefined}
                      className={`block rounded-lg px-3 py-2 text-sm ${m.id === email.id ? 'bg-indigo-50 ring-1 ring-indigo-100' : 'hover:bg-slate-50'}`}>
                      <div className="flex justify-between gap-2">
                        <span className={`truncate ${m.is_read ? 'text-slate-600' : 'font-semibold text-slate-900'}`}>{m.sender_name || m.sender_email}</span>
                        <time className="shrink-0 text-xs text-slate-400">{formatDateTime(m.received_at)}</time>
                      </div>
                      <p className="truncate text-xs text-slate-500">{m.snippet}</p>
                    </Link>
                  </li>
                ))}
              </ol>
            </section>
          )}
          <section className="card p-5 text-xs text-slate-500">
            <h2 className="mb-2 text-sm font-semibold text-slate-800">Details</h2>
            <dl className="space-y-1">
              <div className="flex justify-between gap-2"><dt>Provider</dt><dd className="font-medium text-slate-700">{email.provider}</dd></div>
              <div className="flex justify-between gap-2"><dt>Status</dt><dd className="font-medium text-slate-700">{email.is_read ? 'Read' : 'Unread'}</dd></div>
              <div className="flex justify-between gap-2"><dt>Message ID</dt><dd className="truncate font-mono">{email.external_message_id}</dd></div>
              <div className="flex justify-between gap-2"><dt>Thread ID</dt><dd className="truncate font-mono">{email.thread_id}</dd></div>
            </dl>
          </section>
        </aside>
      </div>
    </>
  );
}
