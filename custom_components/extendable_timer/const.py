"""Constants for the extendable_timer integration."""

DOMAIN = "extendable_timer"

# Bus events fired by the controller at each state transition. All
# carry `instance_name` and `config_entry_id` so device-trigger handlers
# can filter to a specific timer. Discrete events (rather than one
# composite "state changed" event with a `kind` field) so each
# transition shows up as its own selectable trigger in the automation
# editor without YAML data filtering.
#
# - STARTED:  idle -> running   (Extend pressed while idle or after expiry).
#             Carries `finishes_at`.
# - EXTENDED: running -> running with finishes_at pushed out
#             (Extend pressed while already counting).
#             Carries `previous_finishes_at`, `finishes_at`, `extend_seconds`.
# - CANCELED: running -> idle   (Cancel pressed before zero).
#             Carries `previous_finishes_at`, `remaining_seconds` (the time
#             left at the moment of cancel).
# - FINISHED: running -> idle   (timer reached zero, including the
#             restart-recovery path).
#             Carries `was_stale`, `staleness_seconds`.
EVENT_STARTED = "extendable_timer_started"
EVENT_EXTENDED = "extendable_timer_extended"
EVENT_CANCELED = "extendable_timer_canceled"
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
