from __future__ import annotations

import os
import requests
from typing import Any
from pathlib import Path

def load_env_file(path: str | Path) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    env = {}
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip("'").strip('"')
                env[key.strip()] = value
    except Exception:
        pass
    return env

def get_doppler_token() -> str | None:
    # 1. Environment
    token = os.environ.get("DOPPLER_TOKEN")
    if token:
        return token

    # 2. .env
    dot_env = load_env_file(".env")
    if "DOPPLER_TOKEN" in dot_env:
        return dot_env["DOPPLER_TOKEN"]
    
    return None

def fetch_doppler_secrets(token: str) -> dict[str, Any] | None:
    url = "https://api.doppler.com/v3/configs/config/secrets/download?format=json"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def resolve_b2_credentials(args: Any = None) -> tuple[str | None, str | None, str | None]:
    """
    Resolve B2 credentials with priority:
    1. CLI Arguments
    2. Doppler
    3. Environment Variables
    4. .env file
    """
    c_id = getattr(args, "b2_id", None)
    c_key = getattr(args, "b2_key", None)
    c_bucket = getattr(args, "bucket", None)

    def fill_from(source: dict[str, Any]) -> None:
        nonlocal c_id, c_key, c_bucket
        if not c_id:
            c_id = source.get("CODEX_B2_KEY_ID")
        if not c_key:
            c_key = source.get("CODEX_B2_APP_KEY")
        if not c_bucket:
            c_bucket = source.get("CODEX_B2_BUCKET")

    # 2. Doppler
    token = get_doppler_token()
    if token:
        secrets = fetch_doppler_secrets(token)
        if secrets:
            fill_from(secrets)

    if c_id and c_key and c_bucket:
        return c_id, c_key, c_bucket

    # 3. Environment
    fill_from(dict(os.environ))
    
    if c_id and c_key and c_bucket:
        return c_id, c_key, c_bucket

    # 4. .env
    fill_from(load_env_file(".env"))

    return c_id, c_key, c_bucket
