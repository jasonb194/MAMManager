# MAM Manager

A **Home Assistant** custom integration for [MyAnonamouse](https://www.myanonamouse.net) (MAM). View your user stats on a dashboard and run daily automations: donate to the vault, buy VIP, and buy upload credit.

## Features

- **Dashboard**: See your MAM user info (class, ratio, uploaded, downloaded, seedbonus, wedges, notifications) and whether you’ve donated today.
- **Daily automations** (run at 02:00 UTC, in order):
  1. **Donate to vault** (if enabled)
  2. **Buy VIP** (if enabled, class is VIP or Power user, and seedbonus ≥ 5,000)
  3. **Buy upload credit** (if enabled and seedbonus ≥ 25,000)
- User data and bonus points are refreshed between each action. Session cookie is updated automatically when MAM returns a new one.

## Installation

### Via HACS (recommended)

1. In HACS go to **Integrations** → **⋮** (top right) → **Custom repositories**.
2. Add repository URL: `https://github.com/YOUR_USERNAME/MAMManager` (use your actual GitHub repo URL).
3. Choose category **Integration** and add.
4. Search for **MAM Manager** in HACS, install it, then restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for **MAM Manager** to configure.

### Manual

1. Copy the `custom_components/mam_manager` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for **MAM Manager**.
4. Enter your **User ID** (numeric) and **MAM session cookie** (`mam_id` from your browser after logging in to MAM). Submit.
5. Open the integration card → **Configure** to turn on **Auto donate to vault**, **Auto buy VIP**, and/or **Auto buy credit** as desired.

## Finding the integration

- **Add integration**: **Settings → Devices & services → Add integration** → search for **MAM Manager**. If it does not appear, ensure `custom_components/mam_manager` is in your config folder and restart Home Assistant.
- **After setup**: The integration appears as a card (e.g. your user ID). Click it to **Configure** and to see the MAM status sensor.
- **Dashboard**: A **MAM Manager** dashboard is created. Open it from the **sidebar** or go to `/mam-manager`.

## Configuration

### Setup (one-time)

- **User ID**: Your MAM user ID (numeric), e.g. `230826`.
- **MAM session cookie**: After logging in to MAM in your browser, copy the `mam_id` cookie value (e.g. from DevTools → Application → Cookies). The integration will update this automatically when MAM sends a new cookie.

### Options (Configure)

- **Auto donate to vault (once per day)** – Donate to the vault at 02:00 UTC each day when enabled.
- **Auto buy VIP (once per day)** – Spend bonus points on VIP when enabled. Only runs if your class is **VIP** or **Power user** and seedbonus ≥ **5,000**.
- **Auto buy credit (once per day)** – Spend 50 bonus points on upload credit when enabled. Only runs if seedbonus ≥ **25,000**.

All automation URLs are fixed in the integration (no URL overrides). User data is refreshed between each action so bonus points are up to date.

## How it works

1. **User data**: The integration fetches your MAM user data every 15 minutes from `jsonLoad.php` (class, ratio, seedbonus, etc.) and shows it on the dashboard and sensor.
2. **Daily run (02:00 UTC)**:
   - Donate to vault (if enabled and not already done today).
   - Refresh user data (and cookie if set).
   - Buy VIP (if enabled, class is VIP or Power user, seedbonus ≥ 5,000, and not done today).
   - Refresh user data again.
   - Buy credit (if enabled, seedbonus ≥ 25,000, and not done today).
3. **Cookie**: If any request returns a new `Set-Cookie` (e.g. session refresh), the integration saves it so the next request uses the updated session.

## Icon

**HACS and Home Assistant** load integration icons from [brands.home-assistant.io](https://github.com/home-assistant/brands) (by integration domain). To show the MAM Manager icon in HACS and **Settings → Integrations**:

1. In the [Home Assistant brands repository](https://github.com/home-assistant/brands), add a folder `custom_integrations/mam_manager/`.
2. Add **`icon.png`** (e.g. 256×256 PNG) as `custom_integrations/mam_manager/icon.png`.
3. Submit a pull request. Once merged, the icon will appear in HACS and **Settings → Integrations**.

This repo includes `custom_components/mam_manager/icon.svg` (mouse icon) as the source; you can export a PNG from it for the brands repo.

## Requirements

- Home Assistant (tested on recent versions).
- A MyAnonamouse account. You need your **user ID** and **session cookie** (`mam_id`) from your browser after logging in.
- Dependency (installed automatically): `aiohttp`.

## License

MIT
