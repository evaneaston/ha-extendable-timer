"""Sensor platform — remaining time entity for an extendable_timer instance."""

from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .controller import ExtendableTimerController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the remaining-time sensor for a config entry."""
    controller: ExtendableTimerController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ExtendableTimerRemainingSensor(controller)])


def _format_remaining(seconds: int) -> str:
    if seconds <= 0:
        return "idle"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class ExtendableTimerRemainingSensor(SensorEntity):  # type: ignore[misc]  # HA SensorEntity is Any without stubs
    """Sensor reporting remaining time until the timer expires."""

    _attr_should_poll = False
    _attr_icon = "mdi:timer-outline"

    def __init__(self, controller: ExtendableTimerController) -> None:
        """Initialise the sensor with its controller."""
        self._controller = controller
        self._attr_unique_id = f"{controller.entry.entry_id}_remaining"
        self._attr_name = f"{controller.name} remaining"
        self._unsub_dispatcher = None
        self._unsub_tick = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so entities group under one device card."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._controller.entry.entry_id)},
            name=self._controller.name,
            manufacturer="extendable_timer",
        )

    @property
    def native_value(self) -> str:
        """Return remaining time formatted as HH:MM:SS, or 'idle'."""
        return _format_remaining(self._controller.remaining_seconds)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return finishes_at, status, and remaining_seconds as attributes."""
        f = self._controller.finishes_at
        return {
            "finishes_at": f.isoformat() if f else None,
            "status": "active" if self._controller.is_active else "idle",
            "remaining_seconds": self._controller.remaining_seconds,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to dispatcher and start 1-second tick on HA add."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self._controller.signal, self._handle_change
        )
        self._unsub_tick = async_track_time_interval(
            self.hass, self._tick, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe dispatcher and tick on HA remove."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
        if self._unsub_tick:
            self._unsub_tick()

    @callback  # type: ignore[untyped-decorator]  # HA's @callback is untyped when stubs are absent
    def _handle_change(self) -> None:
        self.async_write_ha_state()

    @callback  # type: ignore[untyped-decorator]  # HA's @callback is untyped when stubs are absent
    def _tick(self, _now: datetime) -> None:
        if self._controller.is_active or self._controller.remaining_seconds > 0:
            self.async_write_ha_state()
