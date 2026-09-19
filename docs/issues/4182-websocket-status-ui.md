# Issue #4182 — WebSocket status UI

## Links

- [rommapp/romm#4182 — Popup if WebSockets are missing](https://github.com/rommapp/romm/issues/4182)
- Related: [rommapp/romm#4639](https://github.com/rommapp/romm/issues/4639) (Storybook / static import cycles)
- Gate work: [rommapp/romm#4643](https://github.com/rommapp/romm/pull/4643) (dpdm circular dependency check)

## User story

After moving RomM behind HTTPS and a reverse proxy (for example Nginx Proxy Manager), REST `/api` can work while the Socket.IO WebSocket path is misconfigured. Scans, tasks, and other realtime features then fail quietly unless the user reads server logs. Audiobookshelf-style products surface an immediate in-app notice; RomM should do the same without adding toast spam.

## Current behavior

| Piece                                                                                      | Role                                                                                                             |
| ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| [`frontend/src/services/socket.ts`](../../frontend/src/services/socket.ts)                 | Singleton Socket.IO client: `path: /ws/socket.io/`, `transports: ["websocket", "polling"]`, `autoConnect: false` |
| Feature code                                                                               | Calls `socket.connect()` when needed (scan, upload, `useSocketEvent`, etc.)                                      |
| [`useServerConnection`](../../frontend/src/v2/composables/useServerConnection/index.ts)    | **HTTP** reachability: axios DOM events + `/heartbeat` poll (5 min online / 5 s offline)                         |
| [`BackendStatusBanner`](../../frontend/src/v2/components/AppShell/BackendStatusBanner.vue) | v2 banner when `heartbeat.connected` is false; copy `common.server-offline-retrying`                             |
| [`RomM.vue`](../../frontend/src/RomM.vue)                                                  | Lazy-loads the banner for v2 only                                                                                |

There is **no** user-visible signal when the socket stays on polling or WebSocket upgrade fails while HTTP health checks pass.

## Problem

`heartbeat.connected === true` and the offline banner hidden, but Socket.IO never reaches a WebSocket transport → realtime features appear broken with no in-app explanation.

## Constraints

- Do not replace Socket.IO or change backend architecture.
- Do not add repeated popups or toasts on every heartbeat poll (HTTP polling stays as-is).
- Reuse the existing **banner** pattern (`role="alert"`, fixed toast-style card), not a new modal framework.
- WebSocket health is **event-driven** off the existing socket singleton (connect / upgrade / connect_error), not a second polling loop.

## Proposed fix

1. **`useSocketTransportHealth`** — idempotent one-time listeners on the shared socket. Set `websocketDegraded` when transport is polling after connect or on connect error; clear on engine `upgrade` to websocket. Optional single delayed re-check after connect, not recurring polls.
2. **`BackendStatusBanner`** — show when offline **or** when websocket degraded and not offline (offline wins). Separate i18n string. Retry: HTTP uses existing `retryNow`; WebSocket uses `disconnect()` + `connect()`.
3. **Storybook** — `BackendStatusBanner.stories.ts` with `storyMode` props so stories do not install live connection/socket wiring.
4. **Tests** — transport helper unit tests; banner tests for websocket copy.

## Out of scope

- Parsing or auto-fixing proxy configuration from the app.
- Forcing websocket-only transport.
- v1 UI changes.
- Full Vue SFC coverage in dpdm (see #4643 discussion).

## Branch

`feat/4182-websocket-status-banner` from `chore/dpdm-circular-deps`.
