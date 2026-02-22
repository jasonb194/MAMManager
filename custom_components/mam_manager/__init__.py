"""MAM Manager: MyAnonamouse dashboard and daily automations."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
    CONF_AUTO_BUY_CREDIT,
    CONF_AUTO_BUY_VIP,
    CONF_AUTO_DONATE_VAULT,
    CONF_BASE_URL,
    CONF_MAM_ID,
    CONF_USER_ID,
    DEFAULT_BASE_URL,
    DEFAULT_BUY_CREDIT_PATH,
    DEFAULT_BUY_VIP_PATH,
    DEFAULT_DONATE_VAULT_PATH,
    DOMAIN,
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
) -> tuple[bool, str | None]:
    """Perform a request to MAM (e.g. buy credit or donate). Returns (success, new_mam_id or None)."""
    if not path or not path.strip():
        return False, None
    url = base_url.rstrip("/") + path.strip()
    if not url.startswith("http"):
        return False, None
    headers = {"Cookie": f"mam_id={mam_id}"}
    new_cookie = None
    try:
        async with aiohttp.ClientSession() as session:
            if method.lower() == "post":
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
        if new_cookie and new_cookie != mam_id:
            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MAM_ID: new_cookie})

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
        """Run once per day: buy credit and/or donate if enabled and not done today."""
        options = entry.options or entry.data or {}
        data = entry.data or {}
        base_url = (data.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip()
        mam_id = (data.get(CONF_MAM_ID) or "").strip()
        if not mam_id:
            return
        today = _today_iso()
        saved = await store.async_load() or {}
        updated = False

        # Order: 1) donate to vault, 2) buy VIP, 3) buy credit (refresh user data between each)
        if options.get(CONF_AUTO_DONATE_VAULT) and DEFAULT_DONATE_VAULT_PATH:
            if saved.get(STORAGE_LAST_DONATE_DATE) != today:
                ok, new_cookie = await _mam_request(
                    hass, base_url, DEFAULT_DONATE_VAULT_PATH, mam_id
                )
                if new_cookie:
                    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MAM_ID: new_cookie})
                if ok:
                    saved[STORAGE_LAST_DONATE_DATE] = today
                    updated = True
                    _LOGGER.info("MAM Manager: auto donate to vault completed for today")
        await coordinator.async_request_refresh()
        mam_id = (entry.data or {}).get(CONF_MAM_ID) or mam_id

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
                        if new_cookie:
                            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MAM_ID: new_cookie})
                        if ok:
                            saved[STORAGE_LAST_BUY_VIP_DATE] = today
                            updated = True
                            _LOGGER.info("MAM Manager: auto buy VIP completed for today")
                elif options.get(CONF_AUTO_BUY_VIP):
                    _LOGGER.debug(
                        "MAM Manager: auto buy VIP skipped (seedbonus %s < %s)",
                        seedbonus,
                        MIN_SEEDBONUS_FOR_VIP,
                    )
            elif classname and options.get(CONF_AUTO_BUY_VIP):
                _LOGGER.debug(
                    "MAM Manager: auto buy VIP skipped (classname '%s' not in %s)",
                    user_data.get("classname"),
                    ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
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
                    if new_cookie:
                        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MAM_ID: new_cookie})
                    if ok:
                        saved[STORAGE_LAST_BUY_CREDIT_DATE] = today
                        updated = True
                        _LOGGER.info("MAM Manager: auto buy credit completed for today")
            elif options.get(CONF_AUTO_BUY_CREDIT):
                _LOGGER.debug(
                    "MAM Manager: auto buy credit skipped (seedbonus %s < %s)",
                    seedbonus,
                    MIN_SEEDBONUS_FOR_CREDIT,
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
