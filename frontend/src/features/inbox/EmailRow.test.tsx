import { http, HttpResponse } from 'msw';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { server } from '@/test/server';
import { analysis, inboxItem, renderWithProviders } from '@/test/utils';
import { EmailRow } from './EmailRow';

function row(item = inboxItem()) {
  return <ul><EmailRow email={item} /></ul>;
}

describe('EmailRow analyze action', () => {
  it('queues analysis for that email without navigating', async () => {
    let called = 0;
    server.use(
      http.get('/api/v1/auth/csrf', () => HttpResponse.json({})),
      http.post('/api/v1/emails/42/reanalyze', () => { called += 1; return HttpResponse.json({ status: 'PENDING' }, { status: 202 }); }),
    );
    renderWithProviders(row(inboxItem({ id: 42, subject: 'Outage' })));
    const btn = screen.getByRole('button', { name: 'Re-analyze email: Outage' });
    expect(btn.closest('a')).toBeNull(); // not nested inside the row link
    await userEvent.click(btn);
    await screen.findByRole('button', { name: /Outage/ });
    expect(called).toBe(1);
    expect(screen.getByRole('link')).toHaveAttribute('href', '/emails/42');
  });

  it('says Analyze when there is no result yet and is disabled while in flight', () => {
    const { unmount } = renderWithProviders(row(inboxItem({ analysis: analysis({ status: 'FAILED', priority: null }) })));
    expect(screen.getByRole('button', { name: /^Analyze email/ })).toBeEnabled();
    unmount();
    renderWithProviders(row(inboxItem({ analysis: analysis({ latest_status: 'PENDING' }) })));
    expect(screen.getByRole('button', { name: /Analyzing… email/ })).toBeDisabled();
  });
});
