import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Paginated } from '@/shared/api/client';

export type SyncStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'FAILED';
export type AccountStatus = 'ACTIVE' | 'REVOKED' | 'ERROR' | 'DISCONNECTED';

export interface Sync {
  id: number;
  type: 'INITIAL' | 'INCREMENTAL';
  status: SyncStatus;
  fetched_count: number;
  imported_count: number;
  failed_count: number;
  started_at: string | null;
  completed_at: string | null;
  error: string;
  created_at: string;
}

export interface GmailAccount {
  id: number;
  email: string;
  status: AccountStatus;
  last_synced_at: string | null;
  next_sync_at: string | null;
  last_error: string;
  created_at: string;
  latest_sync: Sync | null;
  sync_in_progress: boolean;
}

export interface GmailConnection {
  connected: boolean;
  account: GmailAccount | null;
  demo_mode: boolean;
}

export const CONNECT_URL = '/api/v1/integrations/gmail/connect';
export const gmailKey = ['gmail-connection'] as const;

/** Connection status; polls quickly while a sync is pending/running (progressive UI). */
export function useGmailConnection() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: gmailKey,
    queryFn: () => api.get<GmailConnection>('/integrations/gmail'),
    refetchInterval: (q) => (q.state.data?.account?.sync_in_progress ? 1000 : 10_000),
  });
  // When a sync finishes, refresh everything that shows synced mail.
  const prev = useRef<string | undefined>(undefined);
  const latest = query.data?.account?.latest_sync;
  const marker = latest ? `${latest.id}:${latest.status}` : undefined;
  useEffect(() => {
    if (prev.current && marker && prev.current !== marker && latest && !['PENDING', 'RUNNING'].includes(latest.status)) {
      qc.invalidateQueries({ queryKey: ['emails'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['gmail-syncs'] });
    }
    prev.current = marker;
  }, [marker, latest, qc]);
  return query;
}

export function useSyncHistory(accountId: number | undefined, poll: boolean) {
  return useQuery({
    queryKey: ['gmail-syncs', accountId],
    queryFn: () => api.get<Paginated<Sync>>(`/integrations/gmail/${accountId}/syncs`, { page_size: 10 }),
    enabled: !!accountId,
    refetchInterval: poll ? 1500 : 15_000,
  });
}

function useInvalidateGmail() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: gmailKey });
    qc.invalidateQueries({ queryKey: ['gmail-syncs'] });
    qc.invalidateQueries({ queryKey: ['dashboard'] });
  };
}

export function useSyncNow() {
  const invalidate = useInvalidateGmail();
  return useMutation({
    mutationFn: (accountId: number) => api.post<Sync>(`/integrations/gmail/${accountId}/sync`),
    onSettled: invalidate,
  });
}

export function useDisconnect() {
  const invalidate = useInvalidateGmail();
  return useMutation({
    mutationFn: (accountId: number) => api.delete<void>(`/integrations/gmail/${accountId}`),
    onSettled: invalidate,
  });
}

export function useDemoAction() {
  const invalidate = useInvalidateGmail();
  return useMutation({
    mutationFn: ({ accountId, action }: { accountId: number; action: 'new-messages' | 'revoke' | 'rate-limit' }) =>
      api.post<{ detail: string }>(`/demo/gmail/${accountId}/${action}`),
    onSettled: invalidate,
  });
}
