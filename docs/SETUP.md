# X API Setup – Step by Step

This guide takes you from zero to the 5 credentials the bot needs. It takes about 15 minutes. The X developer portal changes its design from time to time, so button names may differ slightly.

## 1. Create an X Developer account

1. Log in to X with the account you want the bot to post from.
2. Go to **https://developer.twitter.com** (also reachable at developer.x.com) and click **Developer Portal** / **Sign up**.
3. Describe how you will use the API. Be honest and simple, for example:
   > "I will use the API to publish my own pre-written text posts on my own account at scheduled times. No data collection, no automated replies or likes."
4. Accept the terms and confirm your email if asked.
5. Add API credits / choose a plan in the billing section. The API is **pay-per-use**: without credits, posting returns `402 Payment Required`.

## 2. Create a project and an app

1. In the dashboard, open **Projects & Apps**.
2. Create a **Project** (any name, e.g. `My Posting Bot`) and choose a use case such as "Making a bot".
3. Inside the project, create an **App** (e.g. `my-scheduler-app`).
4. The portal may show you some keys right away. You can copy them now, but you will regenerate them in step 5 anyway.

## 3. Set app permissions to "Read and Write"

By default apps can only **read**. The bot needs to **write** (post).

1. Open your app → **Settings** → **User authentication settings** → **Set up** (or **Edit**).
2. **App permissions**: select **Read and write**.

## 4. App type, callback URL and website URL

In the same form:

1. **Type of App**: select **Web App, Automated App or Bot**.
2. **Callback URI / Redirect URL**: the bot does not use it, but the field is required. Use something like `http://localhost:3000/callback`.
3. **Website URL**: any valid public URL, e.g. your profile `https://x.com/YOUR_HANDLE`.
4. Click **Save**.

## 5. Generate the 5 credentials

Open your app → **Keys and tokens**.

| Credential | Where | `.env` variable |
|---|---|---|
| API Key | Consumer Keys → Regenerate | `X_API_KEY` |
| API Key Secret | Consumer Keys → Regenerate | `X_API_SECRET` |
| Access Token | Authentication Tokens → Access Token and Secret → Generate | `X_ACCESS_TOKEN` |
| Access Token Secret | same as above | `X_ACCESS_TOKEN_SECRET` |
| Bearer Token | Authentication Tokens → Bearer Token → Generate | `X_BEARER_TOKEN` |

⚠️ **Important:** generate the **Access Token and Secret AFTER** setting "Read and write" (step 3). Tokens created before keep the old read-only permission and posting fails with `403 Forbidden`. If in doubt, regenerate them.

Each secret is shown **only once**. Copy it straight into your `.env` file (next step) or a password manager.

## 6. Copy them into your `.env` file

```bash
cp .env.example .env
```

Open `.env` and paste your values:

```
X_API_KEY=paste_your_api_key
X_API_SECRET=paste_your_api_key_secret
X_ACCESS_TOKEN=paste_your_access_token
X_ACCESS_TOKEN_SECRET=paste_your_access_token_secret
X_BEARER_TOKEN=paste_your_bearer_token
```

No quotes, no spaces around `=`.

## 7. Test it

```bash
python poster_bot.py --check
```

You should see `Authenticated on X as @YOUR_HANDLE` and `Setup check PASSED`. If not:

| Error | Fix |
|---|---|
| `Missing credentials in .env` | A variable is empty or still has the placeholder value. |
| `401 Unauthorized` | A key was copied wrong. Regenerate and paste again. |
| `403 Forbidden` when posting | Permissions are read-only. Do step 3, then regenerate the Access Token (step 5). |
| `402 Payment Required` | No API credits. Add credits in the billing section. |

## Security tips

- Never commit `.env` or paste your keys in issues, chats or screenshots.
- If a key leaks, **regenerate it immediately** in the portal — the old one stops working.
