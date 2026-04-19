# Codex Manager 🚀

**Codex account snapshot manager: automatically normalize, back up, and restore your Codex state.**

[![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Maintenance Status](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/dhruv13x/codex-manager/commits/main)

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10+
- Existing Codex account data (`~/.codex` or `.codex_sample`)

### Installation
You can install Codex Manager directly via `pip` or using `uv` for a virtual environment.

```bash
git clone https://github.com/dhruv13x/codex-manager.git
cd codex-manager
pip install .
```

### Run
Get started in under 5 minutes:

```bash
# 1. Normalize existing legacy backups into the inventory
codex-manager normalize --source-dir ~/.codex_sample

# 2. Check current weekly availability
codex-manager cooldown

# 3. Find the best account to use right now
codex-manager recommend

# 4. Use the recommended account
codex-manager use --email your.account@example.com
```

---

## ✨ Features

- **Core State Management**: Easily `backup`, `restore`, and switch (`use`) active Codex states, keeping your `~/.codex` directory clean and safe.
- **Legacy Normalization**: Parse and normalize unstructured legacy account snapshots (`*auth.json`) into a machine-readable format.
- **Intelligent Cooldown Tracking**: Predicts account quota resets using exactly 7 days from `session_start_at` instead of inaccurate end-of-quota estimates.
- **Smart Recommendations**: Always know which account to use next based on actual availability and lease freshness.
- **Cloud Synchronization**: Sync your snapshots to S3-compatible cloud storage using `push` and `pull` via `boto3`.
- **System Doctor**: Built-in `doctor` command to diagnose system health and ensure directory/dependency integrity.

---

## 🛠️ Configuration

Codex Manager prioritizes configuration via command-line arguments but falls back to environment variables and its local `config.json`.

### Environment Variables

| Variable | Description | Default | Required |
| --- | --- | --- | --- |
| `CODEXMGR_HOME` | Base directory for backups and inventory. | `~/.codexmgr` | No |
| `AWS_ENDPOINT_URL` | S3 endpoint URL for remote backups. | None | No |
| `AWS_ACCESS_KEY_ID` | AWS access key for cloud syncing. | None | No |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for cloud syncing. | None | No |

### Key CLI Arguments

| Flag | Description |
| --- | --- |
| `--source-dir` | Target directory for legacy files or active state (default: `~/.codex_sample` or `~/.codex`). |
| `--inventory-path` | Output path for the normalized JSON inventory (default: `~/.codexmgr/inventory.json`). |
| `--backup-dir` | Directory to store or retrieve `.tar.gz` snapshots (default: `~/.codexmgr/backups`). |
| `--dry-run` | Preview actions (backup, restore, use, prune) without making system changes. |
| `--refresh` | Force an inventory regeneration from disk before running recommendations. |

---

## 🏗️ Architecture

### Directory Tree
```text
src/codex_manager/
├── cli.py             # Main entrypoint and argument routing
├── args.py            # Centralized CLI parser configuration
├── config.py          # Environment defaults and base paths
├── normalize.py       # Core legacy file normalization engine
├── inventory.py       # Disk-based inventory state management
├── backup.py          # Creation of live Codex snapshots
├── restore.py         # Snapshot restoration functionality
├── use_account.py     # Clean environment switching
├── cooldown.py        # Weekly quota cooldown calculator
├── recommend.py       # Smart account selection logic
├── sync.py            # S3 backup upload/download mechanics
└── doctor.py          # System environment diagnostics
```

### Data Flow
1. **Normalization**: `codex-manager normalize` scans `~/.codex_sample` (legacy files), infers timeframes, and writes to `~/.codexmgr/inventory.json`.
2. **Evaluation**: `codex-manager cooldown` and `recommend` read the JSON inventory, assess 7-day windows, and rank accounts.
3. **Execution**: `codex-manager backup` archives current `~/.codex` files. `codex-manager use` replaces live files with an archive safely, maintaining backups in `~/.codexmgr/backups/`.

---

## 🐞 Troubleshooting

| Common Error | Solution |
| --- | --- |
| `JSONDecodeError: Expecting value` | Check if `~/.codexmgr/config.json` is corrupted. Delete it and retry. |
| No ready accounts found | Run `codex-manager cooldown --refresh` to ensure the inventory matches your disk files. |
| Cannot sync to S3 | Ensure the `boto3` dependency is installed and AWS environment variables are set correctly. |
| Tmux capture failed in --live | Increase `--startup-timeout-seconds` or check if `codex --no-alt-screen` is working. |

### Debug Mode
If you run into issues, evaluate your environment health using:
```bash
codex-manager doctor
```
This checks directory existences, dependency availability, and parser integrity.

---

## 🤝 Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) (if available) for detailed guidelines.

### Dev Setup
1. **Environment Setup**:
   ```bash
   uv pip install --system -e .[dev]
   ```
2. **Run Tests**:
   ```bash
   python -m pytest
   ```
3. **Linting and Formatting**:
   ```bash
   ruff check .
   black --check .
   mypy src
   ```

---

## 🗺️ Roadmap

- [ ] Automated UI scheduling indicators and system tray notifications.
- [ ] Add direct support for Webhook notifications when quotas clear.
- [ ] Implement robust conflict resolution for cloud backup synchronization.
- [ ] Web dashboard extension for tracking account metrics over time.
