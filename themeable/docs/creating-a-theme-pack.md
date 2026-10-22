# Creating a theme pack

A theme pack is a `.zip` archive holding a `theme.json` file and any artwork, fonts or CSS it uses. RomM compiles it into a stylesheet plus replacement files, and the theme applies to RomM's v2 interface (and, for colors only, the older v1 interface).

## Where packs live

| Location | Used for |
| --- | --- |
| The themes folder on the host, mapped to `/romm/themes` in the container | Your own packs. Add or edit them here, then use **Administration → Branding**. |
| `themeable/packs/` in this repository | Built-in packs that ship inside the image: `phosphor`, `handheld`, `neon`, `cabinet`, `carbon`, `aurora`, `ember`, and the accessibility packs `contrast-dark`, `contrast-light` and `signal`. They are folders here for easy editing, and the image build zips them. A pack in the themes folder with the same id replaces the built-in one. |

Each pack is one archive, and its file name must be the pack's `id` plus `.zip`. Inside, `theme.json` sits at the archive's root, or inside one top-level folder, which is what most zip tools make when you zip a folder. RomM reads the archive directly; nothing is unpacked into the themes folder.

```
themes/
  themeable.json          ← written by Branding: the server's selected theme
  midnight.zip
    midnight/             ← optional top-level folder
      theme.json
      assets/
        isotipo.svg
        auth_background.svg
      fonts/
        Inter-Variable.woff2
      custom.css
```

**Folder packs.** A folder named after its id, holding a `theme.json`, still works in this release. Branding marks it **Folder pack: convert to .zip**, and its **Convert** button writes `<id>.zip`, moves the folder to `themes/.converted/<id>/` and recompiles. If the archive wouldn't compile, nothing changes and Branding says why. The next release drops folder packs. When a folder and an archive share an id, the archive is used.

## Your first pack

1. In a working folder of your own (not the themes folder), create `midnight/theme.json`:

   ```json
   {
     "$schema": "https://raw.githubusercontent.com/Stealthx3/romm-themeable/themeable/themeable/schema/theme.schema.json",
     "id": "midnight",
     "name": "Midnight",
     "description": "Deep blue with a cyan accent",
     "author": "you",
     "version": "1.0.0",
     "tokens": {
       "common": {
         "--r-color-brand-primary": "#38bdf8",
         "--r-color-brand-primary-hover": "#7dd3fc",
         "--r-color-brand-accent": "#f472b6"
       },
       "dark": {
         "--r-color-bg": "#0b1020"
       }
     }
   }
   ```

2. Zip the `midnight` folder (see [Zipping a pack](#zipping-a-pack)).
3. In RomM, open **Administration → Branding** and drop the archive on **Upload a theme pack**. Branding checks it before installing anything and lists every problem it finds. You can also copy it into the themes folder as `midnight.zip` and click the refresh button. Midnight appears in the list with its login background and logo, its wordmark on a dark and a light page, and its browser tab icon; anything the pack doesn't replace shows RomM's own. If anything in it is wrong, the entry says **Can't be used** and lists each problem.
4. Click **Preview** to open RomM with the theme in a new tab, without changing anything for anyone else.
5. Choose Midnight and click **Save changes**. Reload the page to see it.

To change the pack later, edit its files, zip it again and upload it; Branding asks before replacing the installed Midnight. Copying it over `midnight.zip` in the themes folder and clicking the refresh button works too. Only archives that changed are read again.

The pack's id comes from `theme.json`, not the archive's name, and a built-in pack can't be replaced by an upload: to change one, copy it, give it a new id and upload that.

## Zipping a pack

Zip the pack's folder, then make sure the archive's name is the pack's id plus `.zip`.

- **Windows:** in File Explorer, right-click the `midnight` folder and choose **Send to → Compressed (zipped) folder** (on Windows 11, **Compress to → ZIP File**). In PowerShell: `Compress-Archive -Path midnight -DestinationPath midnight.zip`.
- **macOS:** in Finder, right-click the folder and choose **Compress "midnight"**. The `__MACOSX` and `.DS_Store` entries Finder adds are ignored. In Terminal: `zip -r midnight.zip midnight -x '*.DS_Store'`.
- **Linux:** right-click the folder in your file manager and choose **Compress**, picking `.zip`. In a terminal: `zip -r midnight.zip midnight`.

Zipping the files themselves, so `theme.json` is at the root of the archive, works too.

**Limits.** Packs come from users and the web, so each archive is checked before anything in it is read: at most 2,000 files, 64 MB uncompressed in total, 16 MB per file, and a compression ratio of at most 100:1. Files must be stored or deflated, which every common zip tool does by default; encrypted, split and ZIP64 archives are refused. An administrator can change the limits with the `THEMEABLE_ZIP_MAX_ENTRIES`, `THEMEABLE_ZIP_MAX_TOTAL_MB`, `THEMEABLE_ZIP_MAX_FILE_MB` and `THEMEABLE_ZIP_MAX_RATIO` environment variables.

## theme.json reference

[`theme.example.json`](theme.example.json) sets every option below: each token at its stock value, the v1 palette, every replaceable file, every favicon, a font, tags, placeholder covers, the browser color and custom CSS. Copy the parts you want into your own `theme.json` and delete the rest; the file paths in it show where each replacement would go in your pack, but the files themselves aren't included. It is regenerated for every RomM release, so it always matches the current one.

| Key | Required | What it does |
| --- | --- | --- |
| `id` | yes | Lowercase letters, digits and dashes, up to 64 characters, matching the archive's file name without `.zip`. `none`, `default`, `random`, `index` and `stock` are reserved. |
| `name` | yes | Shown in Branding and the theme picker; up to 80 characters. Administrators can change it later with **Rename** in Branding. |
| `description`, `author`, `version` | no | Shown in Branding and the theme picker. |
| `tags` | no | Up to 8 lowercase words, see [Tags and the Accessibility label](#tags-and-the-accessibility-label). |
| `covers` | no | Placeholder covers for games without one, see [Placeholder covers](#placeholder-covers). |
| `tokens` | no | Design-token overrides, see [Colors, spacing and fonts](#colors-spacing-and-fonts). |
| `assets` | no | Replacement artwork, see [Artwork](#artwork). |
| `rootFiles` | no | Favicons and app icons, see [Favicons](#favicons). |
| `fonts` | no | Font files to load, see [Fonts](#fonts). |
| `extraCss` | no | A CSS file for anything tokens can't reach, see [Custom CSS](#custom-css). |
| `vuetify` | no | Colors for the older v1 interface, see [The v1 interface](#the-v1-interface). |
| `pwa.themeColor` | no | The browser's toolbar color on phones (`<meta name="theme-color">`), as a hex color. |

The `$schema` line is optional; it gives editors such as VS Code autocompletion and inline checks.

## Colors, spacing and fonts

RomM's v2 interface takes nearly every visual value from **design tokens**: CSS custom properties named `--r-...`. A pack overrides them by name. The full list for the current release, with each token's group and its stock values, is in [`catalog/tokens.json`](../catalog/tokens.json).

Tokens are set per **scope**:

| Scope | Applies |
| --- | --- |
| `common` | In both dark and light mode. |
| `dark`, `light` | Only in that mode, and win over `common`. |
| `input-key`, `input-pad` | Only while a keyboard or a gamepad is driving focus (mostly focus-ring width). |

Useful groups:

| Group | Examples |
| --- | --- |
| Brand | `--r-color-brand-primary`, `-primary-hover`, `-primary-pressed`, `--r-color-brand-secondary`, `--r-color-brand-accent`, `--r-color-fav` |
| Surfaces and text | `--r-color-bg`, `--r-color-bg-elevated`, `--r-color-surface`, `--r-color-panel`, `--r-color-fg`, `--r-color-fg-muted`, `--r-color-border` (usually set per mode) |
| Status | `--r-color-success`, `--r-color-warning`, `--r-color-danger`, `--r-color-info` |
| Shape | `--r-radius-sm` … `--r-radius-card`, `--r-radius-pill` |
| Spacing and size | `--r-space-1` … `--r-space-14`, `--r-font-size-xs` … `--r-font-size-4xl` |
| Type | `--r-font-family-sans`, `--r-font-family-display`, `--r-font-weight-*` |
| Motion | `--r-motion-*` durations and easings |

Values are plain CSS: `#38bdf8`, `rgba(255, 255, 255, 0.08)`, `18px`, `linear-gradient(...)`. They can't contain `{ } ; < >` or backslashes.

## Artwork

`assets` maps a stock file's URL to a file in your pack. The replacement must have the same extension, because browsers decide how to show it from the URL:

```json
"assets": {
  "/assets/isotipo.svg": "assets/isotipo.svg",
  "/assets/logotipo.svg": "assets/logotipo.svg",
  "/assets/auth_background.svg": "assets/auth_background.svg",
  "/assets/auth_background_static.svg": "assets/auth_background_static.svg"
}
```

Every file you can replace is listed in [`catalog/assets.json`](../catalog/assets.json). The most visible:

| File | Where it shows |
| --- | --- |
| `/assets/isotipo.svg` | The logo mark: top bar, login card |
| `/assets/logotipo.svg` | The "RomM" wordmark in the top bar |
| `/assets/logos/romm_logo_xbox_one_circle_grayscale.svg` | The logo on the loading screen |
| `/assets/auth_background.svg`, `/assets/auth_background_static.svg` | The login and setup background (the static one is used by Firefox) |
| `/assets/default/*` | Placeholder covers and the default avatar |
| `/assets/platforms/<slug>.svg` or `.ico` | Platform icons (only platforms RomM already ships an icon for) |
| `/assets/scrappers/*.png` | Metadata provider logos |

Artwork follows each visitor's theme: two people using different themes see different logos at the same time.

## Favicons

`rootFiles` replaces the browser-tab icons. Allowed keys are `/favicon.ico`, `/favicon.svg`, `/favicon-16x16.png`, `/favicon-32x32.png`, `/apple-touch-icon.png`, `/android-chrome-192x192.png`, `/android-chrome-512x512.png` and `/safari-pinned-tab.svg`. They follow each visitor's theme, like the rest of the artwork; a browser that hasn't loaded a RomM page yet gets the server's theme's icons. Browsers cache favicons aggressively, so a change can take a while to show.

## Placeholder covers

When a game has no cover, RomM draws one: a backdrop with two shapes placed by the game's name and an icon, a grid for an identified game ("missing") and a question mark for an unidentified one ("unmatched"). `covers` themes that art in either of two ways, or both:

```json
"covers": {
  "colors": { "base": "#2a0845", "shade": "#0a0316", "warm": "#e0259f", "icon": "#3ce8ff" },
  "missing": ["covers/missing-1.svg", "covers/missing-2.svg", "covers/missing-3.svg"],
  "unmatched": ["covers/unmatched-1.svg", "covers/unmatched-2.svg"]
}
```

- `colors` redraws RomM's art in your colors: `base` is the backdrop, `shade` and `warm` the two shapes, `icon` the icon. Leave any out to keep RomM's.
- `missing` and `unmatched` replace the art with your own images, up to 8 of each (`.svg`, `.png`, `.webp` or `.jpg`; 600 by 800 pixels, or that shape, works best). Each game always gets the same one, picked from its name, so a library mixes them instead of repeating one tile. RomM paints the game's title over the middle, darkened slightly, so keep important detail away from the center.

Branding previews the first `missing` image at the end of each pack's artwork, or a sketch in your `colors` when there is none. Every built-in pack ships its own covers, which make good starting points.

## Tags and the Accessibility label

`tags` is a list of up to 8 short lowercase words (letters, digits and dashes), such as `["accessibility", "retro"]`. Branding gives a pack tagged `accessibility` a colored **Accessibility** label, lists it with the accessibility themes near the top, and puts it in Random's accessibility group, which administrators can include in or leave out of Random's draw. Use the tag only for a pack built for accessibility, such as the built-in `contrast-dark`, `contrast-light` and `signal`; see [Readable colors](#readable-colors) for what they meet. Other tags are kept with the pack for now.

## Fonts

```json
"fonts": [
  { "family": "Inter", "src": "fonts/Inter-Variable.woff2", "weight": "100 900", "style": "normal" }
],
"tokens": {
  "common": { "--r-font-family-sans": "Inter, system-ui, sans-serif" }
}
```

`src` is a `.woff2`, `.woff`, `.ttf` or `.otf` file inside the pack. Declaring a font only loads it; point a token at it. `--r-font-family-sans` sets nearly all text, headings included, and `--r-font-family-mono` sets code-style text. `--r-font-family-display` is barely used by the current RomM release, so setting it alone changes almost nothing. Check a font's license before shipping it in a pack.

## Custom CSS

For changes tokens can't make, such as a different layout, a hidden element or an animation, add a CSS file:

```json
"extraCss": "custom.css"
```

Everything in it applies only while your theme is active: the compiler wraps the file in `:root[data-romm-theme="<id>"] { ... }`, so plain selectors match inside the page:

```css
/* Show only the logo mark in the top bar, without the wordmark */
.r-v2-nav__logo-word {
  display: none;
}

/* Only in light mode: & is the page's root element, which carries the mode class */
&.r-v2-light .r-v2-nav-bar {
  border-bottom: 2px solid var(--r-color-brand-primary);
}
```

Tips:

- Find class names with your browser's developer tools. RomM's v2 components use readable names starting with `.r-v2-`. Ignore the `data-v-...` attributes, which change with every build.
- Use tokens inside your CSS (`var(--r-color-brand-primary)`), so the CSS keeps working with your token overrides and in both modes.
- Your selectors already outrank most of RomM's own because of the theme wrapper; add `!important` only if a rule still loses.
- Custom CSS isn't checked against new RomM releases the way tokens are. If a release renames a class your CSS uses, that rule silently stops matching. Prefer tokens wherever they can do the job.

## The v1 interface

RomM's older interface (users can still switch to it) isn't themed beyond colors. `vuetify.dark` and `vuetify.light` set its palette with hex colors:

```json
"vuetify": {
  "dark": { "primary": "#38bdf8", "background": "#0b1020", "surface": "#111a33" },
  "light": { "primary": "#0369a1" }
}
```

## What gets checked

When packs compile, each one is validated, and problems show in Branding with the key at fault:

- that the archive is a readable zip within the limits above, with no paths that leave it, no duplicate names and no links;
- the `id` format, and that it matches the archive's file name;
- every token name exists in this RomM release, and values contain no unsafe characters;
- every replaced file exists in the pack, sits inside the pack and keeps the original's extension; files under `/assets/emulatorjs`, `/assets/ruffle` and other player or library folders can't be replaced;
- fonts and the CSS file exist;
- `tags` are short lowercase words, and `covers` names colors as hex and images that exist inside the pack, with up to 8 of each kind.

A pack with problems is skipped; RomM keeps running with the other packs, and with its default look if the broken pack was the selected one.

## Trying a pack without a server

From a clone of this repository, the local preview serves a frontend build through the same nginx setup as the image, with your folder of `.zip` packs as the themes folder:

```bash
node themeable/dev/preview.mjs --packs-folder ./my-themes --default midnight
```

See the [README](../README.md#developing-the-module) for building the frontend first.

## Readable colors

Solid buttons draw white text on `--r-color-brand-primary`, so keep that color at a contrast of at least 3:1 with white, in both modes, and at least 3:1 against `--r-color-bg` so selected items stand out. Put bright neon or pastel shades in `--r-color-brand-accent` instead. The wordmark (`/assets/logotipo.svg`) sits on the page background in both modes, so give it a mid-tone or an outline that reads on dark and light alike. The login screen is always dark; `--r-color-canvas-bg-deep` tints its card. It still reads some light-mode tokens when a visitor uses light mode, so keep light-mode `--r-color-bg-elevated` and `--r-color-surface` translucent, as stock RomM does, rather than solid near-white.

For a pack aimed at accessibility, set solid text colors (`--r-color-fg-muted`, `--r-color-fg-faint` and the status colors) at 7:1 or better against `--r-color-bg`, and strengthen focus with `--r-color-focus`, `--r-focus-ring-width` (per input scope) and `--r-focus-ring-offset`. The built-in `contrast-dark`, `contrast-light` and `signal` packs are worked examples.

## Sharing a pack

A pack is one self-contained `.zip`: anyone running romm-themeable can upload it in Branding, or copy it into their themes folder, and select it.
