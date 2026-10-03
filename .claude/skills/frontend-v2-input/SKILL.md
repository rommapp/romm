---
name: frontend-v2-input
description: Universal input (mouse, touch, keyboard, gamepad) and responsive/universal-viewport layout in the RomM v2 frontend. Use when adding interactive v2 components, focus management, spatial navigation, gamepad/keyboard handling, modality-gated focus rings, breakpoints, or responsive layout. Covers useGamepad, useSpatialNav, useGridNav, the escape stack, useInputModality, useBreakpoint, and the data-bp/data-input attributes. Trigger on interactive or responsive work under frontend/src/v2/.
---

# RomM v2: Universal Input & Universal Viewport

**Premise:** all v2 UI works with mouse, touch, keyboard, **and** gamepad; and every surface reads cleanly from a 320px phone to a 4K display. Both mechanisms are fixed; don't invent a parallel one.

**One model: everything is keyboard.** `useGamepad` turns the pad into keyboard input, so a component that works with the keyboard works with a pad for free. Write keyboard handlers, never gamepad ones. The pieces (composables in `src/v2/composables/`; the global ones are installed once from `AppLayout`):

| Piece                                   | Job                                                                                                                                                                                                                                                                                                    |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `useGamepad`                            | Polls the pad. D-pad / left stick → synthetic `Arrow*` keydowns on the focused element (350ms delay, 120ms repeat). A → `.click()` on the focused element. B / Back → synthetic `Escape`, then `router.back()` only if no handler claimed it. LB/RB cycle the nav sections, Start opens the user menu. |
| `useSpatialNav`                         | Moves focus to the nearest control by arrow key, for any arrow nobody else claimed. Steps the caret in text fields for pad arrows.                                                                                                                                                                     |
| `useGridNav`                            | Per-view 2D grids with focus restore and pad autofocus. Row containers (`rowSelector` / `getRows`) or wrapping CSS grids (`cellSelector`).                                                                                                                                                             |
| `escapeStack` (`lib/overlays/RDialog/`) | Overlay stack. Escape (and so pad B) closes the topmost entry.                                                                                                                                                                                                                                         |
| `useInputModality`                      | Sets `data-input` on `<html>`.                                                                                                                                                                                                                                                                         |
| `useGlobalHotkeys`                      | `/`, `g h`, `g p`, `g c`.                                                                                                                                                                                                                                                                              |

There are **no `/console/*` routes in v2**; `src/console/` (with its own input bus) is v1 only. Don't import from it.

## The claim rule

Handlers coordinate through `preventDefault`. **Claim a key you handle; leave alone a key you don't.**

- Arrow keys a widget uses itself (a listbox, a slider, a grid moving inside its bounds) must be claimed, or `useSpatialNav` moves focus too. A grid leaves the key unclaimed at its edge so spatial nav carries focus to the next region.
- Escape: claim it only when it actually did something (closed a panel, cleared a selection). An unclaimed Escape from pad B navigates back, so claiming an Escape that did nothing traps the user on the page.
- `isPadEvent(e)` tells a synthetic pad key from a real one, for the rare handler that must differ (caret stepping).

For buttons the keyboard has no equivalent for (Y, X, triggers), listen for the `gamepad:buttondown` window event (`detail.name`: `"y"`, `"rt"`, …). The player listens for `gamepad:exitchord` (Select+Start held), since B is the game's while one is running.

## While a game runs

`storePlaying().playing` hands the pad and keyboard to the emulator: no pad translation, spatial nav or hotkeys. An open escapable overlay (the exit dialog) takes the pad back with the arrows, A, B and Back only.

## Modality

`useInputModality` sets `data-input="mouse|touch|key|pad"` on `<html>` from the most recent input.

- **Focus rings appear only with `key` and `pad`** (CSS in `global.css`). **Never use bare `:focus` in styles**; use the modality-gated selectors, or focus rings flash on mouse click.
- **Focus programmatically with `focusFromInput(el)`** (`utils/autofocus`), not `el.focus()`, so the ring shows when the move came from a key or pad.
- **Modality gates appearance and behaviour, never size**: focus rings, hover-reveal, autofocus. A tap is followed by compatibility mouse events, so anything sized off `data-input` resizes under the finger. Hit targets scale by breakpoint instead (below).

## Coverage: every interactive primitive participates

Buttons, list items, tabs, menu items, focusable cards, toggleable chips: all take part in pad and keyboard navigation (not optional). A new interactive primitive must:

- be focusable (a natively focusable element, or a proper `tabindex`), so `useSpatialNav` and `useGridNav` can reach it;
- activate on `.click()`, which is what pad A calls; a native `<button>` or link already does. A custom `role="button"` element also needs Enter/Space;
- show a modality-gated focus state.

Storybook `play()` covering gamepad input is required **only when applicable** (the primitive is interactive enough that gamepad navigation matters).

## Focus geometry

Most views need nothing: `useSpatialNav` moves between controls by position. Add `useGridNav` where a view has a grid of tiles, so up/down keep their column, focus comes back to the last tile on return (`data-focus-key` on each tile), and a pad lands on the grid without a first press. Pass `roving: true` for one tab stop per grid (the ARIA grid pattern).

## Overlays (escape stack)

Every overlay pushes itself on the escape stack while open and pops on close. Escape and pad B close only the top entry, and spatial nav stays inside the top entry's `panel`. `RDialog`, `RDrawer` and `RMenu` do this automatically; a custom popover uses `usePopoverDismiss` (Escape, B and click-outside) or `useEscapable`. A custom overlay with its own Escape listener is an anti-pattern.

Only push an entry with a `panel`: while a panel-less entry is on top, spatial nav has no panel to stay in and stops. A mode that Escape should end but that isn't an overlay (gallery selection) handles Escape in its own keydown listener and claims it.

---

## Responsive layout (universal viewport)

- **Single breakpoint source: `useBreakpoint`** (`src/v2/composables/useBreakpoint/`). Material thresholds: `xs <600`, `sm 600–959`, `md 960–1279`, `lg 1280–1919`, `xl ≥1920`. `installBreakpointAttribute()` mirrors the active set onto `<html data-bp="…">` (from `AppLayout` and `AuthLayout` in the app, and from `.storybook/preview.ts` so stories match production CSS).
- **Layout switches live in CSS** via the attribute selector: `html[data-bp~="xs"] .foo { … }`, `html[data-bp~="sm-and-down"] .foo { … }`. **No raw `@media` for layout**: the only allowed `@media` are `prefers-reduced-motion` and print. The attribute is on `<html>` so it reaches teleported overlays. `romm/no-layout-media-query` (ESLint) enforces this in SFC styles.
- **Conditional rendering** (mount/unmount a different component per tier) uses the `useBreakpoint()` refs in `<script>`, e.g. `v-if="xs"`. Prefer mount-gating over `display:none` for focusable chrome so hidden controls never sit in the tab/spatial-nav order.
- **`--r-row-pad` is the global horizontal gutter**, already re-scoped responsive in `global.css` (36 → 20 → 14px). Consume `var(--r-row-pad)`; don't hard-code a smaller `xs` padding per component.
- **Touch targets** scale with the breakpoint, never with `data-input`: `--r-touch-target` (44px) at `sm-and-down`, less only where the row would not fit.
- **Overlays go full-bleed on `xs`.** `RDialog` renders full-screen / bottom-sheet on phones (`fullscreenOnMobile`, default on); `RMenu` bottom-sheets large menus. Never float a 600px dialog on a 360px screen.
- **Label→icon collapse** (the AppNav precedent) is the canonical way to compress chrome; the four primary destinations relocate to `BottomNav` on `sm-and-down`.
- **Grids** size via `useResponsiveColumns` (ResizeObserver), never a fixed column count.

Verification adds a breakpoint sweep; see `review-polish`. In Storybook, use the viewport toolbar presets in `.storybook/rommViewports.ts` (RomM xs/sm/md tiers, Steam Deck for lg, AYN Thor top/bottom screens). A story that needs a tier sets `globals: { viewport: { value: "rommPhoneXs" } }` instead of writing `data-bp` itself. Layout that depends on `html[data-bp~="xs"]` needs a canvas **under 600px** wide (e.g. **390×844 · RomM phone**), not just `useBreakpoint()` switching subtabs at tablet widths.
