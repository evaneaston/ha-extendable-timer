# Extendable Timer

A sleep-timer-style countdown that survives Home Assistant restarts.

Each timer is its own device with a live remaining-time sensor, an **Extend**
button that adds a configurable amount of time (the default is 10 minutes),
and a **Cancel** button. A matching Lovelace card ships with the integration
and shows up automatically in the "Add card" picker as **Extendable Timer**.

See the README for installation and configuration.
