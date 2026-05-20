// Extendable Timer Lovelace card
// See spec: docs/superpowers/specs/2026-05-08-extendable-timer-card-design.md

const PLATFORM = "extendable_timer";

function formatExtendLabel(seconds) {
  // No leading '+' — the mdi:plus icon next to this label already conveys
  // the add-time action, and double-plus reads as a typo.
  if (seconds == null) return "";
  const s = Math.max(1, Math.round(Number(seconds)));
  if (s < 60) return `${s}s`;
  const m = Math.round(s / 60);
  if (s < 3600) return `${m}m`;
  const hours = Math.floor(s / 3600);
  const remMin = Math.round((s % 3600) / 60);
  return remMin === 0 ? `${hours}h` : `${hours}h ${remMin}m`;
}

function formatRemainingDisplay(sensorState) {
  // The sensor publishes HH:MM:SS / "idle" to keep its state stable
  // across consumers. The card relabels "idle" as "off" (more natural
  // for a sleep-timer use case) and drops the leading 00: when hours
  // are zero — the seconds digit ticking makes the unit unambiguous.
  if (!sensorState || sensorState === "idle") return "off";
  const m = /^(\d{1,2}):(\d{2}):(\d{2})$/.exec(sensorState);
  if (!m) return sensorState;
  const h = parseInt(m[1], 10);
  if (h === 0) return `${m[2]}:${m[3]}`;
  return sensorState;
}

function classifyEntity(entityId) {
  // Returns "remaining" | "extend" | "cancel" | null based on the integration's
  // documented unique_id suffix (which the entity_id slug also reflects when
  // names haven't been renamed).
  if (entityId.endsWith("_remaining")) return "remaining";
  if (entityId.endsWith("_extend")) return "extend";
  if (entityId.endsWith("_cancel")) return "cancel";
  return null;
}

function findFirstTimerDeviceId(hass) {
  if (!hass || !hass.entities) return "";
  for (const reg of Object.values(hass.entities)) {
    if (reg.platform === PLATFORM && reg.device_id) {
      return reg.device_id;
    }
  }
  return "";
}

class ExtendableTimerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._renderedShell = false;
    this._anchor = null;
    this._hass = null;
  }

  static getConfigElement() {
    return document.createElement("extendable-timer-card-editor");
  }

  static getStubConfig(hass) {
    return { device: findFirstTimerDeviceId(hass) };
  }

  setConfig(config) {
    // Never throw — HA's Lovelace can transiently pass a partial config
    // during page-reload / component-recycle paths, and a thrown setConfig
    // makes HA replace the entire card with "Configuration error" and not
    // retry, even when a valid config arrives one tick later. Store
    // whatever we get; _resolveEntities renders an inline error if the
    // config is missing required fields.
    const cfg = config || {};
    this._device = cfg.device || null;
    this._anchorEntity = cfg.entity || null;
    this._renderedShell = false;
    this.shadowRoot.innerHTML = "";
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 1;
  }

  // --- internals ---

  _resolveEntities() {
    const hass = this._hass;
    if (!hass || !hass.entities || !hass.states) return null;

    // Resolve the device. Prefer the explicit `device:` config; fall
    // back to deriving it from a legacy `entity:` config (still
    // supported for any pasted YAML using the old shape).
    let deviceId = this._device;
    if (!deviceId && this._anchorEntity) {
      const anchorReg = hass.entities[this._anchorEntity];
      if (!anchorReg) {
        return { error: `Entity not found: ${this._anchorEntity}` };
      }
      if (anchorReg.platform !== PLATFORM) {
        return { error: `Not an Extendable Timer entity: ${this._anchorEntity}` };
      }
      deviceId = anchorReg.device_id;
    }
    if (!deviceId) {
      return { error: "No Extendable Timer device selected" };
    }

    const siblings = { remaining: null, extend: null, cancel: null };
    for (const [entityId, reg] of Object.entries(hass.entities)) {
      if (reg.device_id !== deviceId || reg.platform !== PLATFORM) continue;
      const role = classifyEntity(entityId);
      if (role && !siblings[role]) siblings[role] = entityId;
    }
    for (const role of ["remaining", "extend", "cancel"]) {
      if (!siblings[role]) {
        return { error: `Timer device incomplete: missing ${role}` };
      }
    }
    return { siblings };
  }

  _renderError(message) {
    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="error">${message}</div>
        <div class="hint">
          Set <code>device</code> to an Extendable Timer device id, or
          <code>entity</code> to any of its entities (e.g.
          <code>sensor.bedroom_sleep_remaining</code>) and the card
          will resolve the device automatically.
          Easiest: open the card editor and pick from the dropdown.
        </div>
        <style>
          ha-card {
            padding: 16px;
            border-radius: var(--ha-card-border-radius, 12px);
          }
          .error {
            color: var(--error-color, #db4437);
            font-weight: 600;
            margin-bottom: 8px;
          }
          .hint {
            color: var(--secondary-text-color);
            font-size: 0.9em;
            line-height: 1.4;
          }
          code {
            background: var(--secondary-background-color, #2a2a2a);
            padding: 1px 4px;
            border-radius: 3px;
          }
        </style>
      </ha-card>
    `;
    this._renderedShell = false;
  }

  _renderShell() {
    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="row">
          <div class="tile remaining" data-role="remaining">
            <div class="time">idle</div>
          </div>
          <div class="tile button extend" data-role="extend" tabindex="0" role="button">
            <ha-icon icon="mdi:plus"></ha-icon>
            <div class="extend-label">+</div>
          </div>
          <div class="tile button cancel" data-role="cancel" tabindex="0" role="button">
            <ha-icon icon="mdi:stop"></ha-icon>
          </div>
        </div>
        <style>
          /* Layout uses HA's --ha-space-3 spacing token (~12px) for tile
             padding directly — no local indirection. Override via a theme
             that redefines --ha-space-3, or via card-mod for instance-level
             tweaks. */
          ha-card {
            padding: 8px;
            border-radius: var(--ha-card-border-radius, 12px);
          }
          .row {
            display: flex;
            gap: 6px;
            align-items: stretch;
          }
          .tile {
            display: flex;
            justify-content: center;
            align-items: center;
            border: none;
            border-radius: var(--ha-card-border-radius, 12px);
            padding: var(--ha-space-3, 12px);
            box-sizing: border-box;
            /* Inner gap (icon-to-label) is half the tile padding so
               proportions hold if padding is tuned in the theme. */
            gap: calc(var(--ha-space-3, 12px) / 2);
          }
          /* Remaining tile is display-only — transparent fill so the
             active-state primary tint reads cleanly when the timer is
             running, and there's no "button surface" implication when
             it's off. */
          .remaining {
            flex: 1 1 auto;
            min-width: 0;
            background: transparent;
          }
          /* Extend / cancel tiles use a filled button surface so they
             read as interactive even when the timer is off (no border,
             no active-state highlight). The cancel tile's width is
             set in JS to mirror the extend tile's natural content
             width. */
          .extend, .cancel {
            flex: 0 0 auto;
            cursor: pointer;
            background: var(--secondary-background-color, #2a2a2a);
            transition: background 0.1s;
          }
          .extend:hover, .cancel:hover {
            background: color-mix(
              in srgb,
              var(--primary-color) 15%,
              var(--secondary-background-color, #2a2a2a)
            );
          }
          .extend:focus, .cancel:focus {
            outline: 2px solid var(--primary-color);
            outline-offset: -2px;
          }
          .time {
            font-size: 1.4em;
            font-weight: 400;
            color: var(--secondary-text-color);
            line-height: 1;
            display: inline-flex;
            align-items: center;
          }
          .time.active {
            font-weight: 600;
            color: var(--primary-text-color);
          }
          .extend-label {
            font-size: 0.95em;
            color: var(--primary-text-color);
            /* Tight line-height so the label's box matches the glyph
               height (digits + 'm' have no descenders, so a default
               line-height pushes the visual center upward relative to
               the icon's bounding-box center). */
            line-height: 1;
          }
          .remaining.active {
            background: color-mix(
              in srgb,
              var(--primary-color) 12%,
              var(--card-background-color)
            );
          }
          /* Off-state cancel tile is dimmed to suggest it's a no-op. The
             click still fires — cancelling an already-off timer is a
             harmless no-op — the opacity is purely cosmetic. */
          .cancel.off { opacity: 0.5; }
          ha-icon { --mdc-icon-size: 26px; color: var(--primary-text-color); }
        </style>
      </ha-card>
    `;
    const sr = this.shadowRoot;
    this._timeEl = sr.querySelector(".time");
    this._remainingTile = sr.querySelector(".remaining");
    this._extendTile = sr.querySelector(".extend");
    this._extendLabel = sr.querySelector(".extend-label");
    this._cancelTile = sr.querySelector(".cancel");

    this._setupExtendGestures();
    this._cancelTile.addEventListener("click", () => this._onCancel());
    for (const el of [this._extendTile, this._cancelTile]) {
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          el.click();
        }
      });
    }

    // Mirror the extend tile's content-driven width to the cancel tile
    // so the two buttons are visually balanced regardless of whether
    // the duration label is "30s" or "1h 30m".
    if (this._sizeObserver) this._sizeObserver.disconnect();
    this._sizeObserver = new ResizeObserver(() => this._syncCancelWidth());
    this._sizeObserver.observe(this._extendTile);
    requestAnimationFrame(() => this._syncCancelWidth());

    this._renderedShell = true;
  }

  _syncCancelWidth() {
    if (!this._extendTile || !this._cancelTile) return;
    const w = this._extendTile.offsetWidth;
    if (w > 0) this._cancelTile.style.minWidth = `${w}px`;
  }

  disconnectedCallback() {
    if (this._sizeObserver) {
      this._sizeObserver.disconnect();
      this._sizeObserver = null;
    }
  }

  _render() {
    if (!this._hass) return;
    const result = this._resolveEntities();
    if (!result || result.error) {
      this._renderError(result ? result.error : "Loading...");
      return;
    }
    const { remaining, extend, cancel } = result.siblings;
    const remainingState = this._hass.states[remaining];
    const extendState = this._hass.states[extend];
    if (!remainingState || !extendState) {
      this._renderError("Entity state unavailable");
      return;
    }

    if (!this._renderedShell) this._renderShell();

    const isActive = remainingState.state !== "idle";
    this._timeEl.textContent = formatRemainingDisplay(remainingState.state);
    this._timeEl.classList.toggle("active", isActive);
    this._remainingTile.classList.toggle("active", isActive);
    this._cancelTile.classList.toggle("off", !isActive);

    const extendSeconds = extendState.attributes.extend_seconds;
    this._extendLabel.textContent = formatExtendLabel(extendSeconds);

    this._extendId = extend;
    this._cancelId = cancel;
  }

  _onExtend() {
    if (!this._hass || !this._extendId) return;
    this._hass.callService("button", "press", { entity_id: this._extendId });
  }

  _onCancel() {
    if (!this._hass || !this._cancelId) return;
    this._hass.callService("button", "press", { entity_id: this._cancelId });
  }

  // --- Long-press gesture on the extend tile ---
  //
  // Tap = extend (existing behavior). Hold for 500ms = navigate to the
  // integration's config page so the user can edit options without the
  // Settings → Devices walk. Admin-only (HA convention is to silently
  // ignore admin-only gestures for non-admins; the tap still works).
  //
  // Implementation: pointerdown starts the hold timer; pointerup/cancel/
  // leave clears it. If the hold timer fires, we set a flag that the
  // subsequent click handler checks to suppress the press-extend that
  // would otherwise follow.
  _setupExtendGestures() {
    const HOLD_MS = 500;
    let holdTimer = null;
    let didLongPress = false;

    this._extendTile.addEventListener("pointerdown", () => {
      didLongPress = false;
      if (holdTimer != null) clearTimeout(holdTimer);
      holdTimer = setTimeout(() => {
        holdTimer = null;
        didLongPress = true;
        this._onExtendLongPress();
      }, HOLD_MS);
    });

    const cancelHold = () => {
      if (holdTimer != null) {
        clearTimeout(holdTimer);
        holdTimer = null;
      }
    };
    this._extendTile.addEventListener("pointerup", cancelHold);
    this._extendTile.addEventListener("pointercancel", cancelHold);
    this._extendTile.addEventListener("pointerleave", cancelHold);

    this._extendTile.addEventListener("click", () => {
      if (didLongPress) {
        didLongPress = false;
        return;
      }
      this._onExtend();
    });
  }

  _onExtendLongPress() {
    // Silent no-op for non-admins — matches HA's convention of hiding
    // admin-only gestures rather than showing toasts/errors.
    if (!this._hass?.user?.is_admin) return;
    const path = `/config/integrations/integration/${PLATFORM}`;
    history.pushState({}, "", path);
    this.dispatchEvent(
      new CustomEvent("location-changed", {
        detail: { replace: false },
        bubbles: true,
        composed: true,
      })
    );
  }
}

// --- Config editor for the "Add card" / "Edit card" dialog ---
//
// Uses HA's <ha-form> with an entity selector. <ha-form> is registered
// eagerly by HA's frontend (most native dialogs use it), whereas
// <ha-entity-picker> is only loaded by some code paths — we'd be
// fighting load-order races by talking to it directly.

const EDITOR_SCHEMA = [
  {
    name: "device",
    required: true,
    selector: {
      device: {
        filter: { integration: PLATFORM },
      },
    },
  },
];

class ExtendableTimerCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = null;
    this._form = null;
  }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;
    if (!this._form) {
      this.innerHTML = "";
      const form = document.createElement("ha-form");
      form.computeLabel = (s) => (s.name === "device" ? "Extendable Timer device" : s.name);
      form.addEventListener("value-changed", (ev) => {
        // Merge form output into the *existing* config so top-level
        // keys we don't render in the form survive — most importantly
        // `type`, which HA's lovelace preview needs to render the card
        // and which it strips here if we replace the object outright
        // ("No card type configured." in the preview pane).
        const next = { ...this._config, ...(ev.detail?.value || {}) };
        if (next.device === this._config.device) return;
        this._config = next;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          })
        );
      });
      this._form = form;
      this.appendChild(form);
      const help = document.createElement("div");
      help.style.cssText = "margin-top: 8px; color: var(--secondary-text-color); font-size: 0.9em;";
      help.textContent =
        "Pick the timer device. The card auto-discovers its remaining, extend, and cancel entities.";
      this.appendChild(help);
    }
    // <ha-form>'s `data` is the value object keyed by schema field
    // names. We feed only `{ device }` so legacy `entity:` configs
    // don't pre-populate the device picker with a stale value; the
    // user can then pick a device explicitly.
    this._form.hass = this._hass;
    this._form.schema = EDITOR_SCHEMA;
    this._form.data = { device: this._config.device || "" };
  }
}

// Idempotent registration. Re-evaluating this module (HA hot reload,
// service-worker cache mixing, dev refresh) would otherwise call
// customElements.define a second time and throw "name already used",
// which leaves customElements.whenDefined hanging and produces the
// "Custom element not found: extendable-timer-card" error in the card
// picker.
if (!customElements.get("extendable-timer-card")) {
  customElements.define("extendable-timer-card", ExtendableTimerCard);
}
if (!customElements.get("extendable-timer-card-editor")) {
  customElements.define("extendable-timer-card-editor", ExtendableTimerCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "extendable-timer-card")) {
  window.customCards.push({
    type: "extendable-timer-card",
    name: "Extendable Timer",
    description: "Compact countdown with + and stop buttons",
  });
}

// Race-recovery: HA's createCustomCardElement instantiates the element and
// calls setConfig synchronously. If our async module hasn't finished loading
// at that moment (more likely on cold cache + forced reload), the element
// has no setConfig method, HA renders a generic "Configuration error" card.
// HA *should* rebuild via customElements.whenDefined but doesn't always.
// We nudge stale error cards by firing ll-rebuild on them — the same event
// the error card itself uses as its retry button.
//
// HA's lovelace tree is mostly inside shadow DOMs, which document.querySelectorAll
// does not penetrate. We walk shadow roots manually. We also re-scan on a
// schedule because lovelace's render can complete after our module finishes
// loading (delayed dashboard hydration), meaning the error card appears AFTER
// our initial nudge. The schedule covers the typical load-sequence window
// without being a polling loop.
(() => {
  const findErrorCardsIn = (root, results) => {
    if (!root) return;
    if (root.nodeType === Node.ELEMENT_NODE) {
      if (root.tagName && root.tagName.toLowerCase() === "hui-error-card") {
        results.push(root);
      }
      if (root.shadowRoot) {
        for (const c of root.shadowRoot.children) findErrorCardsIn(c, results);
      }
    }
    const kids = root.children;
    if (kids) {
      for (const c of kids) findErrorCardsIn(c, results);
    }
  };

  const seen = new WeakSet();
  const nudge = () => {
    const cards = [];
    findErrorCardsIn(document.body, cards);
    for (const ec of cards) {
      if (seen.has(ec)) continue;
      seen.add(ec);
      ec.dispatchEvent(new Event("ll-rebuild", { bubbles: true, composed: true }));
    }
  };

  // Cover three windows:
  // - Immediately, in case error cards already exist by the time our
  //   module's last expression runs.
  // - 100ms / 500ms / 2s / 10s, to catch error cards that materialise
  //   later as lovelace finishes hydrating.
  const scan = () => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", nudge, { once: true });
    } else {
      nudge();
    }
  };
  scan();
  for (const delay of [100, 500, 2000, 10000]) setTimeout(nudge, delay);
})();
