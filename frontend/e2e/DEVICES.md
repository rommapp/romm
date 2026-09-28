# Testing on target devices

v2 is built to work from a 390px phone to a 1920px handheld screen, with mouse, touch, keyboard or gamepad. The e2e suite can run any test on each target device, so a layout or input bug on the Steam Deck shows up as a failing test, not a bug report.

## The devices

They're defined once, in [`src/v2/devices.ts`](../src/v2/devices.ts). Storybook's viewport toolbar and the Playwright device projects are both built from that file, so the two can't drift apart.

| Playwright project                        | Storybook key   | Size      | Breakpoint tier |
| ----------------------------------------- | --------------- | --------- | --------------- |
| `Phone XS (touch)`                        | `rommPhoneXs`   | 390×844   | xs              |
| `Tablet SM (touch)`                       | `rommTabletSm`  | 768×1024  | sm              |
| `Desktop MD`                              | `rommDesktopMd` | 1024×768  | md              |
| `Steam Deck (touch, gamepad)`             | `steamDeck`     | 1280×800  | lg              |
| `AYN Thor top screen (touch, gamepad)`    | `aynThorTop`    | 1920×1080 | xl              |
| `AYN Thor bottom screen (touch, gamepad)` | `aynThorBottom` | 1240×1080 | md              |

The brackets are generated from each device's `hasTouchHci` and `hasGamepadHci` flags, so a name can't contradict what the project emulates. The project name is what VS Code's test panel shows and what `--project` takes.

## How a device becomes a project

Each device project takes the device's viewport, turns on touch when it has a touchscreen (only the phone also gets `isMobile`), gets a virtual gamepad when it has built-in controls, and depends on the `setup` project so tests start signed in.

It runs **only tests tagged `@devices`**, which keeps the everyday run fast: an untagged test runs once, on desktop Chrome. Tag tests whose behaviour depends on screen size, touch or gamepad input.

```ts
test("...", { tag: "@devices" }, async ({ page }) => { ... });
```

## The virtual gamepad

The app mirrors the last input it saw onto `<html data-input="…">` (`mouse`, `touch`, `key` or `pad`), and focus rings, autofocus and hover styles key off it. On a handheld, the built-in controls are a connected gamepad, and `useGamepad` switches to `pad` when it finds one. The `gamepad` option in `fixtures/test.ts` puts one connected, idle, standard-mapping pad into the page before the app loads, so the app goes through its real detection code.

It does **not** yet press buttons. Playwright's keyboard sends real key presses, which switch the app to `key` mode, so use clicks, taps and assertions when the modality matters. The login page stays in its default mode, because `useGamepad` is installed by the signed-in layout.

```ts
test("...", { tag: "@devices" }, async ({ page, gamepad }) => {
  test.skip(!gamepad, "Only devices with built-in game controls.");
});

test.use({ gamepad: true }); // or turn it on for any test, on any project
```

## Running

```bash
npm run test:e2e -- --project="steam*"       # one device
npm run test:e2e -- --project="*thor*"       # both AYN Thor screens
npm run test:e2e -- --project="*gamepad*"    # every device with built-in controls
npm run test:e2e -- --grep @devices          # every tagged test, every project
```

`--project` ignores case and accepts `*` wildcards. In VS Code, tick device projects in the Playwright panel of the Testing sidebar; with **Show browser** on, the browser opens at that device's size.

## Adding a device

Add an entry to `ROMM_DEVICES` in `src/v2/devices.ts`. It then appears in Storybook's viewport toolbar and as a Playwright project automatically. The list holds real hardware combinations rather than a full size × input matrix; for a one-off "what if this had a controller", use `test.use({ gamepad: true })`.

## Limits

Every device project runs in Chromium at a device pixel ratio of 1, with a desktop Chrome identity. It emulates each device's screen and inputs, not its browser, performance or physical controls. Check those on the hardware before a release.
