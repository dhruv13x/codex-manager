from __future__ import annotations

from dataclasses import dataclass

from .cooldown import CooldownStatus, format_remaining


@dataclass(frozen=True)
class Recommendation:
    selected: CooldownStatus
    reason: str


def choose_best_account(statuses: list[CooldownStatus]) -> Recommendation:
    if not statuses:
        raise ValueError("No account statuses available for recommendation.")

    selected = min(
        statuses,
        key=lambda item: (
            item.status != "ready",
            item.validation_status != "live",
            item.next_available_at if item.status != "ready" else item.session_start_at,
            item.email,
        ),
    )

    if selected.status == "ready":
        if selected.validation_status == "live":
            reason = "Ready now from live Codex status."
        else:
            reason = "Ready now from backup metadata."
    else:
        reason = (
            "No account is ready. This account becomes available first in "
            f"{format_remaining(selected.remaining_seconds)}."
        )

    return Recommendation(selected=selected, reason=reason)


def recommendation_to_text(recommendation: Recommendation) -> str:
    selected = recommendation.selected
    lines = [
        f"account: {selected.email}",
        f"status: {selected.status}",
        f"available_in: {format_remaining(selected.remaining_seconds)}",
        f"next_available_at: {selected.next_available_at.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"session_start_at: {selected.session_start_at.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"validation_status: {selected.validation_status}",
        f"archive_name: {selected.proposed_archive_name}",
        f"reason: {recommendation.reason}",
    ]
    return "\n".join(lines)
