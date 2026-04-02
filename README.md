# VK Post Scheduler

A Windows desktop application for mass-filling VK's native scheduled posts. It creates delayed posts through the API (`wall.post` with `publish_date`), so VK publishes them on its own. The app only needs to be running while the queue is being created, not at publication time.

![Main interface](screenshots/main_interface.png)

## How it works

1. Add a VK access token and one or more communities.
2. Write the text, pick photos or GIFs, set a date range and a list of times.
3. The app turns every date/time pair into a job in a persistent queue (`jobs_state.json`).
4. A background worker uploads the media and creates the delayed posts one by one.

Jobs survive restarts. A failed job is retried up to 3 times with growing delays. Errors that no retry can fix (blocked application, auth failure, a publish time in the past) fail immediately.

## Token storage

Tokens are kept in the **Windows Credential Manager**, not in a file. The `vk_config.json` file holds only names, group ids and schedules; the secrets go through the [`keyring`](https://pypi.org/project/keyring/) library into the OS credential store, tied to your Windows account. On macOS/Linux the same code uses Keychain / Secret Service.

On the first start after an upgrade from an older version, existing tokens are moved out of `vk_config.json` into the credential store automatically. The plain-text copy is not kept.

To inspect or remove stored tokens manually: Control Panel > Credential Manager > Windows Credentials, look for entries named `VKPostScheduler`.

## Requirements

- Python 3.9 or newer
- Windows (the code itself also runs on Linux/macOS)

## Installation

Run `run.bat`: it creates a virtual environment, installs dependencies and starts the app. Manually:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Getting a token

1. Create a standalone application at [vk.com/dev](https://vk.com/dev).
2. Open this URL in a browser, replacing `YOUR_APP_ID` with your application id:

```
https://oauth.vk.com/authorize?client_id=YOUR_APP_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,photos,docs,groups&response_type=token&v=5.131
```

3. Authorize and copy the token from the redirect URL.
4. In the app: **Add** next to *Token*, paste it; then **Add** next to *Group* and enter the group id (the number from `vk.com/club123456789`).

## Usage

- **Post** tab: token/group selection, text, images (JPG/PNG/GIF), GIF name.
- **Schedule** tab: date range, posting times, delay between posts, Schedule/Stop.
- **Status** tab: progress, counters, pending jobs (right-click to remove one), pause/resume, log.

Behaviors worth knowing:

- **Different posts** hands out images from your selection to time slots one by one and stops scheduling when the pool runs out. Each new plan starts from the first image again.
- Schedules and default text are saved per group; adding or removing a time saves it to the selected group automatically.
- GIFs are uploaded as documents and padded or cropped to VK's aspect ratio limits (0.66:1 to 2.5:1) when the transform option is on.
- On a posting error the queue pauses and shows the details; you decide whether to resume.

## Configuration files

| File | Purpose |
|---|---|
| `vk_config.json` | Token names, groups, per-group schedules and default text. No secrets. |
| Windows Credential Manager | Token values, entries under `VKPostScheduler` |
| `jobs_state.json` | Persistent job queue and photo rotation state |
| `logs/app_*.log` | Application log |
| `error.log` | Errors only |
| `crash.log` | Uncaught exceptions |

If a config file gets corrupted, the app moves it aside to `*.corrupt.bak` and starts with an empty one instead of wiping it silently.

## Tests

```bash
python -m pip install pytest
python -m pytest tests
```

## Building a standalone executable

```batch
build_exe.bat
```

Produces `dist\PostScheduler.exe` via PyInstaller.

## Project structure

```
main.py              Entry point: logging, crash handling, Qt loop
gui.py               PyQt5 interface
scheduler.py         Job queue, worker thread, retries, photo rotation
job_store.py         Persistence for the queue (jobs_state.json)
vk_client.py         VK API calls: uploads, wall.post
vk_config.py         Token/group configuration, keyring storage
gif_transformer.py   GIF aspect ratio fixing (Pillow)
tests/               pytest suite
```

## Troubleshooting

- **`ApiError: [8] Application is blocked`** — the standalone app the token belongs to was blocked by VK; create a new application and token. The app detects this and fails such jobs immediately instead of retrying.
- **`Publish time ... has already passed`** — the job sat in the queue too long (the app was closed, or earlier jobs errored). Posts cannot be scheduled retroactively.
- **`ApiError: [14]` (captcha)** — VK is asking for a captcha, which the API client cannot answer; wait and try again later.
- **Token errors on a fresh machine** — Credential Manager entries do not travel with file copies; re-enter the tokens or copy them via `keyring` on the old machine.
- Check `error.log` and the Status tab for anything else.

## Changelog

### 1.0.0

- Tokens now live in the Windows Credential Manager (keyring); `vk_config.json` holds no secrets, and tokens from older versions migrate automatically on first start.
- The codebase was reworked: the queue worker, persistence and VK API calls were split into focused modules (`scheduler.py`, `job_store.py`, `vk_client.py`), the queue internals are covered by tests.
- Permanent VK errors (5, 7, 8, 15, 100) and expired publish times fail immediately instead of burning the retry cycle.
- Media upload requests have network timeouts; the VK session is reused between posts.
- `jobs_state.json` and `vk_config.json` are written atomically; an unreadable file is backed up to `*.corrupt.bak` instead of being silently reset.
- Removing a job from the Status tab also cancels it in the worker; rescheduling cannot resurrect jobs from an old plan.
- GIFs are padded or cropped to VK's aspect ratio limits before upload.

### 0.9.5 - 0.9.7

PyQt5 interface, photo rotation, persistent job state, pause/resume, progress tracking, GIF transformation.
