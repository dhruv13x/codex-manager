# Codex Manager

`codex-manager` is a CLI for backing up Codex account state and tracking account cooldown data from live `/status` output.

## Core model

- Backups are stored as `*.tar.gz` archives plus adjacent `*.metadata.json`.
- Metadata is the source of truth for `cooldown`, `recommend`, and account rotation decisions.
- Live Codex `/status` output is parsed to capture:
  - account email
  - quota text
  - quota percent left when available
  - weekly reset timestamp

## Main commands

- `cm backup`: capture live status, build archive metadata, and create a backup.
- `cm status`: parse live status and patch the latest metadata for the current account.
- `cm cooldown`: show account availability from stored metadata, optionally merged with live status.
- `cm recommend`: choose the best account to use next.
- `cm use`: switch to another account, defaulting to auth-only restore unless `--clean` is used.
- `cm restore`: restore a full backup into the Codex home.

## Status tracking policy

- `use` and `restore` sync the current account status before switching away from it.
- If live status capture fails, the command retries once.
- If status capture fails twice, the command exits and instructs the user to rerun with `--without-status-check`.

## Emergency fallback

`--without-status-check` exists for cases where Codex layout changes or live status is temporarily unavailable.

In that mode:

- cooldown is estimated as `now + 7 days`
- metadata is still written so cooldown state is not lost
- fallback archive and metadata names are based on the estimated reset time, not the current time

## Storage defaults

- manager home: `~/.codex-manager`
- backup directory: `~/.codex-manager/backups`
- Codex home: `~/.codex`

## Cloud support

- Backblaze B2 is supported for remote backup metadata and archive storage.
- Local and cloud entries can be merged for recommendation and cooldown reporting.
