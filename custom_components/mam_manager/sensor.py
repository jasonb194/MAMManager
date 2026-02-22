"""MAM Manager sensor: user info and donated-today status."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
    CONF_AUTO_BUY_CREDIT,
    CONF_AUTO_BUY_VIP,
    CONF_AUTO_DONATE_VAULT,
    DOMAIN,
    STORAGE_LAST_DONATE_DATE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MAM Manager sensor."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data:
        return
    coordinator = data.get("coordinator")
    if not coordinator:
        return
    async_add_entities([MAMManagerSensor(entry, coordinator)])


class MAMManagerSensor(CoordinatorEntity, SensorEntity):
    """Sensor exposing MAM user data and donated-today status."""

    _attr_has_entity_name = True
    _attr_name = "MAM status"

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mam_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "MAM Manager",
            "manufacturer": "MyAnonamouse",
        }

    @property
    def coordinator_data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def native_value(self) -> str:
        """Primary value: username or 'Unknown'."""
        user = self.coordinator_data.get("user_data") or {}
        return (user.get("username") or "Unknown").strip()

    @property
    def extra_state_attributes(self) -> dict:
        user = self.coordinator_data.get("user_data") or {}
        last_donate = self.coordinator_data.get("last_donate_date")
        last_buy = self.coordinator_data.get("last_buy_credit_date")
        last_buy_vip = self.coordinator_data.get("last_buy_vip_date")
        today = date.today().isoformat()
        options = self._entry.options or self._entry.data or {}
        notifs = user.get("notifs") or {}
        return {
            "classname": user.get("classname"),
            "country_code": user.get("country_code"),
            "country_name": user.get("country_name"),
            "downloaded": user.get("downloaded"),
            "downloaded_bytes": user.get("downloaded_bytes"),
            "ratio": user.get("ratio"),
            "seedbonus": user.get("seedbonus"),
            "uid": user.get("uid"),
            "uploaded": user.get("uploaded"),
            "uploaded_bytes": user.get("uploaded_bytes"),
            "username": user.get("username"),
            "wedges": user.get("wedges"),
            "notifs_pms": notifs.get("pms"),
            "notifs_about_to_drop_client": notifs.get("aboutToDropClient"),
            "notifs_tickets": notifs.get("tickets"),
            "notifs_waiting_tickets": notifs.get("waiting_tickets"),
            "notifs_requests": notifs.get("requests"),
            "notifs_topics": notifs.get("topics"),
            "donated_today": last_donate == today,
            "last_donate_date": last_donate,
            "last_buy_credit_date": last_buy,
            "last_buy_vip_date": last_buy_vip,
            "auto_buy_credit": options.get(CONF_AUTO_BUY_CREDIT, False),
            "auto_donate_vault": options.get(CONF_AUTO_DONATE_VAULT, False),
            "auto_buy_vip": options.get(CONF_AUTO_BUY_VIP, False),
            "auto_buy_vip_eligible": (user.get("classname") or "").strip().lower() in ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
        }
