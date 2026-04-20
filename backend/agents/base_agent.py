from __future__ import annotations
import asyncio, os, re, time
from pathlib import Path
import anthropic
from models import AgentResult

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_BACKOFF_BASE = 2.0
_MAX_BACKOFF = 30.0
_MAX_RETRIES = 3


class BaseAgent:
    agent_name: str = "base"
    model: str = "claude-opus-4-6"
    max_tokens: int = 4000
    tools = [{"type": "web_search_20250305", "name": "web_search"}]

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        path = _PROMPTS_DIR / f"{self.agent_name}.md"
        return path.read_text(encoding="utf-8")

    async def run(self, ticker: str) -> AgentResult:
        prompt = self._prompt.replace("{{TICKER}}", ticker)
        last_error: str | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    tools=self.tools,
                    messages=[{"role": "user", "content": prompt}],
                )
                full_text = self._extract_text(response)
                raw_score, recommendation = self.parse_score(full_text)
                report = self._extract_report(full_text)
                result = AgentResult(
                    agent_name=self.agent_name,
                    ticker=ticker,
                    raw_score=raw_score,
                    recommendation=recommendation,
                    raw_response=full_text,
                    report=report,
                )
                return result

            except anthropic.RateLimitError as e:
                last_error = str(e)
                wait = min(_BACKOFF_BASE * (2 ** attempt), _MAX_BACKOFF)
                await asyncio.sleep(wait)
            except Exception as e:
                last_error = str(e)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE)
                else:
                    break

        return AgentResult(
            agent_name=self.agent_name,
            ticker=ticker,
            status="failed",
            error=last_error or "Unknown error",
        )

    def _extract_text(self, response) -> str:
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)

    def _extract_report(self, text: str) -> str:
        lines = text.strip().splitlines()
        report_lines = []
        for line in lines:
            if re.match(r"^(SCORE|RECOMMENDATION|GROWTH POTENTIAL|FINANCIAL STATE):", line.strip()):
                continue
            report_lines.append(line)
        return "\n".join(report_lines).strip()

    def parse_score(self, response: str) -> tuple[float | None, str | None]:
        score_match = re.search(r"SCORE:\s*([\d.]+)", response, re.IGNORECASE)
        rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else None
        rec = rec_match.group(1).strip() if rec_match else None
        return score, rec
