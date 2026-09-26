import { Badge } from '@/shared/ui/Badge';
import { Spinner } from '@/shared/ui/feedback';
import type { AnalysisSummary, Category, Priority } from '@/shared/api/types';
import { CATEGORY_META, PRIORITY_META } from './labels';

const AI = 'AI suggestion — not a fact';

export function PriorityBadge({ priority }: { priority: Priority }) {
  const m = PRIORITY_META[priority];
  return <Badge tone={m.tone} title={`Priority (${AI})`}>{m.label}</Badge>;
}

export function CategoryBadge({ category }: { category: Category }) {
  const m = CATEGORY_META[category];
  return <Badge tone={m.tone} title={`Category (${AI})`}>{m.label}</Badge>;
}

export function UrgencyBadge({ value, high }: { value: number; high: boolean }) {
  return (
    <Badge tone={high ? 'orange' : 'slate'} title={`Reply urgency ${value}% (${AI})`}>
      <span aria-hidden="true">↩</span> {value}%
    </Badge>
  );
}

export function SpamBadge({ value, flagged }: { value: number; flagged: boolean }) {
  return (
    <Badge tone={flagged ? 'red' : 'slate'} title={`Spam likelihood ${value}%${flagged ? ' — potential spam' : ''} (${AI})`}
      className={flagged ? 'font-semibold' : ''}>
      {flagged ? 'Spam?' : 'Spam'} {value}%
    </Badge>
  );
}

function isInFlight(s: string) {
  return s === 'PENDING' || s === 'RUNNING';
}

/** Compact AI indicators for list rows. */
export function AnalysisIndicators({ analysis }: { analysis: AnalysisSummary | null }) {
  if (!analysis || isInFlight(analysis.status)) {
    return (
      <Badge tone="blue" title="AI analysis in progress">
        <Spinner className="h-3 w-3" /> Analyzing
      </Badge>
    );
  }
  if (analysis.status === 'FAILED') {
    return <Badge tone="amber" title={analysis.error ?? 'Analysis failed'}>Analysis failed</Badge>;
  }
  if (analysis.status === 'SKIPPED') {
    return <Badge tone="slate" title={analysis.error ?? 'Not eligible for analysis'}>Not analyzed</Badge>;
  }
  return (
    <div className="flex flex-wrap items-center gap-1">
      {analysis.priority && <PriorityBadge priority={analysis.priority} />}
      {analysis.category && <CategoryBadge category={analysis.category} />}
      {analysis.reply_urgency !== null && <UrgencyBadge value={analysis.reply_urgency} high={analysis.is_high_urgency} />}
      {analysis.spam_likelihood !== null && <SpamBadge value={analysis.spam_likelihood} flagged={analysis.is_potential_spam} />}
      {isInFlight(analysis.latest_status) && (
        <Badge tone="blue" title="Re-analysis in progress"><Spinner className="h-3 w-3" /> Re-analyzing</Badge>
      )}
    </div>
  );
}

export function hasAnalysisInFlight(a: AnalysisSummary | null | undefined): boolean {
  return !a || isInFlight(a.status) || isInFlight(a.latest_status);
}
