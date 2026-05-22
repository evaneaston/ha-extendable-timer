"""ExtendableTimerController — durable state, scheduling, expiry firing."""

import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .const import (
    CONF_EXTEND_SECONDS,
    CONF_NAME,
    CONF_SCRIPT_ENTITY,
    CONF_STALE_THRESHOLD_MINUTES,
    DEFAULT_EXTEND_SECONDS,
    DEFAULT_STALE_THRESHOLD_MINUTES,
    EVENT_CANCELED,
    EVENT_EXTENDED,
    EVENT_FINISHED,
    EVENT_STARTED,
    SIGNAL_STATE_CHANGED,
)
from .logic import (
    StartupCase,
    classify_startup_state,
    compute_extended_finish,
    compute_remaining_seconds,
)

_LOGGER = logging.getLogger(__name__)

# Per-entry Store for the durable finishes_at. Lives at
# .storage/extendable_timer.<entry_id>. Per-entry rather than per-integration
# so writes are scoped to one tiny file (vs the shared core.config_entries
# file that would block the event loop on bursts) — see issue #5.
STORAGE_VERSION = 1
STORAGE_KEY_FORMAT = "extendable_timer.{entry_id}"
SAVE_DEBOUNCE_SECONDS = 1.0


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def build_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Construct the per-entry Store. Exposed for async_remove_entry."""
    return Store(hass, STORAGE_VERSION, STORAGE_KEY_FORMAT.format(entry_id=entry_id))


class ExtendableTimerController:
    """One controller per config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the controller — one instance per config entry."""
        self.hass = hass
        self.entry = entry
        self._unsub_callback: CALLBACK_TYPE | None = None
        self._store: Store[dict[str, Any]] = build_store(hass, entry.entry_id)
        # In-memory authoritative copy. Loaded from Store in async_setup.
        # Mutations go in-memory immediately; disk persistence is debounced
        # for extends and immediate for cancel/expiry-fire.
        self._finishes_at: datetime | None = None

    # --- Properties read by entity classes ---

    @property
    def name(self) -> str:
        """Return the user-configured timer name."""
        return str(self.entry.data[CONF_NAME])

    @property
    def signal(self) -> str:
        """Return the dispatcher signal string for this entry."""
        return SIGNAL_STATE_CHANGED.format(entry_id=self.entry.entry_id)

    @property
    def finishes_at(self) -> datetime | None:
        """Return the in-memory finish time, or None when idle."""
        return self._finishes_at

    @property
    def is_active(self) -> bool:
        """Return True when a finish time is set and still in the future."""
        f = self._finishes_at
        return f is not None and f > _utcnow()

    @property
    def remaining_seconds(self) -> int:
        """Return seconds remaining until expiry, clamped to zero when idle."""
        return compute_remaining_seconds(now=_utcnow(), finishes_at=self._finishes_at)

    @property
    def extend_seconds(self) -> int:
        """Return the configured extension step in seconds."""
        return int(self.entry.options.get(CONF_EXTEND_SECONDS, DEFAULT_EXTEND_SECONDS))

    @property
    def script_entity(self) -> str | None:
        """Return the script entity to call on expiry, or None if not configured."""
        v = self.entry.options.get(CONF_SCRIPT_ENTITY)
        return v or None

    @property
    def stale_threshold_seconds(self) -> int:
        """Return the stale-expiry threshold converted from minutes to seconds."""
        mins = int(
            self.entry.options.get(
                CONF_STALE_THRESHOLD_MINUTES, DEFAULT_STALE_THRESHOLD_MINUTES
            )
        )
        return mins * 60

    # --- Lifecycle ---

    async def async_setup(self) -> None:
        """Load durable state, run startup recovery, schedule or fire as needed."""
        await self._async_load_finishes_at()

        case, staleness = classify_startup_state(
            now=_utcnow(),
            persisted_finishes_at=self._finishes_at,
            stale_threshold_seconds=self.stale_threshold_seconds,
        )
        _LOGGER.info(
            "%s startup case=%s staleness=%ss", self.name, case.value, staleness
        )
        if case is StartupCase.IDLE:
            return
        if case is StartupCase.FUTURE:
            self._schedule_expiry()
            return
        if case is StartupCase.STALE_WITHIN_THRESHOLD:
            # Defer firing until HA is fully started. During boot, integration
            # setup runs in the same stage as automations and can complete
            # *before* automations subscribe their triggers — firing
            # EVENT_FINISHED here would land before the device-trigger
            # automation is listening (validated against #21 logs). When
            # HA is already running (mid-session reload), fire immediately.
            if self.hass.is_running:
                await self._fire_expiry(was_stale=True, staleness_seconds=staleness)
            else:
                self._defer_stale_fire(staleness)
            return
        # STALE_BEYOND_THRESHOLD
        _LOGGER.info(
            "%s skipping stale firing (staleness=%ss exceeds threshold=%ss)",
            self.name,
            staleness,
            self.stale_threshold_seconds,
        )
        await self._async_persist_immediate(None)

    async def async_unload(self) -> None:
        """Cancel pending callback and force-flush any debounced save."""
        self._cancel_scheduled()
        # Commit the in-memory state synchronously. If a debounced save was
        # pending, this cancels it and writes the final value.
        await self._store.async_save(self._serialize())

    # --- User actions ---

    async def async_extend(self) -> None:
        """Extend the timer by the configured duration and notify entities.

        Fires EVENT_STARTED if the timer was previously idle or expired, or
        EVENT_EXTENDED if it was already counting. The idle predicate
        matches compute_extended_finish (None or finish in the past) so the
        events stay consistent with the state machine.
        """
        now = _utcnow()
        previous = self._finishes_at
        was_idle = previous is None or previous < now
        new_finish = compute_extended_finish(
            now=now,
            current_finishes_at=previous,
            extend_seconds=self.extend_seconds,
        )
        # In-memory immediately so entities see new state right away;
        # disk write coalesces bursts into one flush after SAVE_DEBOUNCE_SECONDS.
        self._finishes_at = new_finish
        self._store.async_delay_save(self._serialize, SAVE_DEBOUNCE_SECONDS)
        self._cancel_scheduled()
        self._schedule_expiry()
        self._notify()

        common = {
            "instance_name": self.name,
            "config_entry_id": self.entry.entry_id,
            "finishes_at": new_finish.isoformat(),
        }
        if was_idle:
            self.hass.bus.async_fire(EVENT_STARTED, common)
        else:
            assert previous is not None  # was_idle False -> previous is in the future
            self.hass.bus.async_fire(
                EVENT_EXTENDED,
                {
                    **common,
                    "previous_finishes_at": previous.isoformat(),
                    "extend_seconds": self.extend_seconds,
                },
            )

    async def async_cancel(self) -> None:
        """Cancel the timer immediately and notify entities.

        Fires EVENT_CANCELED only when there was a running timer to cancel
        (was_active). Pressing Cancel while idle is a no-op event-wise so
        automations don't see spurious cancel events on idle button mashing.
        """
        now = _utcnow()
        previous = self._finishes_at
        was_active = previous is not None and previous > now
        remaining_at_cancel = compute_remaining_seconds(now=now, finishes_at=previous)
        await self._async_persist_immediate(None)
        self._cancel_scheduled()
        self._notify()

        if was_active:
            assert previous is not None  # was_active True -> previous is in the future
            self.hass.bus.async_fire(
                EVENT_CANCELED,
                {
                    "instance_name": self.name,
                    "config_entry_id": self.entry.entry_id,
                    "previous_finishes_at": previous.isoformat(),
                    "remaining_seconds": remaining_at_cancel,
                },
            )

    # --- Internal ---

    def _serialize(self) -> dict[str, Any]:
        """Return the current state as a serializable dict.

        Called by Store at flush time (for debounced saves) so the latest
        in-memory value is what gets written, regardless of when the save
        was scheduled.
        """
        return {
            "finishes_at": (
                self._finishes_at.isoformat() if self._finishes_at else None
            ),
        }

    async def _async_load_finishes_at(self) -> None:
        """Populate in-memory state from Store. Empty Store == idle."""
        loaded = await self._store.async_load()
        if loaded is None:
            return
        raw = loaded.get("finishes_at")
        self._finishes_at = datetime.fromisoformat(raw) if raw else None

    async def _async_persist_immediate(self, value: datetime | None) -> None:
        """Update in-memory state and force-write to Store now.

        Used for cancel and expiry-fire — paths where correctness depends on
        the new value being durable before the next observable side effect
        (e.g. EVENT_FINISHED). Cancels any pending debounced save.
        """
        self._finishes_at = value
        await self._store.async_save(self._serialize())

    def _cancel_scheduled(self) -> None:
        if self._unsub_callback is not None:
            self._unsub_callback()
            self._unsub_callback = None

    def _schedule_expiry(self) -> None:
        f = self._finishes_at
        if f is None:
            return
        delay = max(0.0, (f - _utcnow()).total_seconds())
        self._unsub_callback = async_call_later(
            self.hass, delay, self._on_scheduled_fire
        )

    def _defer_stale_fire(self, staleness_seconds: int) -> None:
        """Hook EVENT_HOMEASSISTANT_STARTED to fire the stale-expiry path.

        Used during HA boot when the integration sets up before automations
        have subscribed their triggers. By the time HOMEASSISTANT_STARTED
        fires, every automation's trigger is initialized, so the
        EVENT_FINISHED event reaches them.

        Cleaned up via entry.async_on_unload so a removed-during-boot entry
        doesn't fire a stale event.
        """

        async def _fire_when_ready(_event: Event) -> None:
            await self._fire_expiry(was_stale=True, staleness_seconds=staleness_seconds)

        unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, _fire_when_ready
        )
        self.entry.async_on_unload(unsub)
        _LOGGER.info(
            "%s deferring stale-fire until HOMEASSISTANT_STARTED (staleness=%ss)",
            self.name,
            staleness_seconds,
        )

    @callback  # type: ignore[untyped-decorator]  # HA's @callback is untyped when stubs are absent
    def _on_scheduled_fire(self, _now: datetime) -> None:
        self._unsub_callback = None
        self.hass.async_create_task(
            self._fire_expiry(was_stale=False, staleness_seconds=0)
        )

    async def _fire_expiry(self, *, was_stale: bool, staleness_seconds: int) -> None:
        """Fire event + invoke configured script.

        Always clears finishes_at first (durably) so a crash mid-fire doesn't
        leave a stale finish that re-fires on next startup.
        """
        await self._async_persist_immediate(None)

        self.hass.bus.async_fire(
            EVENT_FINISHED,
            {
                "instance_name": self.name,
                "config_entry_id": self.entry.entry_id,
                "was_stale": was_stale,
                "staleness_seconds": staleness_seconds,
            },
        )

        script_entity = self.script_entity
        if script_entity:
            try:
                await self.hass.services.async_call(
                    "script", "turn_on", {"entity_id": script_entity}, blocking=False
                )
            except Exception as exc:
                _LOGGER.warning(
                    "%s expiry script call failed for %s: %s",
                    self.name,
                    script_entity,
                    exc,
                )

        self._notify()

    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)
