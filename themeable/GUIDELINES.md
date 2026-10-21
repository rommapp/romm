# romm-themeable project guidelines

These rules apply to all work on romm-themeable, in every release, by people and by agents. They sit on top of upstream RomM's [`AGENTS.md`](../AGENTS.md): upstream's code-style rules still apply (English only, no em-dashes, short comments that explain why, one home per value, tests travel with code, Trunk linting, never `--no-verify`, never commit secrets). Where upstream's rules on branches, pushes and pull requests conflict with this file, this file wins, because they describe contributing to `rommapp/romm`, not running this fork.

The owner is Micaiah Fonken (GitHub `Stealthx3`). "Approval" below always means his explicit approval in the conversation, given for that specific action. An approval is never carried over to a later push, merge or build.

## Commits, pushes and builds

- **Commit locally as you go.** Commit changes to the local working copy as they are made, in small, focused commits with clear messages. Don't hold work back for one big commit at the end of a phase.
- **Push only at the end of a major phase, and only with approval.** A phase is finished when its unit tests (`npm test`), visual check (`npm run visual`) and patched-source check pass and its README and guide updates are done. Then ask the owner to approve the push, listing the commits it contains. Nothing is pushed while a phase is in progress.
- **Build containers only at the very end, and only with approval.** No container image is built or published, locally or in CI, until every phase of the current development plan is complete. Then ask the owner to approve the build. This includes `docker build`, `docker compose build`, running the `themeable` workflow by hand, and any merge or push to `main` (see below).
- **Never rewrite published history.** No force-pushes, rebases of pushed commits or deleted remote branches without the owner asking for it.

## Branches

| Branch | Holds | Rules |
| --- | --- | --- |
| `main` | The released fork: upstream RomM plus this module | Every push that touches the module builds and publishes `ghcr.io/stealthx3/romm-themeable:<ROMM_VERSION>` and `:latest`, so it only receives a finished release, merged with approval |
| `upstream` | A clean copy of stock RomM release commits | Moved only by the `themeable upstream release` workflow. Never commit to it, and never use GitHub's **Sync fork** button |
| `release/<version>` | Development of one release, for example `release/1.1.0-5.4.0` | Created from `main` when a plan starts; receives the phase pushes; tests, source check and visual check run on it, the image job doesn't |
| `themeable-upstream/<tag>` | Automated adoption of an upstream release | Created and managed by the workflow; don't work on it by hand |

The local development folder is `/mnt/FileDrive/Personal/Projects/Git/romm-themeable`. Switch it to the current `release/<version>` branch while a plan is in progress.

## Versions

Releases are numbered `<major>.<feature>.<fix>-<RomM version>`:

- `major` goes up by one for each RomM release adopted;
- `feature` goes up by one for each feature update;
- `fix` goes up by one for each bug-fix or optimization update;
- the suffix is the RomM release the fork is built on, as in `themeable/ROMM_VERSION`.

The module's own version (`<major>.<feature>.<fix>`) lives in `themeable/package.json`. Change it only on the release branch, never directly on `main`.

## Development plans

- Each release starts from a written development plan, kept in `themeable/docs/plans/<version>.md` and in the claude.ai Project for this repository. The plan in the repository is the copy agents work from.
- Phases are built in the plan's order. Each phase ends with its checks passing, its documentation updated and a push request to the owner.
- Anything the plan doesn't cover, or that it lists as deferred, waits for a later release. If work seems to need something outside the plan, stop and ask rather than widening the scope.
- When a decision in the plan changes during the work, update the plan in the same commit as the change.

## Staying independent of upstream

- Everything the module owns lives in `themeable/`, plus the `themeable*` workflows in `.github/workflows/`, the banner at the top of the root `README.md`, the root `docker-compose.yml` and the root `CLAUDE.md`. Keep it that way: new module files go in `themeable/`.
- Change RomM's own files only through `themeable/overlay/` (new files) and `themeable/patches/` (anchored edits), applied at build time. Don't edit upstream files in place, so each RomM release merges cleanly.
- Each upstream release is adopted by the `themeable upstream release` workflow: merge, compatibility check, catalog and example refresh, visual and source checks. Fixes for a release that breaks the module go into the module, not into upstream's code.

## Unattended operation

The long-term goal is for module development and downstream patching to run without anyone stepping in, with the owner auditing the results. In practice:

- Prefer an automated check over a manual step. When something has to be checked by hand twice, propose a script or test for it.
- Every failure should say what broke and where: a pack name, a patch name, a file and line. A workflow that can't finish opens an issue or leaves its pull request open as "needs attention" instead of failing silently.
- Reports (compatibility, visual, source) are written so the owner can audit them without rerunning anything.

## Module conventions

- **No dependencies.** The module runs on Node 20 or later with built-in modules only. Don't add npm packages to `themeable/`.
- **Shared values have one home.** Ids, cookie and storage names, URL parameters and preview slots live in `themeable/lib/client.mjs` and reach the browser files through the manifest. Reserved ids (`none`, `default`, and `random` from 1.1.0) are defined there only.
- **Never leave the server worse off.** Compiles build into a new folder and switch over with one atomic rename, under the compile lock and timeout. Anything that changes the themes folder (upload, rename, delete, convert) validates first, swaps in atomically and restores the previous state if the compile fails.
- **Uploaded and host-provided packs are untrusted.** Check sizes, entry counts, compression ratios and paths before reading anything, and keep every path inside its pack.
- **Built-in themes stay original.** Artwork in built-in packs is made for this project; don't copy existing logos, characters or other people's artwork into them.
- **Readable colors.** Built-in packs keep `--r-color-brand-primary` at 3:1 or better against white button text, and accessibility-focused packs aim at WCAG AAA (7:1) for body text.
- **Documentation moves with the code.** A change that affects admins, pack authors or developers updates `themeable/README.md`, `themeable/docs/creating-a-theme-pack.md` and any other guide it affects, in the same phase.

## Writing

Follow upstream's writing rules in all docs, comments and commit messages: plain English, no em-dashes, short sentences, describe the current behavior rather than the history of a change. Reasons for a change go in the commit message.
