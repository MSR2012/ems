import { http, HttpResponse } from 'msw';
import { screen, within } from '@testing-library/react';
import { server } from '@/test/server';
import { inboxItem, renderWithProviders } from '@/test/utils';
import DashboardPage from './DashboardPage';

const summary = {
  counts: { total: 40, unread: 24, high_priority: 8, high_urgency: 5, potential_spam: 3 },
  analysis: { analyzed: 35, in_progress: 2, failed: 2, skipped: 1 },
  recent: [inboxItem({ id: 7, subject: 'Recent one' })],
  sync: { provider: 'gmail', connected: true, status: 'ACTIVE', email: 'demo@gmail.com', last_synced_at: new Date().toISOString(),
    latest_sync: { status: 'COMPLETED', type: 'INCREMENTAL' } },
  thresholds: { spam: 70, urgency: 70 },
};
const attention = {
  description: 'AI-based suggestion: excludes potential spam…', ai_suggestion: true, thresholds: { spam: 70, urgency: 70 }, total: 1,
  results: [{ email: { id: 1, sender_name: 'Priya', sender_email: 'p@x.com', subject: 'Outage', snippet: '', received_at: new Date().toISOString(), is_read: false },
    analysis: { priority: 'CRITICAL', priority_confidence: 80, reply_urgency: 100, spam_likelihood: 3, category: 'CUSTOMER', analyzed_at: null },
    reasons: ['Reply urgency 100%', 'Critical priority'] }],
};

describe('DashboardPage', () => {
  it('shows counters, Needs Attention labelled as AI suggestion, status and recent emails', async () => {
    server.use(
      http.get('/api/v1/auth/session', () => HttpResponse.json({ authenticated: true, user: null })),
      http.get('/api/v1/dashboard/summary', () => HttpResponse.json(summary)),
      http.get('/api/v1/dashboard/needs-attention', () => HttpResponse.json(attention)),
    );
    renderWithProviders(<DashboardPage />);
    const unread = await screen.findByRole('link', { name: /Not yet read/ });
    expect(within(unread).getByText('24')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Potential spam/ })).toHaveAttribute('href', '/inbox?spam_likelihood_min=70');
    expect(screen.getByRole('link', { name: /High urgency/ })).toHaveTextContent('Reply urgency ≥ 70%');
    expect(await screen.findByText('AI-based suggestion')).toBeInTheDocument();
    expect(screen.getByText('Outage')).toBeInTheDocument();
    expect(screen.getByText('35 of 40 analyzed')).toBeInTheDocument();
    expect(screen.getByText('Recent one')).toBeInTheDocument();
  });
});
