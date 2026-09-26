import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ensureCsrf } from '@/shared/api/client';

export interface AppSettings {
  spam_threshold_percent: number;
  urgency_threshold_percent: number;
  ai_provider: string;
  ai_provider_name: string;
  demo_mode: boolean;
}

export interface Me {
  id: number;
  email: string;
  name: string;
  created_at: string;
  settings: AppSettings;
}

export const meKey = ['me'] as const;

/** Current user, or null when not signed in (401). */
export function useMe() {
  return useQuery<Me | null>({
    queryKey: meKey,
    queryFn: async () => {
      const session = await api.get<{ authenticated: boolean; user: Me | null }>('/auth/session');
      return session.user;
    },
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => api.post<Me>('/auth/login', body),
    onSuccess: async (me) => {
      await ensureCsrf(true); // Django rotates the CSRF token on login
      qc.clear();
      qc.setQueryData(meKey, me);
    },
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; email: string; password: string }) =>
      api.post<Me>('/auth/register', body),
    onSuccess: async (me) => {
      await ensureCsrf(true);
      qc.clear();
      qc.setQueryData(meKey, me);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>('/auth/logout'),
    onSettled: async () => {
      qc.clear();
      qc.setQueryData(meKey, null);
      await ensureCsrf(true);
    },
  });
}

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: (body: { email: string }) => api.post<{ detail: string }>('/auth/password-reset', body),
  });
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: (body: { uid: string; token: string; new_password: string }) =>
      api.post<{ detail: string }>('/auth/password-reset/confirm', body),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string }) => api.patch<Me>('/me', body),
    onSuccess: (me) => qc.setQueryData(meKey, me),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api.post<{ detail: string }>('/me/password', body),
  });
}
