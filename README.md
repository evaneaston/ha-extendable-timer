# Extendable Timer

A sleep-timer-style countdown for Home Assistant that survives restarts and
that you can extend with a single button press.

Each timer you add is its own device. You get:

- a **live remaining-time sensor** that counts down second by second,
- an **Extend** button that adds your configured chunk of time (10 minutes
  by default — pick any amount),
- a **Cancel** button that stops the timer immediately,
- a **`finished` device trigger** for automations that should fire when the
  timer reaches zero,
- and a matching **Lovelace card** that loads automatically — no separate
  install, no YAML required.

If Home Assistant restarts while a timer is running, the timer keeps running.
If HA was down past the scheduled end time, the timer fires as soon as HA is
back up.

## Install

### HACS (recommended)

1. In HACS, open the menu in the top-right of the **Integrations** page and
   choose **Custom repositories**.
2. Add `https://github.com/evaneaston/ha-extendable-timer`, category
   **Integration**.
3. Install **Extendable Timer** and restart Home Assistant.

### Manual

1. Copy `custom_components/extendable_timer/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Add a timer

1. **Settings → Devices & Services → Add Integration**, search for
   **Extendable Timer**.
2. Give the timer a name (e.g. "Bedroom Fan") and pick the default extend
   amount.
3. Repeat for as many independent timers as you want — each becomes its own
   device with its own entities.

You can change the extend amount any time without restarting:
**Settings → Devices & Services → Extendable Timer → Configure**.

## Use it in the dashboard

The bundled card appears in the **Add card** picker as **Extendable Timer**.
Pick a timer from the device dropdown — that's all the configuration it needs.

The card shows three tiles:

- the live countdown,
- an extend button with the current amount baked into the label
  (e.g. `+10m`, `+1h 30m`) — the label updates live when you change the
  amount in **Configure**,
- a cancel button.

If you'd rather drive the timer from a script or voice command, the entities
are standard buttons and a sensor — `button.press` and the usual
`{{ states('sensor.<name>_remaining') }}` patterns work fine.

## Automations

Each timer device exposes a `finished` device trigger. Use it in the
automation editor to react to a timer reaching zero (e.g. turn off the fan,
play a chime). The trigger fires once per timer expiry, including stale
expiries that happened while HA was down.

## Compatibility

- Home Assistant 2024.x or newer.

## Issues and source

Development happens in the upstream monorepo:
<https://github.com/evaneaston/ha-apps>. Please file issues and PRs there.
