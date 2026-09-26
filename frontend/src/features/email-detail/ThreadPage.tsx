import { Link, useLocation, useParams } from 'react-router-dom';
import { ApiError } from '@/shared/api/client';
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/shared/ui/feedback';
import { formatDateTime } from '@/shared/lib/format';
import { AnalysisIndicators } from '@/features/email-analysis/AnalysisBadges';
import { useThread } from './api';
import { BackLink } from './EmailDetailPage';
import { SafeEmailBody } from './SafeEmailBody';

export default function ThreadPage() {
  const { threadId = '' } = useParams();
  const location = useLocation();
  const { data, isLoading, isError, error, refetch } = useThread(threadId);
  if (isLoading) return <LoadingState label="Loading thread…" />;
  if (isError || !data) {
    return (
      <>
        <BackLink />
        {error instanceof ApiError && error.status === 404
          ? <div className="card"><EmptyState title="Thread not found" /></div>
          : <ErrorState onRetry={() => refetch()} />}
      </>
    );
  }
  return (
    <>
      <BackLink />
      <PageHeader title={data.subject || '(no subject)'} description={`${data.messages.length} messages in this conversation`} />
      <ol className="space-y-4">
        {data.messages.map((m) => (
          <li key={m.id} className="card overflow-hidden">
            <div className="flex flex-col gap-2 border-b border-slate-100 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <Link to={`/emails/${m.id}`} state={location.state} className="font-semibold text-slate-900 hover:underline">{m.sender_name || m.sender_email}</Link>
                <p className="text-xs text-slate-500">{formatDateTime(m.received_at)}</p>
              </div>
              <AnalysisIndicators analysis={m.analysis} />
            </div>
            <div className="p-5"><SafeEmailBody html={m.body_html_sanitized} text={m.body_text} /></div>
          </li>
        ))}
      </ol>
    </>
  );
}
