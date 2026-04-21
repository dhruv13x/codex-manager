from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def recommendation_to_text(recommendation: Recommendation) -> Any:
    from .rich_utils import create_table, get_status_style

    selected = recommendation.selected

    status_text = selected.status.upper()
    email_display = selected.email

    style = get_status_style(selected.status)
    if style:
        status_text = f"[{style}]{status_text}[/]"
    email_display = f"[bold green]{selected.email}[/]"

    headers = ["Field", "Value"]
    rows = [
        ["Account", email_display],
        ["Status", status_text],
        ["Available In", format_remaining(selected.remaining_seconds)],
        ["Next Available At", selected.next_available_at.strftime("%Y-%m-%d %H:%M:%S %z")],
        ["Session Start At", selected.session_start_at.strftime("%Y-%m-%d %H:%M:%S %z")],
        ["Validation Status", selected.validation_status],
        ["Archive Name", selected.proposed_archive_name],
        ["Reason", recommendation.reason],
    ]

    return create_table(title="Recommendation", headers=headers, rows=rows)
