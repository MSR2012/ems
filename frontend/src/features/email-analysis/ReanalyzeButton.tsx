import { useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/shared/api/client';
import type { AnalysisSummary } from '@/shared/api/types';
import { Spinner } from '@/shared/ui/feedback';
import { IconCheck, IconRefresh, IconSparkles } from '@/shared/ui/icons';

/** Queues analysis of one email in the backend (POST /emails/{id}/reanalyze → analysis queue). */
export function useReanalyze(emailId: number, analysis: AnalysisSummary | null) {
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.post<{ status: string }>(`/emails/${emailId}/reanalyze`),
    onSuccess: () => {
      // List/detail/dashboard poll while an analysis is in flight, so the result appears live.
      qc.invalidateQueries({ queryKey: ['emails'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
  const inFlight = !!analysis && (['PENDING', 'RUNNING'].includes(analysis.status)
    || ['PENDING', 'RUNNING'].includes(analysis.latest_status));
  const errorText = mutation.error instanceof ApiError && mutation.error.status === 429
    ? 'Too many requests — try again shortly.' : mutation.error ? 'Could not queue analysis.' : null;
  return { mutation, busy: mutation.isPending || inFlight, errorText };
}

export function ReanalyzeButton({ emailId, analysis }: { emailId: number; analysis: AnalysisSummary | null }) {
  const { mutation, busy, errorText } = useReanalyze(emailId, analysis);
  return (
    <div className="flex flex-col items-end">
      <button type="button" className="btn-ghost px-2 py-1 text-xs" disabled={busy} onClick={() => mutation.mutate()}
        title="Run the AI analysis again with the current model and prompt">
        {busy ? <Spinner className="h-3.5 w-3.5" /> : <IconRefresh className="h-3.5 w-3.5" />} Re-analyze
      </button>
      {errorText && <span role="alert" className="text-xs text-rose-600">{errorText}</span>}
    </div>
  );
}

/** Compact per-row action for email lists. */
export function RowAnalyzeButton({ emailId, analysis, subject }: {
  emailId: number; analysis: AnalysisSummary | null; subject: string;
}) {
  const { mutation, busy, errorText } = useReanalyze(emailId, analysis);
  // Brief confirmation after queueing (fast providers may finish before the list refreshes).
  const { isSuccess, reset } = mutation;
  useEffect(() => {
    if (!isSuccess) return;
    const t = setTimeout(reset, 2000);
    return () => clearTimeout(t);
  }, [isSuccess, reset]);
  const hasResult = analysis?.status === 'COMPLETED';
  const queued = isSuccess && !busy;
  const label = busy ? 'Analyzing…' : queued ? 'Queued' : hasResult ? 'Re-analyze' : 'Analyze';
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-indigo-600 ring-1 ring-inset ring-indigo-200 transition hover:bg-indigo-50 disabled:cursor-not-allowed disabled:text-slate-400 disabled:ring-slate-200 disabled:hover:bg-transparent"
        disabled={busy || queued}
        onClick={() => mutation.mutate()}
        aria-label={`${label} email: ${subject || '(no subject)'}`}
        title="Queue AI analysis of this email with the current model and prompt"
      >
        {busy ? <Spinner className="h-3 w-3" /> : queued ? <IconCheck className="h-3 w-3" />
          : hasResult ? <IconRefresh className="h-3 w-3" /> : <IconSparkles className="h-3 w-3" />}
        <span className="hidden sm:inline">{label}</span>
      </button>
      {errorText && <span role="alert" className="max-w-[10rem] text-right text-xs text-rose-600">{errorText}</span>}
    </div>
  );
}
