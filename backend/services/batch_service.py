from __future__ import annotations
import asyncio, json, os
from datetime import datetime, timezone
from pathlib import Path
import anthropic
from models import AgentResult, FairValueResult, TickerResult, BatchJobFile
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

_JOBS_DIR = Path(__file__).parent.parent / "jobs"

_AGENTS = {
    "buffett_munger": BuffettMungerAgent,
    "lynch_garp": LynchGarpAgent,
    "growth_stock": GrowthStockAgent,
    "business_engine": BusinessEngineAgent,
    "canslim": CANSLIMAgent,
    "pre_screener": PreScreenerAgent,
}


# ── Job file helpers ──────────────────────────────────────────────────────────

def _jobs_dir() -> Path:
    _JOBS_DIR.mkdir(exist_ok=True)
    return _JOBS_DIR


def write_job_file(job: BatchJobFile) -> None:
    path = _jobs_dir() / f"{job.job_id}.json"
    path.write_text(job.model_dump_json(), encoding="utf-8")


def read_job_file(job_id: str) -> BatchJobFile | None:
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return None
    return BatchJobFile.model_validate_json(path.read_text(encoding="utf-8"))


def update_job_status(job_id: str, status: str) -> None:
    job = read_job_file(job_id)
    if job:
        job.status = status
        write_job_file(job)


# ── Batch request building ────────────────────────────────────────────────────

def _parse_custom_id(custom_id: str) -> tuple[str, str, str]:
    parts = custom_id.split("__")
    return parts[0], parts[1], parts[2]


def build_batch_requests(
    job_id: str,
    ticker_blocks: dict[str, str],
) -> list[dict]:
    requests = []
    for ticker, financial_block in ticker_blocks.items():
        for agent_name, agent_cls in _AGENTS.items():
            agent = agent_cls()
            user_content = f"Analyze ticker: {ticker}\n\n{financial_block}"
            params: dict = {
                "model": agent.model,
                "max_tokens": agent.max_tokens,
                "system": [
                    {
                        "type": "text",
                        "text": agent._system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [{"role": "user", "content": user_content}],
            }
            if agent.tools:
                params["tools"] = agent.tools
            requests.append({
                "custom_id": f"{job_id}__{ticker}__{agent_name}",
                "params": params,
            })
    return requests


# ── Submit / status / cancel ──────────────────────────────────────────────────

async def submit_batch_job(
    job_id: str,
    tickers: list[str],
) -> dict:
    """Pre-fetch yfinance blocks, submit batch, write job file. Returns {job_id, failed_prefetch}."""
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    ticker_blocks: dict[str, str] = {}
    failed_prefetch: list[str] = []

    for ticker in tickers:
        block = await format_financial_block(ticker)
        if block is None:
            failed_prefetch.append(ticker)
        else:
            ticker_blocks[ticker] = block

    if not ticker_blocks:
        raise ValueError("All tickers failed yfinance pre-fetch")

    requests = build_batch_requests(job_id, ticker_blocks)
    batch = await client.messages.batches.create(requests=requests)

    job = BatchJobFile(
        job_id=job_id,
        batch_id=batch.id,
        tickers=list(ticker_blocks.keys()),
        failed_prefetch=failed_prefetch,
        status="processing",
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )
    write_job_file(job)

    return {"job_id": job_id, "failed_prefetch": failed_prefetch}


async def get_batch_status(job_id: str) -> dict:
    job = read_job_file(job_id)
    if not job:
        return {"error": "job not found"}

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    batch = await client.messages.batches.retrieve(job.batch_id)

    counts = batch.request_counts
    total = counts.processing + counts.succeeded + counts.errored
    return {
        "job_id": job_id,
        "status": batch.processing_status,
        "submitted_at": job.submitted_at,
        "failed_prefetch": job.failed_prefetch,
        "request_counts": {
            "processing": counts.processing,
            "succeeded": counts.succeeded,
            "errored": counts.errored,
            "total": total,
        },
    }


async def cancel_batch_job(job_id: str) -> bool:
    job = read_job_file(job_id)
    if not job:
        return False
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    await client.messages.batches.cancel(job.batch_id)
    update_job_status(job_id, "cancelled")
    return True


# ── Results ───────────────────────────────────────────────────────────────────

async def fetch_and_aggregate_results(job_id: str) -> list[TickerResult]:
    """Parse Anthropic batch results, run FV scripts, aggregate per ticker, upsert to Sheets."""
    job = read_job_file(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Collect raw agent results per ticker
    agent_results_by_ticker: dict[str, dict[str, AgentResult]] = {
        t: {} for t in job.tickers
    }

    async for result in client.messages.batches.results(job.batch_id):
        job_id_parsed, ticker, agent_name = _parse_custom_id(result.custom_id)
        if ticker not in agent_results_by_ticker:
            continue

        if result.result.type == "succeeded":
            msg = result.result.message
            full_text = "\n".join(
                b.text for b in msg.content if hasattr(b, "text")
            )
            agent_cls = _AGENTS.get(agent_name)
            if agent_cls:
                agent = agent_cls()
                raw_score, recommendation, rationale = agent.parse_score(full_text)
                ar = AgentResult(
                    agent_name=agent_name,
                    ticker=ticker,
                    raw_score=raw_score,
                    recommendation=recommendation,
                    rationale=rationale,
                    raw_response=full_text,
                )
                ar = apply_normalisation(agent_name, ar)
                agent_results_by_ticker[ticker][agent_name] = ar
        else:
            agent_results_by_ticker[ticker][agent_name] = AgentResult(
                agent_name=agent_name,
                ticker=ticker,
                status="failed",
                error=f"batch result: {result.result.type}",
            )

    # For each ticker: run FV scripts + fetch company info concurrently, then aggregate
    ticker_results: list[TickerResult] = []

    async def _process_ticker(ticker: str) -> TickerResult:
        fv_tasks = [
            asyncio.create_task(_run_fv("gemini_fv", gemini_fv_run, ticker)),
            asyncio.create_task(_run_fv("calculator_1", calc1_run, ticker)),
            asyncio.create_task(_run_fv("calculator_2", calc2_run, ticker)),
        ]
        fv_raw = await asyncio.gather(*fv_tasks, return_exceptions=True)

        fv_results: dict[str, FairValueResult] = {}
        for i, res in enumerate(fv_raw):
            key = ["gemini_fv", "calculator_1", "calculator_2"][i]
            if isinstance(res, Exception):
                fv_results[key] = FairValueResult(
                    ticker=ticker, method_name=key, status="failed", error=str(res)
                )
            else:
                _, fvr = res
                fv_results[key] = fvr

        company_name = None
        current_price = None
        try:
            info = await fetch_ticker_info(ticker)
            fin = extract_financials(info)
            company_name = fin.get("company_name")
            current_price = fin.get("current_price")
        except Exception:
            pass

        return aggregate(
            ticker,
            company_name,
            current_price,
            agent_results_by_ticker[ticker],
            fv_results,
        )

    results = await asyncio.gather(
        *[_process_ticker(t) for t in job.tickers], return_exceptions=True
    )

    for res in results:
        if isinstance(res, Exception):
            continue
        ticker_results.append(res)
        if res.status != "failed":
            try:
                await upsert_result(res)
            except Exception:
                pass

    update_job_status(job_id, "completed")
    return ticker_results


async def _run_fv(key: str, fn, ticker: str):
    return key, await fn(ticker)
