"""Compare NEW pipelines (dynamic WACC-blended rate + quality MOS + Option A wacc())
against OLD (static 10% rate / 0.90 MOS + pre-Option-A wacc()) for every ticker in
the Database sheet. One fetch per ticker; four numbers derived from the same data.

OLD FV  = engine.evaluate(fin with the three source keys stripped) -> neutral 0.10/0.90
NEW FV  = engine.run(ticker).fair_value (live sourcing on this branch)
OLD Q   = compute_metrics+score with pre-Option-A wacc() (no non-financial floor/cap)
NEW Q   = compute_metrics+score with current Option A wacc()

Writes rows incrementally to compare_out.csv.
"""
import asyncio, csv, os, sys, time
from dotenv import load_dotenv
load_dotenv(r"C:/Users/f_lub/proj/Agent Stock/backend/.env")

import valuation.engine as engine
import screener.metrics as M
from screener.metrics import compute_metrics, ERP, BETA_CEILING, DEFAULT_RISK_FREE, _tax_rate
from screener.scoring import score
from services.sheets import read_database

OUT = os.path.join(os.path.dirname(__file__), "compare_out.csv")
# CONCURRENCY MUST be 1: the FV capture monkeypatches shared module globals
# (engine.evaluate / engine.fetch_screener_inputs / metrics.wacc), so concurrent
# coroutines would corrupt each other's captures. This comparison is serial.
CONCURRENCY = 1
SOURCE_KEYS = ("wacc", "roic_wacc_spread", "roic_5y_avg",
               "discount_rate", "ddm_rate", "mos")

_orig_wacc = M.wacc


def old_wacc(inp, tax_rate):
    """Pre-Option-A wacc(): identical to current minus the non-financial floor+cap."""
    info = inp.info
    beta = info.get("beta")
    if beta is None:
        return None
    beta = min(beta, BETA_CEILING)
    rf = inp.risk_free if inp.risk_free is not None else DEFAULT_RISK_FREE
    cost_equity = rf + beta * ERP
    debt = info.get("totalDebt") or 0.0
    equity = info.get("marketCap") or 0.0
    total = debt + equity
    if total <= 0:
        return cost_equity
    interest = inp.income.latest("Interest Expense") if inp.income is not None else None
    cost_debt = (abs(interest) / debt) * (1 - tax_rate) if (interest and debt > 0) else 0.0
    w_debt = debt / total
    return (1 - w_debt) * cost_equity + w_debt * cost_debt


def quality_of(inp, wacc_fn):
    prev = M.wacc
    M.wacc = wacc_fn
    try:
        met = compute_metrics(inp)
        sector = getattr(met, "sector", None) or inp.info.get("sector")
        q, *_ = score(met, sector)
        return q, met
    finally:
        M.wacc = prev


async def one(ticker, sem):
    async with sem:
        row = {"ticker": ticker}
        try:
            from screener.data import fetch_screener_inputs
            inp = await fetch_screener_inputs(ticker)
        except Exception as e:
            inp = None
            row["note"] = f"screener_fetch_fail:{type(e).__name__}"

        # ---- FV: capture the fin run() hands to evaluate, run live, then strip for OLD ----
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
            engine.fetch_screener_inputs = cached_fetch  # reuse the fetch above
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
            row["fv_new"] = lv.get("fair_value")
            row["status"] = lv.get("status")
            fin = cap.get("fin")
            if fin is not None and lv.get("fair_value") is not None:
                neutral_fin = {k: v for k, v in fin.items() if k not in SOURCE_KEYS}
                try:
                    row["fv_old"] = real_eval(neutral_fin).get("fair_value")
                except Exception as e:
                    row["note"] = (row.get("note", "") + f" fvold_fail:{type(e).__name__}").strip()
                # record the actually-injected knobs for transparency
                row["wacc"] = fin.get("wacc")
                row["spread"] = fin.get("roic_wacc_spread")
                row["roic5"] = fin.get("roic_5y_avg")

        # ---- Quality: old vs new wacc ----
        if inp is not None:
            try:
                row["q_new"], _ = quality_of(inp, _orig_wacc)
            except Exception as e:
                row["note"] = (row.get("note", "") + f" qnew_fail:{type(e).__name__}").strip()
            try:
                row["q_old"], _ = quality_of(inp, old_wacc)
            except Exception as e:
                row["note"] = (row.get("note", "") + f" qold_fail:{type(e).__name__}").strip()
        return row


FIELDS = ["ticker", "company", "type", "status", "price",
          "fv_old", "fv_new", "fv_delta", "fv_delta_pct",
          "q_old", "q_new", "q_delta",
          "wacc", "spread", "roic5", "note"]


def finalize(row):
    fo, fn = row.get("fv_old"), row.get("fv_new")
    if isinstance(fo, (int, float)) and isinstance(fn, (int, float)):
        row["fv_delta"] = round(fn - fo, 2)
        row["fv_delta_pct"] = round(100.0 * (fn - fo) / fo, 1) if fo else None
    qo, qn = row.get("q_old"), row.get("q_new")
    if isinstance(qo, (int, float)) and isinstance(qn, (int, float)):
        row["q_delta"] = round(qn - qo, 2)
    for k in ("price", "fv_old", "fv_new", "wacc", "spread", "roic5", "q_old", "q_new"):
        v = row.get(k)
        if isinstance(v, float):
            row[k] = round(v, 3)
    return {k: row.get(k, "") for k in FIELDS}


async def main():
    tickers = await read_database()
    tickers = [getattr(r, "ticker", None) for r in tickers]
    tickers = [t for t in tickers if t]
    # de-dup preserving order
    seen, uniq = set(), []
    for t in tickers:
        if t.upper() not in seen:
            seen.add(t.upper()); uniq.append(t)
    print(f"DB tickers: {len(uniq)}", flush=True)

    sem = asyncio.Semaphore(CONCURRENCY)
    f = open(OUT, "w", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader(); f.flush()

    done = 0
    t0 = time.time()
    tasks = [asyncio.create_task(one(t, sem)) for t in uniq]
    for coro in asyncio.as_completed(tasks):
        row = await coro
        w.writerow(finalize(row)); f.flush()
        done += 1
        if done % 10 == 0 or done == len(uniq):
            print(f"  {done}/{len(uniq)}  ({time.time()-t0:.0f}s)", flush=True)
    f.close()
    print(f"DONE {done} rows -> {OUT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
