# Ticker links `/t/{TICKER}`: design

**Status:** approved by the founder on 2026-10-03 (the spec, and the implementation plan after it).
**Branch:** `06-Intrinsica_Fake_Door_Launch_Checklist` (after B1 `59c5683` and B4 `51e2289`).
**Source:** launch checklist B2 (`MonetizationPlan/Intrinsica_Fake_Door_Launch_Checklist.html`), advertising strategy review blocker 2.
**Mockups:** `.superpowers/brainstorm/827-1790977003/` (`ticker-page-v2.html`; the card screens are in `archive/`).

## 1. Purpose

Ads and posts about one stock must land on that stock. Today every path except `/checkout` and `/privacy` shows the homepage with the AAPL demo, and every shared link shows the same generic preview image.

**In scope:**
- `intrinsica.io/t/NVDA` shows the normal landing page with NVDA as the featured result;
- a per-ticker preview card for X, Reddit and chat apps;
- a Share button on results;
- self-hosted fonts.

**Out of scope:**
- server-rendered pages for search engines (SEO);
- numbers on the share card (they wait for licensed prices, see §6);
- multi-ticker links.

## 2. Decisions (founder, 2026-10-03)

| # | Decision |
|---|---|
| D1 | Purpose: ad and post landing, plus a small Share button. Not SEO. |
| D2 | The share card is a branded per-ticker image with **no numbers**. Scores are added once prices are licensed, to the right of the big ticker. |
| D3 | Card: teal, with the headline "Quality business? · Durable moat? · Fair price?" and the small line "Quality · Moat · Fair Value · Reward/Risk, scored from fundamentals" (§5). |
| D4 | Page layout B: the card comes first on phones (§4). *Revised 2026-10-03 (founder):* the headline no longer names the stock; it stays the site's own, since the card already says which stock it is. The logo links home on every page. |
| D5 | A `/t/` link **always shows its stock**, on every visit, whether or not the allowance is used up. While analyses remain, opening a link **uses one**, including repeat visits. Typed runs are unchanged. There is no per-stock memory anywhere. The loophole (hand-typing `/t/` addresses after the allowance is gone) is accepted. |
| D6 | Events: `ticker_link_opened` and `share_clicked` (§7). |
| D7 | The Share button's link carries `?ref=share`. B1 records the referrer `t.co` as channel `x`. |
| D8 | An unknown ticker falls back to the AAPL homepage with a note. Only tickers on the SEC list get their own card. |
| D9 | Ticker case is ignored; `BRK.B` = `BRK-B` (canonical `BRK.B`); one stock per link. |
| D10 | "Engaged visitor" in the B3 keep/stop rules = a typed analysis, **or** a link arrival whose stock loaded **and** who then did one more thing: opened a score breakdown, viewed pricing, pressed Share, or typed a ticker. *Revised 2026-10-03 after the final review:* counting every link arrival made "engaged" equal "landed" for ad traffic, so the 10% health check could not tell channels apart. The go/no-go bars are unchanged. |
| D11 | Fonts are self-hosted (removes the Google Fonts transfer from B4's privacy notice). |

## 3. Routes and the ticker check

**Frontend route:** `/t/:ticker` renders `LandingPage` with a `linkTicker` prop, in public mode and in dev alike. Every other unknown path still falls back to the plain landing page.

**Normalising a ticker:** `normalizeTicker(raw)` trims and upper-cases the input, then accepts it only if it matches `^[A-Z]{1,5}([.-][A-Z]{1,2})?$`, the same shape the analysis endpoint already validates (`services/yahoo.py` `_TICKER_RE`) widened to accept a dash. The canonical form uses a **dot** (`BRK-B` → `BRK.B`), because `/api/landing/analyze` rejects the dash form. The SEC list is keyed by the **dash** form (`sec_key("BRK.B")` = `BRK-B`). Commas, spaces and anything else make it invalid. The same rules exist in Python (`landing/tickers.py`) and TypeScript (`landing/ticker.ts`), and a shared JSON table of test cases pins both.

**Known-ticker list:**
- `landing/tickers.py` loads `https://www.sec.gov/files/company_tickers.json`, with the `User-Agent` taken from the env var `SEC_USER_AGENT`.
- The list is cached in memory for 7 days and keyed by normalised ticker. Each entry holds the company title.
- **If the fetch fails** and nothing is cached, `is_known()` returns `False`. Every card then degrades to the generic image, and the page still works; see the endpoint below for what visitors see.
- **If `SEC_USER_AGENT` is unset,** the fetch is skipped and a warning is logged once. Production must set it (DEPLOY.md gets one line).
- **Overlap with branch `05-yfinance-replacement`:** that branch has an EDGAR client with the same CIK map. This module stays standalone and small. When the branches meet, it should switch to that client; the plan notes this.

**`GET /api/landing/ticker/{raw}`** returns `{"ticker": "BRK.B", "known": true, "name": "Berkshire Hathaway Inc"}`.
- An invalid format returns `{"ticker": null, "known": false, "name": null}`.
- It is rate-limited with the existing landing limiter key.
- **If the SEC list can't be loaded,** the endpoint answers `known: true` for any ticker with a valid format. The page then tries the analysis, and a failed run falls back exactly as an unknown ticker does (§4). Only the card generator treats "list unavailable" as unknown.

## 4. The `/t/NVDA` page

**Flow on mount** (replaces the sample run when `linkTicker` is set):
1. Normalise the ticker. If it's invalid, go to the fallback.
2. Call `/api/landing/ticker/{t}`. If `known` is false, go to the fallback.
3. Fire `ticker_link_opened` with `{ticker, known}`. It fires once per page load, including for unknown tickers, which carry `known: false`.
4. Run `analyze([t], 'link')`.
5. If the run returns no usable row (`invalid`, an error, or a failed status), go to the fallback.

**Fallback:**
- runs the normal AAPL sample;
- shows the notice "We couldn't find {RAW}. Here's an example instead.", where `{RAW}` is the normalised form, or the first 12 characters of the raw input stripped of anything except letters, digits, `.` and `-`;
- replaces the address bar with `/` so a copied link isn't the broken one.

**Free allowance (D5)** lives in `demoLimit.ts`:
- **No change to the stored state** (`count` and `windowStart` only). No list of tickers is kept.
- **`link` runs** call the existing `recordRun()` after a successful row, but only if `canAnalyze()` was true. Once the allowance is used up, the link still shows its stock and nothing more is recorded. Repeat visits count like any other run.
- **Typed runs:** unchanged, every successful run counts.
- **Never blocked:** a `link` run ignores `canAnalyze()`. The linked stock always shows. Afterwards `exhausted` is recomputed, so the input wall appears for anything further.

**Headline and layout (D4):**
- The hero headline is unchanged on a link page (revised 2026-10-03; the earlier `{T}: judge the business.` prefix was dropped). The logo links to `/` from every page, so a visitor can always get back to the plain homepage.
- The input placeholder becomes "Try another ticker…".
- **On phones (≤ 900px, the existing single-column breakpoint),** the result card is ordered right after the headline via CSS `order` (the left column uses `display: contents` in link mode). The DOM order stays the same, so screen readers and tab order are unchanged.
- **Header pill:** `link` runs show "Live analysis · computed just now", `sample` keeps "Live example · computed just now", and typed keeps "Your analysis".
- The document title becomes `{T}: Quality, Moat, Fair Value · Intrinsica`.

**Loading:** the existing pending/busy card state, showing the ticker immediately. A cold ticker takes a few seconds once, then the landing cache (fundamentals 7 days, price layer `LANDING_FAST_TTL`) serves it. Operational note for the founder: open each ad's `/t/` link once before the ad goes live.

## 5. Preview tags and the card image

**Tag swap:** `spa.py` serves `/t/{raw}` as `index.html` with the preview tags replaced. This applies only when the ticker normalises and `is_known()` returns true.

| Tag | Value |
|---|---|
| `<title>`, `og:title` | `{T}: quality business? Durable moat? Fair price? · Intrinsica` |
| `og:description`, `description` | The existing site description, unchanged |
| `og:url` | `https://intrinsica.io/t/{T}` |
| `og:image`, `twitter:image` | `https://intrinsica.io/og/{T}.png` |

How the swap works:
- It is a string replacement on the built `index.html`, read once at startup.
- Every inserted value is HTML-escaped. Tickers pass the regex anyway; escaping is defence in depth.
- Unknown or invalid tickers get the untouched `index.html`, with the generic card.
- The response keeps `Cache-Control: no-cache`.

**`GET /og/{T}.png`:** `landing/og_card.py` draws the card with Pillow. Pillow is added to `requirements.txt`; the bundled TTFs live in `backend/assets/fonts/`.
- **Size and background:** 1200×630, the teal gradient `#17696f` → `#0a3a3e`.
- **Content:**
  - the brand mark and "Intrinsica", top-left;
  - the ticker in Space Grotesk Bold at about 150px;
  - the headline in Space Grotesk SemiBold, on two lines: "● Quality business?  ● Durable moat?" / "● Fair price?". The dots use the logo colours `#66fff7`, `#3d8bff` and `#fae842`;
  - a 1px rule at 18% white;
  - the small line in Inter at about 25px, `#cfe6e4`: "Quality · Moat · Fair Value · Reward/Risk, scored from fundamentals";
  - "intrinsica.io" right-aligned in bold white.
- **Spacing:** follows the approved mockup (`share-card-v3.html` layout with the `share-line` text). The footer clears X's bottom-left domain chip.
- **Long tickers** (up to 8 characters, e.g. GOOGL.AB) shrink the font until the text fits within 60% of the width.
- **Unknown or invalid tickers** answer with a 302 redirect to `/og-image.png`. No image is ever drawn for text outside the SEC list.
- **Caching:** an in-process LRU of 256 PNGs, plus `Cache-Control: public, max-age=86400`.
- **The brand mark** is drawn from the same geometry as `mark.ts`. A test compares the colour constants.
- **Route order:** `/og/*` is registered before the SPA catch-all.

**Check before launch:** the plan includes a manual step. Post a test link and confirm the card appears, or use X's card preview where available, then take a screenshot at phone width.

## 6. Share button

- **Placement:** a `Share` button in each result row's header, beside the watchlist bookmark. Results are shown for every source.
- **Link:** `https://intrinsica.io/t/{T}?ref=share`.
- **When `navigator.share` exists** (phones), it calls `navigator.share({ title, text, url })` with:
  - `title` = `{T} on Intrinsica`;
  - `text` = `{T} on Intrinsica: quality business? Durable moat? Fair price?`;
  - `url` = the link.

  A rejection, including the user cancelling, is silent.
- **Otherwise** it copies the link with `navigator.clipboard.writeText` and shows "Link copied" for 2 seconds in an `aria-live="polite"` region. If the clipboard fails, the button shows the URL in a read-only selected input instead.
- **Event:** `share_clicked` with `{ticker, method: 'native' | 'copy', place: 'card' | 'row' | 'breakdown'}`, fired on click before the share or copy resolves.
- **Revised 2026-10-03 (founder):** Share appears only for a result where at least one assessment computed. A single result shows "Share {T}" at the footer's right; comparison rows show an icon-only Share grouped with the bookmark at the right of the ticker line; the breakdown header shows "Share {T}" beside Close. Non-production builds link to their own origin.
- **Future:** when scores are licensed (D2), the card gains a score row. Nothing in the button changes.

## 7. Analytics

**New events:** `ticker_link_opened` and `share_clicked`. They are added to:
- `EVENTS` in `analytics.ts`;
- `SPEC_EVENTS` in `analytics.test.ts`;
- `FUNNEL_EVENTS` in `routers/events.py`;
- this spec and the fake-door spec §9, which gets a dated addendum. Its "closed list" rule stays, and the list grows by these two.

**Other changes:**
- `AnalyzeSource` becomes `'sample' | 'typed' | 'link'`. `analysis_started` and `analysis_completed` carry it as today.
- B1 tweak (D7): in `attribution.ts`, the referrer domain `t.co` maps to the channel `x`. The raw `referrer` field keeps `t.co`.
- B3 rules (D10): "engaged visitor" becomes a visitor with `analysis_completed` where `source` = `typed`, **or** with `analysis_completed` where `source` = `link` plus at least one of `breakdown_opened`, `pricing_viewed` or `share_clicked`. This is updated in the checklist HTML. That file is untracked and never committed; it is edited in place.
- **Tagging guide:** a table added to the checklist HTML with one ready link per channel. For example:
  - `https://intrinsica.io/t/NVDA?utm_source=x&utm_campaign=<label>`;
  - the same pattern for reddit, hn, google, indiehackers and producthunt;
  - a note that X Ads and Google Ads take the tagged link in their website-URL field.

## 8. Self-hosted fonts (D11)

- **Frontend:** `@fontsource/inter`, `@fontsource/space-grotesk` and `@fontsource/jetbrains-mono` (only the weights in use), imported in `main.tsx`. Vite bundles the font files under `/assets/` (immutable caching already applies). The `@import url('https://fonts.googleapis.com…')` lines are removed from `theme.css` and `index.css`.
- **A test fails if** any file under `frontend/src` or `frontend/index.html` references `fonts.googleapis.com` or `fonts.gstatic.com`.
- **Backend:** OFL TTFs for Inter Regular and Space Grotesk SemiBold/Bold are in `backend/assets/fonts/` with their `OFL.txt`.
- **Privacy notice:** remove the Google Fonts bullet, and drop "Google Fonts" from the list `PrivacyPage.test.tsx` requires. Add a test that the page **doesn't** mention Google Fonts once the import is gone, so the two stay in step.

## 9. Error handling summary

| Situation | Behaviour |
|---|---|
| Invalid format (`/t/a,b`, `/t/<script>`) | Fallback page with the cleaned raw text in the notice; generic card; nothing drawn |
| Valid format, not on the SEC list | Fallback page; generic card |
| SEC list unavailable | Page: tries the analysis, and falls back if it fails. Card: generic |
| Analysis fails or times out | Fallback page, with `analysis_completed` not fired (as today) |
| Allowance used up | The linked stock still shows; the wall appears for further typed runs |
| Rate limited | The existing 429 copy, shown as the notice; the AAPL card stays |

## 10. Testing

- **Normalisation:** a shared case table, run in Python and Vitest:
  - `nvda` → NVDA; `brk-b` → BRK.B;
  - ` msft ` → MSFT;
  - `a,b`, an empty string, `<x>` and an 11-character input are all invalid.
- **`tickers.py`:**
  - parses a recorded SEC fixture;
  - the 7-day cache;
  - a fetch failure means unknown;
  - a missing User-Agent skips the fetch.
- **Ticker endpoint:** known, unknown, invalid, the list unavailable (valid format reads as known), and rate limiting.
- **`spa.py`:**
  - `/t/NVDA` has the swapped tags, escaped;
  - `/t/XYZQ` and `/t/a,b` get the untouched HTML;
  - other paths are unchanged;
  - `HEAD` works.
- **`og_card.py`:**
  - a 1200×630 PNG for a known ticker;
  - a 302 to `/og-image.png` for unknown and invalid tickers;
  - the LRU is reused;
  - 8-character tickers fit;
  - the mark colours equal `mark.ts`.
- **LandingPage with `linkTicker`:**
  - the headline, the placeholder and the pill;
  - `ticker_link_opened` fires once;
  - a link run uses one analysis while some remain, and a repeat visit uses another;
  - the stock still shows when the allowance is used up;
  - the unknown and failed fallbacks set the notice and `/`;
  - CSS order on phones is checked by class.
- **Share button:** the native path, the copy path, the clipboard-failure path, and the event props.
- **Analytics:**
  - the event list tests on both sides;
  - `t.co` → `x`;
  - `link` reaches `analysis_completed`.
- **Fonts:** the no-Google-Fonts guard; the privacy page's sync test.
- **App routes:** `/t/AMZN` renders LandingPage with `linkTicker`, in public mode and in dev.
