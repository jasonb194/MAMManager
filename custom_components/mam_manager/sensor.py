"""MAM Manager sensors: user info, stats, and donated-today status."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
    CONF_MAM_ID,
    CONF_USER_ID,
    DOMAIN,
)


def _device_info(entry: ConfigEntry) -> dict:
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "MAM Manager",
        "manufacturer": "MyAnonamouse",
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MAM Manager sensors."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data:
        return
    coordinator = data.get("coordinator")
    if not coordinator:
        return

    entities: list[SensorEntity] = [
        MAMManagerStatusSensor(entry, coordinator),
        MAMManagerUserIDSensor(entry),
        MAMManagerMamIdPreviewSensor(entry, coordinator),
        MAMManagerStatSensor(entry, coordinator, "classname", "Class", "classname"),
        MAMManagerStatSensor(entry, coordinator, "uploaded", "Uploaded", "uploaded"),
        MAMManagerStatSensor(entry, coordinator, "downloaded", "Downloaded", "downloaded"),
        MAMManagerStatSensor(entry, coordinator, "ratio", "Ratio", "ratio"),
        MAMManagerStatSensor(entry, coordinator, "seedbonus", "Seedbonus", "seedbonus"),
        MAMManagerStatSensor(entry, coordinator, "wedges", "Wedges", "wedges"),
        MAMManagerDonatedTodaySensor(entry, coordinator),
        MAMManagerVIPEligibleSensor(entry, coordinator),
        MAMManagerLastRunSensor(entry, coordinator, "last_buy_credit_date", "Last buy credit date", "last_buy_credit"),
        MAMManagerLastRunSensor(entry, coordinator, "last_donate_date", "Last donate date", "last_donate"),
        MAMManagerLastRunSensor(entry, coordinator, "last_buy_vip_date", "Last buy VIP date", "last_buy_vip"),
    ]
    async_add_entities(entities)


class MAMManagerStatusSensor(CoordinatorEntity, SensorEntity):
    """Main status sensor: username as value, full attributes for dashboard."""

    _attr_has_entity_name = True
    _attr_name = "Username"

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mam_status"
        self._attr_device_info = _device_info(entry)

    @property
    def coordinator_data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def native_value(self) -> str:
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
            "country_code": user.get("country_code"),
            "country_name": user.get("country_name"),
            "downloaded_bytes": user.get("downloaded_bytes"),
            "uploaded_bytes": user.get("uploaded_bytes"),
            "uid": user.get("uid"),
            "notifs_pms": notifs.get("pms"),
            "notifs_about_to_drop_client": notifs.get("aboutToDropClient"),
            "notifs_tickets": notifs.get("tickets"),
            "notifs_waiting_tickets": notifs.get("waiting_tickets"),
            "notifs_requests": notifs.get("requests"),
            "notifs_topics": notifs.get("topics"),
            "last_donate_date": last_donate,
            "last_buy_credit_date": last_buy,
            "last_buy_vip_date": last_buy_vip,
            "auto_buy_vip_eligible": (user.get("classname") or "").strip().lower() in ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
        }


class MAMManagerUserIDSensor(SensorEntity):
    """User ID from config (always available)."""

    _attr_has_entity_name = True
    _attr_name = "User ID"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_user_id"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str:
        return str((self._entry.data or {}).get(CONF_USER_ID, ""))


class MAMManagerMamIdPreviewSensor(CoordinatorEntity, SensorEntity):
    """First 10 characters of mam_id (session cookie) for identification only."""

    _attr_has_entity_name = True
    _attr_name = "MAM ID (first 10 chars)"

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mam_id_preview"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str:
        mam_id = (self._entry.data or {}).get(CONF_MAM_ID) or ""
        if not mam_id:
            return "Not set"
        return mam_id[:10]


class MAMManagerStatSensor(CoordinatorEntity, SensorEntity):
    """Single stat from user_data (class, uploaded, downloaded, ratio, seedbonus, wedges)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        key: str,
        name: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = _device_info(entry)

    @property
    def coordinator_data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def native_value(self) -> str | int | float | None:
        user = self.coordinator_data.get("user_data") or {}
        val = user.get(self._key)
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return val
        return str(val)


class MAMManagerDonatedTodaySensor(CoordinatorEntity, SensorEntity):
    """Whether user has donated today."""

    _attr_has_entity_name = True
    _attr_name = "Donated today"

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_donated_today"
        self._attr_device_info = _device_info(entry)

    @property
    def coordinator_data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def native_value(self) -> str:
        last_donate = self.coordinator_data.get("last_donate_date")
        today = date.today().isoformat()
        return "Yes" if last_donate == today else "No"

    @property
    def extra_state_attributes(self) -> dict:
        return {"last_donate_date": self.coordinator_data.get("last_donate_date")}


class MAMManagerVIPEligibleSensor(CoordinatorEntity, SensorEntity):
    """Whether user class allows auto buy VIP (VIP or Power user)."""

    _attr_has_entity_name = True
    _attr_name = "Auto buy VIP eligible"

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_vip_eligible"
        self._attr_device_info = _device_info(entry)

    @property
    def coordinator_data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def native_value(self) -> str:
        user = self.coordinator_data.get("user_data") or {}
        classname = ((user.get("classname") or "").strip()).lower()
        return "Yes" if classname in ALLOWED_CLASSNAMES_FOR_AUTO_VIP else "No"


class MAMManagerLastRunSensor(CoordinatorEntity, SensorEntity):
    """Last run date for an automation (buy credit, donate, buy VIP)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        key: str,
        name: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = _device_info(entry)

    @property
    def coordinator_data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def native_value(self) -> str | None:
        return self.coordinator_data.get(self._key)
