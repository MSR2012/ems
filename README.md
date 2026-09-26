# Inbox AI — AI Email Management Platform (MVP)

An AI-assisted layer on top of Gmail. It connects a Gmail account over OAuth, syncs the inbox in the
background, analyzes each email (priority, category, spam likelihood %, reply urgency %) and surfaces
what needs attention. It never sends, deletes, archives or modifies Gmail messages.

**Stack:** Django 5 + DRF (DDD modular monolith) · React 18 + TypeScript + Vite + TanStack Query +
Tailwind · PostgreSQL 16 · Redis + Celery (worker + Beat) · Gmail API · Jev AI, both behind ports.
**Demo mode** (fake Gmail + fake AI) is the default and needs **no external credentials**.

## Quick start

```bash
make up          # = docker compose up -d --build   (migrates + seeds demo data automatically)
```

Open **http://localhost:5173** and sign in as **demo@example.com / DemoPass123!**, or register a new
account and connect the demo Gmail yourself.

The first start installs npm packages in the frontend container, which takes about a minute. To
check readiness, run `make ps` and `curl http://localhost:5173/api/v1/health`. The health endpoint
reports the database, Redis and Celery worker.

| Command | Purpose |
|---|---|
| `make up` / `make down` | Start / stop the whole stack |
| `make logs` | Follow all service logs (structured JSON, bodies/tokens redacted) |
| `make seed` | Re-run the idempotent demo seed |
| `make test` | Backend tests (pytest: unit, integration, API, security) |
| `make lint` | ruff + import-linter (DDD layer contracts) |
| `make lint-frontend` | ESLint + TypeScript strict type-check |
| `make test-frontend` | Vitest + React Testing Library + MSW |
| `make e2e` | Playwright end-to-end tests against the running stack (desktop + mobile) |
| `make check-bundle` | Production build + assert no token material in the JS bundle |
| `make test-all` | All of the above |

Services: `db`, `redis`, `api` (Django, :8000), `worker` (Celery queues `sync`, `analysis`, `default`),
`beat` (Celery Beat), `frontend` (Vite, :5173). The frontend proxies `/api` to the API, so the SPA and
API are same-origin (session cookie + CSRF). API docs: http://localhost:5173/api/v1/docs.

## Demo walkthrough

1. **Register** (or use the demo user). The dashboard asks you to connect Gmail.
2. **Integrations → Connect Gmail.** A simulated Google consent screen opens. It never asks for a
   password. Choose **Allow**. You return to *Connected*, and the initial sync moves
   `Pending → Running → Completed` live.
3. **Inbox.** Emails appear right away with an *Analyzing* badge. Priority, category, reply urgency %
   and spam % fill in as analysis completes. Search and filter; filters live in the URL, so you can
   reload or share the link.
4. **Open an email.** The body is shown sanitized in a sandboxed iframe. Remote images and scripts are
   blocked. You also see the thread, attachment metadata and the AI panel with **Re-analyze**.
   Try *"Your weekly account summary (HTML test)"*, which is a malicious-HTML sample.
5. **Dashboard.** Counts (inbox, unread, critical/high, high urgency, potential spam), *Needs attention*
   (labelled as an AI suggestion), sync/analysis status and recent emails.
6. **Demo tools** (Integrations page):
   - *Deliver 3 new emails*: the next sync is `INCREMENTAL` and imports only those.
   - *Simulate Gmail rate limit (429)*: the failed attempts appear in sync history and are retried
     with backoff.
   - *Simulate revoked authorization*: the account becomes *Revoked*, scheduled syncs stop, and a
     *Reconnect* prompt appears.
   - *Simulated AI behaviour*: malformed JSON, an unknown enum, an out-of-range percentage, or a
     timeout. The output is rejected, retried, then marked *Analysis failed*. Nothing invalid is
     stored, and the email stays viewable.
7. **Disconnect** deletes the stored credentials. **Sign out** returns you to login.

**Analyze with Jev AI** (Inbox header, or Settings → AI analysis & privacy) queues your inbox for
analysis in the backend. `POST /api/v1/emails/analyze` returns 202 right away. A Celery task
(`email_intelligence.reanalyze_emails`, `analysis` queue) then creates the pending analyses and
enqueues one `analyze_email` job per email. By default it covers emails with no analysis for the
active model/prompt version, plus failed ones. Tick *Also re-analyze emails that already have
results* (`force`) to re-run everything. Progress shows live in the inbox and dashboard. The command
does the same:

```bash
docker compose exec api python manage.py reanalyze_emails [--user-id N] [--force]
```

Each email row (inbox and the dashboard's recent emails) also has an **Analyze / Re-analyze** button.
It queues just that email (`POST /api/v1/emails/{id}/reanalyze` → `analyze_email` on the `analysis`
queue). The row shows *Analyzing…* until the result arrives, without leaving the list.

To change the prompt version and re-analyze everything:

```bash
AI_PROMPT_VERSION=v2 docker compose up -d api worker
docker compose exec api python manage.py reanalyze_emails
```

This creates new analysis rows, which become the current analysis.

## Architecture

```
backend/src/
  shared_kernel/        Entity, AggregateRoot, DomainEvent, UnitOfWork (events dispatched on commit),
                        event bus, Fernet TokenCipher (key rotation), log redaction, health, metrics
  identity/             users, session auth, password reset, profile
  gmail_integration/    GmailAccount, EmailSync aggregates; OAuth; sync use cases; Gmail ACL
                        (GoogleGmailGateway + FakeGmailGateway); Celery sync tasks + Beat dispatch
  mailbox_context/      Email aggregate (provider-neutral); ImportEmail; inbox/detail/thread/dashboard
                        query services; HTML sanitization (nh3); published facade for other contexts
  email_intelligence/   EmailAnalysis, Priority/Category, Percentage, AttentionPolicy; AnalyzeEmail
                        pipeline; AIClassifier port (JevAIClassifier + FakeClassifier); Pydantic
                        output schema; versioned prompts; analysis tasks
  demo/                 seed_demo command (dev tooling, not a bounded context)
```

Each context has `domain/` (pure Python, no Django), `application/` (use cases and ports, no Django),
`infrastructure/` (ORM, adapters, Celery) and `interfaces/api/` (DRF). The rules are enforced by
**import-linter** (`backend/.importlinter`, 7 contracts):

- Domain and application layers are framework-free.
- Mailbox never imports other contexts.
- Gmail Integration and Email Intelligence reach Mailbox only through
  `mailbox_context.application.facade` (the `ImportEmail` command, content queries, the
  `EmailImported` event).
- Mailbox reads analysis results through the `current_email_analyses` database view, which Email
  Intelligence publishes.

Key flows:

- **Connect:** OAuth `state` is stored in the session and checked on the callback. Tokens are
  encrypted and never serialized. `GmailAccountConnected` → `RequestSync` → Celery
  `gmail_integration.sync_gmail_account`.
- **Sync:** a per-account Redis lock prevents concurrent runs. The initial sync covers a bounded
  window (30 days). Incremental syncs use `history.list`; an expired history id falls back to a
  bounded full re-sync. Upserts are idempotent (`UNIQUE(mail_account_id, external_message_id)`).
  Rate limits and outages are retried with exponential backoff and jitter. A revoked authorization
  marks the account `REVOKED`.
- **Analysis:** `EmailImported` → `RequestAnalysis` (PENDING row) → `email_intelligence.analyze_email`
  on the `analysis` queue. The pipeline strips quoted text and signatures, applies a size limit, and
  passes the email only as `state` data, never inside the question instructions. The provider's output is validated by Pydantic
  (strict enums, integers 0–100) before a domain object is created. Every call writes an
  `ai_usage_logs` row (tokens, duration, no content). Beat re-queues stale analyses.
- **Needs Attention** is an explicit product rule (`AttentionPolicy`): exclude potential spam; include
  emails with reply urgency ≥ threshold or priority CRITICAL/HIGH; sort by urgency, then priority,
  then unread first, then newest.

### Jev AI integration

`JevAIClassifier` (`email_intelligence/infrastructure/ai/jev_ai.py`) implements the
[Jev AI System One API](https://thejevai.com/docs#quickstart):
`POST https://thejevai.com/v1/systemone` with `Authorization: Bearer sk_…`, a `state` (the email as
data), `model` (`jev-latest`) and typed `questions` (versioned per `AI_PROMPT_VERSION` in
`ai/prompts.py`). Answers map to the domain as follows (all percentages are integers 0–100):

| Field | Jev question | Mapping |
|---|---|---|
| priority (+ confidence) | `choice` CRITICAL/HIGH/NORMAL/LOW | chosen option; confidence = its probability × 100 |
| category | `choice` over the 12 categories | chosen option |
| spam likelihood % | `noul` "spam or phishing?" | P(yes) × 100 |
| reply urgency % | `score` over 5 urgency levels (0 = no reply … 4 = reply immediately) | score ÷ 4 × 100 |
| sentiment | `choice` POSITIVE/NEUTRAL/NEGATIVE | chosen option |

- The translated answers go through the same strict Pydantic schema as every provider. Unknown
  options or out-of-range numbers are rejected.
- The concrete model version Jev reports (e.g. `jev-1.13.0`) is stored in `model_version`, shown in
  the UI and recorded in `ai_usage_logs`.
- 429/529/5xx errors and timeouts are retried with backoff. 401 (invalid key) and 422 fail
  immediately with a clear error.

To use it:

```bash
JEV_AI_API_KEY=sk_... AI_PROVIDER=jev_ai docker compose up -d api worker
docker compose exec api python manage.py reanalyze_emails   # analyze existing mail with Jev AI
```

`JEV_API_KEY` (the name used in the Jev docs) is accepted as an alias. `JEV_AI_BASE_URL` defaults to
`https://thejevai.com/v1/systemone` and `JEV_AI_MODEL` to `jev-latest`.

### Real Gmail

Set `GMAIL_GATEWAY=google`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` and
`GOOGLE_OAUTH_REDIRECT_URI=http://localhost:5173/api/v1/integrations/gmail/callback`, which must be
registered in Google Cloud. Scopes are `openid email gmail.readonly` (read-only).

## Security & privacy

- Session-cookie auth: `HttpOnly`, `SameSite=Lax`, `Secure` in prod. CSRF is enforced on every
  unsafe request, including anonymous login and register. CORS is limited to `FRONTEND_URL`.
- Every query is scoped to the user. Other users' resources return **404**.
- OAuth tokens are stored as Fernet ciphertext (`TOKEN_ENCRYPTION_KEY`; comma-separate keys to
  rotate) and never reach the browser or any API response.
- Email HTML is sanitized server-side with nh3:
  - no scripts, event handlers, iframes or forms
  - no `javascript:` links and no CSS `url()`
  - remote images removed

  The client runs DOMPurify again and renders the body in a sandboxed `<iframe srcdoc>` with no
  `allow-scripts` and a `default-src 'none'` CSP. ESLint forbids `dangerouslySetInnerHTML`.
- Logs are JSON. `SensitiveDataFilter` redacts bodies, tokens, Fernet ciphertext, Bearer headers,
  OAuth codes and search terms.
- Error tracking: set `SENTRY_DSN` and install `sentry-sdk`. Request bodies and local variables are
  stripped before events are sent.
- Operational metrics (staff only): `GET /api/v1/ops/metrics`.

## Configuration

All variables from PRD §34 are listed in `env.example`. The demo defaults are built into
`docker-compose.yml`. Notable ones:

- `SPAM_THRESHOLD_PERCENT` / `URGENCY_THRESHOLD_PERCENT` (default 70; read on every request).
- `GMAIL_INITIAL_SYNC_DAYS` (30), `GMAIL_SYNC_INTERVAL_SECONDS` (300), `SYNC_DISPATCH_INTERVAL` (60).
- `AI_PROMPT_VERSION`, `AI_MAX_INPUT_CHARS`, `AI_REQUEST_TIMEOUT_SECONDS`.
- Demo realism: `FAKE_GMAIL_LATENCY_MS` and `FAKE_AI_LATENCY_MS` add small delays so progress is
  visible. `INITIAL_SYNC_START_DELAY_SECONDS` does the same for the first sync.
- `LOG_JSON` (1), `LOG_LEVEL`, `SENTRY_DSN`.

## Tests

- **Backend:** pytest, about 200 tests: domain unit tests, use cases, respx-mocked Gmail and Jev AI
  adapters, API tests (auth, Gmail, inbox, dashboard) with query-count assertions, and a security
  suite (IDOR, stored XSS, CSRF, OAuth state, token exposure, log redaction).
- **Frontend:** Vitest, React Testing Library and MSW.
- **E2E:** Playwright, run in a `mcr.microsoft.com/playwright` container that shares the frontend's
  network. It covers the primary journey (register → connect → sync/analyze → search/filter → detail
  → re-analyze → dashboard → revoke/reconnect → disconnect → logout), malicious-email safety,
  cross-user access and a mobile run.
