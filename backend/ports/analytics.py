"""
Analytics Port — Technical Blueprint Section 14 (Plugin Architecture),
listed there as an example optional plugin. This is that plugin,
purpose-built for exactly one question raised at the end of the last
strategy discussion: "did this student come back next assignment?"

Deliberately minimal — this is NOT a general analytics/telemetry
system. It tracks the smallest signal that answers the retention
question, per the "instrument a simple feedback signal" step from
the earlier execution plan. Nothing here is required for the product
to function — removing this plugin must never affect generation,
per Constitution Principle 16.
"""

from typing import Protocol
from dataclasses import dataclass


@dataclass
class RetentionSummary:
    total_generations: int
    unique_users: int
    returning_users: int  # users with 2+ generations on different days
    exports_completed: int


class AnalyticsPort(Protocol):
    def record_generation(self, owner_id: str | None, structure_source: str) -> None:
        """Called once per completed generation, whether AI-enhanced or
        rule-based. owner_id is None for anonymous use — still counted
        toward total volume, just not toward per-user retention."""
        ...

    def record_export(self, owner_id: str | None) -> None:
        """Called when a student actually downloads a file — the real
        'did they get value' signal, distinct from just generating."""
        ...

    def get_retention_summary(self) -> RetentionSummary:
        ...
