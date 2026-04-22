from agents.base_agent import BaseAgent


class LynchGarpAgent(BaseAgent):
    agent_name = "lynch_garp"
    model = "claude-haiku-4-5-20251001"
    max_tokens = 300
    tools: list = []
