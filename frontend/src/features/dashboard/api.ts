import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import type { DashboardSummary, NeedsAttention } from '@/shared/api/types';

export function useDashboardSummary() {
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => api.get<DashboardSummary>('/dashboard/summary'),
    // Poll fast while a sync or analyses are in flight; otherwise refresh every 30s.
    refetchInterval: (q) => {
      const d = q.state.data;
      const busy = d && (d.analysis.in_progress > 0 || ['PENDING', 'RUNNING'].includes(String(d.sync?.latest_sync?.status ?? '')));
      return busy ? 3000 : 30_000;
    },
  });
}

export function useNeedsAttention() {
  return useQuery({
    queryKey: ['dashboard', 'needs-attention'],
    queryFn: () => api.get<NeedsAttention>('/dashboard/needs-attention', { limit: 8 }),
    refetchInterval: 15_000,
  });
}
