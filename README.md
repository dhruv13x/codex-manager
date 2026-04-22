<h1 align="center">Codex Manager</h1>
<p align="center"><strong>The Ultimate Account Snapshot and Quota Manager for OpenAI Codex</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code%20Style-Black%20%7C%20Ruff-000000?style=flat-square" alt="Code Style: Black/Ruff" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT" />
  <img src="https://img.shields.io/badge/Maintenance-Active-success?style=flat-square" alt="Maintenance Status: Active" />
  <img src="https://img.shields.io/badge/Coverage-90%25-brightgreen?style=flat-square" alt="Test Coverage: 90%" />
</p>

---

## ⚡ Quick Start

Get up and running with Codex Manager in under 5 minutes.

### Prerequisites
- **Python:** 3.10 or higher.
- **Dependency Manager:** [uv](https://github.com/astral-sh/uv) (recommended) or pip.

### Install
```bash
uv pip install codex-manager
```

### Run
Verify the installation by running the CLI help command:
```bash
cm --help
```

### Demo
Switch to the best available Codex account effortlessly:
```bash
# Recommend the best account based on cooldown status
cm recommend

# Quickly switch to an account, preserving current session history
cm use --email my.account@example.com
```

---

## ✨ Features

Codex Manager brings order to managing multiple Codex accounts with advanced tracking, rotation, and backup capabilities.

### Core
- **Account Rotation:** Easily swap out Codex identities while preserving your workspace data using `cm use`.
- **Live Status Parsing:** Parses Codex's `/status` output or `tmux` helper outputs to log quota limits and reset times seamlessly.
- **Smart Recommendations:** Uses `cm recommend` to evaluate cooldown registries and intelligently suggest the next available account.

### Performance & Storage
- **Rich Terminal UI:** Enjoy beautiful, highly readable outputs via `rich` panels, tables, and spinners.
- **Cloud Synchronization:** First-class support for S3-compatible endpoints (like Backblaze B2) to push and pull your account state.
- **Space Management:** Built-in `cm prune` and `cm prune-backups` commands efficiently clean up old state directories and backup files.

### Security
- **Identity Isolation:** The `--auth-only` flag ensures identity tokens are swapped cleanly without losing valuable session logs.
- **Offline Fallbacks:** Use `--without-status-check` for emergency restoration when live status checking fails.

---

## 🛠️ Configuration

Configure Codex Manager via Environment Variables or CLI Arguments.

### Environment Variables
| Name | Description | Default | Required |
|------|-------------|---------|----------|
| `CODEX_MANAGER_HOME` | Primary directory for Codex Manager profiles and configuration. | `~/.codex-manager` | No |
| `CODEX_HOME` | Directory for the target Codex runtime. | `~/.codex` | No |
| `AWS_ENDPOINT_URL` | S3 endpoint URL for Cloud sync (e.g. Backblaze B2). | None | Only for Cloud Sync |
| `AWS_ACCESS_KEY_ID` | Access key for your Cloud sync provider. | None | Only for Cloud Sync |
| `AWS_SECRET_ACCESS_KEY`| Secret key for your Cloud sync provider. | None | Only for Cloud Sync |

### Core CLI Arguments
*(See `cm <command> --help` for full details)*

| Flag | Description |
|------|-------------|
| `--dry-run` | Safely simulate actions (backup, restore, prune, etc.) without altering the system. |
| `--cloud` | Perform backup or restore operations directly with a configured Cloud (B2) backend. |
| `--email <addr>` | Specify a target email address to filter backups or force use. |
| `--backup-dir <dir>`| Directory containing local backup archives and metadata. |
| `--auth-only` | (Restore/Use) Only restore `auth.json` and config, leaving session history intact. |

---

## 🏗️ Architecture

### Directory Tree
*(Annotated target representation of standard project structure)*

```text
src/codex_manager/
├── __init__.py
├── account_status.py   # Synchronizes metadata with live Codex statuses
├── backup.py           # Handles packaging and archiving Codex states
├── cli.py              # Main Entrypoint: Orchestrates argparse handlers
├── cloud.py            # Interfaces with S3/B2 for cloud synchronizations
├── config.py           # Environment variables and path resolution logic
├── recommend.py        # Cooldown evaluation and account recommendation engine
├── restore.py          # Safely unpacks archives back to CODEX_HOME
├── ui.py               # Rich text formatting, tables, and spinners
└── use_account.py      # Orchestrates account switching and auth-only swaps
```

### Flow
1. **Status Capture:** The CLI reads raw text from a tmux session or direct input.
2. **Parsing & Metadata:** Text is parsed to extract email, reset time, and quotas. Metadata files (`.metadata.json`) are generated alongside `tar.gz` archives in `CODEX_MANAGER_HOME`.
3. **Evaluation:** When rotating accounts, `cm recommend` scans the local and cloud registry to find an account whose cooldown period has expired.
4. **Restoration:** `cm use` extracts specific identity files (like `auth.json`) into `CODEX_HOME`, avoiding the overwrite of active chat sessions.

---

## 🐞 Troubleshooting

### Common Issues

| Error Message / Symptom | Solution |
|-------------------------|----------|
| `ModuleNotFoundError: No module named 'requests'` | You might be missing dependencies. Re-install using `uv pip install codex-manager` or `uv pip install -e .[dev]` for local setups. |
| `TokenExpiredError: Re-login required` | Your Codex session has expired. The CLI attempts to auto-patch the metadata as "expired". You must manually log back in and then capture a new backup. |
| `Could not resolve Cloud (B2) credentials for upload` | Ensure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are exported in your environment, or passed directly to `sync`. |
| Live capture times out | The target Codex runtime might not be displaying the `/status` output correctly. Try running with `--without-status-check` as an emergency fallback. |

### Debug Mode
Codex Manager utilizes `pytest` with extensive logging for debugging local changes. To see raw execution traces, developers can run tests directly:
```bash
python -m pytest --log-cli-level=DEBUG
```
For CLI execution, detailed error tracebacks will appear when unexpected exceptions bubble up.

---

## 🤝 Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon) for the full guide.

### Dev Setup
1. Clone the repository.
2. Setup your development environment using `uv`:
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e .[dev]
   ```
3. Run the test suite:
   ```bash
   python -m pytest tests --cov=src --cov-report=term-missing
   ```
4. Run linters and formatters:
   ```bash
   uv run ruff check --fix src/ tests/
   ```

---

## 🗺️ Roadmap

Here is a glimpse of what is coming next in our Strategic Vision:
- [ ] **Next-Gen AI integration:** LLM-powered workflows and intelligent recommendation tweaks.
- [ ] **Cloud-Native Scale:** Full native K8s/Docker support for distributed setups.
- [ ] **Extensibility:** Introduce a REST/GraphQL API and a community plugin system.
- [ ] **Interactive CLI Prompts:** Upgrade to an interactive terminal UI for smoother UX without flag memorization.
