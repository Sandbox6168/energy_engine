"""Shared `Issue` shape for run_scenario/run_comparison's `errors`/`warnings` response
fields (ADR-0003) - which list an Issue lands in carries its severity, so unlike
verify_entities' EntityVerification there's no separate status field."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Issue:
    entity_id: str
    role: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


def prefixed(issues: list[Issue], prefix: str) -> list[Issue]:
    """Re-role every Issue with `prefix` (e.g. "data_source." or "scenario.NAME.")."""
    return [Issue(issue.entity_id, f"{prefix}{issue.role}", issue.message) for issue in issues]
