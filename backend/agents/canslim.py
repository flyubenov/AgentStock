from agents.base_agent import BaseAgent


class CANSLIMAgent(BaseAgent):
    agent_name = "canslim"
    model = "claude-haiku-4-5-20251001"
    max_tokens = 300
    tools: list = []
