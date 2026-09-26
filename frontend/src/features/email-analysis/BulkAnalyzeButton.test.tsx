import { http, HttpResponse } from 'msw';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { server } from '@/test/server';
import { renderWithProviders } from '@/test/utils';
import { BulkAnalyzeButton } from './BulkAnalyzeButton';

const me = { id: 1, email: 'd@x.com', name: 'D', created_at: '2026-01-01T00:00:00Z',
  settings: { spam_threshold_percent: 70, urgency_threshold_percent: 70, ai_provider: 'jev_ai', ai_provider_name: 'Jev AI', demo_mode: false } };

describe('BulkAnalyzeButton', () => {
  it('confirms, posts to the backend queue endpoint with the force option, and reports queued', async () => {
    let body: unknown;
    server.use(
      http.get('/api/v1/auth/session', () => HttpResponse.json({ authenticated: true, user: me })),
      http.get('/api/v1/auth/csrf', () => HttpResponse.json({ detail: 'ok' })),
      http.post('/api/v1/emails/analyze', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ status: 'queued', provider: 'jev_ai', model: 'jev-latest', prompt_version: 'v1', force: true }, { status: 202 });
      }),
    );
    renderWithProviders(<BulkAnalyzeButton />);
    await userEvent.click(await screen.findByRole('button', { name: /Analyze with Jev AI/ }));
    expect(screen.getByRole('dialog')).toHaveTextContent('Analyze your inbox with Jev AI?');
    await userEvent.click(screen.getByLabelText(/re-analyze emails that already have results/));
    await userEvent.click(screen.getByRole('button', { name: 'Queue analysis' }));
    expect(await screen.findByText(/Analysis queued for all emails \(jev-latest, prompt v1\)/)).toBeInTheDocument();
    expect(body).toEqual({ force: true });
  });
});
