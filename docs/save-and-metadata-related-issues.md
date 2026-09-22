# Save / label / name / description issues (RomM)

Curated from [rommapp/romm issues](https://github.com/rommapp/romm/issues) via `gh issue list` and targeted searches (2026-09-22).  
**Scope:** save files and save states (names, labels, display, metadata on assets), plus closely related ROM/platform **title/description/naming** requests.

---

## A. Save & save-state identity and display

These are the issues most directly about **what a save/state is called**, **how it is labeled**, and **what the UI shows**.

| #                                                   | State  | Title                                                                            | Link                                        | Notes                                                                                                                                                                 |
| --------------------------------------------------- | ------ | -------------------------------------------------------------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [942](https://github.com/rommapp/romm/issues/942)   | Open   | Favorites & Labels for Saves & States                                            | https://github.com/rommapp/romm/issues/942  | Star/favorite plus user tags (`100%`, seed, route). Explicit alternative to rename/reorder.                                                                           |
| [2653](https://github.com/rommapp/romm/issues/2653) | Open   | Allow renaming Save/State Files                                                  | https://github.com/rommapp/romm/issues/2653 | Today: download, rename locally, re-upload.                                                                                                                           |
| [4320](https://github.com/rommapp/romm/issues/4320) | Closed | Saves and save states don't show the information RomM already has about them     | https://github.com/rommapp/romm/issues/4320 | **Frontend-only:** show emulator, exact timestamp, full filename (tooltip), save `content_hash`; unify state rows with save rows. Parent issue for #4419/#4418/#4420. |
| [4419](https://github.com/rommapp/romm/issues/4419) | Open   | Expose which slot and which disc a save state belongs to                         | https://github.com/rommapp/romm/issues/4419 | Add `slot`, `disc_file_id` to `StateSchema` (data largely already on server).                                                                                         |
| [4418](https://github.com/rommapp/romm/issues/4418) | Open   | Give save states a content_hash so clients can verify one without downloading it | https://github.com/rommapp/romm/issues/4418 | Parity with saves; needs migration/backfill.                                                                                                                          |
| [4420](https://github.com/rommapp/romm/issues/4420) | Open   | Show which device a save came from and where it's synced                         | https://github.com/rommapp/romm/issues/4420 | Origin device (FE) + populate `device_syncs` for browser users (BE).                                                                                                  |
| [3830](https://github.com/rommapp/romm/issues/3830) | Open   | My Library (save/state gallery)                                                  | https://github.com/rommapp/romm/issues/3830 | Cross-ROM view of saves/states; benefits from readable labels/metadata.                                                                                               |
| [3285](https://github.com/rommapp/romm/issues/3285) | Open   | Allow changing save files' core association                                      | https://github.com/rommapp/romm/issues/3285 | Emulator/core label on saves when wrong core picked.                                                                                                                  |
| [1993](https://github.com/rommapp/romm/issues/1993) | Closed | Save matching with external files                                                | https://github.com/rommapp/romm/issues/1993 | Predictable **paths/filenames** vs RomM id/timestamp layout; relates to #1908.                                                                                        |
| [1908](https://github.com/rommapp/romm/issues/1908) | Open   | Ludusavi Integration                                                             | https://github.com/rommapp/romm/issues/1908 | External save manager; naming/layout interoperability.                                                                                                                |
| [55](https://github.com/rommapp/romm/issues/55)     | Closed | Savefiles/states management                                                      | https://github.com/rommapp/romm/issues/55   | Original ask: match saves to game **names**, prompt to rename saves when ROM renamed.                                                                                 |
| [186](https://github.com/rommapp/romm/issues/186)   | Closed | ROM filename/savename correction                                                 | https://github.com/rommapp/romm/issues/186  | IGDB-driven **ROM + save filename** scheme; closed (region/version handled elsewhere).                                                                                |
| [1870](https://github.com/rommapp/romm/issues/1870) | Closed | Notes/Description for individual files                                           | https://github.com/rommapp/romm/issues/1870 | Per-file notes (ROM files), not save rows specifically.                                                                                                               |

### Related save issues (sync / paths, not primarily “labels”)

| #                                                   | State | Title                                                       | Link                                        |
| --------------------------------------------------- | ----- | ----------------------------------------------------------- | ------------------------------------------- |
| [3866](https://github.com/rommapp/romm/issues/3866) | Open  | Support directory-based saves (Wii U, 3DS) in Save Sync     | https://github.com/rommapp/romm/issues/3866 |
| [3977](https://github.com/rommapp/romm/issues/3977) | Open  | Retention Policy for save sync                              | https://github.com/rommapp/romm/issues/3977 |
| [4649](https://github.com/rommapp/romm/issues/4649) | Open  | GameCube Save Interoperability                              | https://github.com/rommapp/romm/issues/4649 |
| [4423](https://github.com/rommapp/romm/issues/4423) | Open  | missing_from_fs can never become true for a save or a state | https://github.com/rommapp/romm/issues/4423 |

---

## B. ROM / platform titles, descriptions, and metadata (library naming)

Separate from save rows, but matches “labels, descriptions, names” in the library UI.

| #                                                   | State  | Title                                                                                       | Link                                        | Notes                                                |
| --------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------- |
| [3021](https://github.com/rommapp/romm/issues/3021) | Open   | Add support of aliases, localized and alternative title                                     | https://github.com/rommapp/romm/issues/3021 | Display/search names beyond primary title.           |
| [2743](https://github.com/rommapp/romm/issues/2743) | Open   | Version Descriptions                                                                        | https://github.com/rommapp/romm/issues/2743 | Text describing ROM variants.                        |
| [4187](https://github.com/rommapp/romm/issues/4187) | Open   | Add a "Version" metadata field for pre-patched games and rom hacks                          | https://github.com/rommapp/romm/issues/4187 | Version label on hacks/patches.                      |
| [2485](https://github.com/rommapp/romm/issues/2485) | Open   | XML or JSON metadata                                                                        | https://github.com/rommapp/romm/issues/2485 | Sidecar metadata (title, description, tags) on disk. |
| [2747](https://github.com/rommapp/romm/issues/2747) | Closed | Add ability to export metadata to local files                                               | https://github.com/rommapp/romm/issues/2747 | Export/import gamelist-style metadata.               |
| [2363](https://github.com/rommapp/romm/issues/2363) | Closed | Edit metadata and video from igdb or other databases                                        | https://github.com/rommapp/romm/issues/2363 | Manual edit shipped (see `manual_metadata`).         |
| [2776](https://github.com/rommapp/romm/issues/2776) | Open   | Lock Metadata                                                                               | https://github.com/rommapp/romm/issues/2776 |
| [3469](https://github.com/rommapp/romm/issues/3469) | Open   | Metadata locking protection                                                                 | https://github.com/rommapp/romm/issues/3469 |
| [4255](https://github.com/rommapp/romm/issues/4255) | Open   | Metadata suggestions while editing metadata                                                 | https://github.com/rommapp/romm/issues/4255 |
| [4569](https://github.com/rommapp/romm/issues/4569) | Open   | Normalize HTML in scraped ROM summaries instead of storing the tags as plain text           | https://github.com/rommapp/romm/issues/4569 | **Description** field quality in UI.                 |
| [4002](https://github.com/rommapp/romm/issues/4002) | Open   | ScreenScraper "Update metadata" scan only fills in missing data, never refreshes stale data | https://github.com/rommapp/romm/issues/4002 |
| [3192](https://github.com/rommapp/romm/issues/3192) | Open   | Automatic scan assigns incorrect metadata (possible state bleed)                            | https://github.com/rommapp/romm/issues/3192 | Wrong **title/cover/description** assigned.          |
| [1865](https://github.com/rommapp/romm/issues/1865) | Open   | Rom renaming feature as an admin tool                                                       | https://github.com/rommapp/romm/issues/1865 | Bulk **ROM file naming**, not save display names.    |
| [4673](https://github.com/rommapp/romm/issues/4673) | Open   | Glyph descenders cut off in platform descriptions                                           | https://github.com/rommapp/romm/issues/4673 | UI/UX for **platform description** text.             |
| [4678](https://github.com/rommapp/romm/issues/4678) | Open   | Seeded permission groups are named "Viewer (legacy)" / "Editor (legacy)"                    | https://github.com/rommapp/romm/issues/4678 | Permission **group labels**, not saves.              |
| [3584](https://github.com/rommapp/romm/issues/3584) | Closed | Changing Platform Display Name Gives 422 Error Code                                         | https://github.com/rommapp/romm/issues/3584 | Platform **custom_name** display.                    |

---

## Suggested fix (product + engineering)

Treat this as **two layers**: (1) show what the server already knows, (2) let users add meaning on top without renaming files on disk.

### Phase 1 — Ship #4320 (no schema change)

Implement the closed issue’s frontend plan (or reopen/track as a PR):

- State rows match save rows: emulator chip, exact + relative time, screenshot in row layout.
- Tooltips / focus for full `file_name` in manage mode.
- `HashChip` for save `content_hash`.

**Unblocks:** telling states apart without new APIs; complements #2653 and #942.

### Phase 2 — Small API extensions (#4419, partial #4420)

- Add **`slot`** and **`disc_file_id`** to `StateSchema` (derive slot with existing `slot_from_state_filename()`).
- For saves: expose **`device_syncs`** (and resolve **`origin_device_id`**) to normal session users, not only device-scoped API keys.

**Unblocks:** “Disc 2, slot 3” and “synced to Deck” without user-chosen labels.

### Phase 3 — User-facing identity (#942 + #2653, one model)

Add optional columns on `saves` / `states` (or a shared `rom_assets` metadata table):

| Field          | Purpose                                                                          |
| -------------- | -------------------------------------------------------------------------------- |
| `display_name` | User label; **does not** rename `file_name` on disk (avoids sync/path breakage). |
| `notes`        | Short description (run notes, route, seed).                                      |
| `is_favorite`  | Sort to top (#942).                                                              |

API: `PATCH /api/saves/{id}`, `PATCH /api/states/{id}` with validation limits; v2 Save data tab inline edit or row menu.

**Why not filesystem rename only (#2653)?** Renaming files breaks hash-based dedup, device sync paths, and streaming slot parsing. **Display name + optional rename** (rename updates DB + moves file atomically) covers both audiences.

### Phase 4 — Library metadata (separate track)

ROM **title/description/tags** stay on the existing `manual_metadata` / provider pipeline (#3021, #2485, #4569). Do not overload save-state labels into ROM metadata.

---

## How to refresh this list

```bash
gh issue list --repo rommapp/romm --state open --search "save label OR save rename OR save state display" --limit 50 --json number,title,state,url
gh issue list --repo rommapp/romm --state open --search "metadata OR description OR rename OR display name" --limit 80 --json number,title,state,url
gh issue view 4320 --repo rommapp/romm
```

---

_Document generated for maintainer triage; issue states may change on GitHub._
