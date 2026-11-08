# Documentation checks: 2.0.5-5.4.1

Run by the `themeable-lab` agent (`.claude/agents/themeable-lab.md`). Each check takes one instruction from the published docs (**current**, the `main` branch) and its replacement (**proposed**, branch `release/2.0.5-5.4.1` from `themeable/test/doc-checks/proposed.bundle`). It records whether the current instruction is outdated and whether the proposed one works.

Paths below are relative to the clone being tested (`current/` or `proposed/`). `$VM` is the lab VM's address.

## Shared setup

Run once, after reverting to `clean`.

1. **Deployment.** In `current/`, copy `docker-compose.yml` to `/home/lab/deploy/`. Replace every `/path/to/...` with a folder under `/home/lab/deploy/` (create them; make `themes` writable by the container). Fill `DB_PASSWD` and `MARIADB_PASSWORD` with the same value, `MARIADB_ROOT_PASSWORD` with another, and `ROMM_AUTH_SECRET_KEY` with `openssl rand -hex 32`. Run `docker compose up -d` there and wait until `docker inspect -f '{{.State.Health.Status}}' romm` is `healthy`. This also exercises **C15**.
2. **Admin and token.** `POST http://$VM/api/users` with JSON `{"username":"lab","email":"lab@example.invalid","password":"<random>","role":"admin"}` creates the first admin. `POST http://$VM/api/token` with form fields `grant_type=password`, `username`, `password` and `scope` set to every scope the admin has (read them from `GET /api/users/me` after a session login, or from `backend/handler/auth/constants.py`) gives a bearer token. Use it as `$TOKEN` below.
3. **Module tools.** Checks that say "runtime" run `node themeable/scripts/runtime.mjs` in the clone, with `THEMEABLE_HOME=$PWD/themeable`, `THEMEABLE_PACKS_PATH=<a fresh temp folder>` and `THEMEABLE_RUNTIME_DIR=<a fresh temp folder>`.
4. **A minimal pack.** `midnight/theme.json` exactly as in step 1 of "Your first pack" in `themeable/docs/creating-a-theme-pack.md`, zipped with `zip -r midnight.zip midnight`.

## Checks

### C01 `$schema` URL (pack guide, "Your first pack")

- **Current:** the `$schema` URL in the guide's example. Run `curl -s -o /dev/null -w '%{http_code}' <url>`. Outdated if it isn't 200.
- **Proposed:** the URL in the proposed guide. Passes if it returns 200 and the body parses as JSON with `"$schema"` at the top level.

### C02 The v1 interface and pack artwork (pack guide, opening paragraph and "The v1 palette")

- **Current:** "the theme applies to RomM's v2 interface (and, for colors only, the older v1 interface)".
- **Steps:** with the deployment from setup, `grep -rn "isotipo.svg\|auth_background" frontend/src/views frontend/src/layouts` in `current/` to find the files v1 requests. Then `curl -s -b romm_theme=neon http://$VM/assets/isotipo.svg | sha256sum` and compare with `sha256sum themeable/packs/neon/assets/isotipo.svg`. Outdated if v1 requests that file and the response is Neon's.
- **Proposed:** "The older v1 interface gets the pack's artwork and tab icons wherever it uses the same files". Passes on the same evidence, plus `curl -s -b romm_theme=neon http://$VM/favicon.svg` matching `themeable/packs/neon/root/favicon.svg`.

### C03 Placeholder covers and `/assets/default/` (pack guide, "Artwork" table)

- **Current:** `/assets/default/*` is "Placeholder covers and the default avatar".
- **Steps:** `docker exec romm sh -c 'grep -rl "default/cover" /var/www/html/assets | head'`. Outdated if nothing in the served frontend references `default/cover`.
- **Proposed:** `/assets/default/user.svg` is the default avatar, and placeholder covers come from `covers`. Make a pack `avatar` whose `assets` maps `/assets/default/user.svg` to its own SVG, upload it (as in C04), then `curl -s -b romm_theme=avatar http://$VM/assets/default/user.svg` must return the pack's file. And `GET /api/themeable/branding` must list a `cover.url` for every built-in pack.

### C04 Upload size cap (pack guide, "Limits")

- **Current:** the guide's limits list. Outdated if it doesn't mention the upload cap and the cap exists.
- **Steps:** `head -c 21M /dev/urandom > big.bin`, zip it with `midnight/theme.json` into `big.zip` using `zip -0`, then `curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" -F file=@big.zip http://$VM/api/themeable/packs`. Expect 413. Upload `midnight.zip` the same way and expect 200 with `"ok": true`.
- **Proposed:** "An upload from Branding is also capped at 20 MB, set by `THEMEABLE_MAX_UPLOAD_MB`". Passes if the 21 MB upload gets 413 and, after setting `THEMEABLE_MAX_UPLOAD_MB=30` and `docker compose up -d`, the same upload no longer gets 413.

### C05 Pack id and file name (pack guide, end of "Your first pack")

- **Current:** "The pack's id comes from `theme.json`, not the archive's name".
- **Steps:** copy `midnight.zip` into the themes folder as `other-name.zip` and `POST /api/themeable/branding/rescan`. Outdated if the pack is refused or listed with a problem because the name doesn't match.
- **Proposed:** "For an upload, the pack's id comes from `theme.json` ... A pack copied into the themes folder by hand must already be named `<id>.zip`". Passes if the upload of a file named `other-name.zip` installs as `midnight.zip`, and a hand-copied `midnight.zip` is listed without problems.

### C06 Replacing a built-in pack (README "Uploading a pack" and "Built-in themes"; pack guide)

- **Steps:** make a pack with id `neon` (copy `midnight/`, change `id` and `name`). Upload it: record the response. Then copy it into the themes folder as `neon.zip`, rescan, and read the `neon` entry's `source` in `GET /api/themeable/branding`.
- **Current:** the README says both that an upload can't replace a built-in pack and that a themes-folder pack with the same id replaces one. Outdated (contradictory) if the upload is refused and the hand copy replaces the built-in pack without the docs explaining the difference.
- **Proposed:** both behaviours stated side by side. Passes if the upload is refused and the hand copy shows `source: "folder"`.

### C07 When folder packs are converted (pack guide, "Folder packs"; README "Folder packs")

- **Current:** converted "when the container starts".
- **Steps:** with the container running, copy the unzipped `midnight/` folder into the themes folder (remove any `midnight.zip` first), then `POST /api/themeable/branding/rescan` without restarting. Outdated if `midnight.zip` appears and the folder moves to `.converted/midnight/` without a restart.
- **Proposed:** "at start-up or the next recompile". Passes on the same result.

### C08 Archive limits wording (pack guide, "Limits")

- **Current:** "at most 2,000 files" and "a compression ratio of at most 100:1".
- **Steps (runtime `--validate-archive`):**
  1. 1,999 one-byte files plus `theme.json`, inside one top-level folder, so 2,001 entries counting the folder. Outdated if it's refused for too many entries.
  2. A pack whose `theme.json` sits next to a 2 MB file of zeros, padded with enough random bytes that the whole archive's ratio stays under 100:1 while the zeros alone are over 100:1. Outdated if it's accepted.
- **Proposed:** "at most 2,000 entries (files and folders)" and "100:1 for the whole archive". Passes if both results match that wording.

### C09 Pack rules added to the guide (proposed only)

Runtime `--validate-archive` on variants of `midnight`, each expected as stated:

| Variant | Expected |
| --- | --- |
| id `-midnight` | refused |
| id `index`, and id `stock` | refused (reserved) |
| name with a tab character | refused |
| tags `["1retro"]`, a 33-character tag, `["retro","retro"]` | each refused |
| tags `["retro"]` | accepted |
| a cover `covers/missing-1.jpeg` listed under `covers` | accepted |
| `assets` mapping `/assets/platforms/vsmile.png` to a `.png` | accepted |
| an asset SVG containing `<handler>` | refused |
| `extraCss` containing `<style>` | refused |

The proposed guide passes if every row matches. Note any row where the current guide is silent.

### C10 Zipping on Windows (pack guide, "Zipping a pack")

Needs a Windows guest. Look for one with `virsh -c qemu:///system list --all`. If none exists, mark **not run** and list it for the owner.

- **Current:** `Compress-Archive -Path midnight -DestinationPath midnight.zip` in PowerShell.
- **Steps:** in Windows PowerShell 5.1 and in PowerShell 7 if installed, zip `midnight/` that way, copy each archive to the lab VM, and run runtime `--validate-archive`. Outdated if the 5.1 archive is refused for "a backslash in the path".
- **Proposed:** the PowerShell 7 command and the File Explorer route. Passes if both archives validate.

### C11 Adopting a release by hand (README, "Staying current with RomM")

Local only: use a bare repository in the VM as `origin`, never GitHub.

- **Current:** "Merge the release tag into `main` ... and push". Outdated if following it commits the version change directly on `main`, which `GUIDELINES.md` forbids. Record the conflict; don't run the push.
- **Proposed:** follow the four proposed steps exactly, using tag `5.4.1` (already merged, so the merge is a no-op) and pushing to the local bare repository. Passes if every command runs as written, `npm run check-upstream` exits 0, and `npm run example -- --check` passes.

### C12 Which pushes run the `themeable` workflow (README table; GUIDELINES branches table)

Inspection only; the VM can't run GitHub Actions.

- **Current:** "Every push to `main` or a `release/**` branch". Outdated if `.github/workflows/themeable.yml` has a `paths` filter.
- **Proposed:** the listed paths and docs-only exclusions. Passes if the wording matches `on.push.paths` in the proposed `themeable.yml` exactly. The live confirmation is the first push of `release/2.0.5-5.4.1`, which the owner approves separately.

### C13 Repository setup (README, "Repository setup")

On the host, only if `gh auth status` succeeds; read-only API calls.

- `gh api repos/Stealthx3/romm-themeable --jq .has_issues`
- `gh api repos/Stealthx3/romm-themeable/branches/main/protection` (a 404 means unprotected)
- `gh api repos/Stealthx3/romm-themeable/rulesets`

Report each value. The proposed steps 3 and 4 are still needed if issues are off or `main` is unprotected.

### C14 Image tags (README "Deploying"; compose file)

- `docker manifest inspect` (or `docker buildx imagetools inspect`) `ghcr.io/stealthx3/romm-themeable:5.4.1`, `:2.0.1-5.4.1`, `:2.0.4-5.4.1` and `:latest`.
- **Current:** the examples use `:2.0.1-5.4.1`. Outdated if that tag isn't the newest release, which is the case if `:5.4.1` matches `:2.0.4-5.4.1` instead.
- **Proposed:** the examples use `:<module>-5.4.1`, and the compose comment says `2.0.5-5.4.1`, which exists only after the 2.0.5 merge. Passes if `:5.4.1`, `:latest` and `:2.0.4-5.4.1` share one digest today.

### C15 First start (README, "Deploying")

Covered by shared setup step 1, following the README's **First start** paragraph as written. Passes if the container is healthy and `http://$VM/` serves RomM's setup page. The wording is unchanged in the proposed branch.

### C16 Previewing without Docker (README, "Developing the module")

Run the README's five-line recipe in `proposed/` (it's unchanged from `current/`), with `--packs-folder` pointing at a folder holding `midnight.zip` and `--default midnight`. Passes if `http://localhost:8099/login` and `/themeable/` load and the login page has `data-romm-theme="midnight"` on `<html>`.
