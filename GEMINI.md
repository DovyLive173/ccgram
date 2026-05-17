# ccgram Development & Maintenance Guide

This document outlines the workflow for maintaining the custom fork of `ccgram` while staying synchronized with the upstream repository.

## Repository Structure
- **Origin:** `https://github.com/DovyLive173/ccgram` (Your fork)
- **Upstream:** `https://github.com/alexei-led/ccgram` (Original repo)
- **Branch:** `webhook-support` (Active development branch)

## Environment Setup
- **Location:** `~/ccgram`
- **Virtual Env:** `.venv/` (Managed by `uv`)
- **Config:** `~/.ccgram/.env` (Symlinked or copied to `~/ccgram/.env` for dev)

## Systemd Service
- **Service Name:** `ccgram.service`
- **Path:** `/etc/systemd/system/ccgram.service`
- **Commands:**
  - Start: `sudo systemctl start ccgram`
  - Stop: `sudo systemctl stop ccgram`
  - Restart: `sudo systemctl restart ccgram`
  - Logs: `journalctl -u ccgram -f`

## Upstream Synchronization (The "Clean" Workflow)
To pull the latest changes from the original repository without breaking custom patches:

```bash
# 1. Fetch latest upstream changes
git fetch upstream

# 2. Ensure you are on your dev branch
git checkout webhook-support

# 3. Rebase your changes on top of upstream main
git rebase upstream/main

# 4. If there are conflicts, resolve them and continue:
# git add <files>
# git rebase --continue

# 5. Push to your fork (requires force because of rebase)
git push origin webhook-support --force
```

## Implementation Guidelines for Custom Patches
- **Feature Flags:** Always wrap custom logic in environment variable checks (e.g., `if config.webhook_url:`).
- **Minimal Surface:** Avoid refactoring core classes unless necessary. Prefer adding new methods or extending via composition.
- **Fallback:** Ensure the bot defaults to original behavior (e.g., Polling) if custom config is missing.

## Diagnostics
- **Check Status:** `ccgram status`
- **Diagnostic Tool:** `ccgram doctor`
- **Service Status:** `systemctl status ccgram`

## Rollback Procedure
If a rebase or patch breaks the bot:
1. Identify the last working commit: `git log`
2. Reset the branch: `git reset --hard <commit_hash>`
3. Restart service: `sudo systemctl restart ccgram`
