# Changelog

## [v1.0.0]

- **Brand icon.** Adds the HACS brand assets (`brand/icon.png`, `brand/icon@2x.png`) that the validation pipeline requires. No functional change.
- **Stable API.** Bumping to 1.0 to signal that the entity surface (remaining-time sensor, extend/cancel buttons, configured-extend `extend_seconds` attribute), the event surface (`extendable_timer_started` / `_extended` / `_canceled` / `_finished` with their payload fields), the device triggers, and the Lovelace card config schema are now under semver. Breaking changes will bump the major.

## [v0.1.2]

- **New state-change events and device triggers.** Three new triggers join the existing `Timer finished`:
  - `Timer started` — fires when an Extend press kicks the timer off from idle.
  - `Timer extended` — fires when Extend is pressed while the timer is already running.
  - `Timer canceled` — fires when Cancel is pressed before the timer reaches zero.

  Pressing Cancel while the timer is already idle stays a no-op (no event fired). Each event carries `instance_name`, `config_entry_id`, plus payload fields you can use in automation templates (`finishes_at`, `previous_finishes_at`, `extend_seconds`, `remaining_seconds`).

## [v0.1.1]

- **Card editor:** picking a different device in the visual editor no longer breaks the preview ("No card type configured." under a spinner). The editor was dropping the card's `type` when emitting config changes.
- **Issue tracker link:** the integration page's *Known issues* menu now opens this repo's issues, not a private monorepo (which 404'd for HACS installers).

## [v0.1.0]

Initial release.
