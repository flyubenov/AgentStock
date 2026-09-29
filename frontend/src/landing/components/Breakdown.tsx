import { type ReactNode } from 'react'
import type {
  AssessmentId, FairValueBlock, MoatBlock, QualityBlock,
  RewardRiskBlock, RewardRiskFactor, TickerPayload,
} from '../types'
import {
  DASH, RR_TIERS, dollars, gapClass, gapPct, money, moatTier, num, qualityTier, weight,
} from '../format'
import Tip from './Tip'

/** The breakdown inside an expanded grid row (spec 5.3), laid out as the approved
 *  mock's "slim tabs, full width": a tab strip carrying each assessment's headline,
 *  one summary line, and one Factor | Data | Score | Weight table with a shaded row
 *  per category and a total row.
 *
 *  The tab strip is indexed by `AssessmentId`, the same bare index Hero's
 *  assessment links hand back. Kept in the same order and wording as Hero's
 *  ASSESSMENTS — Breakdown.test.tsx pins the two together, because a silent drift
 *  would mean clicking "Moat" in the hero opens "Fair Value" here. Never
 *  "Risk/Reward" (spec section 8). */
const TABS = ['Quality', 'Moat', 'Fair Value', 'Reward / Risk'] as const

/** The two figures are rounded to DIFFERENT precisions, in different places, by
 *  backend/landing/contract.py: the published `score` to one decimal, the
 *  categories' own `fundamentals_composite` to two. So they can differ by a
 *  rounding hair — up to half of the coarser step — without anything having
 *  been adjusted, and 0.05 is that half-step. Anything larger is a real
 *  adjustment and gets explained. */
const COMPOSITE_TOLERANCE = 0.05

/** Concept only, never a threshold (spec section 8 rule 3). The pillar weights
 *  are public and shown as % of the Moat score (spec §7, 2026-09-29: the landing
 *  page reads Moat on 0–10, so no raw points). Keyed by backend/landing/labels.py's
 *  MOAT_FACTOR_LABELS. */
const MOAT_TIPS: Record<string, string> = {
  'ROIC level': '20% of the Moat score. How much profit the business earns on the capital it employs — the more it earns per dollar invested, the higher it scores.',
  'Economic spread (ROIC - WACC)': '20% of the Moat score. Whether those returns beat what the capital costs. Earning above the cost of capital creates value; earning below it destroys value, however large the company.',
  'Persistence of economic profit': '25% of the Moat score, the largest single factor. How long the business has kept earning above its cost of capital: one good year is luck, a decade of them suggests something competitors cannot copy.',
  'Consistency of returns': '10% of the Moat score. How steady those returns are year to year, rather than swinging with the cycle.',
  'Margin durability': '15% of the Moat score. Whether margins hold up or expand over time instead of eroding under competition.',
  'Free-cash-flow conversion': '10% of the Moat score. How much of the reported profit turns into actual cash — a moat that never shows up as cash is an accounting one.',
}

const GATE_TIP = 'A Moat-wide check: a business that does not earn above its cost of capital has its Moat capped. Passed means no cap was applied.'

/** What each fired calibration did, and which assessments it touches. Keyed by the
 *  reader-facing names backend/landing/contract.py emits. A name missing here still
 *  renders — on every tab, without a tooltip — so a new calibration is never hidden. */
const CAL_INFO: Record<string, { tip: string; affects: AssessmentId[] }> = {
  'ROIC on tangible capital': { affects: [0, 1], tip: 'Acquisition goodwill and intangibles dominate invested capital, so ROIC is measured on tangible capital — a past deal is not misread as poor capital efficiency.' },
  'Economic-profit gate': { affects: [1], tip: 'Returns do not exceed the cost of capital, so the Moat score is capped: no durable advantage without economic profit.' },
  'Pre-profit growth blend': { affects: [0], tip: 'The company is not yet profitable, so Quality blends in a growth and cash-runway read instead of judging it on profits alone.' },
  'Unprofitable cap': { affects: [0], tip: 'Net income or free cash flow is negative, so the Quality score is capped.' },
  'Not scored for banks & insurers': { affects: [0, 1, 2], tip: 'A lender or insurer: metrics that do not fit a balance-sheet business are excluded, and Moat and Fair Value use equity-based measures.' },
  'Skipped during a heavy capex cycle': { affects: [0], tip: 'Capex is deliberately consuming free cash flow, so FCF-derived metrics are excluded and the balance sheet is judged on EBITDA leverage.' },
  'Skipped — one-off earnings distortion': { affects: [0], tip: 'Trailing earnings are depressed by amortization or a one-off trough, so EPS growth is excluded rather than understating growth.' },
  'Skipped — recent acquisition distortion': { affects: [0], tip: 'A just-closed acquisition dominates the balance sheet, so the amortization-depressed operating margin is excluded.' },
  'Skipped — recent acquisition': { affects: [0], tip: 'Deal debt is measured against pre-acquisition earnings, so the distorted leverage ratios are excluded.' },
  'Skipped — balance-sheet cross-check': { affects: [0], tip: 'FCF-based leverage reads far worse than EBITDA-based leverage while EBITDA leverage is healthy, so the noisy FCF ratio is excluded.' },
  'Not meaningful (negative EBITDA)': { affects: [0], tip: 'EBITDA is negative, so a debt-to-EBITDA ratio carries no leverage information and is left unscored.' },
  'Not meaningful (negative FCF)': { affects: [0], tip: 'Free cash flow is negative, so a debt-to-FCF ratio carries no leverage information and is left unscored.' },
}

/** A score with its strength bar, as the mock draws it: "8.5/10 ▬▬▬". */
function Score({ v, max, risk = false }: { v: number | null; max: number; risk?: boolean }) {
  if (v === null || !Number.isFinite(v)) return <>{DASH}</>
  const r = max > 0 ? v / max : 0
  const cls = risk ? `bar risk${v >= 4 ? ' hi' : ''}` : `bar${r <= 0.5 ? ' lo' : ''}`
  return (
    <span className="sc">
      <span>{String(Number(v.toFixed(1)))}/{max}</span>
      <span className={cls} aria-hidden="true"><i style={{ width: `${Math.round(Math.min(1, Math.max(0, r)) * 100)}%` }} /></span>
    </span>
  )
}

function Table({ cols, children }: { cols: string[]; children: ReactNode }) {
  return (
    <table className="bt">
      <thead>
        <tr>{cols.map(c => <th key={c}>{c}</th>)}</tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  )
}

const FACTOR_COLS = ['Factor', 'Data', 'Score', 'Weight']

function Missing({ what }: { what: string }) {
  return <p className="bd-missing">{what} could not be computed for this company.</p>
}

/* Rows are keyed by position as well as label: nothing in the contract enforces
 * distinct labels within a table, and the index removes the whole class of
 * duplicate-key warning. */

function QualityPanel({ q }: { q: QualityBlock }) {
  const composite = q.fundamentals_composite
  const adjusted = composite !== null && q.score !== null
    && Math.abs(composite - q.score) > COMPOSITE_TOLERANCE
  const tier = qualityTier(q.score)
  return (
    <>
      <div className="sum">
        <span className="big">{num(q.score, 1)} / 10</span>
        {tier && <span className={q.score !== null && q.score >= 7 ? 'pill good' : 'pill'}>{tier}</span>}
        {q.profile_label && <span>{q.profile_label} profile</span>}
        <span className="hint">Metrics are equally weighted within their section</span>
      </div>
      <Table cols={FACTOR_COLS}>
        {q.categories.map((c, ci) => (
          <CategoryRows key={`${ci}-${c.key}`} n={ci + 1} c={c} />
        ))}
        <tr className="tot">
          <td>Quality score</td><td />
          <td className="s">{composite === null ? DASH : `${num(composite * 10, 1)} / 100`}</td>
          <td className="w">100%</td>
        </tr>
      </Table>
      {/* For an operationally unprofitable company the engine legitimately moves
          the published score away from what these categories roll up to. Saying
          so is the point of a panel that claims every number is checkable. */}
      {adjusted && (
        <p className="bd-note">
          The categories above roll up to <b>{num(composite, 1)}</b>; the published
          Quality score of <b>{num(q.score, 1)}</b> is that figure after the
          calibrations listed below.
        </p>
      )}
    </>
  )
}

function CategoryRows({ n, c }: { n: number; c: QualityBlock['categories'][number] }) {
  // Points earned = the category's 0–10 score scaled to its weight, so the four
  // shaded rows add up to the total row exactly as the mock's do.
  const pts = c.score === null ? null : (c.score / 10) * c.weight_pct
  return (
    <>
      <tr className="sec">
        <td>{n} · {c.name}</td><td />
        <td className="s">{pts === null ? DASH : `${num(pts, 1)} / ${String(c.weight_pct + 0)}`}</td>
        <td className="w">{weight(c.weight_pct)}</td>
      </tr>
      {c.metrics.map((m, mi) => m.excluded ? (
        <tr key={`${mi}-${m.label}`} className="off">
          <td>
            {m.label}{' '}
            {m.excluded_by
              ? <Tip label="calibration: excluded" tip={m.excluded_by} className="xn" />
              : <span className="xn">excluded</span>}
          </td>
          <td className="d">n/a</td>
          <td className="s">{DASH}</td>
          <td className="w">0%</td>
        </tr>
      ) : (
        <tr key={`${mi}-${m.label}`}>
          <td>{m.label}</td>
          <td className="d">{m.display ?? DASH}</td>
          <td className="s"><Score v={m.score} max={10} /></td>
          <td className="w">{weight(m.weight_pct)}</td>
        </tr>
      ))}
    </>
  )
}

function MoatPanel({ m }: { m: MoatBlock }) {
  const tier = moatTier(m.score)
  const groups: string[] = []
  for (const f of m.factors) if (!groups.includes(f.group)) groups.push(f.group)
  return (
    <>
      <div className="sum">
        <span className="big">{num(m.score, 1)} / 10</span>
        {tier && <span className={m.score !== null && m.score >= 6 ? 'pill good' : 'pill'}>{tier}</span>}
        <span>
          <Tip label={m.gated ? 'Economic-profit gate ✗ Moat capped' : 'Economic-profit gate ✓ passed'}
               tip={GATE_TIP} />
        </span>
        <span className="hint">Hover a factor for what it measures</span>
      </div>
      <Table cols={FACTOR_COLS}>
        {groups.map(g => {
          const fs = m.factors.filter(f => f.group === g)
          const scored = fs.filter(f => f.score !== null)
          const sw = scored.reduce((a, f) => a + f.weight_pct, 0)
          const gs = sw > 0 ? scored.reduce((a, f) => a + (f.score as number) * f.weight_pct, 0) / sw : null
          const w = fs.reduce((a, f) => a + f.weight_pct, 0)
          return (
            <GroupRows key={g} title={g} score={`${num(gs, 1)} / 10`} w={weight(w)}>
              {fs.map((f, i) => (
                <tr key={`${i}-${f.label}`}>
                  <td>{MOAT_TIPS[f.label] ? <Tip label={f.label} tip={MOAT_TIPS[f.label]} /> : f.label}</td>
                  <td className="d">{f.display ?? DASH}</td>
                  <td className="s"><Score v={f.score} max={10} /></td>
                  <td className="w">{weight(f.weight_pct)}</td>
                </tr>
              ))}
            </GroupRows>
          )
        })}
        <tr className="tot">
          <td>Moat score</td><td />
          <td className="s">{num(m.score, 1)} / 10</td>
          <td className="w">100%</td>
        </tr>
      </Table>
      {m.excluded.length > 0 && (
        <p className="bd-note">Not scored for this company, and re-weighted out: {m.excluded.join(', ')}.</p>
      )}
    </>
  )
}

function GroupRows({ title, score, w, children }: {
  title: string; score: string; w: string; children: ReactNode
}) {
  return (
    <>
      <tr className="sec"><td>{title}</td><td /><td className="s">{score}</td><td className="w">{w}</td></tr>
      {children}
    </>
  )
}

function FairValuePanel({ fv, price }: { fv: FairValueBlock; price: number | null }) {
  return (
    <>
      <div className="sum">
        <span className="big">{dollars(fv.value)}</span>
        <span>vs price {money(price)}</span>
        <span className={gapClass(fv.gap_pct)} style={{ fontWeight: 700 }}>{gapPct(fv.gap_pct)}</span>
        {fv.type_label && <span className="pill">{fv.type_label} valuation blend</span>}
        <span className="hint">The company type sets the method weights</span>
      </div>
      <Table cols={['Method', 'Value / share', 'Contribution', 'Weight']}>
        {fv.methods.map((mt, i) => (
          <tr key={`${i}-${mt.label}`}>
            <td>{mt.label}</td>
            <td className="d">{money(mt.value)}</td>
            <td className="s mono">{money(mt.contribution)}</td>
            <td className="w">{weight(mt.weight_pct)}</td>
          </tr>
        ))}
        {/* One exact blended number, never a range (spec section 8 rule 7). */}
        <tr className="tot">
          <td>Blended fair value</td><td />
          <td className="s">{money(fv.value)}</td>
          <td className="w">100%</td>
        </tr>
      </Table>
    </>
  )
}

function AxisRows({ title, score, factors, risk }: {
  title: string; score: number | null; factors: RewardRiskFactor[]; risk?: boolean
}) {
  return (
    <GroupRows title={title} score={score === null ? DASH : `${num(score, 1)} / 5`} w="100%">
      {factors.map((f, i) => f.dropped ? (
        <tr key={`${i}-${f.label}`} className="off">
          <td>{f.label} <span className="xn">no data</span></td>
          <td className="d">n/a</td>
          <td className="s">{DASH}</td>
          <td className="w">0%</td>
        </tr>
      ) : (
        <tr key={`${i}-${f.label}`}>
          <td>{f.label}</td>
          <td className="d">{f.display ?? DASH}</td>
          <td className="s"><Score v={f.score} max={5} risk={risk} /></td>
          <td className="w">{weight(f.weight_pct)}</td>
        </tr>
      ))}
    </GroupRows>
  )
}

function RewardRiskPanel({ rr }: { rr: RewardRiskBlock }) {
  const favoured = rr.tier === 'Asymmetric Upside' || rr.tier === 'Reward-Favored'
  return (
    <>
      <div className="sum">
        <span className="big">{rr.ratio === null ? DASH : `${num(rr.ratio, 1)}×`}</span>
        {rr.tier && <span className={favoured ? 'pill good' : 'pill'}>{rr.tier}</span>}
        <span>Reward {num(rr.reward_score, 1)} ÷ Risk {num(rr.risk_score, 1)}</span>
        {/* The direction has to be stated: a bare ratio leaves a reader guessing
            which way is good, and the range is the clamp the engine applies. */}
        <span className="hint">Range 0.2×–5.0× · above 1.0 = more reward than risk</span>
      </div>
      <Table cols={FACTOR_COLS}>
        <AxisRows title="Reward axis · higher is better" score={rr.reward_score} factors={rr.reward} />
        <AxisRows title="Risk axis · higher = more risk" score={rr.risk_score} factors={rr.risk} risk />
      </Table>
      <div className="ladder">
        {[...RR_TIERS].reverse().map(t => (
          <div key={t} className={t === rr.tier ? 'step on' : 'step'}>{t}</div>
        ))}
      </div>
    </>
  )
}

function headline(row: TickerPayload, i: AssessmentId): string {
  if (i === 0) return num(row.quality?.score ?? null, 1)
  if (i === 1) return num(row.moat?.score ?? null, 1)
  if (i === 2) return dollars(row.fair_value?.value ?? null)
  const r = row.reward_risk?.ratio ?? null
  return r === null || !Number.isFinite(r) ? DASH : `${num(r, 1)}×`
}

export default function Breakdown({ row, tab, onTab }: {
  row: TickerPayload
  tab: AssessmentId
  onTab: (id: AssessmentId) => void
}) {
  // Only the calibrations that fired AND touch the assessment on screen, as the
  // mock shows them; a name this page does not know is shown on every tab.
  const cals = (row.calibrations ?? []).filter(c => !CAL_INFO[c] || CAL_INFO[c].affects.includes(tab))
  return (
    <div className="bd">
      {/* Plain buttons with aria-pressed rather than a real tablist: a tablist
          owes a screen-reader user roving tabindex and arrow-key navigation, and a
          half-built one is worse than none. Switching tabs is deliberately NOT
          tracked — spec section 9 lists "individual breakdown tab switches" among
          the events not instrumented. */}
      <div className="tabs">
        {TABS.map((t, i) => (
          <button key={t} type="button" className={i === tab ? 'tab on' : 'tab'}
                  aria-pressed={i === tab}
                  onClick={() => onTab(i as AssessmentId)}>
            {t}<b>{headline(row, i as AssessmentId)}</b>
          </button>
        ))}
      </div>

      {tab === 0 && (row.quality ? <QualityPanel q={row.quality} /> : <Missing what="Quality" />)}
      {tab === 1 && (row.moat ? <MoatPanel m={row.moat} /> : <Missing what="Moat" />)}
      {tab === 2 && (row.fair_value
        ? <FairValuePanel fv={row.fair_value} price={row.price} />
        : <Missing what="Fair Value" />)}
      {tab === 3 && (row.reward_risk
        ? <RewardRiskPanel rr={row.reward_risk} />
        : <Missing what="Reward / Risk" />)}

      {cals.length > 0 && (
        <div className="applied">
          <div className="al"><span className="ci" aria-hidden="true">◆</span>Calibrations applied · hover for why &amp; effect</div>
          <div className="cal-chips">
            {cals.map((c, i) => CAL_INFO[c]
              ? <Tip key={`${i}-${c}`} label={c} tip={CAL_INFO[c].tip} className="cal trig" />
              : <span key={`${i}-${c}`} className="cal trig">{c}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}
