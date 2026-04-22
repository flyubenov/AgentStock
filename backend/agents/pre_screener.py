from __future__ import annotations
import re
from agents.base_agent import BaseAgent
from models import AgentResult
from services.normalizer import derive_pre_screener


class PreScreenerAgent(BaseAgent):
    agent_name = "pre_screener"
    model = "claude-haiku-4-5-20251001"
    max_tokens = 300
    tools: list = []

    def parse_score(self, response: str) -> tuple[float | None, str | None, str | None]:
        rec_m = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        growth_m = re.search(r"GROWTH POTENTIAL:\s*(.+)", response, re.IGNORECASE)
        fin_m = re.search(r"FINANCIAL STATE:\s*(.+)", response, re.IGNORECASE)
        rat_m = re.search(r"RATIONALE:\s*(.+)", response, re.IGNORECASE)

        rec = rec_m.group(1).strip() if rec_m else None
        growth = growth_m.group(1).strip() if growth_m else None
        fin = fin_m.group(1).strip() if fin_m else None
        rationale = rat_m.group(1).strip() if rat_m else None

        derived = derive_pre_screener(rec, growth, fin)
        return derived, rec, rationale
