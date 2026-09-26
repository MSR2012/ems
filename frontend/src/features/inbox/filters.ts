import type { Category, Priority } from '@/shared/api/types';
import { CATEGORIES, PRIORITIES } from '@/shared/api/types';

/** Inbox filters mirror the API query params and live in the URL (shareable/reloadable). */
export interface InboxFilters {
  q: string;
  priority: Priority[];
  category: Category[];
  spam_likelihood_min: string;
  spam_likelihood_max: string;
  hide_potential_spam: boolean;
  reply_urgency_min: string;
  reply_urgency_max: string;
  is_read: '' | 'true' | 'false';
  received_from: string;
  received_to: string;
  page: number;
}

export const EMPTY_FILTERS: InboxFilters = {
  q: '', priority: [], category: [], spam_likelihood_min: '', spam_likelihood_max: '',
  hide_potential_spam: false, reply_urgency_min: '', reply_urgency_max: '', is_read: '',
  received_from: '', received_to: '', page: 1,
};

const pct = (v: string | null) => (v && /^\d{1,3}$/.test(v) && +v <= 100 ? v : '');
const date = (v: string | null) => (v && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : '');

export function filtersFromParams(p: URLSearchParams): InboxFilters {
  const list = <T extends string>(key: string, allowed: readonly T[]) =>
    (p.get(key) ?? '').split(',').map((s) => s.trim().toUpperCase()).filter((s): s is T => (allowed as readonly string[]).includes(s));
  const isRead = p.get('is_read');
  return {
    q: p.get('q') ?? '',
    priority: list('priority', PRIORITIES),
    category: list('category', CATEGORIES),
    spam_likelihood_min: pct(p.get('spam_likelihood_min')),
    spam_likelihood_max: pct(p.get('spam_likelihood_max')),
    hide_potential_spam: p.get('hide_potential_spam') === 'true',
    reply_urgency_min: pct(p.get('reply_urgency_min')),
    reply_urgency_max: pct(p.get('reply_urgency_max')),
    is_read: isRead === 'true' || isRead === 'false' ? isRead : '',
    received_from: date(p.get('received_from')),
    received_to: date(p.get('received_to')),
    page: Math.max(1, parseInt(p.get('page') ?? '1', 10) || 1),
  };
}

export function filtersToParams(f: InboxFilters): Record<string, string> {
  const out: Record<string, string> = {};
  if (f.q.trim()) out.q = f.q.trim();
  if (f.priority.length) out.priority = f.priority.join(',');
  if (f.category.length) out.category = f.category.join(',');
  for (const k of ['spam_likelihood_min', 'spam_likelihood_max', 'reply_urgency_min', 'reply_urgency_max', 'received_from', 'received_to'] as const) {
    if (f[k]) out[k] = f[k];
  }
  if (f.hide_potential_spam) out.hide_potential_spam = 'true';
  if (f.is_read) out.is_read = f.is_read;
  if (f.page > 1) out.page = String(f.page);
  return out;
}

export function activeFilterCount(f: InboxFilters): number {
  return [
    f.priority.length > 0, f.category.length > 0, !!(f.spam_likelihood_min || f.spam_likelihood_max),
    f.hide_potential_spam, !!(f.reply_urgency_min || f.reply_urgency_max), !!f.is_read,
    !!(f.received_from || f.received_to),
  ].filter(Boolean).length;
}
