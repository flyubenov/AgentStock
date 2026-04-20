from __future__ import annotations
import re
from agents.base_agent import BaseAgent
from models import AgentResult
from services.normalizer import derive_pre_screener


class PreScreenerAgent(BaseAgent):
    agent_name = "pre_screener"
    max_tokens = 2000

    def parse_score(self, response: str) -> tuple[float | None, str | None]:
        rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        growth_match = re.search(r"GROWTH POTENTIAL:\s*(.+)", response, re.IGNORECASE)
        fin_match = re.search(r"FINANCIAL STATE:\s*(.+)", response, re.IGNORECASE)

        rec = rec_match.group(1).strip() if rec_match else None
        growth = growth_match.group(1).strip() if growth_match else None
        fin = fin_match.group(1).strip() if fin_match else None

        derived = derive_pre_screener(rec, growth, fin)
        return derived, rec
