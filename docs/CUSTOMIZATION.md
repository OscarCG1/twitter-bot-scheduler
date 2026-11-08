# Customization Guide

How to adapt the bot to your own niche, schedule and budget. Most changes only need a text editor.

## Change posting times and timezone

In `.env`:

```
POST_TIMES=07:30,12:00,18:45
TIMEZONE=America/New_York
MAX_POSTS_PER_DAY=3
```

- `POST_TIMES`: comma-separated, 24-hour `HH:MM` format.
- `TIMEZONE`: an [IANA timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) such as `Europe/London`, `America/Mexico_City`, `Asia/Tokyo`.
- `MAX_POSTS_PER_DAY`: safety limit. If you add a 4th time, raise this to 4 too.
- `WEEKLY_REPORT_TIME`: when the Monday report is generated.

Restart the scripts after editing `.env`. Run `python poster_bot.py --check` to validate the times and timezone.

## Add or edit content pillars

Content pillars are the 4–6 recurring topics of your account. Edit them in `config/strategy_config.json`:

```json
"content_pillars": [
  {"id": 1, "name": "Productivity tips", "description": "Small habits that save time", "emoji": "⏱️"},
  {"id": 2, "name": "Tool reviews", "description": "Honest one-line opinions", "emoji": "🛠️"},
  {"id": 3, "name": "Behind the scenes", "description": "What my week really looked like", "emoji": "🎬"}
]
```

Each post in the queue references a pillar by its `id`. The weekly report counts posts per pillar so you can see if your mix is balanced. `pillar_rotation_index` and `post_mix` are planning helpers for you (or an AI assistant) when drafting new batches of posts.

## Add posts to the queue

Edit `config/content_queue.json` and append items to the `queue` array. Posts are published **top to bottom**.

| Field | Required | Description |
|---|---|---|
| `id` | yes | Any unique label, e.g. `post_042` |
| `text` | yes (single) | The tweet, max 280 characters |
| `thread` | yes (thread) | List of tweets, each max 280 characters |
| `type` | no | `single` (default), `question` or `thread` |
| `pillar` | no | Pillar `id` from strategy_config.json |
| `created_at`, `scheduled_for` | no | Free-form notes for yourself |

Tips:
- Keep the JSON valid: commas between items, double quotes. Paste the file into any online "JSON validator" if unsure.
- You can edit the queue while the bot is running; it re-reads the file before every post.
- Keep at least a week of posts (21) in the queue so the bot never runs dry.

## Adjust budget caps

In `.env`:

```
MONTHLY_BUDGET_USD=5.00
COST_PER_POST_USD=0.015
```

- Spend is calculated per calendar month from `logs/posts_YYYY-MM.json`.
- Before each post the bot checks `monthly spend + cost of this post <= MONTHLY_BUDGET_USD`. If not, it skips and raises `error_402_week`.
- A thread costs `COST_PER_POST_USD × number of tweets`.
- The weekly report alerts you when spend goes above 80% of the cap.

## Modify tone guidelines

`tone_guidelines`, `persona_description`, `red_lines` and `style_examples` in `config/strategy_config.json` are your **editorial guide**. The bot does not rewrite your posts, but having them written down keeps your voice consistent — and you can paste the whole file into an AI assistant as instructions when you ask it to draft new posts for the queue.

```json
"tone_guidelines": "Friendly and direct. Short sentences. One idea per post.",
"red_lines": ["No personal attacks", "No invented facts or quotes", "No @mentions"]
```

## Understand the manual queue

Before each post, the bot scans the queue and moves an item to `manual_queue` when:

| Reason | Why |
|---|---|
| `contains_link_or_media` | Has a URL (`https://…`, `www.…`, `example.com`) or a `media` field. Link posts cost much more (~$0.20). |
| `too_long` | A tweet is over 280 characters. |
| `empty_text` | No text to publish. |

Every Monday the report lists these posts. Publish them by hand on X, then delete them from `manual_queue`. If you fix a post (e.g. shorten it or remove the link), you can move it back to `queue`.

## Test changes safely

Set `DRY_RUN=true` in `.env` and run `python poster_bot.py --once`. The bot runs all the logic and logs what it would post, without calling the X API.

> Note: dry runs still update the queue and logs as if the post had been published (with `"dry_run": true` and a cost of $0, so your budget is not affected). Make a copy of `config/content_queue.json` first if you want to restore it afterwards.
