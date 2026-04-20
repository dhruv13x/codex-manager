# Codex Manager Spec

## Goal

Build a `codex-manager` CLI for OpenAI Codex account snapshots, modeled after `geminiai_cli` where that design is sound, but adapted to Codex's weekly quota behavior.

The manager should:

- normalize existing Codex account artifacts into a stable machine-readable format
- back up and restore Codex account state safely
- track weekly availability based on session start time, not quota-end time
- recommend the next available account
- keep filename conventions simple and put richer timing details into metadata

## Source Context

This repo already contains a working `geminiai_cli` reference implementation.

Relevant patterns confirmed from that codebase:

- `backup.py` uses `timestamp + email` naming
- `cooldown.py` tracks `first_used` separately from `last_used`
- `cli.py` and `args.py` define a command-oriented structure we can mirror

Codex sample data lives in `.codex_sample/` and includes:

- shared state files such as `auth.json`, `history.jsonl`, sqlite state, sessions, logs
- many per-account auth snapshots named like `21apr_drdpsbose023@gmail.com_auth.json`

## Weekly Quota Model

For Codex, the controlling timestamp is:

- `session_start_at`

Not:

- auth file modified time
- quota-ended time
- availability date encoded in the legacy filename

For new live backups, the manager should obtain exact status from Codex `/status`.

Preferred live source:

- current `~/.codex/auth.json` for the active account identity where available
- Codex `/status` output for actual account email and actual reset time

Derived fields:

- `quota_end_detected_at`: when the auth snapshot file was last modified
- `session_start_at`: inferred start time of the weekly session
- `next_available_at`: `session_start_at + 7 days`

For live status-based backups:

- `reset_at` comes directly from `/status`
- `session_start_at = reset_at - 7 days`
- no prediction is needed beyond subtracting the fixed weekly window

Example:

- legacy file: `21apr_drdpsbose023@gmail.com_auth.json`
- mtime: `2026-04-14 17:55:00`
- inferred session duration before exhaustion: `2 hours`
- therefore `session_start_at = 2026-04-14 15:55:00`
- `next_available_at = 2026-04-21 15:55:00`

## Archive Naming

Recommended archive naming format:

`yyyy-mm-dd-hhmmss-email-codex.tar.gz`

Example:

`2026-04-14-155500-drdpsbose023@gmail.com-codex.tar.gz`

For live backups, the filename timestamp should be built from exact `session_start_at` derived from `/status`, not from legacy auth-file mtimes.

This is preferred over `dd-mm-yyyy-hhmmss-...` because:

- it sorts lexically and chronologically
- it matches the existing Gemini philosophy of timestamp-first naming
- it uses the actual quota anchor event: session start

## Filename Contract

The archive filename must encode only:

- `session_start_at`
- `email`
- product suffix `codex`

The filename must not try to encode:

- inferred quota duration
- quota end detection time
- availability date separately
- source legacy filename

Those belong in metadata.

## Metadata Contract

Each archive should have a sidecar metadata file with the same base name:

`yyyy-mm-dd-hhmmss-email-codex.metadata.json`

Example:

`2026-04-14-155500-drdpsbose023@gmail.com-codex.metadata.json`

Suggested schema:

```json
{
  "product": "codex",
  "email": "drdpsbose023@gmail.com",
  "session_start_at": "2026-04-14T15:55:00+05:30",
  "next_available_at": "2026-04-21T15:55:00+05:30",
  "reset_at": "2026-04-21T15:55:00+05:30",
  "quota_end_detected_at": "2026-04-14T17:55:00+05:30",
  "inferred_session_duration_seconds": 7200,
  "inference_basis": "legacy filename day-month plus auth file mtime minus configured session duration",
  "legacy_auth_filename": "21apr_drdpsbose023@gmail.com_auth.json",
  "legacy_quota_day_token": "21apr",
  "source_codex_home": "~/.codex",
  "captured_files": [
    "auth.json",
    "history.jsonl",
    "state_5.sqlite",
    "sessions/"
  ],
  "created_at": "2026-04-19T15:30:00+05:30",
  "manager_version": "0.1.0"
}
```

## Legacy Normalization Rules

Legacy auth files follow this rough pattern:

`<day><mon>_<email>_auth.json`

Example:

`21apr_drdpsbose023@gmail.com_auth.json`

Interpretation rule:

- `<day><mon>` is the date when quota becomes available again
- year is inferred from the current operating year unless explicitly overridden
- file mtime is treated as `quota_end_detected_at`
- `session_start_at = quota_end_detected_at - inferred_session_duration`
- `next_available_at = session_start_at + 7 days`

That means the legacy day token is a validation signal, not the primary timestamp we preserve.

## Validation Rule During Normalization

When normalizing legacy data:

1. parse the legacy token, for example `21apr`
2. infer `session_start_at`
3. compute `next_available_at`
4. verify that `next_available_at` falls on the same calendar day as the legacy token

If the day does not match:

- keep the record
- mark it as `validation_status = "mismatch"`
- do not silently rewrite the evidence

## Duration Inference

The 2-hour subtraction in your example should not be hardcoded into the filename logic.

It should be a configurable normalization parameter:

- `--session-duration-hours`

Default for first-pass normalization:

- `2`

Reason:

- old files do not appear to contain enough readable metadata to derive exact session start purely from content
- different accounts or future operating behavior may require a different duration assumption

## Timezone Rule

Store full ISO timestamps with timezone in metadata.

For filenames:

- use local wall-clock time rendered as `YYYY-MM-DD-HHMMSS`

This keeps filenames readable while metadata stays unambiguous.

## What Gets Backed Up

Codex backups should represent account-usable state, not only auth snapshots.

Minimum snapshot set:

- `auth.json`
- account-specific auth snapshot copied into the archive manifest
- `config.toml`
- `history.jsonl`
- `sessions/`
- `state_5.sqlite*`
- `logs_2.sqlite*`
- `models_cache.json`
- `installation_id`
- any other files required for a functioning restore after validation

Files or directories that are clearly ephemeral can be made optional:

- `tmp/`
- `.tmp/`
- transient caches

## Backup Source Priority

When creating a new backup:

1. query live Codex `/status`
2. parse exact `email` and exact `reset_at`
3. derive `session_start_at = reset_at - 7 days`
4. build archive name from that exact session start
5. capture current `~/.codex` state

Legacy `*_auth.json` normalization remains useful for historical inventory and recovery, but should not be the primary source for naming new backups.

## Proposed Commands

Mirror `geminiai_cli` at a high level:

- `codex-manager backup`
- `codex-manager restore`
- `codex-manager list-backups`
- `codex-manager cooldown`
- `codex-manager recommend`
- `codex-manager normalize`
- `codex-manager profile`
- `codex-manager sync`
- `codex-manager prune`
- `codex-manager doctor`
- `codex-manager config`

## Command Responsibilities

### `normalize`

Consumes legacy auth files and emits a normalized inventory.

Responsibilities:

- scan legacy `*_auth.json` files
- parse legacy day tokens and emails
- read file mtimes
- infer `session_start_at`
- compute `next_available_at`
- validate against the legacy quota-day token
- optionally create normalized archive names and metadata records

### `backup`

Creates a Codex snapshot archive.

Responsibilities:

- read live status from Codex `/status`
- extract exact `email` and exact `reset_at`
- derive exact `session_start_at = reset_at - 7 days`
- build archive base name from `session_start_at` and `email`
- capture the Codex state set
- write `.tar.gz`
- write sidecar metadata json
- optionally upload to cloud later if desired

### `restore`

Restores a selected archive back into the active Codex home.

Responsibilities:

- choose archive by filename or metadata
- validate archive contents
- restore atomically
- optionally preserve current state as a safety backup

### `cooldown`

Shows current weekly availability.

Responsibilities:

- read normalized metadata records
- compute `next_available_at`
- show `ready` vs `cooldown`
- display start time, detected end time, and next available time

### `recommend`

Selects the best account to use next.

Priority:

1. available now
2. least recently used
3. earliest next available if none are ready

## Proposed Package Layout

Match the Gemini shape where practical:

```text
src/codex_manager/
├── cli.py
├── args.py
├── config.py
├── backup.py
├── restore.py
├── normalize.py
├── inventory.py
├── cooldown.py
├── recommend.py
├── profile.py
├── sync.py
├── prune.py
├── doctor.py
├── metadata.py
├── utils.py
└── ui.py
```

## Module Mapping From `geminiai_cli`

Direct parallels:

- `geminiai_cli.cli` -> `codex_manager.cli`
- `geminiai_cli.args` -> `codex_manager.args`
- `geminiai_cli.config` -> `codex_manager.config`
- `geminiai_cli.backup` -> `codex_manager.backup`
- `geminiai_cli.restore` -> `codex_manager.restore`
- `geminiai_cli.cooldown` -> `codex_manager.cooldown`
- `geminiai_cli.recommend` -> `codex_manager.recommend`
- `geminiai_cli.profile` -> `codex_manager.profile`
- `geminiai_cli.sync` -> `codex_manager.sync`
- `geminiai_cli.prune` -> `codex_manager.prune`
- `geminiai_cli.doctor` -> `codex_manager.doctor`

Codex-specific additions:

- `codex_manager.normalize`
- `codex_manager.inventory`
- `codex_manager.metadata`

These are needed because the Codex side starts with a legacy auth-file naming problem that Gemini does not have.

## Storage Layout

Suggested manager home:

`~/.codex-manager/`

Suggested subpaths:

- `~/.codex-manager/backups/`
- `~/.codex-manager/inventory.json`
- `~/.codex-manager/cooldown.json`
- `~/.codex-manager/profiles/`
- `~/.codex-manager/tmp/`

## Regex Contracts

Normalized archive filename:

```regex
^\d{4}-\d{2}-\d{2}-\d{6}-.+-codex\.tar\.gz$
```

Legacy auth filename:

```regex
^(?P<day>\d{1,2})(?P<month>[a-z]{3})_(?P<email>.+)_auth\.json$
```

## Safety Rules

- never infer and overwrite original legacy files in place
- preserve the original filename in metadata
- keep normalization idempotent
- restore atomically where possible
- do not rely only on filenames once metadata exists

## First Implementation Slice

Build in this order:

1. `config.py`
2. `normalize.py`
3. `metadata.py`
4. `cooldown.py`
5. `recommend.py`
6. `backup.py`
7. `restore.py`
8. CLI wiring in `args.py` and `cli.py`

This order gives a working normalization and scheduling engine before archive creation and restore.

## Immediate Next Task

Implement `normalize` first.

Output for phase 1 should be:

- parsed legacy account records
- inferred `session_start_at`
- computed `next_available_at`
- validation status against the legacy quota token
- proposed normalized archive basename

That gives a trustworthy inventory before touching live backup and restore flows.
