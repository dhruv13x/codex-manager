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


def recommendation_to_text(recommendation: Recommendation) -> str | object:
    selected = recommendation.selected

    try:
        from rich.panel import Panel
        from rich.text import Text

        t = Text()
        t.append("account: ", style="bold")
        t.append(f"{selected.email}\n", style="green")
        t.append("status: ", style="bold")
        status_color = "green" if selected.status.lower() == "ready" else "yellow"
        t.append(f"{selected.status}\n", style=status_color)
        t.append("available_in: ", style="bold")
        t.append(f"{format_remaining(selected.remaining_seconds)}\n")
        t.append("next_available_at: ", style="bold")
        t.append(f"{selected.next_available_at.strftime('%Y-%m-%d %H:%M:%S %z')}\n")
        t.append("session_start_at: ", style="bold")
        t.append(f"{selected.session_start_at.strftime('%Y-%m-%d %H:%M:%S %z')}\n")
        t.append("validation_status: ", style="bold")
        t.append(f"{selected.validation_status}\n")
        t.append("archive_name: ", style="bold")
        t.append(f"{selected.proposed_archive_name}\n", style="cyan")
        t.append("reason: ", style="bold")
        t.append(f"{recommendation.reason}")
        return Panel(t, title="Recommendation", border_style="blue")
    except ImportError:
        pass

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
