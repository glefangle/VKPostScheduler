# VK Post Scheduler

A Windows desktop application for mass-filling VK's native scheduled posts. It creates delayed posts through the API (`wall.post` with `publish_date`), so VK publishes them on its own. The app only needs to be running while the queue is being created, not at publication time.

## How it works

1. Add a VK access token and one or more communities.
2. Write the text, pick photos or GIFs, set a date range and a list of times.
3. The app turns every date/time pair into a job in a persistent queue (`jobs_state.json`).
4. A background worker uploads the media and creates the delayed posts one by one.

Jobs survive restarts. A failed job is retried up to 3 times with growing delays.

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

Tokens and groups are stored locally in `vk_config.json`. The file also remembers the selected token/group, so the app reopens where you left it. `vk_config.json` is never committed (see `.gitignore`) because it contains the token in plain text.

## Usage

### Post tab

- Pick a token and a group.
- **Browse** one or more images (jpg, png, gif).
- With **Different posts** enabled, each time slot gets the next image from the list and the list wraps around on the next days. With it disabled, every post uses the same image.
- **GIF name** is the document title shown in VK.
- Text is optional if images are selected, and vice versa.

### Schedule tab

- Pick a date range and add one or more times (HH:MM).
- **Delay between posts** throttles the worker so VK does not rate-limit you.
- **Schedule posts** validates the input and queues every date/time pair. The worker runs in the background; you can close the tab and watch progress in *Status*.

### Status tab

- Progress bar and counters for the current plan.
- Right-click a pending job to remove it from the queue.
- **Pause queue** stops posting without losing jobs; **Clear all jobs** drops everything.

When a post fails, the app pauses the queue and shows the error. You can resume (it retries with a longer delay each time) or keep it paused and investigate.

## Building the executable

Run `build_exe.bat`. It produces a standalone `dist\PostScheduler.exe` via PyInstaller.

## Files

- `vk_config.json` - tokens, groups, selection (created on first start)
- `jobs_state.json` - the pending job queue and photo rotation state
- `logs/` - per-run log files, `error.log` - errors only
