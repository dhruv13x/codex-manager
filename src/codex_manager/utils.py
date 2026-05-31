from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def isoformat_local(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.astimezone().isoformat(timespec="seconds")
    return dt.isoformat(timespec="seconds")


def build_archive_name(session_start_at: datetime, email: str, label: str | None = None) -> str:
    suffix = f"-{label}" if label else ""
    return f"{session_start_at.strftime('%Y-%m-%d-%H%M%S')}-{email}{suffix}-codex.tar.gz"


def _decode_jwt_payload(token: Any) -> dict[str, Any]:
    if not isinstance(token, str):
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padded = payload + "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _timestamp_to_local_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def _extract_openai_auth(payload: dict[str, Any]) -> dict[str, Any]:
    auth_payload = payload.get("https://api.openai.com/auth")
    return auth_payload if isinstance(auth_payload, dict) else {}


def extract_email_from_auth_json(auth_path: Path) -> str | None:
    if not auth_path.exists():
        return None
    try:
        auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
        email = auth_data.get("email")
        if email:
            return email

        tokens = auth_data.get("tokens", {})

        id_payload = _decode_jwt_payload(tokens.get("id_token"))
        email = id_payload.get("email")
        if isinstance(email, str) and email:
            return email

        access_payload = _decode_jwt_payload(tokens.get("access_token"))
        profile = access_payload.get("https://api.openai.com/profile")
        if isinstance(profile, dict):
            email = profile.get("email")
            if isinstance(email, str) and email:
                return email
        email = access_payload.get("email")
        if isinstance(email, str) and email:
            return email
    except (json.JSONDecodeError, OSError):
        pass
    return None


def extract_jwt_details(auth_path: Path) -> dict[str, Any]:
    details = {
        "plan_type": "unknown",
        "auth_provider": "unknown",
        "auth_time_at": None,
        "id_token_issued_at": None,
        "id_token_expires_at": None,
        "access_token_issued_at": None,
        "access_token_expires_at": None,
        "auth_expires_at": None,
        "chatgpt_account_id": None,
        "chatgpt_user_id": None,
        "chatgpt_subscription_active_start": None,
        "chatgpt_subscription_active_until": None,
        "chatgpt_subscription_last_checked": None,
        "organizations": [],
        "email_verified": None,
        "display_name": None,
    }
    if not auth_path.exists():
        return details

    try:
        auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
        tokens = auth_data.get("tokens", {})

        id_payload = _decode_jwt_payload(tokens.get("id_token"))
        access_payload = _decode_jwt_payload(tokens.get("access_token"))

        for payload, token_name in ((id_payload, "id_token"), (access_payload, "access_token")):
            if not payload:
                continue

            issued_at = _timestamp_to_local_iso(payload.get("iat"))
            expires_at = _timestamp_to_local_iso(payload.get("exp"))
            if token_name == "id_token":
                details["id_token_issued_at"] = issued_at
                details["id_token_expires_at"] = expires_at
                details["auth_time_at"] = _timestamp_to_local_iso(payload.get("auth_time"))
                details["auth_provider"] = payload.get("auth_provider") or details["auth_provider"]
                details["email_verified"] = payload.get("email_verified")
                details["display_name"] = payload.get("name")
            else:
                details["access_token_issued_at"] = issued_at
                details["access_token_expires_at"] = expires_at

            auth_payload = _extract_openai_auth(payload)
            plan_type = auth_payload.get("chatgpt_plan_type")
            if plan_type:
                details["plan_type"] = plan_type

            for source_key, metadata_key in (
                ("chatgpt_account_id", "chatgpt_account_id"),
                ("chatgpt_user_id", "chatgpt_user_id"),
                ("user_id", "chatgpt_user_id"),
                ("chatgpt_subscription_active_start", "chatgpt_subscription_active_start"),
                ("chatgpt_subscription_active_until", "chatgpt_subscription_active_until"),
                ("chatgpt_subscription_last_checked", "chatgpt_subscription_last_checked"),
            ):
                if auth_payload.get(source_key) and not details.get(metadata_key):
                    details[metadata_key] = auth_payload[source_key]

            organizations = auth_payload.get("organizations")
            if isinstance(organizations, list) and organizations:
                details["organizations"] = [
                    {
                        "id": org.get("id"),
                        "title": org.get("title"),
                        "role": org.get("role"),
                        "is_default": org.get("is_default"),
                    }
                    for org in organizations
                    if isinstance(org, dict)
                ]

        details["auth_expires_at"] = (
            details["access_token_expires_at"] or details["id_token_expires_at"]
        )
    except (json.JSONDecodeError, OSError):
        pass
    return details
