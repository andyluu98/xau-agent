"""History loader: MT5 deals + journal CSV → text brief feed cho LLM."""
from xau_agent.history.loader import HistoryBrief, build_brief

__all__ = ["HistoryBrief", "build_brief"]
