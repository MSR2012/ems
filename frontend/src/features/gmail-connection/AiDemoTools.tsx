import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';

const MODES = [
  { value: 'none', label: 'Healthy (no failures)' },
  { value: 'invalid_json', label: 'Malformed JSON' },
  { value: 'bad_enum', label: 'Unknown enum value' },
  { value: 'out_of_range', label: 'Percentage out of range' },
  { value: 'timeout', label: 'Provider timeout' },
] as const;

/** Demo-mode control for simulating AI provider failures (validation, retries, FAILED state). */
export function AiDemoTools() {
  const qc = useQueryClient();
  const { data, isError } = useQuery({
    queryKey: ['demo-ai-failure-mode'],
    queryFn: () => api.get<{ mode: string }>('/demo/ai/failure-mode'),
    retry: false,
  });
  const set = useMutation({
    mutationFn: (mode: string) => api.post<{ mode: string }>('/demo/ai/failure-mode', { mode }),
    onSuccess: (d) => qc.setQueryData(['demo-ai-failure-mode'], d),
  });
  if (isError || !data) return null;
  return (
    <div className="mt-5 border-t border-indigo-100 pt-4">
      <label htmlFor="ai-failure-mode" className="label text-indigo-900">Simulated AI behaviour</label>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <select id="ai-failure-mode" className="input sm:max-w-xs" value={data.mode} disabled={set.isPending}
          onChange={(e) => set.mutate(e.target.value)}>
          {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
        <p className="text-xs text-indigo-900/70">
          Invalid output is rejected and retried with backoff, then marked failed — nothing invalid is stored and emails stay viewable.
        </p>
      </div>
    </div>
  );
}
