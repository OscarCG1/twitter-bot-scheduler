# Contributing to twitter-bot-scheduler

Thanks for your interest! This project is meant to be **simple and beginner-friendly**, so every contribution — from fixing a typo to adding a feature — is welcome. You do not need to be an expert.

## Ways to help

- 🐛 **Report a bug** — something does not work as the docs say.
- 💡 **Suggest an idea** — a feature or improvement you would find useful.
- ❓ **Ask a question** — if something in the docs confused you, others are probably confused too.
- 📝 **Improve the docs** — clearer explanations, typos, screenshots.
- 🔧 **Send code** — bug fixes or small, focused features.

## Reporting a bug or asking a question

1. Go to the **Issues** tab of the repository and click **New issue**.
2. Pick the right template (*Bug report*, *Feature request* or *Question*).
3. Fill in the sections. The more detail, the faster someone can help.

> ⚠️ **Never paste your `.env` file, API keys, tokens or passwords in an issue.**
> Issues are public. If a log line contains a secret, replace it with `***` before pasting.

Before opening a new issue, please search the existing ones — your question may already be answered.

## Your first code contribution (step by step)

If you have never contributed to a GitHub project, follow these steps:

1. **Fork** the repository (button at the top right of the GitHub page). This creates your own copy.
2. **Clone** your fork to your computer:
   ```bash
   git clone https://github.com/<your-username>/twitter-bot-scheduler.git
   cd twitter-bot-scheduler
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b fix-short-description
   ```
4. **Set up** the project (see the README, section *Installation*).
5. **Make your change** and test it (see below).
6. **Commit** with a clear message:
   ```bash
   git add <files-you-changed>
   git commit -m "Fix: daily counter not resetting at midnight"
   ```
7. **Push** your branch and open a **Pull Request** on GitHub:
   ```bash
   git push origin fix-short-description
   ```
   GitHub will show a button *Compare & pull request*. Fill in the template and submit.

## Testing your change (without spending credits)

Always test in **dry-run mode** first — no real posts are sent and no budget is spent:

```bash
# Validate configuration and credentials
python poster_bot.py --check

# Simulate one post
DRY_RUN=true python poster_bot.py --once

# Generate a weekly report from your logs
python weekly_report.py --now
```

On Windows (PowerShell) use `$env:DRY_RUN="true"; python poster_bot.py --once`.

## Code guidelines

- **Keep it simple.** This repo is for learning: readable code beats clever code.
- **Comment the "why"**, not the obvious "what".
- **English** for code, comments and documentation.
- **One change per pull request.** Small PRs are reviewed faster.
- **No new paid features by default.** Anything that spends more API credits (links, images, media) must stay optional and off by default.
- **No secrets or personal data** in code, configs, examples or screenshots. Use placeholders like `@YOUR_HANDLE`.
- If you change behavior, **update the docs** (README, `docs/`) in the same PR.

## Code of conduct

Be kind and patient. Many people here are beginners — there are no silly questions. Disrespectful, discriminatory or harassing behavior is not tolerated.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
