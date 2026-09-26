import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ErrorState, LoadingState } from '@/shared/ui/feedback';
import { useMe } from './api';

/** Frontend route guard: unauthenticated visitors are redirected to /login (backend enforces too). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: me, isLoading, isError, refetch } = useMe();
  const location = useLocation();
  if (isLoading) return <div className="min-h-screen"><LoadingState label="Loading your workspace…" /></div>;
  if (isError) return <div className="mx-auto max-w-lg p-6"><ErrorState message="Could not reach the server." onRetry={() => refetch()} /></div>;
  if (!me) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`} replace />;
  }
  return <>{children}</>;
}

/** Login/register pages redirect signed-in users to the app. */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { data: me, isLoading } = useMe();
  if (isLoading) return <div className="min-h-screen"><LoadingState /></div>;
  if (me) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/';
}
