import { type ReactNode } from 'react'
import type {
  AssessmentId, FairValueBlock, MetricRow, MoatBlock, QualityBlock,
  RewardRiskBlock, RewardRiskFactor, TickerPayload,
} from '../types'
import { DASH, figure, money, num, weight } from '../format'

/** The tab strip is indexed by `AssessmentId`, the same bare index Hero's
 *  assessment cards hand back from `onSelectAssessment`. Kept in the same order
 *  and wording as Hero's ASSESSMENTS — Breakdown.test.tsx pins the two together,
 *  because a silent drift would mean clicking "Moat" in the hero opens "Fair
 *  Value" here. Never "Risk/Reward" (spec section 8). */
const TABS = ['Quality', 'Moat', 'Fair Value', 'Reward / Risk'] as const

const FACTOR_COLS = ['Factor', 'Data', 'Score', 'Weight']

/** The two figures are rounded to DIFFERENT precisions, in different places, by
 *  backend/landing/contract.py: the published `score` to one decimal, the
 *  categories' own `fundamentals_composite` to two. So they can differ by a
 *  rounding hair — up to half of the coarser step — without anything having
 *  been adjusted, and 0.05 is that half-step. Anything larger is a real
 *  adjustment and gets explained. Do not "correct" this to 0.005: the one-decimal
 *  side is what sets the floor. */
const COMPOSITE_TOLERANCE = 0.05

/** "8.0 / 10" — but a bare em dash when there is no value, since "— / 10" reads
 *  as a scale that broke rather than a metric that was never scored. */
function outOf(v: number | null, max: number | string, dp = 1): string {
  const text = num(v, dp)
  return text === DASH ? text : `${text} / ${max}`
}

/** Appends a unit only to a value that exists, for the same reason. */
function unit(text: string, suffix: string): string {
  return text === DASH ? text : `${text}${suffix}`
}

function Missing({ what }: { what: string }) {
  return <p className="bd-missing">{what} could not be computed for this company.</p>
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

/* Rows are keyed by position as well as label. Every real payload happens to
 * carry distinct labels within a table — screener metric labels are unique per
 * section, moat pillars and fair-value methods are keyed by code upstream, and
 * the reward and risk axes render as separate tables — but nothing in the
 * contract or the types enforces that, and an unmapped code falling through
 * `humanize()` could collide. The index costs nothing and removes the whole
 * class of duplicate-key warning. */

function QualityPanel({ q }: { q: QualityBlock }) {
  const composite = q.fundamentals_composite
  const adjusted = composite !== null && q.score !== null
    && Math.abs(composite - q.score) > COMPOSITE_TOLERANCE

  return (
    <>
      {q.profile_label && (
        <p className="bd-sum">Scored for its profile: <b>{q.profile_label}</b></p>
      )}
      {q.categories.map((c, ci) => (
        <div key={`${ci}-${c.key}`} className="cat">
          <div className="cat-h">
            {c.name}
            <span className="wt">{weight(c.weight_pct)}</span>
            <span className="cs">{outOf(c.score, 10)}</span>
          </div>
          <Table cols={FACTOR_COLS}>
            {c.metrics.map((m: MetricRow, mi) => (
              <tr key={`${mi}-${m.label}`} className={m.excluded ? 'metric excluded' : 'metric'}>
                <td>
                  {m.label}
                  {m.excluded && m.excluded_by && <span className="xn">{m.excluded_by}</span>}
                </td>
                <td>{figure(m.raw)}</td>
                <td>{m.excluded ? DASH : outOf(m.score, 10)}</td>
                <td>{weight(m.weight_pct)}</td>
              </tr>
            ))}
          </Table>
        </div>
      ))}
      {/* The published Quality score is the headline the grid shows; for an
          operationally unprofitable company the engine legitimately moves it
          away from what these categories roll up to. Saying so is the whole
          point of a panel that claims every number is checkable — a headline
          silently contradicting its own table is the worst thing it could do.
          Nothing is rendered in the common case, where the two agree. */}
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

function MoatPanel({ m }: { m: MoatBlock }) {
  return (
    <>
      <p className="bd-sum">
        Durability of economic profit — <b>{outOf(m.score, 100, 0)}</b>
        {m.gated && <span className="xn">Economic-profit gate applied</span>}
      </p>
      {/* Three columns, not the shared four: a moat pillar carries a label, the
          points it was awarded out of its maximum, and that maximum's share of
          the score. There is no fourth fact, so a "Score" column here could only
          repeat the points cell or invent a figure. */}
      <Table cols={['Factor', 'Points', 'Weight']}>
        {m.factors.map((f, i) => (
          <tr key={`${i}-${f.label}`} className="metric">
            <td>{f.label}</td>
            <td>{outOf(f.points, f.max_points, 0)}</td>
            <td>{weight(f.weight_pct)}</td>
          </tr>
        ))}
      </Table>
      {m.excluded.length > 0 && (
        <p className="bd-note">Not scored for this company: {m.excluded.join(', ')}.</p>
      )}
    </>
  )
}

function FairValuePanel({ fv }: { fv: FairValueBlock }) {
  return (
    <>
      <p className="bd-sum">
        {fv.type_label
          ? <>Valued as <b>{fv.type_label}</b> — blended fair value </>
          : <>Blended fair value </>}
        {/* One exact blended number, never a range (spec section 8 rule 7). */}
        <b>{money(fv.value)}</b>
      </p>
      <Table cols={['Method', 'Value', 'Contribution', 'Weight']}>
        {fv.methods.map((mt, i) => (
          <tr key={`${i}-${mt.label}`} className="metric">
            <td>{mt.label}</td>
            <td>{money(mt.value)}</td>
            <td>{money(mt.contribution)}</td>
            <td>{weight(mt.weight_pct)}</td>
          </tr>
        ))}
      </Table>
    </>
  )
}

function Axis({ title, note, score, factors }: {
  title: string
  note?: string
  score: number | null
  factors: RewardRiskFactor[]
}) {
  return (
    <div className="cat">
      <div className="cat-h">
        {title}{note && <span className="an">{note}</span>}
        <span className="cs">{outOf(score, 5)}</span>
      </div>
      <Table cols={FACTOR_COLS}>
        {factors.map((f, i) => (
          <tr key={`${i}-${f.label}`} className={f.dropped ? 'metric excluded' : 'metric'}>
            <td>{f.label}</td>
            <td>{figure(f.raw)}</td>
            <td>{f.dropped ? DASH : outOf(f.score, 5)}</td>
            <td>{weight(f.weight_pct)}</td>
          </tr>
        ))}
      </Table>
    </div>
  )
}

function RewardRiskPanel({ rr }: { rr: RewardRiskBlock }) {
  return (
    <>
      {/* The direction has to be stated: a bare ratio leaves a reader guessing
          which way is good, and the range is the clamp the engine actually
          applies (risk_reward/config.py ratio_clamp). */}
      <p className="bd-sum rr-pill">
        Reward ÷ Risk · range 0.2×–5.0× · higher is better —{' '}
        <b>{unit(num(rr.ratio, 1), '×')}</b>
        {rr.tier && <span className="tier">{rr.tier}</span>}
      </p>
      <Axis title="Reward axis" score={rr.reward_score} factors={rr.reward} />
      <Axis title="Risk axis" note="a high score here is the bad one"
            score={rr.risk_score} factors={rr.risk} />
    </>
  )
}

export default function Breakdown({ row, tab, onTab }: {
  row: TickerPayload
  tab: AssessmentId
  onTab: (id: AssessmentId) => void
}) {
  return (
    <div className="bd">
      {/* Plain buttons with aria-pressed rather than a real tablist: a tablist
          owes a screen-reader user roving tabindex and arrow-key navigation,
          and a half-built one is worse than none. These are toggle buttons, and
          get Enter/Space and a focus ring for free.
          Switching tabs is deliberately NOT tracked — spec section 9 lists
          "individual breakdown tab switches" among the events not instrumented. */}
      <div className="bd-tabs">
        {TABS.map((t, i) => (
          <button key={t} type="button" className={i === tab ? 'on' : ''}
                  aria-pressed={i === tab}
                  onClick={() => onTab(i as AssessmentId)}>
            {t}
          </button>
        ))}
      </div>

      {tab === 0 && (row.quality
        ? <QualityPanel q={row.quality} />
        : <Missing what="Quality" />)}
      {tab === 1 && (row.moat
        ? <MoatPanel m={row.moat} />
        : <Missing what="Moat" />)}
      {tab === 2 && (row.fair_value
        ? <FairValuePanel fv={row.fair_value} />
        : <Missing what="Fair Value" />)}
      {tab === 3 && (row.reward_risk
        ? <RewardRiskPanel rr={row.reward_risk} />
        : <Missing what="Reward / Risk" />)}

      {/* Only the calibrations that actually fired, already reader-facing copy
          from backend/landing/labels.py. Spans, not the hero's `.chip` button
          style — these are not clickable and must not look it. */}
      {row.calibrations.length > 0 && (
        <div className="cals">
          <span className="cals-h">Calibrations applied:</span>
          {row.calibrations.map((c, i) => <span key={`${i}-${c}`} className="cal">{c}</span>)}
        </div>
      )}
    </div>
  )
}
