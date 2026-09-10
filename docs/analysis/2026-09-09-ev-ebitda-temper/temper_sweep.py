"""Blast-radius sweep for the terminal EV/EBITDA multiple temper (Approach A').

Compares TWO candidate trigger signals for tempering the durable (forward-tier)
EV/EBITDA exit-multiple ceiling, holding the ACTION fixed so the comparison
isolates the SIGNAL:

  tempered_ceiling = MATURE_MULT + q * (current_ceiling - MATURE_MULT)      (q in [0,1])
    q = 1  -> no temper (franchise; keeps today's growth-coupled ceiling up to 30x)
    q = 0  -> full temper to MATURE_MULT

  Variant OM   : q = ramp(operating_margin, 0.10 -> 0.25)
  Variant ROIC : q = ramp(roic_5y_avg,      0.10 -> 0.25)

Only the durable=True branch of _ev_ebitda_ceiling is touched (forward tiers with a
reconstructable historical multiple) -- EARLY_GROWTH/capex-reroute names (IREN) are on
the non-durable path and are structurally untouched. Signal missing -> q=1 (never
temper on unknown; fail-safe).

Per ticker: baseline FV, OM-tempered FV, ROIC-tempered FV + deltas, plus the drivers
(type, hist multiple, op margin, roic5). Read-only; writes temper_out.csv.
CONCURRENCY MUST be 1 (monkeypatches shared module globals).
"""
import asyncio, csv, os, sys, time
sys.path.insert(0, r"C:/Users/f_lub/proj/Agent Stock/backend")
from dotenv import load_dotenv
load_dotenv(r"C:/Users/f_lub/proj/Agent Stock/backend/.env")

import valuation.engine as engine
import valuation.models as models
from screener.metrics import compute_metrics
from screener.data import fetch_screener_inputs
from services.sheets import read_database

OUT = os.path.join(os.path.dirname(__file__), "temper_out.csv")
CONCURRENCY = 1
MATURE_MULT = 13.0
LO, HI = 0.10, 0.25       # op-margin / ROIC ramp band (fraction)
GM_LO, GM_HI = 0.25, 0.50  # gross-margin ramp band: <=25% commodity, >=50% franchise

_orig_ceiling = models._ev_ebitda_ceiling
# per-ticker signal for the patched ceiling (serial, so a module global is safe)
_Q = {"val": 1.0}


def _ramp(x, lo, hi):
    if x is None:
        return 1.0                      # unknown -> never temper
    if x <= lo:
        return 0.0
    if x >= hi:
        return 1.0
    return (x - lo) / (hi - lo)


def _patched_ceiling(growth, durable, mega=False, conversion=None):
    base = _orig_ceiling(growth, durable, mega=mega, conversion=conversion)
    if not durable:                     # spot multiple path -> leave alone
        return base
    q = _Q["val"]
    return MATURE_MULT + q * (base - MATURE_MULT)


def _fv_with_signal(fin, q):
    _Q["val"] = q
    models._ev_ebitda_ceiling = _patched_ceiling
    try:
        return engine.evaluate(dict(fin)).get("fair_value")
    finally:
        models._ev_ebitda_ceiling = _orig_ceiling


async def one(ticker):
    row = {"ticker": ticker}
    try:
        inp = await fetch_screener_inputs(ticker)
    except Exception as e:
        inp = None
        row["note"] = f"screener_fail:{type(e).__name__}"
    om = roic5 = gm = None
    if inp is not None:
        try:
            met = compute_metrics(inp)
            om = met.op_margin            # percent
            roic5 = met.roic_5y_avg       # percent
            gm = met.gross_margin_series[0] if met.gross_margin_series else None  # percent
        except Exception as e:
            row["note"] = (row.get("note", "") + f" metrics_fail:{type(e).__name__}").strip()

    cap = {}
    real_eval = engine.evaluate
    real_fetch = engine.fetch_screener_inputs

    async def cached_fetch(_t, _inp=inp):
        return _inp

    def wrap_eval(fin):
        cap["fin"] = dict(fin)
        return real_eval(fin)

    engine.evaluate = wrap_eval
    if inp is not None:
        engine.fetch_screener_inputs = cached_fetch
    try:
        live = await engine.run(ticker)
    except Exception as e:
        live = None
        row["note"] = (row.get("note", "") + f" run_fail:{type(e).__name__}").strip()
    finally:
        engine.evaluate = real_eval
        engine.fetch_screener_inputs = real_fetch

    if live is not None:
        lv = live.__dict__
        row["company"] = lv.get("company_name")
        row["type"] = lv.get("stock_type")
        row["price"] = lv.get("current_price")
        row["fv_base"] = lv.get("fair_value")
        fin = cap.get("fin")
        row["hist_mult"] = fin.get("ev_ebitda_hist") if fin else None
        row["op_margin"] = om
        row["roic5"] = roic5
        row["gross_margin"] = gm
        if fin is not None and lv.get("fair_value") is not None:
            q_om = _ramp(None if om is None else om / 100.0, LO, HI)
            q_roic = _ramp(None if roic5 is None else roic5 / 100.0, LO, HI)
            q_gm = _ramp(None if gm is None else gm / 100.0, GM_LO, GM_HI)
            row["q_om"] = round(q_om, 2)
            row["q_roic"] = round(q_roic, 2)
            row["q_gm"] = round(q_gm, 2)
            try:
                row["fv_om"] = _fv_with_signal(fin, q_om)
            except Exception as e:
                row["note"] = (row.get("note", "") + f" om_fail:{type(e).__name__}").strip()
            try:
                row["fv_roic"] = _fv_with_signal(fin, q_roic)
            except Exception as e:
                row["note"] = (row.get("note", "") + f" roic_fail:{type(e).__name__}").strip()
            try:
                row["fv_gm"] = _fv_with_signal(fin, q_gm)
            except Exception as e:
                row["note"] = (row.get("note", "") + f" gm_fail:{type(e).__name__}").strip()
    return row


FIELDS = ["ticker", "company", "type", "price", "hist_mult",
          "gross_margin", "op_margin", "roic5", "q_gm", "q_om", "q_roic",
          "fv_base", "fv_gm", "fv_om", "fv_roic",
          "d_gm_pct", "d_om_pct", "d_roic_pct", "note"]


def finalize(row):
    b = row.get("fv_base")
    for src, key in (("fv_gm", "d_gm_pct"), ("fv_om", "d_om_pct"), ("fv_roic", "d_roic_pct")):
        v = row.get(src)
        if isinstance(b, (int, float)) and isinstance(v, (int, float)) and b:
            row[key] = round(100.0 * (v - b) / b, 1)
    for k in ("price", "hist_mult", "gross_margin", "op_margin", "roic5",
              "fv_base", "fv_gm", "fv_om", "fv_roic"):
        v = row.get(k)
        if isinstance(v, float):
            row[k] = round(v, 2)
    return {k: row.get(k, "") for k in FIELDS}


async def main():
    recs = await read_database()
    tickers, seen = [], set()
    for r in recs:
        t = getattr(r, "ticker", None)
        if t and t.upper() not in seen:
            seen.add(t.upper()); tickers.append(t)
    print(f"DB tickers: {len(tickers)}", flush=True)
    f = open(OUT, "w", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader(); f.flush()
    t0 = time.time()
    for i, t in enumerate(tickers, 1):
        row = await one(t)
        w.writerow(finalize(row)); f.flush()
        if i % 10 == 0 or i == len(tickers):
            print(f"  {i}/{len(tickers)}  ({time.time()-t0:.0f}s)", flush=True)
    f.close()
    print(f"DONE -> {OUT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
