"""Button platform — extend and cancel buttons for an extendable_timer instance."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import ExtendableTimerController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Extend and Cancel buttons for a config entry."""
    controller: ExtendableTimerController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ExtendButton(controller),
            CancelButton(controller),
        ]
    )


class _BaseButton(ButtonEntity):  # type: ignore[misc]  # HA ButtonEntity is Any without stubs
    _attr_should_poll = False

    def __init__(
        self, controller: ExtendableTimerController, key: str, label: str, icon: str
    ) -> None:
        self._controller = controller
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_name = f"{controller.name} {label}"
        self._attr_icon = icon
        self._unsub = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._controller.entry.entry_id)},
            name=self._controller.name,
            manufacturer="extendable_timer",
        )

    async def async_added_to_hass(self) -> None:
        # Subscribe to the controller's state-changed signal so that
        # extra_state_attributes (e.g. extend_seconds on ExtendButton) is
        # re-published when the user changes options or extend/cancel.
        self._unsub = async_dispatcher_connect(
            self.hass, self._controller.signal, self._on_change
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    @callback  # type: ignore[untyped-decorator]  # HA's @callback is untyped when stubs are absent
    def _on_change(self) -> None:
        self.async_write_ha_state()


class ExtendButton(_BaseButton):
    """Button that extends the timer by the configured duration."""

    def __init__(self, controller: ExtendableTimerController) -> None:
        """Initialize the extend button."""
        super().__init__(controller, "extend", "extend", "mdi:plus-clock")

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extend_seconds so automations can read the configured step."""
        return {"extend_seconds": self._controller.extend_seconds}

    async def async_press(self) -> None:
        """Handle button press — extend the timer."""
        await self._controller.async_extend()


class CancelButton(_BaseButton):
    """Button that cancels the timer immediately."""

    def __init__(self, controller: ExtendableTimerController) -> None:
        """Initialize the cancel button."""
        super().__init__(controller, "cancel", "cancel", "mdi:cancel")

    async def async_press(self) -> None:
        """Handle button press — cancel the timer."""
        await self._controller.async_cancel()
