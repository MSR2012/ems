import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

/** Default handlers every test gets (override per test with server.use). */
export const defaultHandlers = [
  http.get('/api/v1/auth/session', () => HttpResponse.json({ authenticated: false, user: null })),
  http.get('/api/v1/integrations/gmail', () =>
    HttpResponse.json({ connected: true, demo_mode: true, account: null })),
];

export const server = setupServer(...defaultHandlers);
