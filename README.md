# twitter-bot-scheduler

A simple, beginner-friendly bot that publishes **text-only posts on X (Twitter)** at fixed times every day, keeps your spending under a monthly cap, and writes you a **weekly report** every Monday.

---

## 1. What this does

You write your posts in advance in a simple JSON file (the *queue*). The bot publishes them for you **3 times a day** (08:00, 13:00 and 20:00 by default) using the official X API. Posts that contain links are **never auto-posted**: they are moved to a *manual queue* so you can publish them yourself (link posts cost much more on the X pay-per-use API). The bot tracks every cent it spends and **stops automatically** before going over your monthly budget. Every Monday a second script summarizes the week in a Markdown report: posts published, money spent, alerts and the posts waiting for you to publish manually.

## 2. How it works

```
             config/content_queue.json
        ┌──────────────────────────────────┐
        │ queue  →  published              │
        │   └─(has link?)→ manual_queue    │
        └──────────────────────────────────┘
                 ▲                │
                 │ reads/updates  │ logs
                 │                ▼
  ┌──────────────────────┐   logs/posts.log
  │  poster_bot.py       │   logs/posts_YYYY-MM.json
  │  08:00 13:00 20:00   │──────────────┐
  └──────────────────────┘              │ reads
                                        ▼
                          ┌──────────────────────────┐
                          │  weekly_report.py        │
                          │  every Monday 09:00      │
                          └──────────────────────────┘
                                        │
                                        ▼
                         logs/weekly_report_YYYY-WNN.md  (+ optional email)
```

**Agent 1 – `poster_bot.py` (daily posts)**
- Takes the first post in `queue` and publishes it (single tweet or thread).
- Moves posts with links, media or more than 280 characters to `manual_queue`.
- Respects `MAX_POSTS_PER_DAY` (counter resets every midnight).
- Checks the monthly budget **before** every post. If the cap would be exceeded, or X answers `402 Payment Required`, it stops and raises the `error_402_week` flag.
- Logs everything to `logs/posts.log` and `logs/posts_YYYY-MM.json`.

**Agent 2 – `weekly_report.py` (Monday report)**
- Posts published vs target (3/day × 7 = 21/week).
- Budget: weekly spend, monthly spend vs cap, cumulative total, end-of-month projection.
- 🔴 RED ALERT on any 402 / budget-cap event or when spend is above 80% of the cap.
- Breakdown by content pillar and the full list of posts in the manual queue.

## 3. Prerequisites

- **Python 3.9 or newer** (`python --version` to check)
- An **X Developer account** with API credits (see [docs/SETUP.md](docs/SETUP.md))
- Basic terminal knowledge (opening a terminal, `cd`, running a command)

## 4. X API setup

Follow the step-by-step guide in **[docs/SETUP.md](docs/SETUP.md)** to create your app and get your 5 credentials.

## 5. Installation

```bash
# 1. Download the code
git clone https://github.com/YOUR_GITHUB_USER/twitter-bot-scheduler.git
cd twitter-bot-scheduler

# 2. (Recommended) create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install the dependencies
pip install -r requirements.txt

# 4. Create your private settings file
cp .env.example .env            # Windows: copy .env.example .env

# 5. Create your queue from the example
cp config/content_queue.example.json config/content_queue.json
```

Open `.env` in any text editor and replace every `your_..._here` value with your real credentials. **Never share or commit your `.env` file** (it is already listed in `.gitignore`).

> Tip: step 5 is optional — the bot creates `content_queue.json` from the example automatically on its first run.

## 6. Configuration

**`config/strategy_config.json`** – describes your account: handle, persona, content pillars (topics), tone and red lines. The bot uses the pillar names in the weekly report; the rest is your editorial guide (and is handy if you use an AI assistant to draft posts).

**`config/content_queue.json`** – your posts. Add new items to the `queue` array:

```json
{
  "id": "post_010",
  "text": "Your tweet text here. Max 280 characters, no links.",
  "pillar": 2,
  "type": "single"
}
```

Threads use `"type": "thread"` and a `"thread"` list instead of `"text"`:

```json
{
  "id": "post_011",
  "type": "thread",
  "pillar": 3,
  "thread": ["First tweet (1/2)", "Second tweet (2/2)"]
}
```

Posts are published in order, top to bottom. More details in [docs/CUSTOMIZATION.md](docs/CUSTOMIZATION.md).

## 7. Running

First, check that everything is configured correctly:

```bash
python poster_bot.py --check
```

Then:

```bash
python poster_bot.py            # starts the daily scheduler (leave it running)
python weekly_report.py         # starts the Monday report scheduler (leave it running)
```

Useful one-off commands:

```bash
python poster_bot.py --once     # publish the next post right now
python weekly_report.py --now   # generate this week's report right now
```

Want to test without posting anything? Set `DRY_RUN=true` in `.env`. The bot will go through all the steps and log what it *would* publish, without calling the X API.

## 8. Running as a service

The schedulers only work while the scripts are running. To keep them alive 24/7:

- **cron (Linux/macOS)** – skip the built-in scheduler and let cron call the one-shot commands:
  ```cron
  0 8,13,20 * * *  cd /path/to/twitter-bot-scheduler && /path/to/venv/bin/python poster_bot.py --once
  0 9 * * 1        cd /path/to/twitter-bot-scheduler && /path/to/venv/bin/python weekly_report.py --now
  ```
  (cron uses the server's timezone — adjust the hours if it differs from `TIMEZONE`.)
- **systemd (Linux server)** – create a service that runs `python poster_bot.py` with `Restart=always`, and another for `weekly_report.py`.
- **Cloud** – any small VPS, a Raspberry Pi at home, or a scheduled job on a cloud platform that runs the `--once` / `--now` commands.

## 9. Cost awareness

The X API is **pay-per-use**. Approximate prices at the time of writing (always check the current pricing in your developer portal):

| Post type | Approx. cost |
|---|---|
| Text-only post | ~$0.015 |
| Post with a link | ~$0.20 |

That is why this bot **only auto-publishes text posts** and sends anything with a link to the manual queue. With the defaults (3 posts/day, $0.015 each) you spend about **$1.35/month**, well under the default cap of **$3.33/month**. A thread of 3 tweets counts as 3 posts for budget purposes.

Change `COST_PER_POST_USD` and `MONTHLY_BUDGET_USD` in `.env` to match your plan.

## 10. Folder structure

```
twitter-bot-scheduler/
├── README.md                       ← this guide
├── requirements.txt                ← Python dependencies
├── .env.example                    ← template for your private settings (.env)
├── .gitignore                      ← keeps secrets and logs out of git
├── poster_bot.py                   ← agent 1: daily posting
├── weekly_report.py                ← agent 2: Monday report
├── config/
│   ├── strategy_config.json        ← your persona, pillars and tone (template)
│   └── content_queue.example.json  ← example queue (copied to content_queue.json)
├── logs/                           ← posts.log, monthly JSON logs and reports
└── docs/
    ├── SETUP.md                    ← X API setup, step by step
    └── CUSTOMIZATION.md            ← adapt the bot to your niche
```

`config/content_queue.json` is your personal, live queue: it is ignored by git so your drafts and stats stay private.

## 11. FAQ

**1. The bot is running but nothing is posted. Why?**
Check `logs/posts.log`. The most common causes are: the queue is empty, the daily limit was reached, the budget cap was reached, or the times in `POST_TIMES` have not arrived yet in your `TIMEZONE`.

**2. I get a "401 Unauthorized" or "403 Forbidden" error.**
Your app probably has *Read* permission only. Set it to *Read and Write* and **regenerate** your Access Token and Secret afterwards (see [docs/SETUP.md](docs/SETUP.md)).

**3. What does "402 Payment Required" mean?**
Your X API account has no credits left or hit a plan limit. The bot stops posting and the weekly report shows a red alert. Top up your credits and posting resumes at the next scheduled time.

**4. Can I post images or links automatically?**
Not with this bot, on purpose: they are much more expensive on the pay-per-use API. They are moved to `manual_queue` and listed in your weekly report so you can publish them by hand.

**5. Do I have to keep my computer on?**
Yes, if you run it on your computer. For 24/7 posting, run it on a server, a Raspberry Pi or a cloud scheduler (see section 8).

## 12. License

MIT License. See [LICENSE](LICENSE). Use it, modify it, share it.
