# RomM Themeable

A theme and artwork module for [RomM](https://github.com/rommapp/romm). Theme packs restyle RomM's interface: colors for light and dark mode, fonts, spacing, corner radius, motion, the logo and wordmark, login backgrounds, placeholder art, platform and provider icons, browser tab icons, and any extra CSS a pack brings. Packs live in a folder on the host, and admins choose the server's theme in **Administration → Branding**.

The module sits beside RomM's code instead of inside it. Everything it owns lives in this `themeable/` folder, plus the `themeable*` workflows in `.github/workflows/`, a banner at the top of the root `README.md`, and the root `docker-compose.yml`, which on this branch deploys romm-themeable. Each stock RomM release is merged in, checked and rebuilt automatically, so adopting a new release needs an audit, not a code merge.

## Contents

- [Deploying](#deploying)
- [Choosing a theme](#choosing-a-theme)
- [Built-in themes](#built-in-themes)
- [Writing a pack](#writing-a-pack)
- [How it works](#how-it-works)
- [Staying current with RomM](#staying-current-with-romm)
- [Developing the module](#developing-the-module)
- [Design constraints](#design-constraints)
- [Repository setup](#repository-setup)
- [Future improvements](#future-improvements)

## Deploying

The root [`docker-compose.yml`](../docker-compose.yml) deploys romm-themeable with MariaDB. It pins the image and database versions, health-checks both containers, rotates their logs, and marks every value you must fill in as `REQUIRED`. Settings are written in the file itself, as in upstream's example. Upstream's development stack, which normally lives in that file, stays on `master` with `DEVELOPER_SETUP.md`.

The parts that differ from stock RomM:

```yaml
services:
  romm:
    image: ghcr.io/stealthx3/romm-themeable:5.4.0 # or :latest
    volumes:
      - /path/to/themes:/romm/themes # theme packs, one folder each, plus themeable.json
```

**First start:** replace every `/path/to/...` with a folder on the host, fill in every `REQUIRED` value (`openssl rand -hex 32` makes a good secret), run `docker compose up -d` from the clone's root, and open `http://<host>/` to create the admin account. The themes folder must be writable, because Branding saves its choice there.

**Upgrading:** back up the database, set the image tag to the new RomM release (images are tagged with the release they are built from), then run `docker compose pull && docker compose up -d`. The tag in the compose file always matches [`ROMM_VERSION`](ROMM_VERSION); the release workflow updates both.

**Building the image yourself:** uncomment the `build:` block in the compose file and run `docker compose up -d --build`, or build directly from the repository root:

```bash
docker build -f themeable/docker/Dockerfile --build-arg ROMM_VERSION=5.4.0 -t romm-themeable:5.4.0 .
```

**Switching from stock RomM:** change the image and add the themes volume. The database, library and other volumes stay as they are, and RomM looks exactly as before until a theme is chosen.

**Environment:** the image sets `THEMEABLE_PACKS_PATH` (`/romm/themes`, where packs are read from) and `THEMEABLE_RUNTIME_DIR` (`/tmp/themeable`, where compiled themes and `status.json` go). Both can be changed; a custom runtime folder is linked into place at start-up, and if it can't be used the container falls back to the default and says so in its log.

## Choosing a theme

**Administration → Branding** (admins only) lists every theme: **RomM default** first, then the built-in themes and the packs in the themes folder, ten per page. Each entry shows:

- its name, description, color swatch and source (RomM, built-in, or themes folder);
- its artwork as visitors would see it: the login background with the logo, the wordmark on a dark and a light page, and the browser tab icon, with RomM's own wherever the pack doesn't replace something;
- **In use** for the server's current theme, or **Can't be used** with every problem listed for a pack that fails validation;
- a **Preview** button that opens RomM with the theme in a new tab without changing anything for anyone, including the admin's other tabs.

Choose a theme and click **Save changes**. The choice is stored in `themeable.json` in the themes folder and every pack is recompiled from the folder, so edits made on the host take effect on save. The refresh button rescans the folder without changing the choice. Everyone who hasn't picked a theme of their own gets the server's theme on their next page load.

**Per-browser choice:** `/themeable/` lets each browser pick its own theme or follow the server's. On any RomM URL, `?romm-theme=<id>` switches the browser to a theme, `?romm-theme=default` returns it to the server's theme, and `?romm-theme-preview=<id>` shows a theme in that tab only.

**Getting back to RomM's own look** always works:

- choose **RomM default** in Branding and save;
- delete or empty `themeable.json` and restart the container;
- add `?romm-theme=none` to any RomM URL, which works even if the Branding tab can't load;
- a missing, unreadable or broken selection falls back to RomM's look on its own, and Branding says why. A pack that fails to compile disables only itself and never stops RomM from starting.

## Built-in themes

These ship in the image, ready to choose without adding anything to the themes folder:

| Theme | Style | Look |
| --- | --- | --- |
| `phosphor` | Retro | Green-screen CRT terminal: scanlines, a monitor icon and a pixel wordmark |
| `handheld` | Retro | The four shades of a pocket LCD, with a pixel-art icon, wordmark and landscape |
| `neon` | Arcade | Synthwave magenta and cyan, a neon joystick and a sunset over a scrolling grid |
| `cabinet` | Arcade | Classic cabinet red, yellow and black, a cabinet icon and a twinkling starfield |
| `carbon` | Modern | Console-dashboard black with electric blue and teal, a play-badge icon |
| `aurora` | Modern | Glassy teal, violet and coral over a drifting aurora, a gamepad icon |
| `ember` | Warm | Charcoal and orange; the smallest complete example |

All but Ember replace the logo, wordmark, loading logo, login background (animated, with a still version for Firefox) and every browser tab icon, and all set colors for both modes and for RomM's older v1 interface. Their artwork is original. A pack in the themes folder with the same id replaces a built-in one, and copying one under a new id is a quick way to start a theme of your own.

## Writing a pack

A pack is a folder whose name is its id, holding a `theme.json` and the files it uses. **[Creating a theme pack](docs/creating-a-theme-pack.md)** walks through a first pack and documents every key: design tokens per scope, artwork, favicons, fonts, custom CSS, the v1 palette, readable colors and how packs are validated.

Two references sit alongside it:

- [`docs/theme.example.json`](docs/theme.example.json) sets every option, with all of RomM's tokens at their stock values, the v1 palette, every replaceable file and every favicon. It is regenerated from the catalog for each RomM release.
- [`schema/theme.schema.json`](schema/theme.schema.json) gives editors autocompletion and inline checks when a pack's `theme.json` points `$schema` at it.

Ids are lowercase letters, digits and dashes; `none`, `default`, `index` and `stock` are reserved.

## How it works

![Themes reach RomM through four hooks](docs/hooks.svg)

The image starts from the stock `rommapp/romm:<version>` image and adds four hooks:

1. **A loader in `index.html`.** One `<script src="/themeable/loader.js">` runs before the app renders. It picks the theme (a preview in the URL, then this browser's own choice, then the server's theme), sets `data-romm-theme` on `<html>`, adds the pack's stylesheet and sets the `romm_theme` cookie that tells nginx which artwork to serve. A preview tab leaves that cookie alone and names its theme on each artwork URL instead, so other tabs are unaffected. RomM's service worker precaches `index.html` by MD5 revision, so the hook updates that revision in `sw.js` too.
2. **nginx.** The `/assets` location tries `/themes/<theme>/<path>` before the stock file, where the theme comes from a `romm_theme` URL argument if present, otherwise from the cookie, and only valid ids are accepted. Browser tab icons come from the server's theme, or from the pack (or stock look) a `romm_theme` argument names, which is how Branding previews them. Both rules are anchored rewrites of upstream's template that fail the build if it changes shape.
3. **Branding inside RomM.** New files in `overlay/` (the Branding tab, its API client and text, and an admin-only backend router at `/api/themeable/branding`) are added to RomM's source, and the anchored edits in `patches/` register the tab in `Administration.vue` and the router in `main.py`. The image build rebuilds the frontend with them and patches the release image's backend. Upstream files in this repository are never edited; an overlay file that would replace one, or a patch whose anchor has moved, fails the build with a clear message.
4. **A start-up compile.** The entrypoint runs `scripts/runtime.mjs` before RomM's own. It validates and compiles the built-in packs and the folder's packs into a new build under the runtime folder, then switches to it in one rename, so nginx never serves a half-written theme. Saving in Branding runs the same script through the backend. A lock file keeps compiles from overlapping, and a save that takes too long is stopped and changes nothing.

Each compiled `theme.css` scopes its rules under `:root[data-romm-theme="<id>"]`, which outranks RomM's own token rules whatever order the stylesheets load in, and wraps a pack's custom CSS the same way. Vite inlines small artwork referenced from CSS, such as the login background, into the app bundle as `data:` URIs that never reach nginx, so the catalog records every such rule and the compiler emits a matching rule pointing at the pack's file.

Values the browser files share (the reserved ids, cookie and storage key names, URL parameters, the stock swatch and the preview slots) have one home, [`lib/client.mjs`](lib/client.mjs). The compiler publishes them in the manifest that the loader, the picker and the Branding API read, and a test fails if a browser file declares one itself.

## Staying current with RomM

Four workflows keep the module current and leave a pull request trail to audit:

| Workflow | Runs | Does |
| --- | --- | --- |
| `themeable` | Every push and pull request to `themeable` | Unit tests, compatibility check, then the source and visual checks; on push, builds the image, smoke-tests it (start-up compile, theme links, patched files, nginx config) and publishes `ghcr.io/stealthx3/romm-themeable:<ROMM_VERSION>` and `:latest` |
| `themeable upstream release` | Hourly, or by hand with a tag | When RomM publishes a stable release: moves `master` to the release commit, merges the tag into a `themeable-upstream/<tag>` branch, runs the compatibility check, refreshes the catalog and the example pack, bumps `ROMM_VERSION` and the compose file's image tag, runs the visual and source checks against the new release, and opens a pull request with the reports. If everything passes it merges, which publishes the new image; otherwise it stays open as "needs attention" |
| `themeable visual check` | Called by the other two | Builds the frontend with the overlay and patches, then loads the login screen for the stock look and every built-in pack in dark and light mode, failing if a pack's tokens, artwork or inlined artwork didn't apply or it looks identical to stock. Screenshots are kept for 90 days |
| `themeable source check` | Called by the other two | Lints and type-checks the patched frontend and runs the Branding API tests against MariaDB with the patched backend |

`master` holds nothing but upstream release commits and moves only when a stable release is published; prereleases and manual runs with other tags leave it alone, and GitHub's **Sync fork** button shouldn't be used. When a release changes upstream's root `docker-compose.yml`, the merge keeps this branch's version. Any other merge conflict, or a missing token, opens an issue instead. Setting the repository variable `THEMEABLE_AUTO_MERGE` to `false` holds every adoption for review.

To adopt a release by hand:

1. Merge the release tag into `themeable`, keeping this branch's root `docker-compose.yml` if it conflicts.
2. Run `npm run check-upstream` for the report of added, removed and renamed tokens and artwork, and any pack, hook or patch that would break.
3. Record token renames in `catalog/token-aliases.json` (`{"--r-old": "--r-new"}`); packs using an old name keep compiling, with a warning.
4. Run `npm run catalog` and `npm run example`, set `ROMM_VERSION` and the compose file's image tag to the release, and push.

## Developing the module

Everything runs from `themeable/` with Node 20 or later and no dependencies to install.

| Folder | Holds |
| --- | --- |
| `packs/` | The built-in theme packs |
| `lib/` | Pack validation and compilation, the catalog, the hooks, the overlay and patch engine, and the shared client values |
| `scripts/` | Command-line entry points, listed below |
| `loader/`, `picker/` | The page loader and the `/themeable/` picker |
| `overlay/`, `patches/` | Files added to RomM's source, and anchored edits to its existing files |
| `catalog/` | RomM's tokens, replaceable files and CSS artwork references for the current release, plus token aliases |
| `docker/` | The Dockerfile and entrypoint |
| `schema/`, `docs/` | The pack schema, the authoring guide, the full example pack and the hooks diagram |
| `test/`, `dev/` | Unit and visual tests, and the local preview server |

| Command | Does |
| --- | --- |
| `npm test` | Unit tests, including the patches and the nginx rewrite against the real upstream files |
| `npm run build -- [--packs packs] [--catalog catalog] [--out dist] [--default <id>\|none]` | Validates and compiles the built-in packs into `dist/`; fails on any invalid pack |
| `npm run catalog` | Regenerates `catalog/` from this repository's `frontend/`; `--tokens <css file\|dir> --assets-list <file> --out <dir>` reads a built image instead |
| `npm run check-upstream -- [--upstream <repo root>] [--report <file.md>]` | Compares the committed catalog with the current tree and checks hook anchors, patches, overlay collisions and packs; exits 1 on breakage |
| `npm run example -- [--check]` | Regenerates `docs/theme.example.json`; `--check` fails if it is out of date |
| `npm run preview` | The local preview described below |
| `npm run visual -- [--out <dir>] [--port 8199]` | The visual check; needs a frontend build, nginx and Playwright's Chromium from `frontend/node_modules` (`CHROMIUM_PATH` picks another browser) |
| `node scripts/apply-source.mjs --root <copy> [--only frontend\|backend] [--no-tests]` | Applies `overlay/` and `patches/` to a copy of RomM's source; refuses the repository checkout itself unless `--force` |
| `node scripts/runtime.mjs [--select <id>\|none]` | The container's start-up and save step; prints its status as JSON |
| `node scripts/apply-hooks.mjs --webroot <dir> --nginx <template> --out <dir> [--root-overlay <dir>] [--default <id>\|none]` | Writes the hooked `index.html`, nginx template and `sw.js`; the Dockerfile runs it |
| `node scripts/verify-image.mjs --css <image /assets dir> [--packs packs]` | Checks every pack token against a built image's CSS |

**Previewing without Docker:** build the frontend with the module applied, then serve it through the patched nginx (needs `nginx` on the PATH). Without a backend, a stub API is enough for the login screen and the picker. With `--api-port`, nginx proxies `/api` to a running RomM backend; start it with the `THEMEABLE_*` variables the preview prints so Branding can recompile. Other options are `--packs-folder <dir>`, `--default <id>|none`, `--port` (8099) and `--dist <frontend build>`.

```bash
mkdir -p /tmp/rt && cp -r frontend themeable /tmp/rt/   # a throwaway copy; the checkout stays untouched
node /tmp/rt/themeable/scripts/apply-source.mjs --root /tmp/rt --only frontend --force
(cd /tmp/rt/frontend && npm ci && npm run build)
node themeable/dev/preview.mjs --dist /tmp/rt/frontend/dist --packs-folder ./my-themes --default ember
# http://localhost:8099/login and /themeable/
```

## Design constraints

What RomM's codebase offers, and what follows from it:

| Area | Upstream | Consequence |
| --- | --- | --- |
| Two interfaces | v1 (Vuetify) is frozen; v2 (`frontend/src/v2/`) is the active one | Packs target v2; v1 gets a palette |
| Design tokens | `tokens.css` defines the `--r-*` variables v2 is built from | Overriding them re-skins v2 |
| Theme classes | `.r-v2` with `.r-v2-dark` or `.r-v2-light` on `<html>` | Pack CSS scopes on `<html>` |
| Color discipline | No color literals in v2 components, enforced by lint | Nearly every color is a token |
| Artwork | `frontend/assets` is served as-is from `/assets` under stable names | Same-URL replacement through nginx |
| Login screen | Always dark, whatever the mode | Packs tint it with `--r-color-canvas-bg-deep` |
| Solid buttons | White text on the brand color | Packs keep `--r-color-brand-primary` at 3:1 or better against white |

Known limits:

| Limit | Effect | Handling |
| --- | --- | --- |
| v2 changes quickly | Tokens are added and renamed between releases | Catalog diff, aliases and the compatibility check on every release |
| Custom CSS targets component classes | It can stop matching after a release | Documented as unchecked; tokens are preferred wherever they reach |
| Colors baked in JavaScript | Generated placeholder covers and the player canvas ignore themes | Accepted for now |
| Build-time platform list | Packs can replace platform icons but not add platforms RomM lacks | Replacement only |
| Per-browser choice | A visitor's own pick doesn't follow them to other devices | The server's theme covers everyone who hasn't picked one |
| Patched RomM files | A release that reshapes `Administration.vue` or the router list in `main.py` stops a patch applying | The compatibility check, source check and image build fail with the patch's name, and the adoption stays open |
| Frontend rebuilt from this branch | The image's interface is built from this branch's copy of RomM's source | Each release is merged before building, and the checks compare the two |
| Preview of CSS-only artwork | In a preview tab, backgrounds from RomM's own stylesheets that the previewed pack doesn't replace follow the visitor's theme | Affects that tab only |
| Visual check scope | It covers logged-out screens | The source check and unit tests cover the rest |

## Repository setup

One-time settings for unattended running:

1. **Default branch:** set it to `themeable`. Scheduled workflows only run from the default branch, and the landing page then shows this module.
2. **Bot token:** create a fine-grained personal access token for this repository with Contents, Pull requests and Workflows set to read and write, and save it as the Actions secret `THEMEABLE_BOT_TOKEN`. GitHub's built-in token can't push the workflow-file changes most upstream releases include. Renew it before it expires; the workflow opens an issue when it's missing.
3. **Upstream's scheduled workflows:** disable upstream's `build.yml`, `image-scan.yml`, `trunk-check-all.yml`, `trunk-upgrade.yml` and `update-hltb-api-url.yml` under Actions. They run on schedules once `themeable` is the default branch and fail without upstream's secrets; disabling them leaves the files untouched, so merges stay clean.

GitHub pauses scheduled workflows after 60 days without repository activity; each adopted release counts as activity.

RomM is AGPL-3.0, so published images must keep their source available, which this public fork does.

## Future improvements

Ideas that would build naturally on what exists, roughly in order of value:

- **Theme editor.** A page at `/themeable/studio/` for editing a pack's tokens by group, with contrast warnings, a live preview (the loader's `preview()` hook and `postMessage` channel already exist for this), artwork slots with upload, and saving into the themes folder.
- **Pack management in Branding.** Upload a zipped pack, download one, duplicate a built-in theme under a new id to customise it, and delete folder packs, all without touching the host.
- **Contrast checks in the validator.** Warn when a pack's brand color is hard to read against white button text or the page, or its wordmark against either background, using the rules the built-in themes were made to.
- **Theme choice that follows the user.** Store a visitor's own pick in their RomM account (`user.ui_settings`) so it carries across devices; the backend replaces that whole object on write, so the loader would read, merge and send it back.
- **Separate light and dark choices.** Let the server, or a visitor, pair one theme for light mode with another for dark, or schedule seasonal themes.
- **Applying a theme without a reload.** Swap the stylesheet and re-request artwork in place after saving or picking, instead of asking for a page reload.
- **Visual checks behind the login.** Seed a backend in CI so the visual check covers the library, game and settings screens, and keeps a screenshot diff across releases to catch custom CSS that stopped matching.
- **Translations.** Carry the Branding tab's text into every RomM locale, ideally through a mechanism that doesn't edit upstream locale files.
- **Themed app manifest.** Give installed web apps the theme's colors and icons through the web app manifest, not just the page.
- **Pack metadata.** A minimum RomM version, a homepage and a license field per pack, shown in Branding, as groundwork for a shared gallery of community packs.
- **Theming JavaScript-baked colors.** A small patch so generated placeholder covers and the player canvas read tokens instead of fixed values.
- **Release publishing.** Have the release workflow also create the matching GitHub release, with notes generated from the adoption report.
