import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useMe } from '@/features/auth/api';
import { api, ApiError } from '@/shared/api/client';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import { Alert } from '@/shared/ui/feedback';
import { IconSparkles } from '@/shared/ui/icons';

interface BulkAnalyzeResponse { status: string; provider: string; model: string; prompt_version: string; force: boolean }

/** Queues AI analysis of the user's inbox in the backend (Celery `analysis` queue). */
export function BulkAnalyzeButton({ variant = 'secondary' }: { variant?: 'primary' | 'secondary' }) {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [force, setForce] = useState(false);
  const analyze = useMutation({
    mutationFn: (body: { force: boolean }) => api.post<BulkAnalyzeResponse>('/emails/analyze', body),
    onSuccess: () => {
      // Inbox and dashboard poll while analyses are in flight, so progress shows up live.
      const refresh = () => {
        qc.invalidateQueries({ queryKey: ['emails'] });
        qc.invalidateQueries({ queryKey: ['dashboard'] });
      };
      refresh();
      setTimeout(refresh, 300); // the fan-out task creates the PENDING rows a moment later
    },
  });
  const provider = me?.settings.ai_provider_name.replace(/\s*\(.*\)$/, '') ?? 'AI';
  const error = analyze.error instanceof ApiError && analyze.error.status === 429
    ? 'Analysis was just requested — please wait a minute before trying again.'
    : analyze.error ? 'Could not queue the analysis. Please try again.' : null;

  return (
    <div className="flex flex-col items-stretch gap-2 sm:items-end">
      <button type="button" className={variant === 'primary' ? 'btn-primary' : 'btn-secondary'}
        disabled={analyze.isPending} onClick={() => { setForce(false); setOpen(true); }}>
        <IconSparkles className="h-4 w-4" /> Analyze with {provider}
      </button>
      {analyze.isSuccess && (
        <Alert tone="success">
          Analysis queued{analyze.data.force ? ' for all emails' : ''} ({analyze.data.model}, prompt {analyze.data.prompt_version}).
          Results appear as each email finishes.
        </Alert>
      )}
      {error && <Alert tone="error">{error}</Alert>}
      <ConfirmDialog
        open={open}
        title={`Analyze your inbox with ${provider}?`}
        confirmLabel="Queue analysis"
        busy={analyze.isPending}
        onCancel={() => setOpen(false)}
        onConfirm={() => analyze.mutate({ force }, { onSettled: () => setOpen(false) })}
      >
        <p>
          Emails that haven't been analyzed with the current model and prompt version — or whose analysis failed — are
          queued for analysis in the background. You can keep using the app meanwhile.
        </p>
        <label className="mt-4 flex items-start gap-2 text-slate-700">
          <input type="checkbox" className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600"
            checked={force} onChange={(e) => setForce(e.target.checked)} />
          <span>Also re-analyze emails that already have results</span>
        </label>
      </ConfirmDialog>
    </div>
  );
}
