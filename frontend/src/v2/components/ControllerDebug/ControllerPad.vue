<script setup lang="ts">
// ControllerPad — renders a single connected Gamepad as the silhouette of
// a generic controller: triggers + shoulders top corners, D-pad bottom-
// left, face buttons in a diamond bottom-right, sticks below their
// respective halves, and Back / Home / Start in the centre. Each element
// lights up brand-primary when its button is held; triggers also fill
// from the bottom proportionally to their analog value.
//
// Buttons 0..16 follow the W3C "Standard Gamepad" mapping. Pads exposing
// more than 17 buttons (touchpad click, paddles…) get an "extras" row
// rendered beneath the silhouette so the data isn't lost.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import type { GamepadSnapshot } from "./types";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  pad: GamepadSnapshot;
}>();

const EMPTY_BTN = { pressed: false, value: 0 } as const;

function btn(i: number) {
  return props.pad.buttons[i] ?? EMPTY_BTN;
}

const axisL = computed(() => ({
  x: props.pad.axes[0] ?? 0,
  y: props.pad.axes[1] ?? 0,
}));
const axisR = computed(() => ({
  x: props.pad.axes[2] ?? 0,
  y: props.pad.axes[3] ?? 0,
}));

const extras = computed(() =>
  props.pad.buttons.slice(17).map((b, i) => ({
    idx: 17 + i,
    pressed: b.pressed,
    value: b.value,
  })),
);

function magnitude(x: number, y: number) {
  return Math.min(1, Math.sqrt(x * x + y * y));
}
</script>

<template>
  <div class="r-v2-pad__wrap">
    <div class="r-v2-pad">
      <!-- Triggers + bumpers (left) -->
      <div class="r-v2-pad__corner r-v2-pad__corner--left">
        <div
          class="r-v2-pad__trigger"
          :class="{ 'r-v2-pad__trigger--pressed': btn(6).pressed }"
          :title="`#6 — LT / L2 (${btn(6).value.toFixed(2)})`"
        >
          <div
            class="r-v2-pad__trigger-fill"
            :style="{ height: `${btn(6).value * 100}%` }"
          />
          <span class="r-v2-pad__trigger-label">LT</span>
          <span class="r-v2-pad__trigger-value">
            {{ btn(6).value.toFixed(2) }}
          </span>
        </div>
        <div
          class="r-v2-pad__bumper"
          :class="{ 'r-v2-pad__bumper--pressed': btn(4).pressed }"
          title="#4 — LB / L1"
        >
          LB
        </div>
      </div>

      <!-- Triggers + bumpers (right) -->
      <div class="r-v2-pad__corner r-v2-pad__corner--right">
        <div
          class="r-v2-pad__trigger"
          :class="{ 'r-v2-pad__trigger--pressed': btn(7).pressed }"
          :title="`#7 — RT / R2 (${btn(7).value.toFixed(2)})`"
        >
          <div
            class="r-v2-pad__trigger-fill"
            :style="{ height: `${btn(7).value * 100}%` }"
          />
          <span class="r-v2-pad__trigger-label">RT</span>
          <span class="r-v2-pad__trigger-value">
            {{ btn(7).value.toFixed(2) }}
          </span>
        </div>
        <div
          class="r-v2-pad__bumper"
          :class="{ 'r-v2-pad__bumper--pressed': btn(5).pressed }"
          title="#5 — RB / R1"
        >
          RB
        </div>
      </div>

      <!-- D-pad (cross, top-left of the controls block) -->
      <div class="r-v2-pad__dpad">
        <div
          class="r-v2-pad__dpad-arm r-v2-pad__dpad-arm--up"
          :class="{ 'r-v2-pad__dpad-arm--pressed': btn(12).pressed }"
          title="#12 — D-pad Up"
        >
          <RIcon icon="mdi-menu-up" size="20" />
        </div>
        <div
          class="r-v2-pad__dpad-arm r-v2-pad__dpad-arm--left"
          :class="{ 'r-v2-pad__dpad-arm--pressed': btn(14).pressed }"
          title="#14 — D-pad Left"
        >
          <RIcon icon="mdi-menu-left" size="20" />
        </div>
        <div class="r-v2-pad__dpad-center" />
        <div
          class="r-v2-pad__dpad-arm r-v2-pad__dpad-arm--right"
          :class="{ 'r-v2-pad__dpad-arm--pressed': btn(15).pressed }"
          title="#15 — D-pad Right"
        >
          <RIcon icon="mdi-menu-right" size="20" />
        </div>
        <div
          class="r-v2-pad__dpad-arm r-v2-pad__dpad-arm--down"
          :class="{ 'r-v2-pad__dpad-arm--pressed': btn(13).pressed }"
          title="#13 — D-pad Down"
        >
          <RIcon icon="mdi-menu-down" size="20" />
        </div>
      </div>

      <!-- System cluster (Back / Home / Start) -->
      <div class="r-v2-pad__system">
        <div
          class="r-v2-pad__sys-btn"
          :class="{ 'r-v2-pad__sys-btn--pressed': btn(8).pressed }"
          title="#8 — Back / Select / Share"
        >
          <RIcon icon="mdi-view-dashboard-outline" size="13" />
          <span>Back</span>
        </div>
        <div
          class="r-v2-pad__sys-btn r-v2-pad__sys-btn--home"
          :class="{ 'r-v2-pad__sys-btn--pressed': btn(16).pressed }"
          title="#16 — Home / Guide / PS"
        >
          <RIcon icon="mdi-circle-double" size="18" />
        </div>
        <div
          class="r-v2-pad__sys-btn"
          :class="{ 'r-v2-pad__sys-btn--pressed': btn(9).pressed }"
          title="#9 — Start / Options / Menu"
        >
          <RIcon icon="mdi-menu" size="13" />
          <span>Start</span>
        </div>
      </div>

      <!-- Face buttons (diamond, top-right) -->
      <div class="r-v2-pad__face">
        <div
          class="r-v2-pad__face-btn r-v2-pad__face-btn--top"
          :class="{ 'r-v2-pad__face-btn--pressed': btn(3).pressed }"
          title="#3 — Y / △"
        >
          Y
        </div>
        <div
          class="r-v2-pad__face-btn r-v2-pad__face-btn--left"
          :class="{ 'r-v2-pad__face-btn--pressed': btn(2).pressed }"
          title="#2 — X / □"
        >
          X
        </div>
        <div
          class="r-v2-pad__face-btn r-v2-pad__face-btn--right"
          :class="{ 'r-v2-pad__face-btn--pressed': btn(1).pressed }"
          title="#1 — B / ○"
        >
          B
        </div>
        <div
          class="r-v2-pad__face-btn r-v2-pad__face-btn--bottom"
          :class="{ 'r-v2-pad__face-btn--pressed': btn(0).pressed }"
          title="#0 — A / ✕"
        >
          A
        </div>
      </div>

      <!-- Left stick (L3 click) -->
      <div class="r-v2-pad__stick-wrap r-v2-pad__stick-wrap--left">
        <div
          class="r-v2-pad__stick"
          :class="{ 'r-v2-pad__stick--pressed': btn(10).pressed }"
          :title="`#10 — L3 click (axes 0/1)`"
        >
          <div class="r-v2-pad__stick-axis r-v2-pad__stick-axis--h" />
          <div class="r-v2-pad__stick-axis r-v2-pad__stick-axis--v" />
          <div class="r-v2-pad__stick-deadzone" />
          <div
            class="r-v2-pad__stick-dot"
            :style="{
              left: `${50 + axisL.x * 50}%`,
              top: `${50 + axisL.y * 50}%`,
              opacity: magnitude(axisL.x, axisL.y) > 0.05 ? 1 : 0.45,
            }"
          />
        </div>
        <p class="r-v2-pad__stick-label">
          L-Stick
          <span v-if="btn(10).pressed" class="r-v2-pad__stick-click">· L3</span>
        </p>
        <p class="r-v2-pad__stick-values">
          X {{ axisL.x.toFixed(2) }} · Y {{ axisL.y.toFixed(2) }}
        </p>
      </div>

      <!-- Right stick (R3 click) -->
      <div class="r-v2-pad__stick-wrap r-v2-pad__stick-wrap--right">
        <div
          class="r-v2-pad__stick"
          :class="{ 'r-v2-pad__stick--pressed': btn(11).pressed }"
          :title="`#11 — R3 click (axes 2/3)`"
        >
          <div class="r-v2-pad__stick-axis r-v2-pad__stick-axis--h" />
          <div class="r-v2-pad__stick-axis r-v2-pad__stick-axis--v" />
          <div class="r-v2-pad__stick-deadzone" />
          <div
            class="r-v2-pad__stick-dot"
            :style="{
              left: `${50 + axisR.x * 50}%`,
              top: `${50 + axisR.y * 50}%`,
              opacity: magnitude(axisR.x, axisR.y) > 0.05 ? 1 : 0.45,
            }"
          />
        </div>
        <p class="r-v2-pad__stick-label">
          R-Stick
          <span v-if="btn(11).pressed" class="r-v2-pad__stick-click">· R3</span>
        </p>
        <p class="r-v2-pad__stick-values">
          X {{ axisR.x.toFixed(2) }} · Y {{ axisR.y.toFixed(2) }}
        </p>
      </div>
    </div>

    <!-- Extra buttons (anything past the standard 17) -->
    <div v-if="extras.length" class="r-v2-pad__extras">
      <div class="r-v2-pad__extras-title">Extra buttons</div>
      <div class="r-v2-pad__extras-grid">
        <div
          v-for="b in extras"
          :key="b.idx"
          class="r-v2-pad__extra"
          :class="{ 'r-v2-pad__extra--pressed': b.pressed }"
        >
          <span class="r-v2-pad__extra-idx">#{{ b.idx }}</span>
          <span class="r-v2-pad__extra-value">{{ b.value.toFixed(2) }}</span>
          <div
            class="r-v2-pad__extra-fill"
            :style="{ transform: `scaleX(${b.value})` }"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Outer wrapper centres the silhouette and caps its width — at full
   container width the layout starts looking sparse. */
.r-v2-pad__wrap {
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.r-v2-pad {
  display: grid;
  width: 100%;
  max-width: 520px;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto auto auto;
  grid-template-areas:
    "corner-l system  corner-r"
    "dpad     .       face"
    "lstick   .       rstick";
  gap: 20px 18px;
  align-items: center;
  justify-items: center;
}

/* Layout area assignments ----------------------------------------- */
.r-v2-pad__corner--left {
  grid-area: corner-l;
  justify-self: start;
}
.r-v2-pad__corner--right {
  grid-area: corner-r;
  justify-self: end;
}
.r-v2-pad__dpad {
  grid-area: dpad;
}
.r-v2-pad__face {
  grid-area: face;
}
.r-v2-pad__system {
  grid-area: system;
  align-self: start;
}
.r-v2-pad__stick-wrap--left {
  grid-area: lstick;
}
.r-v2-pad__stick-wrap--right {
  grid-area: rstick;
}

/* Shared cell visual (pressed = brand primary tint) --------------- */
.r-v2-pad__trigger,
.r-v2-pad__bumper,
.r-v2-pad__face-btn,
.r-v2-pad__dpad-arm,
.r-v2-pad__sys-btn {
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-secondary);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-pad__trigger--pressed,
.r-v2-pad__bumper--pressed,
.r-v2-pad__face-btn--pressed,
.r-v2-pad__dpad-arm--pressed,
.r-v2-pad__sys-btn--pressed {
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 60%,
    transparent
  );
  color: var(--r-color-brand-primary);
}

/* Corner stacks (LT/LB and RT/RB) -------------------------------- */
.r-v2-pad__corner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.r-v2-pad__trigger {
  position: relative;
  width: 60px;
  height: 56px;
  border-radius: 12px 12px 18px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  overflow: hidden;
}
.r-v2-pad__trigger-fill {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  background: color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
  transition: height 40ms linear;
  z-index: 0;
}
.r-v2-pad__trigger-label,
.r-v2-pad__trigger-value {
  position: relative;
  z-index: 1;
}
.r-v2-pad__trigger-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
}
.r-v2-pad__trigger-value {
  font-family: var(--r-font-family-mono, monospace);
  font-size: 10px;
  color: var(--r-color-fg-muted);
}
.r-v2-pad__trigger--pressed .r-v2-pad__trigger-value {
  color: var(--r-color-brand-primary);
}

.r-v2-pad__bumper {
  width: 78px;
  height: 22px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
}

/* D-pad cross ---------------------------------------------------- */
.r-v2-pad__dpad {
  display: grid;
  grid-template-columns: 28px 28px 28px;
  grid-template-rows: 28px 28px 28px;
  gap: 2px;
}
.r-v2-pad__dpad-arm {
  display: flex;
  align-items: center;
  justify-content: center;
}
.r-v2-pad__dpad-arm--up {
  grid-column: 2;
  grid-row: 1;
  border-radius: 6px 6px 0 0;
}
.r-v2-pad__dpad-arm--left {
  grid-column: 1;
  grid-row: 2;
  border-radius: 6px 0 0 6px;
}
.r-v2-pad__dpad-arm--right {
  grid-column: 3;
  grid-row: 2;
  border-radius: 0 6px 6px 0;
}
.r-v2-pad__dpad-arm--down {
  grid-column: 2;
  grid-row: 3;
  border-radius: 0 0 6px 6px;
}
.r-v2-pad__dpad-center {
  grid-column: 2;
  grid-row: 2;
  background: var(--r-color-surface);
  border-top: 1px solid var(--r-color-border);
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-pad__dpad-center::before {
  content: "";
  display: block;
  height: 100%;
  border-left: 1px solid var(--r-color-border);
  border-right: 1px solid var(--r-color-border);
  margin: 0 -1px;
}

/* Face button diamond -------------------------------------------- */
.r-v2-pad__face {
  display: grid;
  grid-template-columns: 32px 32px 32px;
  grid-template-rows: 32px 32px 32px;
  gap: 4px;
}
.r-v2-pad__face-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-family: var(--r-font-family-display, sans-serif);
  font-weight: var(--r-font-weight-bold);
  font-size: 13px;
}
.r-v2-pad__face-btn--top {
  grid-column: 2;
  grid-row: 1;
}
.r-v2-pad__face-btn--left {
  grid-column: 1;
  grid-row: 2;
}
.r-v2-pad__face-btn--right {
  grid-column: 3;
  grid-row: 2;
}
.r-v2-pad__face-btn--bottom {
  grid-column: 2;
  grid-row: 3;
}

/* System cluster (Back / Home / Start) --------------------------- */
.r-v2-pad__system {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-pad__sys-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: var(--r-radius-pill);
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.r-v2-pad__sys-btn--home {
  width: 38px;
  height: 38px;
  padding: 0;
  justify-content: center;
  border-radius: 50%;
}

/* Sticks --------------------------------------------------------- */
.r-v2-pad__stick-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.r-v2-pad__stick {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-pad__stick--pressed {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    transparent
  );
}
.r-v2-pad__stick-axis {
  position: absolute;
  background: var(--r-color-border);
  opacity: 0.55;
}
.r-v2-pad__stick-axis--h {
  top: 50%;
  left: 8%;
  right: 8%;
  height: 1px;
}
.r-v2-pad__stick-axis--v {
  top: 8%;
  bottom: 8%;
  left: 50%;
  width: 1px;
}
.r-v2-pad__stick-deadzone {
  position: absolute;
  inset: 35%;
  border-radius: 50%;
  border: 1px dashed var(--r-color-border-strong);
}
.r-v2-pad__stick-dot {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  box-shadow: 0 0 12px
    color-mix(in srgb, var(--r-color-brand-primary) 60%, transparent);
  transform: translate(-50%, -50%);
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-pad__stick-label {
  margin: 6px 0 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}
.r-v2-pad__stick-click {
  color: var(--r-color-brand-primary);
  margin-left: 2px;
}
.r-v2-pad__stick-values {
  margin: 0;
  font-size: 10px;
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-faint);
}

/* Extras (idx > 16) ---------------------------------------------- */
.r-v2-pad__extras {
  width: 100%;
  padding-top: 16px;
  border-top: 1px solid var(--r-color-border);
}
.r-v2-pad__extras-title {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}
.r-v2-pad__extras-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 6px;
}
.r-v2-pad__extra {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  font-size: 10px;
}
.r-v2-pad__extra--pressed {
  background: color-mix(in srgb, var(--r-color-brand-primary) 16%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 50%,
    transparent
  );
}
.r-v2-pad__extra-idx {
  position: relative;
  z-index: 1;
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-muted);
}
.r-v2-pad__extra-value {
  position: relative;
  z-index: 1;
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-secondary);
}
.r-v2-pad__extra-fill {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
  transform-origin: left center;
  transform: scaleX(0);
  transition: transform 40ms linear;
  z-index: 0;
  pointer-events: none;
}

/* Responsive: tighten gaps + scale sticks on very narrow widths --- */
html[data-bp~="xs"] .r-v2-pad {
  grid-template-columns: 1fr 1fr;
  grid-template-areas:
    "corner-l corner-r"
    "system   system"
    "dpad     face"
    "lstick   rstick";
  gap: 16px 12px;
}
html[data-bp~="xs"] .r-v2-pad__corner--right {
  justify-self: end;
}
html[data-bp~="xs"] .r-v2-pad__system {
  justify-self: center;
}
html[data-bp~="xs"] .r-v2-pad__stick {
  width: 80px;
  height: 80px;
}
</style>
