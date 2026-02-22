"""Register MAM Manager Lovelace dashboard (user info, donated today, automation options)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL_PATH = "mam-manager"
DASHBOARD_TITLE = "MAM Manager"
DASHBOARD_ICON = "mdi:mouse"
LOVELACE_DASHBOARDS_KEY = "lovelace_dashboards"
LOVELACE_DASHBOARDS_VERSION = 1
LOVELACE_CONFIG_KEY_TEMPLATE = "lovelace.{}"
LOVELACE_CONFIG_VERSION = 1


def _register_panel(hass: HomeAssistant) -> None:
    """Register the MAM Manager panel with the frontend so it appears in the sidebar."""
    try:
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            frontend_url_path=DASHBOARD_URL_PATH,
            sidebar_title=DASHBOARD_TITLE,
            sidebar_icon=DASHBOARD_ICON,
            require_admin=False,
            config={"mode": "storage"},
            update=False,
        )
        _LOGGER.debug("MAM Manager panel registered")
    except ValueError:
        pass  # Panel already registered


async def ensure_dashboard(hass: HomeAssistant, entry_id: str | None = None) -> None:
    """Create or ensure the MAM Manager dashboard exists."""
    dashboards_store = Store(hass, LOVELACE_DASHBOARDS_VERSION, LOVELACE_DASHBOARDS_KEY)
    data = await dashboards_store.async_load() or {}
    items = list(data.get("items") or [])

    dashboard_item = None
    for item in items:
        if item.get("id") == DASHBOARD_URL_PATH or item.get("url_path") == DASHBOARD_URL_PATH:
            dashboard_item = item
            break

    if dashboard_item is None:
        new_item = {
            "id": DASHBOARD_URL_PATH,
            "url_path": DASHBOARD_URL_PATH,
            "title": DASHBOARD_TITLE,
            "icon": DASHBOARD_ICON,
            "show_in_sidebar": True,
            "require_admin": False,
        }
        items.append(new_item)
        await dashboards_store.async_save({"items": items})
        dashboard_item = new_item

    # Register panel and add to Lovelace so it appears without restart
    try:
        from homeassistant.components.lovelace import dashboard as lovelace_dashboard

        lovelace_data = hass.data.get("lovelace")
        if lovelace_data and hasattr(lovelace_data, "dashboards"):
            if DASHBOARD_URL_PATH not in lovelace_data.dashboards:
                lovelace_data.dashboards[DASHBOARD_URL_PATH] = lovelace_dashboard.LovelaceStorage(
                    hass, dashboard_item
                )
            _register_panel(hass)
    except Exception as e:
        _LOGGER.debug("Could not register MAM Manager panel at runtime: %s", e)
        _register_panel(hass)

    ent_reg = er.async_get(hass)
    # Collect all entities for MAM Manager (sensors + switches) by unique_id suffix
    entity_ids: dict[str, str] = {}  # suffix -> entity_id
    for config_entry in hass.config_entries.async_entries("mam_manager"):
        for reg_entry in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
            if not reg_entry.entity_id or not reg_entry.unique_id:
                continue
            uid = str(reg_entry.unique_id)
            if uid.endswith("_mam_status"):
                entity_ids["status"] = reg_entry.entity_id
            elif uid.endswith("_user_id"):
                entity_ids["user_id"] = reg_entry.entity_id
            elif uid.endswith("_classname"):
                entity_ids["classname"] = reg_entry.entity_id
            elif uid.endswith("_uploaded"):
                entity_ids["uploaded"] = reg_entry.entity_id
            elif uid.endswith("_downloaded"):
                entity_ids["downloaded"] = reg_entry.entity_id
            elif uid.endswith("_ratio"):
                entity_ids["ratio"] = reg_entry.entity_id
            elif uid.endswith("_seedbonus"):
                entity_ids["seedbonus"] = reg_entry.entity_id
            elif uid.endswith("_wedges"):
                entity_ids["wedges"] = reg_entry.entity_id
            elif uid.endswith("_donated_today"):
                entity_ids["donated_today"] = reg_entry.entity_id
            elif uid.endswith("_vip_eligible"):
                entity_ids["vip_eligible"] = reg_entry.entity_id
            elif uid.endswith("_last_buy_credit"):
                entity_ids["last_buy_credit"] = reg_entry.entity_id
            elif uid.endswith("_last_donate"):
                entity_ids["last_donate"] = reg_entry.entity_id
            elif uid.endswith("_last_buy_vip"):
                entity_ids["last_buy_vip"] = reg_entry.entity_id
            elif uid.endswith("_credit"):
                entity_ids["switch_credit"] = reg_entry.entity_id
            elif uid.endswith("_vault"):
                entity_ids["switch_vault"] = reg_entry.entity_id
            elif uid.endswith("_vip"):
                entity_ids["switch_vip"] = reg_entry.entity_id
        break

    integrations_path = "/config/integrations"
    config_markdown = (
        f"**Configure:** [Settings → Devices & services]({integrations_path}) → **MAM Manager** → **Configure**. "
        "Toggle automations below or from the device card."
    )

    cards: list[dict[str, Any]] = [
        {"type": "markdown", "content": config_markdown, "title": "Configuration"},
    ]

    if entity_ids:
        user_order = ("status", "user_id", "donated_today", "classname", "uploaded", "downloaded", "ratio", "seedbonus", "wedges")
        user_entities = [entity_ids[k] for k in user_order if k in entity_ids]
        if user_entities:
            cards.append({"type": "entities", "title": "User & stats", "entities": [{"entity": e} for e in user_entities]})
        auto_order = ("switch_credit", "switch_vault", "switch_vip", "vip_eligible", "last_buy_credit", "last_donate", "last_buy_vip")
        automation_entities = [entity_ids[k] for k in auto_order if k in entity_ids]
        if automation_entities:
            cards.append({"type": "entities", "title": "Daily automations", "entities": [{"entity": e} for e in automation_entities]})
    else:
        cards.append({
            "type": "markdown",
            "content": "Add MAM Manager in **Settings → Devices & services** to see user info and options here.",
            "title": "No integration",
        })

    view_config: dict[str, Any] = {
        "title": DASHBOARD_TITLE,
        "path": DASHBOARD_URL_PATH,
        "cards": cards,
    }
    dashboard_config = {"views": [view_config]}

    try:
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data and hasattr(lovelace_data, "dashboards"):
            dash = lovelace_data.dashboards.get(DASHBOARD_URL_PATH)
            if dash is not None and hasattr(dash, "async_save"):
                await dash.async_save(dashboard_config)
                _LOGGER.info(
                    "MAM Manager dashboard updated. Open from sidebar or /%s",
                    DASHBOARD_URL_PATH,
                )
                return
    except Exception as e:
        _LOGGER.debug("Could not update dashboard via Lovelace API: %s", e)

    config_store = Store(
        hass,
        LOVELACE_CONFIG_VERSION,
        LOVELACE_CONFIG_KEY_TEMPLATE.format(DASHBOARD_URL_PATH),
    )
    await config_store.async_save({"config": dashboard_config})
    try:
        hass.bus.async_fire("lovelace_updated", {"url_path": DASHBOARD_URL_PATH})
    except Exception:
        pass
    _LOGGER.info(
        "MAM Manager dashboard saved. Open from sidebar or /%s",
        DASHBOARD_URL_PATH,
    )
