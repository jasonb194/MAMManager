"""MAM Manager switches: toggle auto buy credit, auto donate vault, auto buy VIP."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ALLOWED_CLASSNAMES_FOR_AUTO_VIP,
    CONF_AUTO_BUY_CREDIT,
    CONF_AUTO_BUY_VIP,
    CONF_AUTO_DONATE_VAULT,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MAM Manager switches."""
    domain_data = hass.data.get(DOMAIN) or {}
    entry_data = domain_data.get(entry.entry_id) or {}
    coordinator = entry_data.get("coordinator")

    entities: list[MAMManagerSwitch | MAMManagerVIPSwitch] = [
        MAMManagerSwitch(entry, CONF_AUTO_BUY_CREDIT, "Auto buy credit", "credit"),
        MAMManagerSwitch(entry, CONF_AUTO_DONATE_VAULT, "Auto donate to vault", "vault"),
    ]
    if coordinator is not None:
        entities.append(MAMManagerVIPSwitch(entry, coordinator))
    else:
        entities.append(MAMManagerSwitch(entry, CONF_AUTO_BUY_VIP, "Auto buy VIP", "vip"))
    async_add_entities(entities)


class MAMManagerSwitch(SwitchEntity):
    """Switch that toggles a config entry option."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        option_key: str,
        name: str,
        slug: str,
    ) -> None:
        self._entry = entry
        self._option_key = option_key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{slug}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "MAM Manager",
            "manufacturer": "MyAnonamouse",
        }

    @property
    def is_on(self) -> bool:
        opts = self._entry.options or self._entry.data or {}
        return bool(opts.get(self._option_key, False))

    async def async_turn_on(self, **kwargs) -> None:
        opts = dict(self._entry.options or self._entry.data or {})
        opts[self._option_key] = True
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        opts = dict(self._entry.options or self._entry.data or {})
        opts[self._option_key] = False
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()


class MAMManagerVIPSwitch(MAMManagerSwitch):
    """Auto buy VIP switch; hidden (unavailable) when user class is not VIP or Power user."""

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(entry, CONF_AUTO_BUY_VIP, "Auto buy VIP", "vip")
        self._coordinator = coordinator

    @property
    def available(self) -> bool:
        data = self._coordinator.data or {}
        user = data.get("user_data") or {}
        classname = ((user.get("classname") or "").strip()).lower()
        return classname in ALLOWED_CLASSNAMES_FOR_AUTO_VIP

    async def async_added_to_hass(self) -> None:
        """Update availability when coordinator refreshes."""
        self._remove_listener = self._coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        remove = getattr(self, "_remove_listener", None)
        if callable(remove):
            remove()
            self._remove_listener = None

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
