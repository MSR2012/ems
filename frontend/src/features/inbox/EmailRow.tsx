import { Link } from 'react-router-dom';
import type { InboxItem } from '@/shared/api/types';
import { AnalysisIndicators } from '@/features/email-analysis/AnalysisBadges';
import { RowAnalyzeButton } from '@/features/email-analysis/ReanalyzeButton';
import { IconPaperclip } from '@/shared/ui/icons';
import { formatDateTime, formatReceived } from '@/shared/lib/format';

export function EmailRow({ email, backTo }: { email: InboxItem; backTo?: string }) {
  const unread = !email.is_read;
  return (
    <li className={`group flex items-stretch transition hover:bg-slate-50 ${unread ? 'bg-white' : 'bg-slate-50/40'}`}>
      {/* The row link and the analyze action are siblings (no buttons nested inside links). */}
      <Link to={`/emails/${email.id}`} state={{ backTo }}
        className="flex min-w-0 flex-1 gap-3 py-3 pl-4 pr-2 focus:bg-slate-50 focus:outline-none sm:pl-5">
        <span className="mt-2 flex w-2.5 shrink-0 justify-center" aria-label={unread ? 'Unread' : 'Read'}>
          {unread && <span className="h-2.5 w-2.5 rounded-full bg-indigo-600" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <p className={`truncate text-sm ${unread ? 'font-semibold text-slate-900' : 'font-medium text-slate-600'}`}>
              {email.sender_name || email.sender_email}
              {email.thread_count > 1 && <span className="ml-1.5 text-xs font-normal text-slate-400">{email.thread_count}</span>}
            </p>
            <time className={`shrink-0 text-xs ${unread ? 'font-semibold text-slate-700' : 'text-slate-500'}`} dateTime={email.received_at} title={formatDateTime(email.received_at)}>
              {formatReceived(email.received_at)}
            </time>
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            <p className={`truncate text-sm ${unread ? 'font-medium text-slate-800' : 'text-slate-600'}`}>
              {email.subject || <span className="italic text-slate-400">(no subject)</span>}
            </p>
            {email.has_attachments && <IconPaperclip className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-label="Has attachments" />}
          </div>
          <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">{email.snippet}</p>
          <div className="mt-2"><AnalysisIndicators analysis={email.analysis} /></div>
        </div>
      </Link>
      <div className="flex shrink-0 items-end py-3 pr-4 sm:pr-5">
        <RowAnalyzeButton emailId={email.id} analysis={email.analysis} subject={email.subject} />
      </div>
    </li>
  );
}
