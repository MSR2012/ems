import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/shared/api/client';

export function createQueryClient() {
  // A 401 anywhere means the session ended: drop the cached user so route guards redirect.
  const onError = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) client.setQueryData(['me'], null);
  };
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        retry: (count, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
          return count < 2;
        },
      },
    },
  });
  return client;
}
