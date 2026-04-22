# 📦 Codex Manager

**The ultimate CLI tool for managing OpenAI Codex account snapshots, tracking quotas, and ensuring seamless workflow continuity.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linter: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Maintenance Status](https://img.shields.io/badge/Maintenance-Active-success)](#)

---

## ⚡ Quick Start

Get up and running in under 5 minutes.

### Prerequisites
- Python 3.10 or higher
- `uv` (recommended for fast dependency management)

### Install
Clone the repository and install using `uv`:
```bash
git clone https://github.com/dhruv13x/codex-manager.git
cd codex-manager
uv pip install --system -e .
```

### Run
Verify the installation by viewing the CLI help menu:
```bash
codex-manager --help
# Or use the shorter alias:
cm --help
```

### Demo
Here's a quick 5-line workflow to backup your current account, view recommendations, and switch to a new one:
```bash
# 1. Take a live snapshot of your active Codex account state
cm backup --cloud

# 2. Check cooldown statuses for all accounts
cm cooldown

# 3. Get the smartest recommendation for the next account to use
cm recommend

# 4. Switch to a new account using the 'auth-only' method
cm use --email new_user@example.com
```

> **[🖼️ Suggestion: Add an animated GIF here demonstrating the `cm use` command in action with the Rich UI]**

---

## ✨ Features

**Core**
- **Live Status Tracking:** Automatically parses live Codex `/status` output to capture account email, quota text, and weekly reset timestamps.
- **Smart Recommendations:** Recommends the optimal account to use next based on calculated cooldowns and real-time metadata.
- **Full State Recovery:** Backup and restore full Codex runtime states (`auth.json`, history, logs) via `*.tar.gz` archives and `*.metadata.json`.

**Performance & Reliability**
- **Offline & Fallback Mode:** Employs an emergency `--without-status-check` fallback that gracefully estimates cooldowns even when the live tracker is temporarily unavailable.
- **Lightning Fast UI:** Employs the `rich` library for beautiful terminal output, tables, and status animations.

**Security & Cloud**
- **Cloud Synchronization:** First-class support for Backblaze B2 (and S3-compatible buckets) for remote backup metadata and archive storage.
- **Safe Operations:** Every modifying command supports a `--dry-run` flag to safely simulate actions without touching your files.

---

## 🛠️ Configuration

Codex Manager prioritizes configuration via environment variables and CLI arguments for flexibility.

### Environment Variables

| Name | Description | Default | Required |
|---|---|---|---|
| `CODEX_MANAGER_HOME` | The primary home directory for the manager config and backups. | `~/.codex-manager` | No |
| `CODEX_HOME` | The target directory where Codex state resides. | `~/.codex` | No |

*Note: You can also place a `config.json` inside your `CODEX_MANAGER_HOME` to persist configuration settings.*

### Key CLI Arguments

Most commands support these primary flags. Use `cm <command> --help` for a complete list.

| Flag | Description |
|---|---|
| `--dry-run` | Safely preview the changes without modifying local or cloud state. |
| `--cloud` | Enable Backblaze B2/S3 cloud capabilities for the command. |
| `--email <email>` | Specify a target account email for use, restore, or listing. |
| `--backup-dir <dir>` | Override the directory used for reading/writing backups. |
| `--without-status-check`| Bypass live capture and calculate cooldowns statically (+7 days). |
| `--auth-only` | During `use` or `backup`, target only identity/auth files instead of the full state. |

---

## 🏗️ Architecture

### Directory Tree

```
~/.codex-manager/ (CODEX_MANAGER_HOME)
├── backups/                # Local archives and metadata
│   ├── backup_1.tar.gz
│   └── backup_1.metadata.json
├── config.json             # Persistent local configurations
└── cooldown.json           # Registry caching overall account cooldowns
```

### High-Level Data Flow
1. **Capture:** `cm backup` or `cm status` reads live text from a `tmux` session running Codex.
2. **Process:** The CLI parses the text to build a state model (Quota, Cooldown, Email) and packages the `~/.codex` directory into an archive.
3. **Store:** Archives and adjacent JSON metadata are saved locally and pushed to the cloud (if configured).
4. **Evaluate:** When `cm recommend` or `cm cooldown` is invoked, local and cloud metadata are fetched, evaluated against real-time, and ranked to find the optimal active account.
5. **Switch:** `cm use` restores the selected account's data into the `~/.codex` home, rotating your session seamlessly.

---

## 🐞 Troubleshooting

### Common Issues

| Error Message | Cause | Solution |
|---|---|---|
| `TokenExpiredError: TOKEN EXPIRED` | The active Codex session token has expired. | Re-authenticate in Codex manually, or run with `--without-status-check` to bypass. |
| `Could not resolve Cloud (B2) credentials.` | Missing B2 credentials for cloud sync. | Pass `--b2-id` and `--b2-key` flags, or ensure your credentials are set up. |
| `No backups found in Cloud for <email>.` | The requested account isn't backed up to the specified bucket. | Run `cm list-backups --cloud` to verify the email and backup availability. |

### Debug Mode
While the CLI does not have a single `--debug` flag, you can often reveal more information by viewing the full exception traces or by utilizing the built-in doctor command:
```bash
cm doctor
```
The `doctor` command verifies your dependencies, runtime directories, and validates the status parser setup.

---

## 🤝 Contributing

We welcome contributions to Codex Manager! Please review our `CONTRIBUTING.md` (coming soon) before submitting PRs.

### Dev Setup
To set up your local development environment:
```bash
# 1. Install all development dependencies
uv pip install --system -e .[dev]

# 2. Run the tests (Ensure 90%+ coverage)
python -m pytest tests --cov=src --cov-report=term-missing

# 3. Format and lint the codebase
uv run ruff check --fix src/ tests/
uv run black src/ tests/
```

---

## 🗺️ Roadmap

- **Plugin Architecture:** Allow custom plugins to manage other CLI authentication tokens.
- **Enhanced Cloud Coverage:** Add direct first-class integrations for Google Cloud Storage and Azure Blob.
- **Automated Rotation Daemon:** A background worker to automatically rotate accounts when token limits are reached in real-time.
