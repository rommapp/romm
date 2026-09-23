# Storybook static assets (what gets copied on `storybook:build`)

RomM’s Storybook build output (`frontend/storybook-static/`, gitignored) is a **static site**. Anything configured in `staticDirs` in `.storybook/main.ts` is **copied verbatim** into that folder. If you publish Storybook (GitHub Pages, Chromatic, an internal static host), **every mounted file is public**.

`preview.ts` does **not** control static files. Only `staticDirs` and the Storybook/Vite dev server do.

---

## Threat model (what we are avoiding)

| Risk                                            | How it happens                                                                        | Mitigation                                                                                                                                                                                          |
| ----------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Whole `frontend/assets/` tree in the deploy** | `{ from: "../assets", to: "/assets" }`                                                | **Never** mount all of `assets/`. That directory includes logos, auth art, console themes, webrcade metadata, fonts, and (in dev/docker) can include **`assets/romm/`** symlinks to a user library. |
| **Story-only files under prod URLs**            | Putting test SVGs in `assets/platforms/` or serving fixtures at `/assets/platforms/…` | Story-only fixtures live under **`/storybook-fixtures/…`**, a URL prefix the **app never uses**.                                                                                                    |
| **Accidental secrets in fixtures**              | Dropping `.env`, dumps, or user data into `.storybook/public/`                        | No generic `public/` mount at `/`. Only **`/.storybook/fixtures/<category>/`** with a dedicated `to` path.                                                                                          |
| **Unbounded growth of deploy size**             | Mounting directories that change often                                                | Mount **one prod-shaped subtree** (`assets/platforms`) plus **tiny** fixture dirs.                                                                                                                  |

---

## Allowed mounts (see `main.ts`)

1. **`../assets/platforms` → `/assets/platforms`**
   - Same URL shape as production (`/assets/platforms/<file>`).
   - Only SVG/ICO (and attribution files) that ship with the repo under `frontend/assets/platforms/`.
   - Does **not** include `assets/romm/`, `assets/logos/`, `assets/auth_*`, etc.
   - **Not** part of the Vite `import.meta.glob` allowlist unless the file lives in that tree at build time. Files served here but absent from the glob are useful for **`src` override** stories only.

2. **`.storybook/fixtures/<category>` → `/storybook-fixtures/<category>`**
   - **Storybook-only.** Safe to publish: small, intentional test vectors.
   - One `staticDirs` row per category (platform icons, broken loaders, fake 404 HTML, etc.).
   - Import URLs from `.storybook/fixtures/urls.ts` in stories. **Do not import that module from app runtime** (`src/` except `*.stories.ts`).

---

## Scaling Storybook-only fixtures

To exercise loading edge cases (missing files, wrong `Content-Type`, slow assets, etc.) without touching prod URLs:

1. Create **`.storybook/fixtures/<category>/`** and add files there.
2. Add **one** `staticDirs` line in `main.ts`:

   ```ts
   { from: "./fixtures/<category>", to: "/storybook-fixtures/<category>" },
   ```

3. Export URL constants from **`.storybook/fixtures/urls.ts`** (group by category).
4. Reference those constants only from **`*.stories.ts`** / **`*.mdx`**.

All Storybook-only HTTP paths stay under the single prefix **`/storybook-fixtures/`**, which is easy to audit:

```bash
# From repo root: expect hits in .storybook/, *.stories.ts, and docs only
rg "storybook-fixtures" frontend
```

The app and Vite dev server do not mount `/storybook-fixtures/`; those URLs exist only in Storybook dev and in `storybook-static/` after `storybook:build`. You _could_ ban the string in `src/` via ESLint (`no-restricted-syntax` / custom rule); RomM relies on convention and review instead.

**Prod-shaped tests** (real allowlist paths, default fallback) still use the **`/assets/platforms`** mount only. Do not put throwaway files there just for stories.

---

## URL cheat sheet

| URL                                                      | In prod app?                                | In Storybook deploy?                              | Use in stories                             |
| -------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------- | ------------------------------------------ |
| `/assets/platforms/snes.svg`                             | Yes (if shipped)                            | Yes (from mount #1)                               | Allowlist **hit** via `slug="snes"`        |
| `/assets/platforms/non-cached-icon.svg`                  | Only if committed under `assets/platforms/` | Only if you add it there (avoid for tests)        | Prefer **`/storybook-fixtures/…`** instead |
| `/storybook-fixtures/platform-icons/non-cached-icon.svg` | **No**                                      | Yes (from mount #2)                               | Explicit `:src` / “not in glob” demos      |
| `/assets/platforms/default.ico`                          | Yes (fallback)                              | Yes **if** the file exists in `assets/platforms/` | Allowlist **miss** → fallback              |

---

## Adding a new fixture category

1. Add `.storybook/fixtures/<category>/` (keep each category small and purposeful).
2. Append a mount in `main.ts`: `to` must be `/storybook-fixtures/<category>` (same `<category>` as the folder name).
3. Add exports to `.storybook/fixtures/urls.ts`.
4. Use constants only from stories. Run `rg storybook-fixtures frontend` before merging.

Adding files to an **existing** category does not require a new `staticDirs` row.

## CI

`npm run storybook:build` produces the same static copy as a public host. Before publishing externally, run `storybook:build` locally and inspect `storybook-static/` for unexpected paths (`romm/`, `logos/`, `.env`, etc.). There should be **no** `storybook-static/assets/romm/` if mounts are correct.
