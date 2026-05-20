"""AI-assisted fraud detection — explainable rules + IsolationForest.

Designed for the showcase demo: every signal has a plain-English
explanation so evaluators see *why* a transfer was flagged. Risk
scores are deterministic for replayability.
"""

from __future__ import annotations

from .rules import RuleSignal, RULES
from .scorer import SCORER_VERSION, FraudScore, score_subject

__all__ = ["FraudScore", "RULES", "RuleSignal", "SCORER_VERSION", "score_subject"]
