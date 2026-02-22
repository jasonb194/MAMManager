"""MAM Manager switches: toggle auto buy credit, auto donate vault, auto buy VIP."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
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
    async_add_entities([
        MAMManagerSwitch(entry, CONF_AUTO_BUY_CREDIT, "Auto buy credit", "credit"),
        MAMManagerSwitch(entry, CONF_AUTO_DONATE_VAULT, "Auto donate to vault", "vault"),
        MAMManagerSwitch(entry, CONF_AUTO_BUY_VIP, "Auto buy VIP", "vip"),
    ])


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
