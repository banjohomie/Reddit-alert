# Reddit Quick Work Alert Bot (Version: v1.0)

Reddit Quick Work Alert Bot is a local Windows-friendly Python bot that monitors Reddit RSS feeds for fresh quick-work/freelance posts and sends matching alerts to Telegram.

It also includes a Rules-Aware For Hire Draft Assistant. The assistant is safe by design: it does not auto-post to Reddit, does not comment, does not send DMs, and does not submit forms. It only prepares reminders and drafts for manual review.

## Features

- Reads Reddit public RSS feeds with `requests` and `feedparser`.
- Uses separate `FAST_SUBREDDITS` and `SLOW_SUBREDDITS` schedules.
- Sends Telegram alerts through the Telegram Bot API.
- Stores secrets in `.env`.
- Stores local settings in `config.json`.
- Stores runtime state in `seen_posts.json`, `for_hire_posts.json`, and `subreddit_rules.json`.
- Uses `subreddit_rules_presets.json` for rules-aware For Hire draft generation without aggressive Reddit rule fetching.
- Handles RSS HTTP 429 with per-subreddit cooldown and exponential backoff.
- Can be built into a single portable Windows exe with PyInstaller.

## Project Files

Files intended for GitHub:

- `main.py`
- `config.example.json`
- `.env.example`
- `requirements.txt`
- `README.md`
- `.gitignore`
- `subreddit_rules_presets.json`
- `subreddit_rules.example.json`
- `for_hire_posts.example.json`
- `seen_posts.example.json`

Local runtime files ignored by Git:

- `.env`
- `config.json`
- `seen_posts.json`
- `for_hire_posts.json`
- `subreddit_rules.json`
- `*.log`
- `build/`
- `dist/`
- `*.spec`
- `__pycache__/`
- `.venv/`, `venv/`, `env/`

Do not commit `.env` or runtime JSON files. They may contain tokens, personal settings, seen post IDs, or local draft history.

## Setup

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

Create `config.json` from `config.example.json`:

```powershell
Copy-Item config.example.json config.json
```

Then edit:

- `USER_AGENT`
- `FAST_SUBREDDITS`
- `SLOW_SUBREDDITS`
- `FOR_HIRE_GITHUB_URL`
- Telegram-related behavior such as `DRY_RUN`

Telegram tokens must stay in `.env`, not in `config.json`.

## Runtime File Creation

If files are missing, the bot creates them automatically:

- missing `config.json` is created from `config.example.json` or built-in defaults;
- missing `seen_posts.json` starts as `{}`;
- missing `for_hire_posts.json` starts as `{"posts": [], "stats": {}}`;
- missing `subreddit_rules.json` starts as `{}`;
- missing `.env` prints a warning and Telegram sending will not work until you create it from `.env.example`.

The app directory is detected like this:

- when running `main.py`, files are read next to `main.py`;
- when running the PyInstaller exe, files are read next to `RedditQuickWorkBot.exe`.

## Run With Python

```powershell
python main.py
```

Useful commands:

```powershell
python main.py --test-telegram
python main.py rules-check
python main.py rules-check freelance_forhire
python main.py rules-show freelance_forhire
python main.py forhire-draft freelance_forhire
python main.py forhire-status
python main.py forhire-posted freelance_forhire
python main.py forhire-reply freelance_forhire good
python main.py forhire-reply freelance_forhire bad
```

## Rules Presets

`RULES_FETCH_ENABLED` is `false` by default. Reddit often returns HTTP 403 or 429 for automated rules/about/wiki requests, so the bot uses:

1. fresh `subreddit_rules.json` cache;
2. `subreddit_rules_presets.json`;
3. optional live rules fetch only if enabled.

Presets are approximate. Always manually verify subreddit rules before posting.

## For Hire Draft Assistant

The assistant can generate a Telegram reminder with:

- subreddit;
- rules confidence;
- status: `safe`, `low_confidence`, or `risky`;
- rules summary;
- suggested title;
- draft body;
- warnings.

It never publishes anything on Reddit. You must manually check the subreddit rules and post yourself only if allowed.

## Build EXE

```powershell
pyinstaller --onefile --name RedditQuickWorkBot main.py
```

The executable will be:

```text
dist/RedditQuickWorkBot.exe
```

## Portable EXE Usage

1. Build:

```powershell
pyinstaller --onefile --name RedditQuickWorkBot main.py
```

2. Create a folder anywhere, for example:

```text
RedditQuickWorkBot/
```

3. Put inside:

```text
RedditQuickWorkBot.exe
config.json
.env
subreddit_rules_presets.json
```

4. The bot will create missing runtime files automatically:

```text
seen_posts.json
for_hire_posts.json
subreddit_rules.json
```

For troubleshooting, run the exe from PowerShell so you can see logs:

```powershell
.\RedditQuickWorkBot.exe
```

The same CLI commands work with the exe:

```powershell
.\RedditQuickWorkBot.exe --test-telegram
.\RedditQuickWorkBot.exe rules-check
.\RedditQuickWorkBot.exe forhire-draft freelance_forhire
```

## Before Pushing To GitHub

Run:

```powershell
git status
git add .
git status
```

Checklist before commit:

- `.env` is not staged.
- `config.json` is not staged.
- `seen_posts.json` is not staged.
- `for_hire_posts.json` is not staged.
- `subreddit_rules.json` is not staged.
- `dist/` and `build/` are not staged.
- `*.spec` is not staged.
- No real Telegram bot token is staged.

## Safety Notes

- The bot only reads Reddit RSS/public pages and sends Telegram notifications.
- It does not auto-post to Reddit.
- It does not comment.
- It does not send Reddit DMs.
- Never commit `.env` or local runtime files.
