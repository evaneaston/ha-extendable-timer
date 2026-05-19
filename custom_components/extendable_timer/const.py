"""Constants for the extendable_timer integration."""

DOMAIN = "extendable_timer"

# Event fired when the timer reaches zero. Always fires once per scheduled
# expiry, including the restart-recovery path. Carries `was_stale` and
# `staleness_seconds` so non-idempotent automations can gate via condition.
EVENT_FINISHED = "extendable_timer_finished"

# Config flow / options keys.
CONF_NAME = "name"
CONF_EXTEND_DURATION = "extend_duration"  # form-level key (DurationSelector dict)
CONF_EXTEND_SECONDS = "extend_seconds"  # storage-level key (int seconds)
CONF_SCRIPT_ENTITY = "script_entity"  # legacy storage-only key, no UI input
CONF_STALE_THRESHOLD_MINUTES = "stale_threshold_minutes"

DEFAULT_EXTEND_SECONDS = 15 * 60  # 15 minutes
DEFAULT_STALE_THRESHOLD_MINUTES = 60

MIN_EXTEND_SECONDS = 1
MAX_EXTEND_SECONDS = 24 * 3600  # 1 day
MIN_STALE_THRESHOLD_MINUTES = 0
MAX_STALE_THRESHOLD_MINUTES = 10080  # one week

# Platforms this integration provides.
PLATFORMS: list[str] = ["sensor", "button"]

# Dispatcher signal name used by entities to refresh from controller state.
SIGNAL_STATE_CHANGED = "extendable_timer_state_changed_{entry_id}"
