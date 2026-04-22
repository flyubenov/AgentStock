from __future__ import annotations
import asyncio, os, uuid
from collections.abc import AsyncGenerator
from models import TickerResult, AgentResult, FairValueResult
from agents.buffett_munger import BuffettMungerAgent
from agents.lynch_garp import LynchGarpAgent
from agents.growth_stock import GrowthStockAgent
from agents.business_engine import BusinessEngineAgent
from agents.canslim import CANSLIMAgent
from agents.pre_screener import PreScreenerAgent
from valuation.gemini_fv import run as gemini_fv_run
from valuation.calculator_1 import run as calc1_run
from valuation.calculator_2 import run as calc2_run
from services.yahoo import fetch_ticker_info, extract_financials, format_financial_block
from services.normalizer import apply_normalisation
from services.sheets import upsert_result
from orchestrator.aggregator import aggregate

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "5"))

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

_AGENTS = {
    "buffett_munger": BuffettMungerAgent,
    "lynch_garp": LynchGarpAgent,
    "growth_stock": GrowthStockAgent,
    "business_engine": BusinessEngineAgent,
    "canslim": CANSLIMAgent,
    "pre_screener": PreScreenerAgent,
}


async def _run_agent(key: str, cls, ticker: str, financial_block: str) -> tuple[str, AgentResult]:
    async with _semaphore:
        agent = cls()
        result = await agent.run(ticker, financial_block)
        result = apply_normalisation(key, result)
        return key, result


async def _run_fv(key: str, fn, ticker: str) -> tuple[str, FairValueResult]:
    return key, await fn(ticker)


async def analyse_ticker(ticker: str) -> TickerResult:
    """Run all 9 analyses for a single ticker. Aborts if yfinance pre-fetch fails."""
    financial_block = await format_financial_block(ticker)
    if financial_block is None:
        return TickerResult(
            ticker=ticker,
            status="failed",
            errors=["yfinance data unavailable"],
        )

    agent_tasks = [_run_agent(k, cls, ticker, financial_block) for k, cls in _AGENTS.items()]
    fv_tasks = [
        _run_fv("gemini_fv", gemini_fv_run, ticker),
        _run_fv("calculator_1", calc1_run, ticker),
        _run_fv("calculator_2", calc2_run, ticker),
    ]

    all_results = await asyncio.gather(*agent_tasks, *fv_tasks, return_exceptions=True)

    agent_results: dict[str, AgentResult] = {}
    fv_results: dict[str, FairValueResult] = {}

    for i, res in enumerate(all_results):
        if isinstance(res, Exception):
            key = list(_AGENTS.keys())[i] if i < 6 else ["gemini_fv", "calculator_1", "calculator_2"][i - 6]
            if i < 6:
                agent_results[key] = AgentResult(
                    agent_name=key, ticker=ticker, status="failed", error=str(res)
                )
            else:
                fv_results[key] = FairValueResult(
                    ticker=ticker, method_name=key, status="failed", error=str(res)
                )
        else:
            key, result = res
            if isinstance(result, AgentResult):
                agent_results[key] = result
            else:
                fv_results[key] = result

    company_name = None
    current_price = None
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)
        company_name = fin.get("company_name")
        current_price = fin.get("current_price")
    except Exception:
        pass

    return aggregate(ticker, company_name, current_price, agent_results, fv_results)


async def run_batch(
    tickers: list[str],
    job_id: str,
    cancel_event: asyncio.Event,
) -> AsyncGenerator[dict, None]:
    """Process tickers in groups of BATCH_SIZE, yield SSE events."""
    total = len(tickers)
    completed = 0
    failed = 0

    yield {"type": "job_start", "job_id": job_id, "total": total}

    groups = [tickers[i : i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

    for group in groups:
        if cancel_event.is_set():
            break

        group_tasks = {t: asyncio.create_task(analyse_ticker(t)) for t in group}

        for ticker, task in group_tasks.items():
            yield {"type": "ticker_start", "ticker": ticker}
            try:
                result = await task
                if result.status == "failed":
                    failed += 1
                else:
                    completed += 1
                    try:
                        await upsert_result(result)
                    except Exception as e:
                        result.errors.append(f"sheets_write: {e}")
                yield {"type": "ticker_done", "ticker": ticker, "result": result.model_dump()}
            except Exception as e:
                failed += 1
                yield {"type": "ticker_error", "ticker": ticker, "error": str(e)}

    status = "cancelled" if cancel_event.is_set() else "completed"
    yield {"type": "job_done", "job_id": job_id, "completed": completed, "failed": failed, "status": status}
