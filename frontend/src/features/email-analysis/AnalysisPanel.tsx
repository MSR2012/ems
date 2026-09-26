import type { ReactNode } from 'react';
import type { AnalysisSummary } from '@/shared/api/types';
import { Spinner } from '@/shared/ui/feedback';
import { IconSparkles } from '@/shared/ui/icons';
import { formatDateTime } from '@/shared/lib/format';
import { CategoryBadge, PriorityBadge } from './AnalysisBadges';

function Meter({ label, value, flagged, hint }: { label: string; value: number; flagged: boolean; hint: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className={`font-semibold tabular-nums ${flagged ? 'text-rose-600' : 'text-slate-800'}`}>{value}%</span>
      </div>
      <div className="mt-1.5 h-2 rounded-full bg-slate-100" role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-2 rounded-full ${flagged ? 'bg-rose-500' : 'bg-indigo-500'}`} style={{ width: `${value}%` }} />
      </div>
      {flagged && <p className="mt-1 text-xs text-rose-600">{hint}</p>}
    </div>
  );
}

export function AnalysisPanel({ analysis, actions }: { analysis: AnalysisSummary | null; actions?: ReactNode }) {
  const inFlight = !analysis || ['PENDING', 'RUNNING'].includes(analysis.status);
  return (
    <section className="card p-5" aria-labelledby="ai-title">
      <div className="flex items-center justify-between gap-2">
        <h2 id="ai-title" className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          <IconSparkles className="h-4 w-4 text-indigo-500" /> AI analysis
        </h2>
        {actions}
      </div>
      <p className="mt-1 text-xs text-slate-500">AI suggestions, not facts. They never change your Gmail.</p>
      <div className="mt-4 space-y-4">
        {inFlight ? (
          <p className="flex items-center gap-2 text-sm text-slate-600"><Spinner className="h-4 w-4" /> Analyzing this email…</p>
        ) : analysis.status === 'FAILED' ? (
          <p className="text-sm text-amber-700">Analysis failed{analysis.error ? `: ${analysis.error}` : ''}. The email is still fully available.</p>
        ) : analysis.status === 'SKIPPED' ? (
          <p className="text-sm text-slate-600">Not analyzed{analysis.error ? ` — ${analysis.error}` : ''}.</p>
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-slate-500">Priority</dt>
                <dd className="mt-1 flex items-center gap-1.5">
                  {analysis.priority && <PriorityBadge priority={analysis.priority} />}
                  {analysis.priority_confidence !== null && <span className="text-xs text-slate-500">{analysis.priority_confidence}% confidence</span>}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Category</dt>
                <dd className="mt-1">{analysis.category && <CategoryBadge category={analysis.category} />}</dd>
              </div>
            </dl>
            {analysis.reply_urgency !== null && (
              <Meter label="Reply urgency" value={analysis.reply_urgency} flagged={analysis.is_high_urgency} hint="High reply urgency" />
            )}
            {analysis.spam_likelihood !== null && (
              <Meter label="Spam likelihood" value={analysis.spam_likelihood} flagged={analysis.is_potential_spam} hint="Potential spam — never deleted automatically" />
            )}
          </>
        )}
        {analysis && ['PENDING', 'RUNNING'].includes(analysis.latest_status) && analysis.status === 'COMPLETED' && (
          <p className="flex items-center gap-2 text-xs text-indigo-700"><Spinner className="h-3 w-3" /> Re-analysis in progress…</p>
        )}
        {analysis && (
          <p className="border-t border-slate-100 pt-3 text-xs text-slate-400">
            Model {analysis.model}{analysis.model_version && analysis.model_version !== analysis.model ? ` (${analysis.model_version})` : ''} · prompt {analysis.prompt_version}
            {analysis.analyzed_at && <> · {formatDateTime(analysis.analyzed_at)}</>}
          </p>
        )}
      </div>
    </section>
  );
}
