import type { ReactElement } from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { AnalysisSummary, InboxItem } from '@/shared/api/types';

export function renderWithProviders(ui: ReactElement, { route = '/', path = '*' } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes><Route path={path} element={ui} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export function analysis(over: Partial<AnalysisSummary> = {}): AnalysisSummary {
  return {
    status: 'COMPLETED', latest_status: 'COMPLETED', priority: 'HIGH', priority_confidence: 80,
    spam_likelihood: 4, reply_urgency: 91, category: 'CUSTOMER', sentiment: 'NEUTRAL', model: 'fake', model_version: 'fake',
    prompt_version: 'v1', analyzed_at: '2026-09-01T10:00:00Z', error: null, is_potential_spam: false,
    is_high_urgency: true, ...over,
  };
}

export function inboxItem(over: Partial<InboxItem> = {}): InboxItem {
  return {
    id: 1, thread_id: 't1', sender_name: 'Priya Shah', sender_email: 'priya@acme.com',
    subject: 'Production outage', snippet: 'We are down', received_at: '2026-09-01T10:00:00Z',
    is_read: false, has_attachments: true, thread_count: 1, analysis: analysis(), ...over,
  };
}
