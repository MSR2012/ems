import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import type { EmailDetail, ThreadDetail } from '@/shared/api/types';
import { hasAnalysisInFlight } from '@/features/email-analysis/AnalysisBadges';

export function useEmail(id: number) {
  return useQuery({
    queryKey: ['emails', 'detail', id],
    queryFn: () => api.get<EmailDetail>(`/emails/${id}`),
    enabled: Number.isFinite(id),
    refetchInterval: (q) => (q.state.data && hasAnalysisInFlight(q.state.data.analysis) ? 2000 : false),
  });
}

export function useThread(threadId: string) {
  return useQuery({
    queryKey: ['emails', 'thread', threadId],
    queryFn: () => api.get<ThreadDetail>(`/threads/${encodeURIComponent(threadId)}`),
    enabled: !!threadId,
  });
}
