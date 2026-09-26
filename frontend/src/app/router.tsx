import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { GuestOnly, RequireAuth } from '@/features/auth/guards';
import { AppLayout } from './AppLayout';

// Code-split routes (§26).
const LoginPage = lazy(() => import('@/features/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage'));
const PasswordResetPage = lazy(() => import('@/features/auth/PasswordResetPage'));
const PasswordResetConfirmPage = lazy(() => import('@/features/auth/PasswordResetConfirmPage'));
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'));
const InboxPage = lazy(() => import('@/features/inbox/InboxPage'));
const EmailDetailPage = lazy(() => import('@/features/email-detail/EmailDetailPage'));
const ThreadPage = lazy(() => import('@/features/email-detail/ThreadPage'));
const IntegrationsPage = lazy(() => import('@/features/gmail-connection/IntegrationsPage'));
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage'));

export const router = createBrowserRouter([
  { path: '/login', element: <GuestOnly><LoginPage /></GuestOnly> },
  { path: '/register', element: <GuestOnly><RegisterPage /></GuestOnly> },
  { path: '/password-reset', element: <PasswordResetPage /> },
  { path: '/password-reset/confirm', element: <PasswordResetConfirmPage /> },
  {
    element: <RequireAuth><AppLayout /></RequireAuth>,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/inbox', element: <InboxPage /> },
      { path: '/emails/:id', element: <EmailDetailPage /> },
      { path: '/threads/:threadId', element: <ThreadPage /> },
      { path: '/integrations', element: <IntegrationsPage /> },
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
], {
  future: { v7_relativeSplatPath: true, v7_fetcherPersist: true, v7_normalizeFormMethod: true, v7_partialHydration: true, v7_skipActionErrorRevalidation: true },
});
