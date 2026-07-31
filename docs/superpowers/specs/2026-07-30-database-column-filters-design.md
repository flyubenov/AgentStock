# Database Grid Column Filters — Design

**Date:** 2026-07-30
**Status:** Approved (design)
**Scope:** Frontend only — `frontend/src/pages/Database.tsx`

## Problem

The Database grid lists every evaluated company with no way to narrow the view.
Users want Google-Sheets-style per-column filters to focus on a subset of rows:

1. **Ticker** — select multiple tickers, hide the rest.
2. **Stock Type** — select multiple stock types, hide the rest.
3. **Quality** — keep rows bigger/smaller than a threshold.
4. **Gap %** (`price_vs_fair_value_pct`) — keep rows bigger/smaller than a threshold.

## Constraints & Context

- Every row already lives client-side in `Database.tsx`'s `results` state; the page
  already sorts in-memory. Filtering is the same kind of in-memory pass.
- **No backend changes.** No `types.ts` changes. No new API calls.
- **No persistence** — filters reset on reload/Refresh/Recalculate (YAGNI). Can be
  added later via `localStorage` if wanted.
- The frontend has **no test runner** wired up (only `eslint.config.js`). Verification
  is `npm run build` (TypeScript typecheck) plus a manual check in the running app.

## Design

### Data flow

The existing pipeline is `results ──sort──▶ sorted ──▶ render`.
This inserts a filter step: `results ──filter──▶ filtered ──sort──▶ sorted ──▶ render`.

- `filtered = results.filter(rowMatchesFilters)`
- The existing sort then operates on `filtered` instead of `results`.
- Row count in the header reflects `filtered.length` vs `results.length`.

### Filter state

A single `filters` object held in component state:

```ts
type NumRange = { min: number | null; max: number | null }
type Filters = {
  tickers: Set<string>       // empty = no filter (all pass)
  stockTypes: Set<string>    // empty = no filter; "(none)" sentinel matches null stock_type
  quality: NumRange
  gap: NumRange
}
```

Plus `openFilter: 'ticker' | 'stockType' | 'quality' | 'gap' | null` tracking which
popover is open (one at a time).

### Predicate (`rowMatchesFilters`)

A row passes only if it satisfies **every** active column filter (AND across columns):

- **Ticker:** `tickers.size === 0 || tickers.has(r.ticker)`
- **Stock Type:** `stockTypes.size === 0 || stockTypes.has(r.stock_type ?? NONE_SENTINEL)`
- **Quality:** if `quality.min`/`quality.max` set, `r.quality_score` must be non-null and
  within `[min, max]`. A **null** `quality_score` is **hidden** whenever a bound is set.
- **Gap %:** same rule against `r.price_vs_fair_value_pct`.

An empty/unset filter is a no-op for that column.

### UI — Sheets-style funnel per header

- Each of the four filterable headers (Ticker, Stock Type, Quality, Gap%) renders a
  small **▾ funnel button** next to its label.
- The button is **highlighted (blue)** when that column's filter is active, muted
  otherwise. "Active" = non-empty ticker/stockType set, or any numeric bound set.
- Clicking the button toggles a **dropdown popover** anchored under that header.
  Opening one closes any other (single `openFilter`).
- Popover closes on **outside click** or **Esc**.

**Ticker / Stock Type popover (multi-select):**
- A checkbox list of the **distinct values present in the loaded `results`**
  (derived with `useMemo`, sorted). Stock Type includes a `(none)` entry for null.
- A **search box** at the top of the Ticker popover filters the checkbox list
  (Stock Type list is short — no search needed).
- **Select all** / **Clear** links for the column.
- Distinct lists recompute after Refresh/Recalculate; selections that no longer
  exist simply match nothing (harmless).

**Quality / Gap % popover (numeric range):**
- Two numeric `<input>`s: `≥ min` and `≤ max`, each optional. Blank = unbounded on
  that side. Empty string parses to `null`.

**Global affordances:**
- Header text becomes **"Database — {filtered} of {total} records"** when any filter
  is active, else **"Database — {total} records"**.
- A **"Clear all filters"** button appears in the toolbar (next to Refresh) only when
  at least one filter is active; it resets `filters` to empty.

### Component structure

- Extract a small, self-contained **`ColumnFilter`** popover component (co-located in
  `Database.tsx` or a sibling `DatabaseFilters.tsx`) so the header/table markup stays
  readable. It receives the column's current filter value + change/clear callbacks and
  renders the appropriate body (checkbox list vs numeric range).
- A helper renders the **funnel button** (label + active state + click handler).
- `rowMatchesFilters` and the distinct-value memos live in `Database.tsx`.

Boundaries: `ColumnFilter` knows only about its own column's value and callbacks; it
does not read global state. `Database.tsx` owns `filters`, the predicate, and derived
lists. Changing the popover internals does not affect the predicate and vice versa.

## Out of scope

- Persisting filters across reloads.
- Filtering the Company, Fair Value, Price, or Evaluated columns.
- Server-side filtering / pagination.
- A frontend test harness (flagged separately; not added here).

## Verification

1. `cd frontend && npm run build` — passes TypeScript + Vite build.
2. `npm run lint` — clean.
3. Manual, in the running app:
   - Ticker: check 2 tickers → only those rows show; icon highlights; count updates.
   - Stock Type: check one type (and `(none)`) → matching rows only.
   - Quality: `≥ 7` hides sub-7 and null-quality rows; add `≤ 9` for a band.
   - Gap %: `≤ -10` shows overvalued names only.
   - Combine two columns → AND semantics.
   - Sort still works on the filtered set.
   - Clear (per column) and Clear all filters reset correctly.
   - Esc / outside-click closes the popover.
