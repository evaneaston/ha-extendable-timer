"""Extendable Timer integration."""

import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, PLATFORMS, SIGNAL_STATE_CHANGED
from .controller import ExtendableTimerController, build_store

_LOGGER = logging.getLogger(__name__)

CARD_URL = "/extendable_timer_static/extendable-timer-card.js"
CARD_FILE = "custom_components/extendable_timer/www/extendable-timer-card.js"
LOVELACE_DOMAIN = "lovelace"


async def _async_register_static_path_once(hass: HomeAssistant) -> None:
    """Register the Lovelace card's static path so HA serves the JS file.

    Idempotent across config entries: only the first call per HA process
    actually registers; subsequent calls are no-ops. The flag is set
    *before* the await so concurrent setup_entry calls don't both pass
    the guard.

    The path is registered separately from the *loading* mechanism
    (Lovelace resource preferred, add_extra_js_url fallback) handled by
    `_async_ensure_card_loadable`. Splitting concerns keeps the
    HTTP-route registration idempotent in one place.
    """
    if hass.data[DOMAIN].get("_card_static_path_registered"):
        return
    hass.data[DOMAIN]["_card_static_path_registered"] = True
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_URL,
                hass.config.path(CARD_FILE),
                cache_headers=False,
            )
        ]
    )


async def _async_register_lovelace_resource(hass: HomeAssistant) -> bool:
    """Register the card as a Lovelace resource so lovelace awaits its load.

    Avoids the customElements race window that `add_extra_js_url`'s async
    dynamic import leaves open.

    Returns True on success or already-registered. Returns False when
    not applicable (YAML-mode lovelace, lovelace not loaded yet, or any
    error — the integration falls back to `add_extra_js_url`).
    """
    if hass.data[DOMAIN].get("_card_resource_registered"):
        return True

    lovelace = hass.data.get(LOVELACE_DOMAIN)
    resources = getattr(lovelace, "resources", None)
    if resources is None or not hasattr(resources, "async_create_item"):
        # Either lovelace not yet ready, or YAML-mode lovelace which uses
        # a read-only resource collection. Caller will fall back.
        return False

    if not getattr(resources, "loaded", True):
        try:
            await resources.async_load()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("lovelace resources async_load failed: %s", err)
            return False

    try:
        for item in resources.async_items():
            if item.get("url") == CARD_URL:
                hass.data[DOMAIN]["_card_resource_registered"] = True
                return True
        await resources.async_create_item({"url": CARD_URL, "res_type": "module"})
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("lovelace resource registration failed: %s", err)
        return False

    hass.data[DOMAIN]["_card_resource_registered"] = True
    _LOGGER.info("Registered Lovelace resource %s for extendable_timer card", CARD_URL)
    return True


async def _async_ensure_card_loadable(hass: HomeAssistant) -> None:
    """Prefer Lovelace resources; fall back to add_extra_js_url for YAML-mode users.

    Best-effort. If lovelace isn't ready yet at setup time, retry once HA
    finishes starting.
    """
    if await _async_register_lovelace_resource(hass):
        return

    # Always set up the add_extra_js_url fallback so YAML-mode users and
    # any startup-order edge case get the script loaded somehow.
    if not hass.data[DOMAIN].get("_card_extra_js_registered"):
        add_extra_js_url(hass, CARD_URL)
        hass.data[DOMAIN]["_card_extra_js_registered"] = True

    if hass.data[DOMAIN].get("_card_resource_registered"):
        return

    if hass.is_running:
        # HA already started but lovelace resources still unavailable; we've
        # done our best with add_extra_js_url. Nothing more to do.
        return

    async def _retry_after_started(_event: Event) -> None:
        await _async_register_lovelace_resource(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _retry_after_started)


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nudge entities to re-publish state on any entry write (data or options).

    Re-publishes via the controller's dispatcher signal so that attribute
    getters like ExtendButton.extra_state_attributes re-read from current
    options after an OptionsFlow save.

    Safe against reload loops: this listener does NOT write back to the
    entry; it only fans out a dispatcher signal.
    """
    async_dispatcher_send(hass, SIGNAL_STATE_CHANGED.format(entry_id=entry.entry_id))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Extendable Timer from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_static_path_once(hass)
    await _async_ensure_card_loadable(hass)
    controller = ExtendableTimerController(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = controller
    await controller.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller: ExtendableTimerController | None = hass.data[DOMAIN].get(entry.entry_id)
    unloaded: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        if controller:
            await controller.async_unload()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the per-entry Store file when the entry is removed."""
    await build_store(hass, entry.entry_id).async_remove()
