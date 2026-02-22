"""Config flow for MAM Manager."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_AUTO_BUY_CREDIT,
    CONF_AUTO_BUY_VIP,
    CONF_AUTO_DONATE_VAULT,
    CONF_BASE_URL,
    CONF_MAM_ID,
    CONF_USER_ID,
    DEFAULT_AUTO_BUY_CREDIT,
    DEFAULT_AUTO_BUY_VIP,
    DEFAULT_AUTO_DONATE_VAULT,
    DEFAULT_BASE_URL,
    DOMAIN,
    USER_DATA_PARAMS,
    USER_DATA_PATH,
)


def _normalize_base_url(url: str) -> str:
    """Strip trailing slash and ensure scheme."""
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def _validate_user_id(value: str) -> bool:
    """User ID must be numeric."""
    return (value or "").strip().isdigit()


async def _test_mam_connection(
    hass: HomeAssistant, base_url: str, user_id: str, mam_id: str
) -> tuple[bool, str | None]:
    """Test MAM API with given credentials. Returns (success, error_message)."""
    base_url = _normalize_base_url(base_url)
    if not base_url or not (user_id or "").strip() or not (mam_id or "").strip():
        return False, "missing_config"
    url = base_url + USER_DATA_PATH
    # Match MAM URL: ?pretty&id=...&notif&clientStats&snatch_summary
    params = {"id": user_id.strip()}
    for key in USER_DATA_PARAMS:
        params[key] = ""
    headers = {"Cookie": f"mam_id={mam_id.strip()}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return False, "cannot_connect"
                data = await resp.json()
                if not data or (isinstance(data, dict) and "username" not in data):
                    return False, "cannot_connect"
                return True, None
    except aiohttp.ClientError:
        return False, "cannot_connect"
    except Exception:
        return False, "cannot_connect"


class MAMManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for MAM Manager."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "MAMManagerOptionsFlow":
        return MAMManagerOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial setup: user ID and mam_id cookie (base URL is fixed)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id = (user_input.get(CONF_USER_ID) or "").strip()
            mam_id = (user_input.get(CONF_MAM_ID) or "").strip()
            if not _validate_user_id(user_id):
                errors["base"] = "invalid_user_id"
            elif not mam_id:
                errors["base"] = "cannot_connect"
            else:
                ok, err = await _test_mam_connection(
                    self.hass, DEFAULT_BASE_URL, user_id, mam_id
                )
                if not ok:
                    errors["base"] = err or "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=user_id or "MAM",
                        data={
                            CONF_BASE_URL: DEFAULT_BASE_URL,
                            CONF_USER_ID: user_id,
                            CONF_MAM_ID: mam_id,
                        },
                        options={
                            CONF_AUTO_BUY_CREDIT: DEFAULT_AUTO_BUY_CREDIT,
                            CONF_AUTO_DONATE_VAULT: DEFAULT_AUTO_DONATE_VAULT,
                            CONF_AUTO_BUY_VIP: DEFAULT_AUTO_BUY_VIP,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_USER_ID, default=""): str,
                vol.Required(CONF_MAM_ID, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class MAMManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle MAM Manager options: auto buy credit, donate, buy VIP (URLs are fixed)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options: daily automations only."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._config_entry.options or {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_AUTO_BUY_CREDIT,
                    default=opts.get(CONF_AUTO_BUY_CREDIT, DEFAULT_AUTO_BUY_CREDIT),
                ): cv.boolean,
                vol.Required(
                    CONF_AUTO_DONATE_VAULT,
                    default=opts.get(CONF_AUTO_DONATE_VAULT, DEFAULT_AUTO_DONATE_VAULT),
                ): cv.boolean,
                vol.Required(
                    CONF_AUTO_BUY_VIP,
                    default=opts.get(CONF_AUTO_BUY_VIP, DEFAULT_AUTO_BUY_VIP),
                ): cv.boolean,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
