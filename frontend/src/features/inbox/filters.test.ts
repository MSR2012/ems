import { activeFilterCount, EMPTY_FILTERS, filtersFromParams, filtersToParams } from './filters';

describe('inbox URL filters', () => {
  it('round-trips through URL params', () => {
    const f = { ...EMPTY_FILTERS, q: 'acme', priority: ['CRITICAL', 'HIGH'] as const, category: ['WORK'] as const,
      reply_urgency_min: '70', hide_potential_spam: true, is_read: 'false' as const, received_from: '2026-09-01', page: 2 };
    const params = new URLSearchParams(filtersToParams({ ...f, priority: [...f.priority], category: [...f.category] }));
    expect(params.toString()).toContain('priority=CRITICAL%2CHIGH');
    const back = filtersFromParams(params);
    expect(back).toMatchObject({ q: 'acme', priority: ['CRITICAL', 'HIGH'], category: ['WORK'], reply_urgency_min: '70',
      hide_potential_spam: true, is_read: 'false', received_from: '2026-09-01', page: 2 });
  });

  it('ignores invalid values from a hand-edited URL', () => {
    const f = filtersFromParams(new URLSearchParams('priority=BOGUS,low&spam_likelihood_min=500&is_read=maybe&received_to=yesterday&page=-3'));
    expect(f.priority).toEqual(['LOW']);
    expect(f.spam_likelihood_min).toBe('');
    expect(f.is_read).toBe('');
    expect(f.received_to).toBe('');
    expect(f.page).toBe(1);
  });

  it('counts active filters (search excluded)', () => {
    expect(activeFilterCount({ ...EMPTY_FILTERS, q: 'x' })).toBe(0);
    expect(activeFilterCount({ ...EMPTY_FILTERS, priority: ['HIGH'], hide_potential_spam: true, spam_likelihood_max: '40' })).toBe(3);
  });
});
