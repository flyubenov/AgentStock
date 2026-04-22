from __future__ import annotations
import asyncio, os, re
from pathlib import Path
import anthropic
from models import AgentResult

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_BACKOFF_BASE = 15.0
_MAX_BACKOFF = 120.0
_MAX_RETRIES = 5


class BaseAgent:
    agent_name: str = "base"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4000
    tools: list = [{"type": "web_search_20250305", "name": "web_search"}]

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._system_prompt = (
            _PROMPTS_DIR / f"{self.agent_name}.md"
        ).read_text(encoding="utf-8")

    async def run(self, ticker: str, financial_block: str) -> AgentResult:
        user_content = f"Analyze ticker: {ticker}\n\n{financial_block}"
        last_error: str | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                kwargs: dict = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": [
                        {
                            "type": "text",
                            "text": self._system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [{"role": "user", "content": user_content}],
                }
                if self.tools:
                    kwargs["tools"] = self.tools

                response = await self._client.messages.create(**kwargs)
                full_text = self._extract_text(response)
                raw_score, recommendation, rationale = self.parse_score(full_text)
                return AgentResult(
                    agent_name=self.agent_name,
                    ticker=ticker,
                    raw_score=raw_score,
                    recommendation=recommendation,
                    rationale=rationale,
                    raw_response=full_text,
                    report=self._extract_report(full_text),
                )

            except anthropic.RateLimitError as e:
                last_error = str(e)
                wait = min(_BACKOFF_BASE * (2**attempt), _MAX_BACKOFF)
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
        return "\n".join(
            block.text for block in response.content if hasattr(block, "text")
        )

    def _extract_report(self, text: str) -> str:
        skip = re.compile(
            r"^(SCORE|RECOMMENDATION|GROWTH POTENTIAL|FINANCIAL STATE|RATIONALE):",
            re.IGNORECASE,
        )
        lines = [l for l in text.strip().splitlines() if not skip.match(l.strip())]
        return "\n".join(lines).strip()

    def parse_score(self, response: str) -> tuple[float | None, str | None, str | None]:
        score_m = re.search(r"SCORE:\s*([\d.]+)", response, re.IGNORECASE)
        rec_m = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        rat_m = re.search(r"RATIONALE:\s*(.+)", response, re.IGNORECASE)
        score = float(score_m.group(1)) if score_m else None
        rec = rec_m.group(1).strip() if rec_m else None
        rationale = rat_m.group(1).strip() if rat_m else None
        return score, rec, rationale
