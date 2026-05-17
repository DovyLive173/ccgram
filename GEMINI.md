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

## Webhook Mode (Opt-In Transport)
The webhook transport runs via the standalone `webhook_runner.py` wrapper to isolate network logic from the core application. 

### Migration (Polling ↔ Webhook)
To switch to webhook mode:
1. Define the variables in `~/.ccgram/.env`:
   ```env
   WEBHOOK_URL=https://your-domain.com/secret-path
   WEBHOOK_PORT=8084
   WEBHOOK_LISTEN=0.0.0.0
   WEBHOOK_SECRET_TOKEN=your_secure_random_string
   ```
2. Restart the service: `sudo systemctl restart ccgram`

### Rollback & Fallback
- **Automatic Fallback:** If `ccgram` fails to bind the local `WEBHOOK_PORT` (e.g., port in use), it catches the exception, recreates the `asyncio` event loop safely, and automatically falls back to `Polling mode active`.
- **Manual Rollback:** To forcefully rollback to Polling, remove the `WEBHOOK_URL` from the `.env` file and restart the service. The webhook is automatically deleted from Telegram's side by `python-telegram-bot` when polling initializes.

### Webhook State & Duplicate Protection
- `python-telegram-bot` strictly handles the `deleteWebhook` API call. Whenever polling initializes, it guarantees that any active webhook on the Telegram server is removed. This prevents duplicate update deliveries.
- The built-in PTB retry loop automatically applies exponential backoff if the Telegram API encounters errors or timeouts.

### Diagnostics & Future Enhancements
- **Verify Status:** `sudo journalctl -u ccgram -f` (Look for `Webhook registration triggered` or `Polling mode active`).
- **Health Checks:** Currently, health checks rely on systemd (`systemctl status ccgram`). In the future, a dedicated `{"status": "ok"}` health endpoint can be mounted directly on the aiohttp Mini App runner or a custom Tornado route within `webhook_runner.py` to allow load balancers to poll service health.

