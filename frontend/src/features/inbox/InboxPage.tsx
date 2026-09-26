import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { useGmailConnection } from '@/features/gmail-connection/api';
import { EmptyState, ErrorState, LoadingState, PageHeader, Spinner } from '@/shared/ui/feedback';
import { IconFilter, IconSearch } from '@/shared/ui/icons';
import { Pagination } from '@/shared/ui/Pagination';
import { Badge } from '@/shared/ui/Badge';
import { CATEGORY_META, PRIORITY_META } from '@/features/email-analysis/labels';
import { PAGE_SIZE, useInbox } from './api';
import { EmailRow } from './EmailRow';
import { activeFilterCount, EMPTY_FILTERS, filtersFromParams, filtersToParams, type InboxFilters } from './filters';
import { InboxFiltersPanel } from './InboxFiltersPanel';
import { BulkAnalyzeButton } from '@/features/email-analysis/BulkAnalyzeButton';

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function ActiveFilterChips({ f, onChange }: { f: InboxFilters; onChange: (f: InboxFilters) => void }) {
  const chips: { key: string; label: string; clear: Partial<InboxFilters> }[] = [];
  if (f.priority.length) chips.push({ key: 'p', label: `Priority: ${f.priority.map((p) => PRIORITY_META[p].label).join(', ')}`, clear: { priority: [] } });
  if (f.category.length) chips.push({ key: 'c', label: `Category: ${f.category.map((c) => CATEGORY_META[c].label).join(', ')}`, clear: { category: [] } });
  if (f.reply_urgency_min || f.reply_urgency_max) chips.push({ key: 'u', label: `Urgency ${f.reply_urgency_min || 0}–${f.reply_urgency_max || 100}%`, clear: { reply_urgency_min: '', reply_urgency_max: '' } });
  if (f.spam_likelihood_min || f.spam_likelihood_max) chips.push({ key: 's', label: `Spam ${f.spam_likelihood_min || 0}–${f.spam_likelihood_max || 100}%`, clear: { spam_likelihood_min: '', spam_likelihood_max: '' } });
  if (f.hide_potential_spam) chips.push({ key: 'h', label: 'Hiding potential spam', clear: { hide_potential_spam: false } });
  if (f.is_read) chips.push({ key: 'r', label: f.is_read === 'true' ? 'Read' : 'Unread', clear: { is_read: '' } });
  if (f.received_from || f.received_to) chips.push({ key: 'd', label: `Received ${f.received_from || '…'} → ${f.received_to || '…'}`, clear: { received_from: '', received_to: '' } });
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-2.5 sm:px-5">
      {chips.map((c) => (
        <button key={c.key} type="button" onClick={() => onChange({ ...f, ...c.clear, page: 1 })}
          className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
          aria-label={`Remove filter ${c.label}`}>
          {c.label} <span aria-hidden="true">×</span>
        </button>
      ))}
      <button type="button" className="text-xs font-medium text-slate-500 hover:text-slate-700" onClick={() => onChange({ ...EMPTY_FILTERS, q: f.q })}>Clear all</button>
    </div>
  );
}

function InboxEmpty() {
  const { data } = useGmailConnection();
  if (data?.account?.sync_in_progress) {
    return <EmptyState icon={<Spinner className="h-8 w-8" />} title="Syncing your inbox…" description="Emails appear here as soon as they are imported. AI analysis follows in the background." />;
  }
  return (
    <EmptyState title="Your inbox is empty"
      description={data?.account ? 'No emails were found in the synced window yet.' : 'Connect Gmail to sync your inbox.'}
      action={!data?.account ? <Link to="/integrations" className="btn-primary">Connect Gmail</Link> : undefined} />
  );
}

export default function InboxPage() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const filters = useMemo(() => filtersFromParams(params), [params]);
  const [search, setSearch] = useState(filters.q);
  const [showFilters, setShowFilters] = useState(false);
  const debounced = useDebounced(search, 300);

  const update = (f: InboxFilters) => setParams(filtersToParams(f));
  useEffect(() => setSearch(filters.q), [filters.q]);
  useEffect(() => {
    if (debounced.trim() !== filters.q.trim()) update({ ...filters, q: debounced, page: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const { data, isLoading, isError, isFetching, refetch } = useInbox(filters);
  const count = activeFilterCount(filters);
  const backTo = location.pathname + location.search;

  return (
    <>
      <PageHeader title="Inbox" description="Your synced Gmail inbox with AI indicators. Indicators are AI suggestions, not facts."
        actions={<BulkAnalyzeButton />} />
      <div className="card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:px-5">
          <div className="relative flex-1">
            <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <label htmlFor="inbox-search" className="sr-only">Search emails</label>
            <input id="inbox-search" type="search" className="input pl-9" placeholder="Search sender, subject or message text…"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            {isFetching && !isLoading && <Spinner className="h-4 w-4" />}
            <button type="button" className="btn-secondary" aria-expanded={showFilters} aria-controls="inbox-filters"
              onClick={() => setShowFilters((s) => !s)}>
              <IconFilter className="h-4 w-4" /> Filters {count > 0 && <Badge tone="indigo">{count}</Badge>}
            </button>
          </div>
        </div>
        {showFilters && (
          <div id="inbox-filters" className="border-b border-slate-100 bg-slate-50/60 p-4 sm:px-5">
            <InboxFiltersPanel value={filters} onChange={update} onClose={() => setShowFilters(false)} />
          </div>
        )}
        <ActiveFilterChips f={filters} onChange={update} />
        {isLoading ? <LoadingState label="Loading inbox…" /> : isError || !data ? (
          <div className="p-4"><ErrorState message="Could not load your inbox." onRetry={() => refetch()} /></div>
        ) : data.results.length === 0 ? (
          filters.q || count ? (
            <EmptyState title="No emails match" description="Try a different search or clear some filters."
              action={<button type="button" className="btn-secondary" onClick={() => update(EMPTY_FILTERS)}>Clear search & filters</button>} />
          ) : (
            <InboxEmpty />
          )
        ) : (
          <>
            <ul className="divide-y divide-slate-100" aria-label="Emails">
              {data.results.map((e) => <EmailRow key={e.id} email={e} backTo={backTo} />)}
            </ul>
            <div className="border-t border-slate-100">
              <Pagination page={data.page} pageSize={PAGE_SIZE} count={data.count}
                onPageChange={(page) => { update({ ...filters, page }); window.scrollTo({ top: 0 }); }} />
            </div>
          </>
        )}
      </div>
    </>
  );
}
