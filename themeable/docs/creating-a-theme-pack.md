# Creating a theme pack

A theme pack is a folder with a `theme.json` file and any artwork, fonts or CSS it uses. RomM compiles it into a stylesheet plus replacement files, and the theme applies to RomM's v2 interface (and, for colors only, the older v1 interface).

## Where packs live

| Location | Used for |
| --- | --- |
| The themes folder on the host, mapped to `/romm/themes` in the container | Your own packs. Add or edit them here, then use **Administration → Branding**. |
| `themeable/packs/` in this repository | Built-in packs that ship inside the image: `phosphor`, `handheld`, `neon`, `cabinet`, `carbon`, `aurora` and `ember`. A pack in the themes folder with the same id replaces the built-in one. |

Each pack is one folder, and the folder name must equal the pack's `id`:

```
themes/
  themeable.json          ← written by Branding: the server's selected theme
  midnight/
    theme.json
    assets/
      isotipo.svg
      auth_background.svg
    fonts/
      Inter-Variable.woff2
    custom.css
```

## Your first pack

1. Create `themes/midnight/theme.json`:

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

2. In RomM, open **Administration → Branding** and click the refresh button. Midnight appears in the list; if anything in it is wrong, the entry says **Can't be used** and lists each problem.
3. Click **Preview** to open RomM with the theme in a new tab, without changing anything for anyone else.
4. Choose Midnight and click **Save changes**. Reload the page to see it.

To change the pack later, edit its files and click **Save changes** again; saving recompiles every pack from the folder.

## theme.json reference

[`theme.example.json`](theme.example.json) sets every option below: each token at its stock value, the v1 palette, every replaceable file, every favicon, a font, the browser color and custom CSS. Copy the parts you want into your own `theme.json` and delete the rest; the file paths in it show where each replacement would go in your pack, but the files themselves aren't included. It is regenerated for every RomM release, so it always matches the current one.

| Key | Required | What it does |
| --- | --- | --- |
| `id` | yes | Lowercase letters, digits and dashes, up to 64 characters, matching the folder name. `none`, `default`, `index` and `stock` are reserved. |
| `name` | yes | Shown in Branding and the theme picker. |
| `description`, `author`, `version` | no | Shown in Branding and the theme picker. |
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

`rootFiles` replaces the browser-tab icons. Allowed keys are `/favicon.ico`, `/favicon.svg`, `/favicon-16x16.png`, `/favicon-32x32.png`, `/apple-touch-icon.png`, `/android-chrome-192x192.png`, `/android-chrome-512x512.png` and `/safari-pinned-tab.svg`. They come from the **server's** selected theme, not each visitor's, because browsers fetch them without running any page code. Browsers cache favicons aggressively, so a change can take a while to show.

## Fonts

```json
"fonts": [
  { "family": "Inter", "src": "fonts/Inter-Variable.woff2", "weight": "100 900", "style": "normal" }
],
"tokens": {
  "common": { "--r-font-family-sans": "Inter, system-ui, sans-serif" }
}
```

`src` is a `.woff2`, `.woff`, `.ttf` or `.otf` file inside the pack. Declaring a font only loads it; point `--r-font-family-sans` (body text) or `--r-font-family-display` (headings) at it to use it. Check a font's license before shipping it in a pack.

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

- the `id` format, and that it matches the folder name;
- every token name exists in this RomM release, and values contain no unsafe characters;
- every replaced file exists in the pack, sits inside the pack folder and keeps the original's extension; files under `/assets/emulatorjs`, `/assets/ruffle` and other player or library folders can't be replaced;
- fonts and the CSS file exist.

A pack with problems is skipped; RomM keeps running with the other packs, and with its default look if the broken pack was the selected one.

## Trying a pack without a server

From a clone of this repository, the local preview serves a frontend build through the same nginx setup as the image, with your folder as the themes folder:

```bash
node themeable/dev/preview.mjs --packs-folder ./my-themes --default midnight
```

See the [README](../README.md#quick-start) for building the frontend first.

## Readable colors

Solid buttons draw white text on `--r-color-brand-primary`, so keep that color at a contrast of at least 3:1 with white, in both modes, and at least 3:1 against `--r-color-bg` so selected items stand out. Put bright neon or pastel shades in `--r-color-brand-accent` instead. The wordmark (`/assets/logotipo.svg`) sits on the page background in both modes, so give it a mid-tone or an outline that reads on dark and light alike. The login screen is always dark; `--r-color-canvas-bg-deep` tints its card.

## Sharing a pack

A pack is self-contained: zip its folder, and anyone running romm-themeable can unzip it into their themes folder and select it in Branding.
