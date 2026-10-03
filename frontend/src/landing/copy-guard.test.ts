import { describe, it, expect } from 'vitest'
import ts from 'typescript'

/** A standing lint over the *copy* of every landing source, so a banned word
 *  cannot reach the page through a component nobody wrote a render test for.
 *
 *  Per-component guards already exist in `Framework.test.tsx`,
 *  `WhyWorkflow.test.tsx`, `Breakdown.test.tsx`, `Pricing.test.tsx` and
 *  `CheckoutPage.test.tsx`, and they test the real constraint better than this
 *  file can: they read what actually reaches the DOM. This file is not trying to
 *  beat them. Its one job is *file coverage* — a new component added tomorrow is
 *  scanned the moment it lands, with no test of its own.
 *
 *  THE THING THIS FILE MUST NOT DO is scan raw source. Spec section 8 bans words
 *  from the page, and source bytes are not the page. Run `/signal/i` over the raw
 *  tree today and it returns six hits and zero violations: five doc comments
 *  *stating the rule*, and `signal: controller.signal` — the standard
 *  `AbortController` API `LandingPage` uses to time a fetch out. (The
 *  `Risk/Reward` pattern adds three more, all of them the same doc comments.) A
 *  guard that bans those makes the code stop aborting fetches and teaches the
 *  next person to delete the documentation. So the text below is extracted
 *  first, and only string literals, template chunks and JSX text survive it. */

/** THE BOUNDARY: this glob is rooted at `src/landing/` and does not follow
 *  landing copy that is placed outside it. A shared component under
 *  `src/components/`, or a rendered string in `src/App.tsx`, escapes this lint
 *  entirely — and the 13-path assertion below would not notice, because it
 *  checks that known paths are present, not that no copy lives elsewhere. That
 *  is correct today (`src/App.tsx` carries only route paths, and every landing
 *  surface lives under this directory); anyone adding a landing surface outside
 *  `src/landing/` must widen this glob or the copy ships unlinted. */
const files = import.meta.glob('./**/*.{ts,tsx}', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

/** Test files are excluded: they quote the banned words in order to assert
 *  against them, so scanning them would guarantee a permanent false positive. */
const rawSources = Object.entries(files).filter(([path]) => !path.includes('.test.'))

/** Is this string literal a module path rather than a sentence? `import … from
 *  './components/Hero'` is not copy, and a folder named after a banned word
 *  would otherwise fail the build for ever. */
function isModuleSpecifier(node: ts.StringLiteral): boolean {
  const parent = node.parent
  if (!parent) return false
  if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) {
    return parent.moduleSpecifier === node
  }
  return ts.isImportTypeNode(parent) || ts.isExternalModuleReference(parent)
}

/** The copy of one source file: string literals, the literal chunks of template
 *  literals, and JSX text. Nothing else.
 *
 *  TypeScript's own parser does the extraction rather than a regex, because the
 *  regex version of this is the bug the guard exists to avoid. It is already a
 *  devDependency (`tsc -b` builds this project), so nothing new is installed for
 *  it, and it draws the line exactly where spec section 8 draws it:
 *
 *  - comments are trivia and never appear as nodes, so the five doc comments
 *    that *state* these rules are invisible here — as they must be, or the guard
 *    punishes a file for documenting the rule it obeys;
 *  - `controller.signal` and `signal:` are identifiers, not literals, so the
 *    `AbortController` fetch timeout survives;
 *  - an interpolation hole is an *expression*, so `${MAX_TICKERS}` contributes
 *    nothing while the words around it still do.
 *
 *  A string that ends up rendered is caught wherever it is written — a `const`, a
 *  JSX attribute, a ternary inside a hole — because all of those are literals. */
function userFacingText(source: string, file = 'probe.tsx'): string {
  const tree = ts.createSourceFile(
    file,
    source,
    ts.ScriptTarget.Latest,
    /* setParentNodes */ true,
    file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )

  const copy: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isStringLiteral(node)) {
      if (!isModuleSpecifier(node)) copy.push(node.text)
    } else if (
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node) ||
      ts.isJsxText(node)
    ) {
      copy.push(node.text)
    }
    ts.forEachChild(node, visit)
  }
  ts.forEachChild(tree, visit)

  // One chunk per line: a banned phrase may not be assembled across two
  // unrelated literals that happen to sit next to each other in the file.
  return copy.join('\n')
}

/** Every non-test landing source, paired with only its user-facing text. */
const sources: [string, string][] =
  rawSources.map(([path, text]) => [path, userFacingText(text, path)])

const paths = sources.map(([path]) => path)

function offenders(pattern: RegExp): string[] {
  return sources.filter(([, copy]) => pattern.test(copy)).map(([path]) => path)
}

/** Reads the guard the other way round: does this text trip the pattern? Used
 *  for the synthetic probes below, so the guard is proven to bite without a real
 *  offending file being committed to prove it. */
const trips = (pattern: RegExp, source: string, file = 'probe.tsx') =>
  pattern.test(userFacingText(source, file))

const BANNED_WORD = /signal/i
const BANNED_RATIO = /Risk\s*[/-]\s*Reward/i
/** The same ban in the other direction. Deliberately HYPHEN-ONLY, and
 *  deliberately not `[/-]`: the sanctioned house label is `Reward / Risk`
 *  (framework.ts, Breakdown.tsx) and `Reward ÷ Risk`, so a slash or a division
 *  sign between those two words is the correct copy, not an offence. What is
 *  banned is the hyphenated compound `Reward-Risk` / `Reward - Risk`, which
 *  BANNED_RATIO above cannot see because it is anchored Risk-first.
 *
 *  The trailing word boundary keeps `Risk-Favored` and `Reward-Favored` (framework.ts:146,
 *  a spec 5.4 sanctioned band) out of it: matching requires the two words to be
 *  adjacent across nothing but a hyphen and space, which a band listing
 *  `1.3–2.0× Reward-Favored, … 0.5–0.8× Risk-Favored` never is. */
const BANNED_REVERSED = /Reward\s*-\s*Risk\b/i
const BANNED_ABBREV = /\bR\s*[/-]\s*R\b/
const CLASSIFIER_CODE = /\b[A-Z]{3,}_[A-Z]{3,}\b/
const VALUE_RANGE = /fair[- ]value range|value range/i
const CARD_DETAILS = /card number|cardholder|cvc|cvv|expiry date/i
/** Task 11's operator form, `"ROIC > 15% scores 8"`. It runs there against
 *  rendered text; here it runs against extracted copy, for the same reason. */
const OPERATOR_CUTOFF = /[<>≥≤]\s*\d/
/** The worded form Task 11's regex misses: `"ROIC above 15% scores 8"`. It is
 *  deliberately anchored on a verb of scoring, because the loose version flags
 *  the outcome bands spec 5.4 item 4 requires — `9+ is top-decile`, `80+ reads as
 *  a wide moat`, `1.3–2.0× Reward-Favored`, `below 40 little or none`. Those are
 *  labels on a score the reader is already looking at, not per-metric cut-offs,
 *  and they must keep passing. */
const WORDED_CUTOFF =
  /\b(above|below|over|under|at least|no more than)\s+[\d.]+\s*%?\s*(scores?|earns?|gets?|points?)\b/i

describe('copy guard — the files it scans', () => {
  // Pinned, not `> 5`: the named-path test below already supersedes a loose
  // lower bound for the 13 copy-bearing surfaces, so the only thing a bound can
  // still add is visibility of a file deleted from OUTSIDE that list
  // (demoLimit.ts, format.ts, types.ts). An exact count makes that loud.
  it('finds landing sources to check', () => {
    expect(sources.length).toBe(26)
  })

  // A glob that silently matched nothing passes every guard below, for ever.
  // Naming the surfaces that actually carry copy makes that failure loud: a
  // rename or a moved file breaks this line rather than emptying the lint.
  it('covers every surface that renders copy, not an empty glob', () => {
    for (const file of [
      './LandingPage.tsx',
      './CheckoutPage.tsx',
      './PrivacyPage.tsx',
      './components/Hero.tsx',
      './components/Framework.tsx',
      './components/Breakdown.tsx',
      './components/Why.tsx',
      './components/Workflow.tsx',
      './components/Pricing.tsx',
      './components/LiveRunBar.tsx',
      './components/ResultCard.tsx',
      './components/OpenBreakdown.tsx',
      './components/QuestionBand.tsx',
      './components/Nav.tsx',
      './components/SiteFooter.tsx',
      './components/Tip.tsx',
      './components/WatchToast.tsx',
      './content/framework.ts',
      './content/plans.ts',
      './ticker.ts',
    ]) {
      expect(paths).toContain(file)
    }
    expect(paths.some(p => p.includes('.test.'))).toBe(false)
  })

  // The extraction is the whole guard. If it returned nothing, every assertion
  // below would pass against a page that said "signal" in forty-eight point type.
  it('extracts real copy, not an empty string', () => {
    const copy = sources.map(([, text]) => text).join('\n')
    expect(copy).toMatch(/Then judge the price/)       // JSX text in Hero
    expect(copy).toMatch(/no payment was taken/)
    expect(copy).toMatch(/Choose your plan/)
  })
})

describe('copy guard — banned vocabulary', () => {
  it('never says "signal"', () => {
    expect(offenders(BANNED_WORD)).toEqual([])
  })

  it('never says "Risk/Reward" — the ratio is reward over risk', () => {
    expect(offenders(BANNED_RATIO)).toEqual([])
    expect(offenders(BANNED_ABBREV)).toEqual([])
    // Both orders are banned, so both are run over the live copy.
    expect(offenders(BANNED_REVERSED)).toEqual([])
  })

  it('leaks no internal classifier code', () => {
    expect(offenders(CLASSIFIER_CODE)).toEqual([])
  })

  it('never promises a fair-value range', () => {
    expect(offenders(VALUE_RANGE)).toEqual([])
  })

  it('asks for no card details', () => {
    expect(offenders(CARD_DETAILS)).toEqual([])
  })

  it('publishes no scoring cut-off, in either the operator or the worded form', () => {
    expect(offenders(OPERATOR_CUTOFF)).toEqual([])
    expect(offenders(WORDED_CUTOFF)).toEqual([])
  })
})

/** The half of a lint that is usually missing. Every assertion above is a
 *  negative, and a negative over an extraction that returns nothing is a test
 *  that can never fail. Each banned pattern is therefore fed a synthetic source
 *  that must trip it — written here rather than committed as a real offending
 *  file. */
describe('copy guard — it bites', () => {
  it('catches a banned word in a string literal', () => {
    expect(trips(BANNED_WORD, 'const x = "a strong signal"')).toBe(true)
  })

  it('catches a banned word in JSX text', () => {
    expect(trips(BANNED_WORD, 'const C = () => <p>a strong signal to buy</p>')).toBe(true)
  })

  it('catches a banned word inside a template literal', () => {
    expect(trips(BANNED_WORD, 'const x = `the ${name} signal`')).toBe(true)
  })

  it('catches the ratio written backwards', () => {
    expect(trips(BANNED_RATIO, 'const x = "Risk/Reward"')).toBe(true)
    expect(trips(BANNED_RATIO, 'const C = () => <span>Risk - Reward</span>')).toBe(true)
    expect(trips(BANNED_ABBREV, 'const x = "the R/R ratio"')).toBe(true)
  })

  // The gap BANNED_RATIO left open: it is anchored Risk-first, so the reverse
  // hyphenated compound sailed through. This is the file whose whole purpose is
  // catching copy in components with no test of their own, so a banned
  // `Reward-Risk` in SiteFooter.tsx — the very file used to prove this guard
  // works — would have shipped green.
  it('catches the reverse hyphenated compound the Risk-first pattern misses', () => {
    expect(trips(BANNED_REVERSED, 'const x = "Reward-Risk"')).toBe(true)
    expect(trips(BANNED_REVERSED, 'const C = () => <span>Reward - Risk</span>')).toBe(true)
    // Proof the two patterns are not the same pattern: the old one is blind here.
    expect(trips(BANNED_RATIO, 'const x = "Reward-Risk"')).toBe(false)
  })

  it('catches a leaked classifier code in rendered copy', () => {
    expect(trips(CLASSIFIER_CODE, 'const x = "Profile: TECH_GROWTH"')).toBe(true)
    expect(trips(CLASSIFIER_CODE, 'const C = () => <p>Profile: MEGA_CAP today</p>')).toBe(true)
  })

  it('catches a promised fair-value range', () => {
    expect(trips(VALUE_RANGE, 'const x = "we give you a fair-value range"')).toBe(true)
  })

  it('catches a card field label', () => {
    expect(trips(CARD_DETAILS, 'const C = () => <label>Card number</label>')).toBe(true)
  })

  it('catches both forms of a published scoring cut-off', () => {
    expect(trips(OPERATOR_CUTOFF, 'const x = "ROIC > 15% scores 8"')).toBe(true)
    expect(trips(WORDED_CUTOFF, 'const x = "ROIC above 15% scores 8"')).toBe(true)
    expect(trips(WORDED_CUTOFF, 'const C = () => <li>margin below 5% earns 2 points</li>'))
      .toBe(true)
  })
})

/** The other half: the two real cases that made the raw-source version of this
 *  guard unshippable. Both are pinned so the bug cannot be reintroduced by
 *  someone "simplifying" the extraction back to a grep. */
describe('copy guard — it does not bite code or comments', () => {
  it('ignores the AbortController API', () => {
    const source = [
      'const controller = new AbortController()',
      'fetch(url, { signal: controller.signal })',
      'controller.abort()',
    ].join('\n')
    expect(trips(BANNED_WORD, source)).toBe(false)
  })

  it('ignores a comment that states the rule it obeys', () => {
    const source = [
      '/** Spec section 8: never the word "signal" — it is an *assessment*;',
      ' *  and never "Risk/Reward", the ratio is reward over risk. */',
      'export const copy = "How strong is the underlying business?"',
      '// clicking Free is the opposite of a purchase signal',
    ].join('\n')
    expect(trips(BANNED_WORD, source)).toBe(false)
    expect(trips(BANNED_RATIO, source)).toBe(false)
  })

  it('ignores a SCREAMING_SNAKE identifier in an interpolation hole', () => {
    expect(trips(CLASSIFIER_CODE, 'const m = `Up to ${MAX_TICKERS} tickers per run.`'))
      .toBe(false)
    expect(trips(CLASSIFIER_CODE, 'const u = `${API_BASE}/api/landing/analyze`')).toBe(false)
    expect(trips(CLASSIFIER_CODE, 'export const MAX_TICKERS = 3')).toBe(false)
  })

  it('ignores an import path', () => {
    expect(trips(BANNED_WORD, "import { x } from './lib/signal-store'", 'probe.ts'))
      .toBe(false)
  })

  // The bands spec 5.4 item 4 requires. A cut-off guard that flags these is the
  // guard being wrong: they are labels on a score already on screen.
  it('leaves the sanctioned outcome bands alone', () => {
    for (const band of [
      'As a rough read: 9+ is top-decile, 8–9 excellent, 7–8 strong, below 5 weak.',
      'roughly 80+ reads as a wide moat, 60–79 established, 40–59 narrow, below 40 little or none.',
      'Reward ÷ risk, clamped to 0.2–5.0×. Roughly: 2.0× and above is Asymmetric Upside, 1.3–2.0× Reward-Favored, 0.8–1.3× Balanced, 0.5–0.8× Risk-Favored, below that a Value Trap.',
      'ratio · 0.2–5.0×',
      // The two house labels themselves, verbatim from framework.ts:129 and
      // Breakdown.tsx:194. Slash and division sign are the SANCTIONED forms.
      'Reward / Risk',
      'Reward ÷ Risk · range 0.2×–5.0× · higher is better —',
    ]) {
      const source = `export const note = ${JSON.stringify(band)}`
      expect(trips(OPERATOR_CUTOFF, source), band).toBe(false)
      expect(trips(WORDED_CUTOFF, source), band).toBe(false)
      expect(trips(BANNED_RATIO, source), band).toBe(false)
      expect(trips(BANNED_ABBREV, source), band).toBe(false)
      // The reverse pattern must be as blind to sanctioned copy as the forward
      // one. `Reward-Favored` and `Risk-Favored` sit in the same sentence as
      // each other in the band above; a looser pattern would join them.
      expect(trips(BANNED_REVERSED, source), band).toBe(false)
    }
  })
})
