# VK Post Scheduler

This is for those who run VK communities and got tired of scheduling posts one by one in the
web interface, where VK only lets you set a publish date on a single post at a time.
This app takes a text, a set of images and a date range with posting times, and
queues all the delayed posts at once through the API (`wall.post` with
`publish_date`). After that VK handles the publishing automatically: the app only needs to be
running while the queue is being created, not at publication time.

![Main window](screenshots/main_interface.png)

## Installation

You need Python 3.10 or newer. The app is written for Windows; the code itself
also runs on Linux and macOS.

The short way on Windows: run `run.bat`. It creates a virtual environment,
installs the package and starts the app. By hand:

```bash
python -m venv venv
venv\Scripts\activate
pip install -e .
python main.py
```

The project is an installable package, so after `pip install -e .` the
`vkpostscheduler` command and `python -m vkpostscheduler` work too.

## First run: token and groups

The app posts through one or more access tokens; each token carries the
communities you post to.

1. Get the VK API Token
2. In the app: **Add** next to *Token*, give it a name and paste the value.
3. **Add** next to *Group*: a display name and the group id (the number from
   `vk.com/club123456789`).

The token value goes into the **Windows Credential
Manager** through the [`keyring`](https://pypi.org/project/keyring/) library,
tied to your Windows account; on Linux and macOS the same code uses Keychain
or the Secret Service. `vk_config.json` holds only names, group ids and
schedules. To inspect or remove a stored token by hand: Control Panel >
Credential Manager > Windows Credentials, entries named `VKPostScheduler`.
Tokens left over from older versions are moved into the credential store
automatically on first start.

## Usage

Three tabs:

- **Post**: token and group selection, text, images (JPG/PNG/GIF), GIF name.
- **Schedule**: date range, posting times, delay between posts, the Schedule
  and Stop buttons.
- **Status**: progress, pending jobs, pause/resume, log.

Pressing Schedule turns every date/time pair into a job in a persistent queue,
and a background worker uploads the media and creates the delayed posts one by
one. You can close the app while it works: pending jobs survive the restart
and the worker picks them up on the next start.

Good to know:

- **Different posts** (on by default) hands out images from your selection to
  time slots one by one and stops scheduling when the pool runs out; each new
  plan starts from the first image again. With the box off, every post uses
  the first image from the selection.
- The time list and the default text are remembered per group: adding or
  removing a time saves it to the selected group automatically. A plan always
  targets the currently selected group; store as many tokens and groups as
  you need and switch between them.
- Scheduling a new plan replaces the previous one. In the Status tab you can
  also remove a single job (right-click it) or clear the whole queue.
- GIFs are uploaded as documents; with "Transform GIFs" on (default) they are
  padded or cropped to VK's aspect ratio limits (0.66:1 to 2.5:1) first.
- On a posting error the queue pauses and a dialog shows the details; you
  decide whether to resume. Retryable errors are retried up to 3 times with
  growing delays; errors no retry can fix (blocked application, auth failure,
  a publish time in the past) fail immediately.

## Where your data lives

Everything the app writes goes to one per-user folder, not to the working
directory: `%APPDATA%\VKPostScheduler` on Windows and
`~/.local/share/VKPostScheduler` elsewhere. There you will find:

- `vk_config.json`: token names, groups, per-group schedules and default
  text; no secrets.
- `jobs_state.json`: the pending queue and the photo rotation state.
- `logs\app_*.log`: the full application log, plus `error.log` for errors
  only and `crash.log` for uncaught exceptions.

If a config file gets corrupted, the app moves it aside to `*.corrupt.bak` and
starts with an empty one instead of wiping it silently. Files left in the
working directory by older versions are moved here on first start.

## Known limitations

- Posts cannot be scheduled retroactively. If the app sat closed past a slot,
  or earlier jobs errored for long enough, that job fails with "publish time
  has already passed".
- If VK blocked the standalone application your token belongs to, posts fail
  immediately; create a new application and a new token.
- VK occasionally answers with a captcha (error 14), which the API client
  cannot answer; wait and try again later.
- Credential Manager entries do not travel with file copies: on a fresh
  machine, re-enter the tokens.
- For anything else, check the Status tab log and `error.log`.

## Building a standalone executable

`build_exe.bat` installs PyInstaller into the venv if it is missing and
produces `dist\PostScheduler.exe`. `build_exe.py` writes a size-optimized
`PostScheduler.spec` on every build; the spec is generated, so it is not
tracked in git.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest tests
ruff check .
mypy .
```

The test suite covers the queue core and the GUI (PyQt5, run offscreen via
pytest-qt). Ruff, mypy and the tests also run in CI on Linux and Windows.

## Changelog

### 1.3.0

- The application moved into an installable `src/vkpostscheduler` package: `pip install -e .` provides the `vkpostscheduler` command and `python -m vkpostscheduler`; `main.py` at the repo root stays as the launcher for `python main.py` and for PyInstaller.
- Time strings are parsed in one place now (`schedule_time.py`); the scheduler, config and gui go through those parsers instead of handling format strings on their own.
- The test suite gained regression tests for the scheduler's pause and retry waits; all tests and fixtures use the package imports.
- Internal: the whole codebase is annotated so the strict mypy pair holds project-wide, and the run and build scripts install the package instead of requirements files.
