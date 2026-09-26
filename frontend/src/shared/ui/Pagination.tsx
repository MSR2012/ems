import { IconChevronLeft, IconChevronRight } from './icons';

export function Pagination({ page, pageSize, count, onPageChange }: {
  page: number; pageSize: number; count: number; onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (count === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(count, page * pageSize);
  return (
    <nav className="flex items-center justify-between gap-3 px-4 py-3 text-sm" aria-label="Pagination">
      <p className="text-slate-500">
        <span className="font-medium text-slate-700">{from}</span>–<span className="font-medium text-slate-700">{to}</span> of{' '}
        <span className="font-medium text-slate-700">{count}</span>
      </p>
      <div className="flex items-center gap-2">
        <button type="button" className="btn-secondary px-2.5" disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Previous page">
          <IconChevronLeft className="h-4 w-4" /> <span className="hidden sm:inline">Previous</span>
        </button>
        <span className="text-slate-500">Page {page} of {pages}</span>
        <button type="button" className="btn-secondary px-2.5" disabled={page >= pages} onClick={() => onPageChange(page + 1)} aria-label="Next page">
          <span className="hidden sm:inline">Next</span> <IconChevronRight className="h-4 w-4" />
        </button>
      </div>
    </nav>
  );
}
