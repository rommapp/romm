# RomM Themeable

A theme and artwork module for [RomM](https://github.com/rommapp/romm) that lives beside the upstream code instead of inside it. Theme packs change the v2 UI's colors, fonts, spacing, corner radius, motion, logos, backgrounds, placeholder art and platform icons. They are applied on top of a stock RomM release image, so each new upstream release needs a version bump and a read of one compatibility report, not a code merge.

Everything the module owns sits in this `themeable/` folder, plus two workflow files in `.github/workflows/` and a short banner at the top of the root `README.md`.

**Status:** Phases 0 to 3 are built and tested; Phases 4 to 6 are planned. See [Development plan](#development-plan).

## Quick start

Build an image for a RomM release, with the example `ember` pack as the default theme:

```bash
docker build -f themeable/docker/Dockerfile \
  --build-arg ROMM_VERSION=5.4.0 \
  --build-arg THEMEABLE_DEFAULT=ember \
  -t romm-themeable:5.4.0 themeable
```

Use it anywhere you'd use `rommapp/romm:5.4.0`; nothing else in your compose file changes. Then:

- `/themeable/` lists the installed themes and lets each browser pick one ("Stock RomM" turns theming off).
- `?romm-theme=<id>` on any RomM URL switches theme, which is handy for links and testing.
- `THEMEABLE_DEFAULT` sets what visitors get before they pick. `none` means stock.

To preview without Docker, build the frontend and serve it through the patched nginx config with a stub API (needs `nginx` on your PATH):

```bash
(cd frontend && npm ci && npm run build)
node themeable/dev/preview.mjs --default ember    # http://localhost:8099/login and /themeable/
```

## Writing a pack

A pack is a folder in `packs/` holding `theme.json` and its files. The folder name must equal `id`. [`packs/ember`](packs/ember) is a full example; [`schema/theme.schema.json`](schema/theme.schema.json) gives editors autocompletion.

| Key | What it does |
| --- | --- |
| `id`, `name`, `version`, `author`, `description` | Metadata shown in the picker. `id` is lowercase letters, digits and dashes. |
| `tokens.common` / `tokens.dark` / `tokens.light` | Overrides for RomM's `--r-*` design tokens. `common` applies in both modes; `dark` and `light` win over it in their mode. |
| `tokens.input-key` / `tokens.input-pad` | Overrides used only while the keyboard or a gamepad is driving focus. |
| `assets` | Replaces a stock file: `"/assets/isotipo.svg": "assets/logo.svg"`. Same extension as the original. |
| `rootFiles` | Favicons and app icons. Applied only for the image's default pack, since browsers cache them hard. |
| `fonts` | `@font-face` entries for font files in the pack. Point `--r-font-family-sans` or `-display` at the family. |
| `vuetify.dark` / `vuetify.light` | Best-effort palette for the legacy v1 UI (`primary`, `background`, `surface`...). |
| `pwa.themeColor` | The browser chrome color (`<meta name="theme-color">`). |
| `extraCss` | Escape hatch: raw CSS scoped to the theme. Unsupported across releases. |

Every token name is checked against `catalog/tokens.json`, and every replaced file against `catalog/assets.json`. Run `npm run build` in this folder to validate and compile; errors name the key at fault.

## How it works

![Themes reach RomM through three build-time hooks](docs/hooks.svg)

The Dockerfile starts `FROM rommapp/romm:<tag>`, compiles the packs against the CSS and artwork that image actually ships, and changes three things:

1. **Loader in `index.html`.** One `<script src="/themeable/loader.js">` at the end of `<head>`. Before the app renders, it picks the theme (URL, then this browser's choice, then the server default), sets `data-romm-theme` on `<html>`, adds the pack's stylesheet and sets the `romm_theme` cookie. RomM's service worker precaches `index.html` by MD5 revision, so the hook also updates that revision in `sw.js`; otherwise browsers that installed the stock worker would keep the stock page.
2. **nginx `/assets` block.** `try_files /themes/$themeable_theme$uri $uri ...`, where `$themeable_theme` comes from the cookie through a `map` that only accepts valid pack ids. A pack's file wins if it has one; otherwise the stock file is served. These responses are sent `no-cache` with `Vary: Cookie`. This is the only upstream file the module edits, and it does so by anchored rewrite (`lib/nginx.mjs`) that fails the build if the block changes shape.
3. **Packs copied to `/themes/<id>/`.** Each compiled `theme.css` scopes its rules under `:root[data-romm-theme="<id>"]`, which outranks upstream's token rules whatever order the stylesheets load in.

Vite inlines small CSS artwork, such as the login background, into the app bundle as `data:` URIs. Those never hit nginx, so the catalog records every CSS rule in upstream source that uses an `/assets/` file. For each replaced file, the compiler emits a matching rule that points at the pack's copy.

## Commands

Run in `themeable/` (Node 20 or later; no dependencies to install):

| Command | Does |
| --- | --- |
| `npm test` | Unit tests, including the patch against the real nginx template. |
| `npm run build -- --default ember` | Validates and compiles packs into `dist/`. |
| `npm run catalog` | Regenerates `catalog/` from this repo's `frontend/`. |
| `npm run check-upstream` | Compares the committed catalog with the current tree, checks hook anchors and packs; exits 1 on breakage. |
| `npm run preview` | Local preview described above. |
| `npm run visual` | Visual check: loads the login screen for stock and every pack in both modes and fails if a pack's tokens, artwork or inlined artwork didn't apply, or if it looks the same as stock. Needs a frontend build, nginx and Playwright's Chromium (set `CHROMIUM_PATH` to use another). |

`scripts/verify-image.mjs --css <dir>` checks every pack token against a built image's CSS.

## Automation

Three workflows keep the module current without anyone touching it, leaving a PR trail to audit:

| Workflow | Runs | Does |
| --- | --- | --- |
| `themeable` | Every push and PR to `themeable` | Unit tests and compatibility check, then the visual check, then (on push) builds and publishes `ghcr.io/stealthx3/romm-themeable:<ROMM_VERSION>` and `:latest`. |
| `themeable upstream release` | Hourly, or by hand with a tag | When RomM publishes a new stable release: moves `master` forward to that release's commit, merges the tag into a `themeable-upstream/<tag>` branch, runs the compatibility check, refreshes the catalog, bumps `ROMM_VERSION`, runs the visual check against the new release's frontend, and opens a PR with both reports. If everything passed, it merges the PR, which publishes the new image. Otherwise the PR stays open, titled "needs attention". |
| `themeable visual check` | Called by the other two | Builds the frontend with upstream's own setup action and runs `npm run visual`; screenshots are kept as the `themeable-visual` artifact for 90 days. |

`master` is never synced on its own schedule: it moves only when a new stable release is posted, so it always equals the latest release commit (unreleased upstream commits, for example from a past **Sync fork**, are reset away) (prereleases and manual runs with other tags leave it alone). Don't use GitHub's **Sync fork** button, which would move it to upstream's latest commit. A merge conflict or a missing secret opens an issue instead. Set the repository variable `THEMEABLE_AUTO_MERGE` to `false` to review every adoption before it merges.

## Per-release maintenance

The `themeable upstream release` workflow does this within an hour of each release. By hand:

1. Merge the new upstream tag into `themeable`. The module only adds files, so the only likely conflict is the README banner.
2. `npm run check-upstream` reports added, removed and renamed tokens and artwork, and any pack or hook that would break.
3. Add renames to `catalog/token-aliases.json` (`{"--r-old": "--r-new"}`); packs using the old name keep compiling, with a warning.
4. `npm run catalog`, then set `ROMM_VERSION` to the tag and push. The `themeable` workflow builds and publishes `ghcr.io/stealthx3/romm-themeable:<tag>`.

## Development plan

The module ships as files added on top of a stock RomM release, never as edits to upstream source, so it can be rebuilt for every release.

| Phase | Deliverable | Estimate | Status |
| --- | --- | --- | --- |
| 0. Repo and pipeline | `master` holds only upstream release commits; module on `themeable`; CI builds `ghcr.io/stealthx3/romm-themeable:<tag>` | 1 to 2 days | Done |
| 1. Packs and static overlay | Pack schema, validator, compiler, example pack, derived Dockerfile | 3 to 4 days | Done |
| 2. Runtime switching | Loader, cookie-driven nginx artwork, picker page, service worker revision fix, inlined-artwork rewrite | 3 to 5 days | Done, except saving the choice to the user's account |
| 3. Catalog and checker | Token, asset and CSS-reference catalog; release diff report; token aliases | 2 to 3 days | Done |
| 4. Theme editor | Standalone page at `/themeable/studio/`: token editor by group with contrast checks, live preview in an iframe, artwork slots with upload, fonts, zip export and import | 1.5 to 2 weeks | Not started; the loader's `preview()` and `postMessage` channel are in place for it |
| 5. Save service (optional) | Sidecar at `/themeable/api` storing packs on a volume; admin check through RomM's `/api/users/me` | 3 to 5 days | Not started |
| 6. Release automation | Hourly upstream release check and adoption PR with compatibility and visual checks; auto-merge when both pass; image published on merge | 2 to 3 days | Done for logged-out screens; screens behind login need a seeded backend in CI |

**Next steps:**

- Save the chosen theme to `user.ui_settings` so it follows the user across devices. The backend replaces the whole object on each write, so the loader must read, merge and send it all back.
- Add a theme entry to RomM's own UI. That needs an upstream patch, so for now the picker lives at `/themeable/`.
- Build the editor (Phase 4) on the catalog's `group` field and token defaults.

## What the RomM codebase gives the module

| Area | Upstream | Consequence |
| --- | --- | --- |
| Two UIs | v1 (Vuetify) is frozen and slated for deletion; v2 (`frontend/src/v2/`) is the active rewrite | Target v2; v1 gets a palette only |
| Design tokens | `src/v2/tokens/index.ts` generates `tokens.css`: 173 `--r-*` variables in source, 182 in the built CSS | Overriding them re-skins v2 |
| Theme classes | `RomM.vue` puts `.r-v2` plus `.r-v2-dark` or `.r-v2-light` on `<html>` | Pack CSS scopes on `<html>` |
| Color discipline | No hex or `rgba()` literals in v2 components, enforced by lint | Nearly every color is a token |
| Artwork | `frontend/assets` is copied as-is to `/var/www/html/assets` with stable names | Same-URL replacement through nginx |
| Per-user settings | `user.ui_settings` is free-form JSON | Room to store a theme choice |

## Risks and limitations

| Risk | Effect | Mitigation |
| --- | --- | --- |
| v2 changes fast | Tokens get added and renamed | Catalog diff, aliases, compatibility check in CI |
| `extraCss` targets component classes | Breaks across releases | Labelled unsupported; screenshots in Phase 6 |
| JS-baked colors (`colorCoverArt`, `colorCanvas`) | Generated placeholder covers and the player canvas ignore themes | Accept, or carry a small patch to `v2/utils/covers.ts` |
| Local token overrides | `.r-v2-bg__layer--a` redefines some surface tokens over cover art | Override in `extraCss` if needed |
| Build-time platform-icon list | Packs can replace icons but not add platforms upstream lacks | Replace existing icons only |
| Theme choice is per browser | A new device starts on the server default | `ui_settings` sync (next steps) |
| v1 UI | Palette only | v1 is scheduled for deletion upstream |

## Repository setup

One-time settings for unattended running:

1. **Default branch:** set it to `themeable` (Settings, General). Scheduled workflows only run from the default branch, and the landing page then shows this module.
2. **Bot token:** create a fine-grained personal access token limited to this repository with Contents, Pull requests and Workflows set to read and write, and save it as the Actions secret `THEMEABLE_BOT_TOKEN`. GitHub's built-in token can't push upstream's workflow-file changes, which most releases include. Expect to renew it when it expires; the workflow opens an issue when it's missing.
3. **Upstream's scheduled workflows:** once `themeable` is the default branch, upstream's `build.yml`, `image-scan.yml`, `trunk-check-all.yml`, `trunk-upgrade.yml` and `update-hltb-api-url.yml` start running on their schedules and fail or open PRs without upstream's secrets. Disable them under Actions; disabling doesn't touch the files, so upstream merges stay clean.

GitHub also pauses scheduled workflows after 60 days without repository activity; each adopted release counts as activity.
- RomM is AGPL-3.0. Published images must keep their source available, which this public fork does.
