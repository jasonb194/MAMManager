"""Register MAM Manager Lovelace dashboard (user info, donated today, automation options)."""

from __future__ import annotations

import logging
from typing import Any

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


async def ensure_dashboard(hass: HomeAssistant, entry_id: str | None = None) -> None:
    """Create or ensure the MAM Manager dashboard exists."""
    dashboards_store = Store(hass, LOVELACE_DASHBOARDS_VERSION, LOVELACE_DASHBOARDS_KEY)
    data = await dashboards_store.async_load() or {}
    items = list(data.get("items") or [])

    if not any(
        item.get("id") == DASHBOARD_URL_PATH or item.get("url_path") == DASHBOARD_URL_PATH
        for item in items
    ):
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

    ent_reg = er.async_get(hass)
    status_entity_id = None
    for config_entry in hass.config_entries.async_entries("mam_manager"):
        for reg_entry in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
            if reg_entry.unique_id and str(reg_entry.unique_id).endswith("_mam_status"):
                status_entity_id = reg_entry.entity_id
                break
        if status_entity_id:
            break

    integrations_path = "/config/integrations"
    config_markdown = (
        f"**Configure:** [Settings → Devices & services]({integrations_path}) → **MAM Manager** → **Configure**. "
        "Enable *Auto buy credit* and/or *Auto donate to vault* and add API paths when you have them."
    )

    cards: list[dict[str, Any]] = [
        {"type": "markdown", "content": config_markdown, "title": "Configuration"},
    ]

    if status_entity_id:
        state = hass.states.get(status_entity_id)
        attrs = (state.attributes or {}) if state else {}
        donated_today = attrs.get("donated_today", False)
        cards.append({
            "type": "entities",
            "title": "Today",
            "entities": [
                {
                    "type": "attribute",
                    "entity": status_entity_id,
                    "attribute": "donated_today",
                    "name": "Donated today",
                    "icon": "mdi:heart" if donated_today else "mdi:heart-outline",
                },
                {"entity": status_entity_id},
            ],
        })
        cards.append({
            "type": "entities",
            "title": "User info",
            "entities": [
                {"type": "attribute", "entity": status_entity_id, "attribute": "classname", "name": "Class"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "country_name", "name": "Country"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "uploaded", "name": "Uploaded"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "downloaded", "name": "Downloaded"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "ratio", "name": "Ratio"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "seedbonus", "name": "Seedbonus"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "wedges", "name": "Wedges"},
            ],
        })
        cards.append({
            "type": "entities",
            "title": "Notifications",
            "entities": [
                {"type": "attribute", "entity": status_entity_id, "attribute": "notifs_pms", "name": "PMs"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "notifs_tickets", "name": "Tickets"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "notifs_requests", "name": "Requests"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "notifs_topics", "name": "Topics"},
            ],
        })
        cards.append({
            "type": "entities",
            "title": "Daily automations",
            "entities": [
                {"type": "attribute", "entity": status_entity_id, "attribute": "auto_buy_credit", "name": "Auto buy credit (once per day)"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "auto_donate_vault", "name": "Auto donate to vault (once per day)"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "auto_buy_vip", "name": "Auto buy VIP (once per day)"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "auto_buy_vip_eligible", "name": "Auto buy VIP eligible (VIP or Power user)"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "last_buy_credit_date", "name": "Last buy credit date"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "last_donate_date", "name": "Last donate date"},
                {"type": "attribute", "entity": status_entity_id, "attribute": "last_buy_vip_date", "name": "Last buy VIP date"},
            ],
        })
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
