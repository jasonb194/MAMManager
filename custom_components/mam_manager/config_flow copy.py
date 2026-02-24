"""Config flow for MAM Manager."""

from __future__ import annotations

import logging
import re
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
    CONF_PASSWORD,
    CONF_USER_ID,
    CONF_USERNAME,
    DEFAULT_AUTO_BUY_CREDIT,
    DEFAULT_AUTO_BUY_VIP,
    DEFAULT_AUTO_DONATE_VAULT,
    DEFAULT_BASE_URL,
    DOMAIN,
    LOGIN_PATH,
    MAM_LOGIN_HEADERS,
    TAKELOGIN_PATH,
    USER_DATA_PARAMS,
    USER_DATA_PATH,
)

_LOGGER = logging.getLogger(__name__)


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


def _parse_login_form(html: str) -> dict[str, str] | None:
    """Extract form fields from login page for the form that posts to takelogin.php."""
    form_match = re.search(
        r"<form[^>]*action=[\"'][^\"']*takelogin[^\"']*[\"'][^>]*>(.*?)</form>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not form_match:
        return None
    form_body = form_match.group(1)
    fields: dict[str, str] = {}
    for tag in re.finditer(r"<input\s[^>]*>", form_body, re.IGNORECASE):
        attrs = tag.group(0)
        name_m = re.search(r'\bname=[\'"]([^\'"]*)[\'"]', attrs, re.IGNORECASE)
        if not name_m:
            continue
        name = name_m.group(1)
        value_m = re.search(r'\bvalue=[\'"]([^\'"]*)[\'"]', attrs, re.IGNORECASE)
        fields[name] = value_m.group(1) if value_m else ""
    return fields if fields else None


async def _login_mam(
    hass: HomeAssistant, base_url: str, username: str, password: str
) -> tuple[str | None, str | None]:
    """Log in to MAM via login.php + takelogin.php. Returns (session_cookie_value, error_key)."""
    base_url = _normalize_base_url(base_url)
    login_url = base_url + LOGIN_PATH
    takelogin_url = base_url + TAKELOGIN_PATH
    username = (username or "").strip()
    password = password or ""
    if not username:
        return None, "invalid_username"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        get_headers = dict(MAM_LOGIN_HEADERS)
        post_headers = {
            **MAM_LOGIN_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": base_url,
            "Referer": login_url,
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # GET login page to obtain lid cookie and form tokens (same headers as browser)
            async with session.get(login_url, headers=get_headers) as resp:
                if resp.status != 200:
                    return None, "cannot_connect"
                html = await resp.text()
            form_fields = _parse_login_form(html)
            if not form_fields:
                return None, "cannot_connect"
            # POST login with form tokens + email + password (same headers as browser)
            data = {**form_fields, "email": username, "password": password}
            async with session.post(
                takelogin_url,
                data=data,
                headers=post_headers,
            ) as resp:
                body = await resp.text()
                location = resp.headers.get("Location") or resp.headers.get("location") or ""
                set_cookie_names = []
                for header in resp.headers.getall("Set-Cookie", []):
                    part = (header.split(";")[0] or "").strip()
                    if "=" in part:
                        set_cookie_names.append(part.split("=", 1)[0].strip())
                _LOGGER.warning(
                    "MAM Manager: login response status=%s location=%s set_cookie_names=%s body_len=%s body_preview=%s",
                    resp.status,
                    location[:80] if location else "",
                    set_cookie_names,
                    len(body),
                    body[:400].replace("\n", " ").strip() if body else "",
                )
                # Session cookie is usually mam_id or mbsc in Set-Cookie
                session_cookie = None
                for header in resp.headers.getall("Set-Cookie", []):
                    part = header.split(";")[0].strip()
                    if "=" in part:
                        name, value = part.split("=", 1)
                        name = name.strip().lower()
                        if name in ("mam_id", "mbsc"):
                            session_cookie = value.strip()
                            break
                if not session_cookie and resp.headers.get("Set-Cookie"):
                    part = resp.headers.get("Set-Cookie", "").split(";")[0].strip()
                    if "=" in part:
                        session_cookie = part.split("=", 1)[1].strip()
                # Login failure: no cookie, or server sent mam_id=deleted / empty to clear session
                if not session_cookie or not session_cookie.strip():
                    return None, "invalid_auth"
                if session_cookie.strip().lower() == "deleted":
                    return None, "invalid_auth"
                return session_cookie, None
    except aiohttp.ClientError:
        return None, "cannot_connect"
    except Exception:
        return None, "cannot_connect"


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
        """Handle initial setup: either session cookie or username/password login."""
        schema = vol.Schema(
            {
                vol.Optional(CONF_USER_ID, default=""): str,
                vol.Optional(CONF_MAM_ID, default=""): str,
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
            }
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id = (user_input.get(CONF_USER_ID) or "").strip()
            mam_id = (user_input.get(CONF_MAM_ID) or "").strip()
            username = (user_input.get(CONF_USERNAME) or "").strip()
            password = (user_input.get(CONF_PASSWORD) or "")

            # User ID and mam_id are required (for stats) and must be entered manually.
            if not user_id or not mam_id:
                errors["base"] = "missing_credentials"
            elif not _validate_user_id(user_id):
                errors["base"] = "invalid_user_id"
            else:
                ok, err = await _test_mam_connection(
                    self.hass, DEFAULT_BASE_URL, user_id, mam_id
                )
                if not ok:
                    errors["base"] = err or "cannot_connect"
                else:
                    # If username/password also provided, verify login before saving
                    if username and password:
                        _, login_err = await _login_mam(
                            self.hass, DEFAULT_BASE_URL, username, password
                        )
                        if login_err:
                            errors["base"] = login_err
                        if errors:
                            return self.async_show_form(
                                step_id="user", data_schema=schema, errors=errors
                            )
                    entry_data = {
                        CONF_BASE_URL: DEFAULT_BASE_URL,
                        CONF_USER_ID: user_id,
                        CONF_MAM_ID: mam_id,
                    }
                    if username and password:
                        entry_data[CONF_USERNAME] = username
                        entry_data[CONF_PASSWORD] = password
                    return self.async_create_entry(
                        title=user_id or "MAM",
                        data=entry_data,
                        options={
                            CONF_AUTO_BUY_CREDIT: DEFAULT_AUTO_BUY_CREDIT,
                            CONF_AUTO_DONATE_VAULT: DEFAULT_AUTO_DONATE_VAULT,
                            CONF_AUTO_BUY_VIP: DEFAULT_AUTO_BUY_VIP,
                        },
                    )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class MAMManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle MAM Manager options: credentials and daily automations."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options: credentials (user ID, cookie, or username/password) and daily automations."""
        entry_data = self._config_entry.data or {}
        opts = self._config_entry.options or entry_data
        errors: dict[str, str] = {}

        if user_input is not None:
            user_id = (user_input.get(CONF_USER_ID) or "").strip()
            mam_id = (user_input.get(CONF_MAM_ID) or "").strip()
            username = (user_input.get(CONF_USERNAME) or "").strip()
            password_input = user_input.get(CONF_PASSWORD) or ""
            current_user_id = (entry_data.get(CONF_USER_ID) or "").strip()
            current_mam_id = (entry_data.get(CONF_MAM_ID) or "").strip()
            current_password = entry_data.get(CONF_PASSWORD) or ""
            # Leave password unchanged if user left the placeholder (masked) or blank
            password_unchanged = (
                password_input in ("", "********", "••••••••")
                or (current_password and password_input == current_password[:5] + "****")
            )
            new_password = current_password if password_unchanged else password_input
            entry_updated = False

            # If user pasted a new cookie (mam_id), use it first so they can set/restore session
            use_user_id = (user_id or current_user_id).strip()
            if (user_id != current_user_id or mam_id != current_mam_id) and mam_id and _validate_user_id(use_user_id):
                ok, err = await _test_mam_connection(
                    self.hass, DEFAULT_BASE_URL, use_user_id, mam_id
                )
                if not ok:
                    errors["base"] = err or "cannot_connect"
                else:
                    update = {**entry_data, CONF_USER_ID: use_user_id, CONF_MAM_ID: mam_id}
                    # Keep both: mam_id and username/password (from form or existing)
                    if username:
                        update[CONF_USERNAME] = username
                        update[CONF_PASSWORD] = new_password or entry_data.get(CONF_PASSWORD, "")
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=update
                    )
                    entry_updated = True
            elif username and (new_password or current_password):
                # Save username/password only; preserve mam_id so both are used (mam_id for API/VIP/credit, username/pass for donate)
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={
                        **entry_data,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: new_password,
                    },
                )
                entry_updated = True
            elif mam_id != current_mam_id:
                # They changed mam_id but validation failed above (e.g. empty or bad user_id)
                if not _validate_user_id(user_id):
                    errors["base"] = "invalid_user_id"
                elif not mam_id:
                    errors["base"] = "cannot_connect"

            if not errors:
                # Refresh coordinator so sensors and dashboard update when config was changed
                if entry_updated:
                    coordinator = self.hass.data.get(DOMAIN, {}).get(
                        self._config_entry.entry_id, {}
                    ).get("coordinator")
                    if coordinator:
                        await coordinator.async_request_refresh()
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_AUTO_BUY_CREDIT: user_input.get(
                            CONF_AUTO_BUY_CREDIT, DEFAULT_AUTO_BUY_CREDIT
                        ),
                        CONF_AUTO_DONATE_VAULT: user_input.get(
                            CONF_AUTO_DONATE_VAULT, DEFAULT_AUTO_DONATE_VAULT
                        ),
                        CONF_AUTO_BUY_VIP: user_input.get(
                            CONF_AUTO_BUY_VIP, DEFAULT_AUTO_BUY_VIP
                        ),
                    },
                )

        stored_password = entry_data.get(CONF_PASSWORD) or ""
        password_preview = (stored_password[:5] + "****") if stored_password else ""

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USER_ID,
                    default=entry_data.get(CONF_USER_ID, ""),
                ): str,
                vol.Optional(
                    CONF_MAM_ID,
                    default=entry_data.get(CONF_MAM_ID, ""),
                ): str,
                vol.Optional(
                    CONF_USERNAME,
                    default=entry_data.get(CONF_USERNAME, ""),
                ): str,
                vol.Optional(
                    CONF_PASSWORD,
                    default="********" if stored_password else "",
                ): str,
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
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"password_preview": password_preview or "(not set)"},
        )
