"""Config flow for extendable_timer."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_EXTEND_DURATION,
    CONF_EXTEND_SECONDS,
    CONF_NAME,
    CONF_STALE_THRESHOLD_MINUTES,
    DEFAULT_EXTEND_SECONDS,
    DEFAULT_STALE_THRESHOLD_MINUTES,
    DOMAIN,
    MAX_EXTEND_SECONDS,
    MAX_STALE_THRESHOLD_MINUTES,
    MIN_EXTEND_SECONDS,
    MIN_STALE_THRESHOLD_MINUTES,
)


def _seconds_to_duration_dict(seconds: int) -> dict[str, int]:
    """Split a total-seconds count into a duration dict.

    Returns the ``{hours, minutes, seconds}`` mapping that DurationSelector
    expects as its default value.
    """
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return {"hours": h, "minutes": m, "seconds": s}


def _duration_dict_to_seconds(value: Any) -> int:
    """Coerce a DurationSelector value to total seconds.

    HA's DurationSelector returns either a `{hours, minutes, seconds}` dict
    or a `timedelta` depending on configuration; both convert cleanly.
    """
    if hasattr(value, "total_seconds"):
        return int(value.total_seconds())
    return (
        int(value.get("hours", 0)) * 3600
        + int(value.get("minutes", 0)) * 60
        + int(value.get("seconds", 0))
    )


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    seconds_default = d.get(CONF_EXTEND_SECONDS, DEFAULT_EXTEND_SECONDS)
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
            vol.Required(
                CONF_EXTEND_DURATION,
                default=_seconds_to_duration_dict(seconds_default),
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=False)
            ),
            vol.Required(
                CONF_STALE_THRESHOLD_MINUTES,
                default=d.get(
                    CONF_STALE_THRESHOLD_MINUTES, DEFAULT_STALE_THRESHOLD_MINUTES
                ),
            ): vol.All(
                int,
                vol.Range(
                    min=MIN_STALE_THRESHOLD_MINUTES, max=MAX_STALE_THRESHOLD_MINUTES
                ),
            ),
        }
    )


def _options_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_EXTEND_DURATION,
                default=_seconds_to_duration_dict(
                    current.get(CONF_EXTEND_SECONDS, DEFAULT_EXTEND_SECONDS)
                ),
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=False)
            ),
            vol.Required(
                CONF_STALE_THRESHOLD_MINUTES,
                default=current.get(
                    CONF_STALE_THRESHOLD_MINUTES, DEFAULT_STALE_THRESHOLD_MINUTES
                ),
            ): vol.All(
                int,
                vol.Range(
                    min=MIN_STALE_THRESHOLD_MINUTES, max=MAX_STALE_THRESHOLD_MINUTES
                ),
            ),
        }
    )


def _validate_extend_seconds(form_input: dict[str, Any]) -> tuple[int, dict[str, str]]:
    """Convert the form's duration field to integer seconds + return errors dict."""
    errors: dict[str, str] = {}
    seconds = _duration_dict_to_seconds(form_input.get(CONF_EXTEND_DURATION, {}))
    if seconds < MIN_EXTEND_SECONDS or seconds > MAX_EXTEND_SECONDS:
        errors[CONF_EXTEND_DURATION] = "extend_duration_out_of_range"
    return seconds, errors


class ExtendableTimerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg, misc]  # HA ConfigFlow uses metaclass magic mypy can't see without stubs
    """Initial setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user-configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            extend_seconds, range_errors = _validate_extend_seconds(user_input)
            errors.update(range_errors)
            if not name:
                errors[CONF_NAME] = "name_required"

            if not errors:
                await self.async_set_unique_id(f"{DOMAIN}_{name.lower()}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={CONF_NAME: name},
                    options={
                        CONF_EXTEND_SECONDS: extend_seconds,
                        CONF_STALE_THRESHOLD_MINUTES: user_input[
                            CONF_STALE_THRESHOLD_MINUTES
                        ],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input), errors=errors
        )

    @staticmethod
    @callback  # type: ignore[untyped-decorator]  # HA's @callback is untyped when stubs are absent
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler for this integration."""
        return ExtendableTimerOptionsFlow()


class ExtendableTimerOptionsFlow(config_entries.OptionsFlow):  # type: ignore[misc]  # HA OptionsFlow is Any without stubs
    """Edit extend duration and stale-threshold after creation.

    HA injects `self.config_entry` automatically; do not set it in __init__
    (raises AttributeError on modern HA — the property has no setter).
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options flow step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            extend_seconds, range_errors = _validate_extend_seconds(user_input)
            errors.update(range_errors)
            if not errors:
                new_options = dict(self.config_entry.options)
                new_options[CONF_EXTEND_SECONDS] = extend_seconds
                new_options[CONF_STALE_THRESHOLD_MINUTES] = user_input[
                    CONF_STALE_THRESHOLD_MINUTES
                ]
                return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.config_entry.options),
            errors=errors,
        )
