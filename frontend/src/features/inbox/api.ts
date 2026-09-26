import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import type { InboxPage } from '@/shared/api/types';
import { hasAnalysisInFlight } from '@/features/email-analysis/AnalysisBadges';
import { filtersToParams, type InboxFilters } from './filters';
import { useGmailConnection } from '@/features/gmail-connection/api';

export const PAGE_SIZE = 20;

export function useInbox(filters: InboxFilters) {
  const params = { ...filtersToParams(filters), page_size: PAGE_SIZE };
  const syncing = !!useGmailConnection().data?.account?.sync_in_progress;
  return useQuery({
    queryKey: ['emails', 'list', params],
    queryFn: ({ signal }) => api.get<InboxPage>('/emails', params, signal),
    placeholderData: keepPreviousData,
    // Progressive analysis: keep polling while any visible email is still being analyzed.
    refetchInterval: (q) => (syncing || q.state.data?.results.some((r) => hasAnalysisInFlight(r.analysis)) ? 2500 : 30_000),
  });
}
