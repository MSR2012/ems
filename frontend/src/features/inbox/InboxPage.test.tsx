import { http, HttpResponse } from 'msw';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { server } from '@/test/server';
import { inboxItem, renderWithProviders } from '@/test/utils';
import InboxPage from './InboxPage';

function page(results = [inboxItem()], count = results.length) {
  return { count, page: 1, page_size: 20, next: null, previous: null, thresholds: { spam: 70, urgency: 70 }, results };
}

describe('InboxPage', () => {
  it('lists emails with sender, subject and AI indicators', async () => {
    server.use(http.get('/api/v1/emails', () => HttpResponse.json(page())));
    renderWithProviders(<InboxPage />);
    expect(await screen.findByText('Priya Shah')).toBeInTheDocument();
    expect(screen.getByText('Production outage')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByLabelText('Unread')).toBeInTheDocument();
  });

  it('passes URL filters to the API', async () => {
    let seen: URL | undefined;
    server.use(http.get('/api/v1/emails', ({ request }) => { seen = new URL(request.url); return HttpResponse.json(page()); }));
    renderWithProviders(<InboxPage />, { route: '/inbox?priority=CRITICAL,HIGH&hide_potential_spam=true&page=2' });
    await screen.findByText('Priya Shah');
    expect(seen?.searchParams.get('priority')).toBe('CRITICAL,HIGH');
    expect(seen?.searchParams.get('hide_potential_spam')).toBe('true');
    expect(seen?.searchParams.get('page')).toBe('2');
    expect(seen?.searchParams.get('page_size')).toBe('20');
    expect(screen.getByText('Hiding potential spam')).toBeInTheDocument();
  });

  it('debounces search into the query', async () => {
    const queries: string[] = [];
    server.use(http.get('/api/v1/emails', ({ request }) => {
      queries.push(new URL(request.url).searchParams.get('q') ?? '');
      return HttpResponse.json(page());
    }));
    renderWithProviders(<InboxPage />, { route: '/inbox' });
    await screen.findByText('Priya Shah');
    await userEvent.type(screen.getByLabelText('Search emails'), 'acme');
    await waitFor(() => expect(queries).toContain('acme'));
    expect(queries).not.toContain('a');
  });

  it('shows an empty state for no matches and an error state on failure', async () => {
    server.use(http.get('/api/v1/emails', () => HttpResponse.json(page([], 0))));
    const { unmount } = renderWithProviders(<InboxPage />, { route: '/inbox?q=zzz' });
    expect(await screen.findByText('No emails match')).toBeInTheDocument();
    unmount();
    server.use(http.get('/api/v1/emails', () => HttpResponse.json({ detail: 'boom' }, { status: 500 })));
    renderWithProviders(<InboxPage />, { route: '/inbox' });
    expect(await screen.findByText('Something went wrong', {}, { timeout: 5000 })).toBeInTheDocument();
  });
});
