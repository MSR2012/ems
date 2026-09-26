import { useEffect, useState } from 'react';
import { CATEGORIES, PRIORITIES, type Category, type Priority } from '@/shared/api/types';
import { CATEGORY_META, PRIORITY_META } from '@/features/email-analysis/labels';
import { EMPTY_FILTERS, type InboxFilters } from './filters';

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
      className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition ${active ? 'bg-indigo-600 text-white ring-indigo-600' : 'bg-white text-slate-600 ring-slate-300 hover:bg-slate-50'}`}>
      {children}
    </button>
  );
}

function RangeInputs({ label, min, max, onChange, idPrefix }: {
  label: string; min: string; max: string; idPrefix: string; onChange: (min: string, max: string) => void;
}) {
  const clean = (v: string) => v.replace(/\D/g, '').slice(0, 3);
  return (
    <fieldset>
      <legend className="label">{label}</legend>
      <div className="flex items-center gap-2">
        <label className="sr-only" htmlFor={`${idPrefix}-min`}>{label} minimum</label>
        <input id={`${idPrefix}-min`} inputMode="numeric" placeholder="0" className="input w-20" value={min}
          onChange={(e) => onChange(clean(e.target.value), max)} />
        <span className="text-slate-400">–</span>
        <label className="sr-only" htmlFor={`${idPrefix}-max`}>{label} maximum</label>
        <input id={`${idPrefix}-max`} inputMode="numeric" placeholder="100" className="input w-20" value={max}
          onChange={(e) => onChange(min, clean(e.target.value))} />
        <span className="text-sm text-slate-500">%</span>
      </div>
    </fieldset>
  );
}

/** Filter controls. Edits are local until "Apply" (search applies as you type, debounced). */
export function InboxFiltersPanel({ value, onChange, onClose }: {
  value: InboxFilters; onChange: (f: InboxFilters) => void; onClose?: () => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const apply = () => { onChange({ ...draft, page: 1 }); onClose?.(); };

  return (
    <div className="space-y-5">
      <div>
        <p className="label">Priority</p>
        <div className="flex flex-wrap gap-2">
          {PRIORITIES.map((p: Priority) => (
            <Chip key={p} active={draft.priority.includes(p)} onClick={() => setDraft({ ...draft, priority: toggle(draft.priority, p) })}>
              {PRIORITY_META[p].label}
            </Chip>
          ))}
        </div>
      </div>
      <div>
        <p className="label">Category</p>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((c: Category) => (
            <Chip key={c} active={draft.category.includes(c)} onClick={() => setDraft({ ...draft, category: toggle(draft.category, c) })}>
              {CATEGORY_META[c].label}
            </Chip>
          ))}
        </div>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <RangeInputs label="Reply urgency" idPrefix="urgency" min={draft.reply_urgency_min} max={draft.reply_urgency_max}
          onChange={(a, b) => setDraft({ ...draft, reply_urgency_min: a, reply_urgency_max: b })} />
        <div className="space-y-2">
          <RangeInputs label="Spam likelihood" idPrefix="spam" min={draft.spam_likelihood_min} max={draft.spam_likelihood_max}
            onChange={(a, b) => setDraft({ ...draft, spam_likelihood_min: a, spam_likelihood_max: b })} />
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-indigo-600" checked={draft.hide_potential_spam}
              onChange={(e) => setDraft({ ...draft, hide_potential_spam: e.target.checked })} />
            Hide potential spam
          </label>
        </div>
      </div>
      <div className="grid gap-5 sm:grid-cols-3">
        <div>
          <label htmlFor="f-read" className="label">Read state</label>
          <select id="f-read" className="input" value={draft.is_read} onChange={(e) => setDraft({ ...draft, is_read: e.target.value as InboxFilters['is_read'] })}>
            <option value="">All</option>
            <option value="false">Unread</option>
            <option value="true">Read</option>
          </select>
        </div>
        <div>
          <label htmlFor="f-from" className="label">Received from</label>
          <input id="f-from" type="date" className="input" value={draft.received_from} onChange={(e) => setDraft({ ...draft, received_from: e.target.value })} />
        </div>
        <div>
          <label htmlFor="f-to" className="label">Received to</label>
          <input id="f-to" type="date" className="input" value={draft.received_to} onChange={(e) => setDraft({ ...draft, received_to: e.target.value })} />
        </div>
      </div>
      <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
        <button type="button" className="btn-ghost" onClick={() => { onChange({ ...EMPTY_FILTERS, q: value.q }); onClose?.(); }}>Clear filters</button>
        <button type="button" className="btn-primary" onClick={apply}>Apply filters</button>
      </div>
    </div>
  );
}
