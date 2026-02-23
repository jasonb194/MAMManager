"""MAM Manager: MyAnonamouse dashboard and daily automations."""

from __future__ import annotations

import logging
import time
from datetime import date

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .config_flow import _login_mam
from .const import (
    ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
    CONF_AUTO_BUY_CREDIT,
    CONF_AUTO_BUY_VIP,
    CONF_AUTO_DONATE_VAULT,
    CONF_BASE_URL,
    CONF_MAM_ID,
    CONF_MBSC,
    CONF_PASSWORD,
    CONF_USER_ID,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_BUY_CREDIT_PATH,
    DEFAULT_BUY_VIP_PATH,
    DEFAULT_DONATE_POINTS,
    DEFAULT_DONATE_VAULT_PATH,
    DONATE_COOKIE_NAME,
    DOMAIN,
    MAM_DONATE_HEADERS,
    MIN_RATIO_FOR_DONATE,
    MIN_SEEDBONUS_FOR_CREDIT,
    MIN_SEEDBONUS_FOR_VIP,
    STORAGE_KEY,
    STORAGE_LAST_BUY_CREDIT_DATE,
    STORAGE_LAST_BUY_VIP_DATE,
    STORAGE_LAST_DONATE_DATE,
    STORAGE_VERSION,
    USER_DATA_PARAMS,
    USER_DATA_PATH,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _today_iso() -> str:
    return date.today().isoformat()


def _is_valid_session_cookie(value: str | None) -> bool:
    """True if value looks like a real session cookie (not empty or server clear sentinel like 'deleted')."""
    if not value or not value.strip():
        return False
    return value.strip().lower() != "deleted"


async def _fetch_user_data(
    hass: HomeAssistant,
    base_url: str,
    user_id: str,
    mam_id: str,
    store: Store,
) -> tuple[dict | None, str | None]:
    """
    Fetch user data from MAM. Returns (user_data, new_mam_id or None).
    If response has Set-Cookie, return new cookie value so caller can persist it.
    """
    url = base_url.rstrip("/") + USER_DATA_PATH
    # Match MAM URL: ?pretty&id=...&notif&clientStats&snatch_summary
    params = {"id": user_id}
    for key in USER_DATA_PARAMS:
        params[key] = ""
    headers = {"Cookie": f"mam_id={mam_id}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                new_cookie = None
                if "Set-Cookie" in resp.headers or "set-cookie" in resp.headers:
                    set_cookie = resp.headers.get("Set-Cookie") or resp.headers.get("set-cookie") or ""
                    part = set_cookie.split(";")[0].strip()
                    if "=" in part:
                        new_cookie = part.split("=", 1)[1].strip()
                if resp.status != 200:
                    return None, new_cookie
                data = await resp.json()
                if isinstance(data, dict) and "username" in data:
                    return data, new_cookie
                return None, new_cookie
    except Exception as e:
        _LOGGER.warning("MAM user data fetch failed: %s", e)
        return None, None


async def _mam_request(
    hass: HomeAssistant,
    base_url: str,
    path: str,
    mam_id: str,
    method: str = "get",
    json_body: dict | None = None,
    form_data: dict | None = None,
    cookie_name: str = "mam_id",
    extra_headers: dict[str, str] | None = None,
) -> tuple[bool, str | None]:
    """Perform a request to MAM (e.g. buy credit or donate). Returns (success, new_mam_id or None).
    Use form_data for application/x-www-form-urlencoded POST (e.g. donate form).
    Use cookie_name='mbsc' for donate. Use extra_headers for donate (browser-like headers)."""
    if not path or not path.strip():
        return False, None
    url = base_url.rstrip("/") + path.strip()
    if not url.startswith("http"):
        return False, None
    headers = {"Cookie": f"{cookie_name}={mam_id}"}
    if extra_headers:
        headers = {**extra_headers, **headers}
    new_cookie = None
    try:
        async with aiohttp.ClientSession() as session:
            if method.lower() == "post":
                if form_data is not None:
                    async with session.post(
                        url, headers=headers, data=form_data, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if "Set-Cookie" in resp.headers or "set-cookie" in resp.headers:
                            set_cookie = resp.headers.get("Set-Cookie") or resp.headers.get("set-cookie") or ""
                            part = set_cookie.split(";")[0].strip()
                            if "=" in part:
                                new_cookie = part.split("=", 1)[1].strip()
                        return resp.status in (200, 201, 204), new_cookie
                else:
                    async with session.post(
                        url, headers=headers, json=json_body or {}, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if "Set-Cookie" in resp.headers or "set-cookie" in resp.headers:
                            set_cookie = resp.headers.get("Set-Cookie") or resp.headers.get("set-cookie") or ""
                            part = set_cookie.split(";")[0].strip()
                            if "=" in part:
                                new_cookie = part.split("=", 1)[1].strip()
                        return resp.status in (200, 201, 204), new_cookie
            else:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if "Set-Cookie" in resp.headers or "set-cookie" in resp.headers:
                        set_cookie = resp.headers.get("Set-Cookie") or resp.headers.get("set-cookie") or ""
                        part = set_cookie.split(";")[0].strip()
                        if "=" in part:
                            new_cookie = part.split("=", 1)[1].strip()
                    return resp.status == 200, new_cookie
    except Exception as e:
        _LOGGER.warning("MAM request %s failed: %s", path, e)
        return False, None


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up MAM Manager domain."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MAM Manager from a config entry."""
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_{STORAGE_KEY}")

    async def _load_storage() -> dict:
        return await store.async_load() or {}

    async def _update_user_and_storage() -> dict:
        """Fetch user data from MAM, update cookie if needed, merge with storage."""
        data = entry.data or {}
        options = entry.options or data
        base_url = (data.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip()
        user_id = (data.get(CONF_USER_ID) or "").strip()
        mam_id = (data.get(CONF_MAM_ID) or "").strip()
        if not user_id or not mam_id:
            return {"user_data": None, "last_donate_date": None, "last_buy_credit_date": None, "last_buy_vip_date": None}

        saved = await _load_storage()
        user_data, new_cookie = await _fetch_user_data(hass, base_url, user_id, mam_id, store)
        # Only update stored mam_id when we got valid user data and a real new cookie (server may send Set-Cookie: mam_id=deleted or empty to clear session after reboot/expiry - do not overwrite)
        if user_data and _is_valid_session_cookie(new_cookie) and (new_cookie or "").strip() != mam_id:
            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MAM_ID: (new_cookie or "").strip()})

        last_donate = saved.get(STORAGE_LAST_DONATE_DATE)
        last_buy = saved.get(STORAGE_LAST_BUY_CREDIT_DATE)
        last_buy_vip = saved.get(STORAGE_LAST_BUY_VIP_DATE)
        return {
            "user_data": user_data,
            "last_donate_date": last_donate,
            "last_buy_credit_date": last_buy,
            "last_buy_vip_date": last_buy_vip,
        }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_interval=SCAN_INTERVAL,
        update_method=_update_user_and_storage,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator, "store": store}

    async def _run_daily_actions(*_args, **_kwargs) -> None:
        """Run once per day: donate (fresh login + mbsc), then buy VIP/credit (mam_id only)."""
        _LOGGER.info("MAM Manager: daily run started")
        options = entry.options or entry.data or {}
        data = entry.data or {}
        base_url = (data.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip()
        mam_id = (data.get(CONF_MAM_ID) or "").strip()
        has_creds = bool((data.get(CONF_USERNAME) or "").strip() and (data.get(CONF_PASSWORD) or ""))
        if not mam_id and not has_creds:
            _LOGGER.warning("MAM Manager: daily run skipped (no credentials: set user ID + cookie or username + password)")
            return
        today = _today_iso()
        saved = await store.async_load() or {}
        updated = False
        donate_status = "skipped_off"
        vip_status = "skipped_off"
        credit_status = "skipped_off"

        # 1) Donate: only via username/password; fresh login every day, use mbsc only; update mbsc from response
        if options.get(CONF_AUTO_DONATE_VAULT) and DEFAULT_DONATE_VAULT_PATH:
            if not has_creds:
                donate_status = "skipped_no_creds"
                _LOGGER.info("MAM Manager: donate skipped (username/password required for donate)")
            elif saved.get(STORAGE_LAST_DONATE_DATE) != today:
                user_data = (coordinator.data or {}).get("user_data") or {}
                ratio_val = user_data.get("ratio")
                if isinstance(ratio_val, str):
                    try:
                        ratio_val = float(ratio_val.replace(",", ""))
                    except (ValueError, TypeError):
                        ratio_val = 0.0
                ratio_val = float(ratio_val) if ratio_val is not None else 0.0
                if ratio_val >= MIN_RATIO_FOR_DONATE:
                    username = (data.get(CONF_USERNAME) or "").strip()
                    password = data.get(CONF_PASSWORD) or ""
                    session_cookie, login_err = await _login_mam(hass, base_url, username, password)
                    if login_err:
                        donate_status = "skipped_login_failed"
                        _LOGGER.warning("MAM Manager: donate skipped (login failed: %s)", login_err)
                    elif session_cookie:
                        # Update mam_id from login so API/VIP/credit use fresh session
                        hass.config_entries.async_update_entry(
                            entry, data={**entry.data, CONF_MAM_ID: session_cookie}
                        )
                        # Donate with mbsc only (fresh from login); mbsc changes on every page call
                        donate_form = {
                            "Donation": str(DEFAULT_DONATE_POINTS),
                            "time": f"{time.time():.4f}",
                            "submit": "Donate Points",
                        }
                        donate_url = base_url.rstrip("/") + DEFAULT_DONATE_VAULT_PATH
                        donate_headers = {
                            **MAM_DONATE_HEADERS,
                            "Origin": base_url.rstrip("/"),
                            "Referer": donate_url + "?",
                        }
                        ok, new_cookie = await _mam_request(
                            hass,
                            base_url,
                            DEFAULT_DONATE_VAULT_PATH,
                            session_cookie,
                            method="post",
                            form_data=donate_form,
                            cookie_name=DONATE_COOKIE_NAME,
                            extra_headers=donate_headers,
                        )
                        # Update local mbsc when donate response sends Set-Cookie
                        if new_cookie:
                            hass.config_entries.async_update_entry(
                                entry, data={**entry.data, CONF_MBSC: new_cookie}
                            )
                        if ok:
                            saved[STORAGE_LAST_DONATE_DATE] = today
                            updated = True
                            donate_status = "done"
                            _LOGGER.info("MAM Manager: donate to vault completed for today")
                        else:
                            donate_status = "skipped_request_failed"
                            _LOGGER.warning("MAM Manager: donate request failed (check site/connection)")
                else:
                    donate_status = "skipped_ratio"
                    _LOGGER.info(
                        "MAM Manager: donate skipped (ratio %s < %s)",
                        ratio_val,
                        MIN_RATIO_FOR_DONATE,
                    )
            else:
                donate_status = "already_done"
                _LOGGER.info("MAM Manager: donate already done today, skipping")
        await coordinator.async_request_refresh()
        mam_id = (entry.data or {}).get(CONF_MAM_ID) or mam_id

        # 2) VIP and 3) Credit: always use mam_id only (never mbsc)

        if options.get(CONF_AUTO_BUY_VIP) and DEFAULT_BUY_VIP_PATH:
            user_data = (coordinator.data or {}).get("user_data") or {}
            classname = ((user_data.get("classname") or "").strip()).lower()
            seedbonus = user_data.get("seedbonus")
            if isinstance(seedbonus, str):
                try:
                    seedbonus = int(seedbonus.replace(",", ""))
                except (ValueError, TypeError):
                    seedbonus = 0
            seedbonus = int(seedbonus) if seedbonus is not None else 0
            if classname in ALLOWED_CLASSNAMES_FOR_AUTO_VIP:
                if seedbonus >= MIN_SEEDBONUS_FOR_VIP:
                    if saved.get(STORAGE_LAST_BUY_VIP_DATE) != today:
                        ok, new_cookie = await _mam_request(
                            hass, base_url, DEFAULT_BUY_VIP_PATH, mam_id
                        )
                        if _is_valid_session_cookie(new_cookie) and (new_cookie or "").strip() != mam_id:
                            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MAM_ID: (new_cookie or "").strip()})
                        if ok:
                            saved[STORAGE_LAST_BUY_VIP_DATE] = today
                            updated = True
                            vip_status = "done"
                            _LOGGER.info("MAM Manager: buy VIP completed for today")
                        else:
                            vip_status = "skipped_request_failed"
                            _LOGGER.warning("MAM Manager: buy VIP request failed")
                    else:
                        vip_status = "already_done"
                        _LOGGER.info("MAM Manager: VIP already bought today, skipping")
                else:
                    vip_status = "skipped_seedbonus"
                    _LOGGER.info(
                        "MAM Manager: VIP skipped (seedbonus %s < %s)",
                        seedbonus,
                        MIN_SEEDBONUS_FOR_VIP,
                    )
            else:
                vip_status = "skipped_class"
                _LOGGER.info(
                    "MAM Manager: VIP skipped (class '%s' not eligible)",
                    user_data.get("classname") or "?",
                )
        await coordinator.async_request_refresh()
        mam_id = (entry.data or {}).get(CONF_MAM_ID) or mam_id

        if options.get(CONF_AUTO_BUY_CREDIT) and DEFAULT_BUY_CREDIT_PATH:
            user_data = (coordinator.data or {}).get("user_data") or {}
            seedbonus = user_data.get("seedbonus")
            if isinstance(seedbonus, str):
                try:
                    seedbonus = int(seedbonus.replace(",", ""))
                except (ValueError, TypeError):
                    seedbonus = 0
            seedbonus = int(seedbonus) if seedbonus is not None else 0
            if seedbonus >= MIN_SEEDBONUS_FOR_CREDIT:
                if saved.get(STORAGE_LAST_BUY_CREDIT_DATE) != today:
                    ok, new_cookie = await _mam_request(
                        hass, base_url, DEFAULT_BUY_CREDIT_PATH, mam_id
                    )
                    if _is_valid_session_cookie(new_cookie) and (new_cookie or "").strip() != mam_id:
                        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MAM_ID: (new_cookie or "").strip()})
                    if ok:
                        saved[STORAGE_LAST_BUY_CREDIT_DATE] = today
                        updated = True
                        credit_status = "done"
                        _LOGGER.info("MAM Manager: buy credit completed for today")
                    else:
                        credit_status = "skipped_request_failed"
                        _LOGGER.warning("MAM Manager: buy credit request failed")
                else:
                    credit_status = "already_done"
                    _LOGGER.info("MAM Manager: credit already bought today, skipping")
            else:
                credit_status = "skipped_seedbonus"
                _LOGGER.info(
                    "MAM Manager: credit skipped (seedbonus %s < %s)",
                    seedbonus,
                    MIN_SEEDBONUS_FOR_CREDIT,
                )

        _LOGGER.info(
            "MAM Manager: daily run finished — donate: %s, VIP: %s, credit: %s",
            donate_status,
            vip_status,
            credit_status,
        )
        if updated:
            await store.async_save(saved)
            await coordinator.async_request_refresh()

    # Run daily at 02:00 UTC (buy credit and donate)
    remove_daily = async_track_utc_time_change(
        hass, _run_daily_actions, hour=2, minute=0, second=0
    )
    entry.async_on_unload(remove_daily)
    # Run once on load in case we're past midnight and haven't run yet
    hass.async_create_task(_run_daily_actions())

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])

    try:
        from .dashboard import ensure_dashboard
        await ensure_dashboard(hass)
    except Exception as e:
        _LOGGER.warning("Could not create MAM Manager dashboard: %s", e)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(entry, ["sensor", "switch"])
