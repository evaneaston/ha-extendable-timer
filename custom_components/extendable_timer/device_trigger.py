"""Device-trigger platform — expose timer state-change events as triggers.

Buttons are exposed as device triggers automatically by HA's button
platform (those fire on the UI press, not the state change). The
controller's custom state-change events are not auto-exposed — this
module wires each one to a per-device trigger so users can pick
"Timer started" / "Timer extended" / "Timer canceled" / "Timer finished"
from the automation editor's trigger dropdown.
"""

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_CANCELED, EVENT_EXTENDED, EVENT_FINISHED, EVENT_STARTED

TRIGGER_STARTED = "started"
TRIGGER_EXTENDED = "extended"
TRIGGER_CANCELED = "canceled"
TRIGGER_FINISHED = "finished"

# Trigger type -> bus event the controller fires. Keys here drive both
# the automation-editor dropdown (via the device_automation.trigger_type
# translation strings) and the event-trigger wiring below.
TRIGGER_TYPE_TO_EVENT = {
    TRIGGER_STARTED: EVENT_STARTED,
    TRIGGER_EXTENDED: EVENT_EXTENDED,
    TRIGGER_CANCELED: EVENT_CANCELED,
    TRIGGER_FINISHED: EVENT_FINISHED,
}

TRIGGER_TYPES = set(TRIGGER_TYPE_TO_EVENT)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES)}
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return one device-trigger entry per supported trigger type."""
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGER_TYPE_TO_EVENT
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Translate a device-trigger config into an event trigger filtered on entry_id."""
    device = dr.async_get(hass).async_get(config[CONF_DEVICE_ID])
    entry_id = None
    if device:
        for e in device.config_entries:
            if hass.config_entries.async_get_entry(e):
                entry_id = e
                break

    event_type = TRIGGER_TYPE_TO_EVENT[config[CONF_TYPE]]

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: event_type,
            event_trigger.CONF_EVENT_DATA: {"config_entry_id": entry_id},
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
