# RomM complete changelog

## v3.0.3 (_25-03-2024_)

- Fixed: Removed `PUID/GUID` environment variables. Instead, use the `user: "XXXX:XXXX"` entry in docker-compose to set the owner of newly created file/folders and mounted volumes

## v3.0.2 (_25-03-2024_)

> [!WARNING]
> RomM has been organized in `github` and `dockerhub`! New images will be upload to `rommapp/romm` repository on dockerhub and ghcr.

- Added: Famicon disk system to emulatorjs
- Added: Allow setting PUID/GUID/UMASK with environment variables
- Added: Re-added external redis support. You can now use an external redis instance with RomM by setting `REDIS_HOST` and `REDIS_PORT` in the env variables. If you have those variables currently set but want to use the internal one, you'll have to remove those them.

- Changed: Added scrolling to scan logs
- Changed: Disabled amiga emulator until bios support added
- Changed: Updated [docker-compose.example.yml file](https://github.com/rommapp/romm/blob/3.0.1/examples/docker-compose.example.yml) to match new dockerhub `rommapp` organization

- Fixed: Normalized IGDB search for better results
- Fixed: Player viewport to fit screen better
- Fixed: Safari downloads file names

## v3.0.1 (_13-03-2024_)

> [!WARNING]
> This hotfix requires a few changes:

- A new volume has to be bound to `/redis-data`, check the [docker-compose.example.yml file](https://github.com/rommapp/romm/blob/3.0.1/examples/docker-compose.example.yml)
- If you're seeing "Decompress Game Core" when trying to run games in EmulatorJS, you'll need to clear storage in your browser to clear IndexedDB

- Fixed: Integrated redis data persist. Check the [docker-compose.example.yml](https://github.com/rommapp/romm/blob/3.0.1/examples/docker-compose.example.yml)
- Fixed: Emulatorjs integration. Fixes #695
- Fixed: 404 for assets endpoint
- Fixed: Sqlite to mariadb migration
- Fixed: Async tasks not running and throwing errors
- Fixed: Sqlite to mariadb migration. Fixes #697 and #688
- Fixed: Multipart game selector when change between games

## v3.0.0 (_11-03-2024_)

- Highlight: [EmulatorJS player](https://github.com/rommapp/romm/wiki/EmulatorJS-Player): Play retro games in your web browser
- Highlight: Saves and states: Upload/downlaod game saves, and play them with EmulatorJS
- Highlight: More metadata: Extracts more information from IGDB, like release date, genres, related games, etc.
- Highlight: New license: Now licensed under AGPL-3.0 to promote community contributions

- Added: Manually trigger async tasks from the UI
- Added: New /stats endpoint to get library statistics
- Added: Multi-file roms now download with .m3u file
- Added: Small banner in UI when new version is available
- Added: Manual search now also checks alternative names

- Changed: Redis is now built into the image
- Changed: Dropped support for build-in SQLite database
- Changed: Faster search against IGDB API with better results
- Changed: New covers when game or cover art not found
- Changed: Improved build process and release tagging
- Changed: Improved error handling and logging

- Fixed: Validation is run on config.yml file to ensure compatibility
- Fixed: Downloading single file from multi-file roms
- Fixed: Compressing large files for download
- Fixed: Reworked the authetication system to reduce CSRF and login issues
- Fixed: Reconnect websockets on page reload to catch scan progress
- Fixed: Many other small bug fixes and improvements

## v2.3.1 (_08-01-2024_)

- Fixed: Deleting platforms now works properly when having "orphaned" platforms.

- Changed: Platforms can only be deleted from RomM's database. Checkbox to delete platform from filesystem have been removed.

## v2.3.0 (_08-01-2024_)

- Added: Now `platforms` can be `deleted` from the gallery. Closes [#567](https://github.com/rommapp/romm/issues/567)
- Added: Support for `switch` `updates` and `DLC` files. Closes [#554](https://github.com/rommapp/romm/issues/554)
- Added: Additional Webrcade resources by @Casuallynoted.
- Added: `Exclusions` in `config` file now accepts `wildcards`. Check the [config.example.yml](examples/config.example.yml). Closes [#575](https://github.com/rommapp/romm/issues/575)

- Fixed: `Not identified` games are no longer being grouped when `group roms` option is enabled.
- Fixed: Changes in the `config` file from one to other platform are now more consistent. Closes [#567](https://github.com/rommapp/romm/issues/567)
- Fixed: Some other minor fixes.

- Changed: File extensions now can have up to `100` characters. Closes [#531](https://github.com/rommapp/romm/issues/531)
- Changed: Now files without extension are skipped during scan by @bfenty.
- Changed: Logs are now clearer.

## v2.2.1 (_02-01-2024_)

- Added: An option to group different regions of one game in the same entry in the `Control Panel`. Closes [#404](https://github.com/rommapp/romm/issues/404)

- Fixed: An error when scanning games with with `ps2 opl`, `switch titledb/productid` or `mame` format.
- Fixed: Updating roms of a custom platform folder.

- Changed: Now region and language tags are case insensitive to show `emojis`.

## v2.2.0 (_31-12-2023_)

- Added: Support for `productID` in the file name for `switch` titles.
- Added: Rom name sorting now sorts smarter, avoiding leading articles such `The` or `A`, like in `The Legend of Zelda`. Closes [#449](https://github.com/rommapp/romm/issues/449) and [#450](https://github.com/rommapp/romm/issues/450)
- Added: Support for file names with multiple `regions` and `languages`. Also uses `emojis` to display them. Closes [#473](https://github.com/rommapp/romm/issues/473)
- Added: A button to manually `run` all tasks. Closes [#437](https://github.com/rommapp/romm/issues/437)
- Added: Now if a game doesn't have cover, it will show a screenshot if available. Closes [#455](https://github.com/rommapp/romm/issues/455)
- Added: A little warning icon in the platform selector if the platform is not found by IGDB.
- Added: Now if a platform is not found by IGDB, the platform name is `titleized`. Ex: `pocket-challenge-v2 -> Pocket Challenge V2`. Closes [#486](https://github.com/rommapp/romm/issues/486)
- Added: A lot more icons!. Complete list at [PR-488](https://github.com/rommapp/romm/pull/488) and [PR-493](https://github.com/rommapp/romm/pull/493)
- Added: Support for support for AES/MVS. Closes [#503](https://github.com/rommapp/romm/issues/503)
- Added: [Helm Chart](https://artifacthub.io/packages/helm/crystalnet/romm) to deploy on Kubernetes by @psych0d0g
- Added: `Rescan unidentified` added to the scan view, allowing to rescan only those entries that IGDB couldn't identify in previous scans. Closes [#519](https://github.com/rommapp/romm/issues/519)
- Added: `Config file` visualization added to the new `Config` tab in the `Control Panel`. Partially implements some concepts of [#457](https://github.com/rommapp/romm/issues/457)

- Fixed: Now sorting by size in the gallery table view works as expected. Closes [#423](https://github.com/rommapp/romm/issues/423)
- Fixed: Now RomM is more responsive in more kind of devices.
- Fixed: Cover sizes are now standarized to have a more consistent gallery. Closes [#340](https://github.com/rommapp/romm/issues/340)
- Fixed: Improved detection for multiple extension files.
- Fixed: Now the `delete from filesystem` checkbox is reseted when the `delete` dialog is closed. Closes [#466](https://github.com/rommapp/romm/issues/466)
- Fixed: Single file roms now are properly downloaded from backend, fixing a potential security issue. Closes [#471](https://github.com/rommapp/romm/issues/471)
- Fixed: Now a new `scanned` game appears directly in the gallery without refreshing. Closes [#467](https://github.com/rommapp/romm/issues/467)
- Fixed: A lot more of small fixes.
- Fixed: Now the default theme is setup properly.
- Fixed: Scan for custom folders from the `scan` view. Closes [#501](https://github.com/rommapp/romm/issues/501)
- Fixed: Multi-part games download when any part of the game contains a `comma` in the name. Closes [#520](https://github.com/rommapp/romm/issues/520)

- Changed: Improved the docker `init scripts` handling by @psych0d0g.
- Changed: Now the `scan` can continue after failing finding roms for one platform. Closes [#460](https://github.com/rommapp/romm/issues/460)
- Changed: Logs improved a lot.

## v2.1.0 (_31-10-2023_)

- Added: `Scheduler` to run scheduled scans and `Watchdog` to perform scans when adding/renamed/deleted any rom from the filesystem. Added a lot of new environment variables to configure both features. Check the [readme.md](README.md#📅-scheduler) for an explanation of how to configure them.
- Added: new `REDIS_PASSWORD` environment variable to support secured redis with pasword. Closes [#412](https://github.com/rommapp/romm/issues/412)
- Added: New `Recently Added` section in the dashboard shows the last 15 added roms. Closes [#400](https://github.com/rommapp/romm/issues/400)

- Fixed: Upload rom feature is now working properly.
- Fixed: Fixed order roms by size in the gallery list view. Fixes [#423](https://github.com/rommapp/romm/issues/423)

- Changed: Now platforms without roms will be hidden in the drawer and the dashboard. Closes [#396](https://github.com/rommapp/romm/issues/396)

## v2.0.1 (_29-10-2023_)

- Fixed: An error that caused to show the wrong roms for one platform if user navigates directly to that platform from a rom details page. Fixes [#408](https://github.com/rommapp/romm/issues/408)

## v2.0.0 (_27-10-2023_)

- Added: User management system. Check the [docker-compose.example.yml](examples/docker-compose.example.yml) for all the needed changes and environment variables. Closes [#24](https://github.com/rommapp/romm/issues/24)
- Added: Gallery bulk selection. Closes [#50](https://github.com/rommapp/romm/issues/50)
- Added: Roms upload feature.
- Added: Custom cover art.
- Added: Custom name for `roms` folder throught the `ROMS_FOLDER_NAME` environment variable. Closes [#356](https://github.com/rommapp/romm/issues/356)
- Added: `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` as environment variables. `CLIENT_ID` and `CLIENT_ID` are deprecated and will be removed in future versions.
- Added: icons for more platforms: CD-i, 3DO, Neo Geo Pocket Color, Nintendo 64DD, Satellaview, Playdia, Pippin, Mac

- Fixed: some checks before renaming a rom to avoid breaking names. Closes [#348](https://github.com/rommapp/romm/issues/348)
- Fixed: A lot of other minor bugs.

- Changed: RomM internal port changed from `80` to `8080`.
- Changed: RomM docker image size reduced significantly.
- Changed: Improved scanning and IGDB requests returning first the exact match.
- Changed: Scan now times out at 4 hours to improve scans for larger libraries.
- Changed: Other minimal changes in platform icons.

## v1.10 (_15-08-2023_)

- Added: Rom admin menu added to roms in gallery. Closes [#28](https://github.com/rommapp/romm/issues/28)
- Added: Added ps2/opl naming convention support for roms scanning. Closes [#324](https://github.com/rommapp/romm/issues/324)

- Fixed: An error caused by the service worker that sometimes intercepts download requests and returns a bad response. Fixes [#297](https://github.com/rommapp/romm/issues/297)
- Fixed: Rom count in platform selector when deleting/scanning roms. Fixes [#325](https://github.com/rommapp/romm/issues/325)

- Changed: Improved scanning and IGDB requests logs. Fixes [#317](https://github.com/rommapp/romm/issues/317)
- Changed: Improved downloading process. Fixes [#332](https://github.com/rommapp/romm/issues/332)

## v1.9.1 (_01-08-2023_)

- Added: RomM logs are now stored in `/romm/logs` in docker and path can be binded in docker-compose. Check [docker-compose.example.yml](examples/docker-compose.example.yml). Solves [#303](https://github.com/rommapp/romm/issues/303)

- Fixed: multipart roms scanning.
- Fixed: Now platforms folders are case insensitive, allowing to have them lowercase or uppercase. Solves [#282](https://github.com/rommapp/romm/issues/282)
- Fixed: Fixed a bug that caused the platforms drawer to dissapear after scan.

## v1.9 (_31-07-2023_)

- Added: Region and revision system is now more robust and flexible. Solves [#301](https://github.com/rommapp/romm/issues/301). Check [tags support](https://github.com/rommapp/romm#-tags-support)

- Changed: Libraries are now paginated to improve performance in large collections. Solves [#89](https://github.com/rommapp/romm/issues/89) and [#280](https://github.com/rommapp/romm/issues/280)

- Fixed: Downloads are now managed in the backend, allowing the web browser to manage the download progression and avoiding memory overload. Solves [#266](https://github.com/rommapp/romm/issues/266)

## v1.8.4 (_19-05-2023_)

- Fixed: broken scan in multi part games. Solves [#262](https://github.com/rommapp/romm/issues/262)

## v1.8.3 (_17-05-2023_)

- Added: platforms to home page.
- Added: the scan log in real time in the scan section.
- Added: fast scan button in the gallery to direct scan the current platform. Solves [#250](https://github.com/rommapp/romm/issues/250)
- Added: Game and Watch support. Partially solves [#245](https://github.com/rommapp/romm/issues/245)
- Added: Amstrad CPC support. Partially solves [#245](https://github.com/rommapp/romm/issues/245)
- Added: Game and Gear support. Partially solves [#245](https://github.com/rommapp/romm/issues/245)
- Added: PC-98 support. Partially solves [#245](https://github.com/rommapp/romm/issues/245)
- Added: Pokemini support. Partially solves [#245](https://github.com/rommapp/romm/issues/245)
- Added: DOOM support. Partially solves [#245](https://github.com/rommapp/romm/issues/245)

- Fixed: A bug that caused scan to run twice. Solves [#221](https://github.com/rommapp/romm/issues/221)
- Fixed: Improved RomM initial setup logs for bad folder structure configurations. Solves [#217](https://github.com/rommapp/romm/issues/217)
- Fixed: Improved gallery loading when switching between view modes.

## v1.8.2 (_09-05-2023_)

- Added: Atari 2600 support added. Solves [#224](https://github.com/rommapp/romm/issues/224)
- Added: Atari 7800 support added. Solves [#226](https://github.com/rommapp/romm/issues/226)
- Added: Atari 5200 support added. Solves [#225](https://github.com/rommapp/romm/issues/225)
- Added: Sega 32X support added. Solves [#223](https://github.com/rommapp/romm/issues/223)
- Added: Nintendo Virtual Boy support added. Solves [#222](https://github.com/rommapp/romm/issues/222)

- Fixed: Potentially malformed urls for covers and screenshots from IGDB. Solves [#216](https://github.com/rommapp/romm/issues/216)
- Fixed: Potentially scan fail with some games with large names. Solves [#229](https://github.com/rommapp/romm/issues/229)

## v1.8.1 (_27-04-2023_)

- Added: Now it is possible to search a rom match by Name and by ID. Solves [#208](https://github.com/rommapp/romm/issues/208)
- Added: Now screenshots are displayed in screenshots tab (Complete scan needed in order to fetch screenshots from IGDB). Partially solves [#57](https://github.com/rommapp/romm/issues/57)
- Added: Now more rom properties can be manually edited. Solves [#140](https://github.com/rommapp/romm/issues/140)

## v1.8 (_25-04-2023_)

- Added: Home screen.
- Added: Config option to associate custom system folders to platforms (Complete scan needed). Check [config.yml](docker/config.example.yml) example. Solves [#152](https://github.com/rommapp/romm/issues/152).
- Added: Sega Saturn and Master System support added. Check [platforms support](https://github.com/rommapp/romm#platforms-support). Solves [#194](https://github.com/rommapp/romm/issues/194).
- Added: Progress bar when games are being downloaded.

- Changed: Routes to different RomM sections and games changed now allow share direct links to platforms and games.
- Changed: RomM now can scan subdirectories in a multi-part game. Solves [#179](https://github.com/rommapp/romm/issues/179).
- Changed: Settings and Scan sections are now in the main drawer menu.
- Changed: Some UI changes.

- Fixed: Code base stability and speed improved.

## v1.7.1 (_15-04-2023_)

- Added: New UI feel with the new RomM color palette

- Changed: Roms size is now human readable

- Fixed: A bug where multi file roms could break the scan if the rom name have a dot.

## v1.7 (_14-04-2023_)

- Added: More options and flexibility to prevent files/folders to be scanned. Check [config.yml](docker/config.example.yml) example
- Added: Config file example added to docker/config.example.yml

- Changed: Rom details page revamped
- Changed: RomM logo revamped

## v1.6.5 (_12-04-2023_)

- Added: Multiple games gallery display modes

- Changed: Some fixes and improvements

## v1.6.4 (_12-04-2023_)

- Added: Now RomM allows to fix missmatched games by searching by IGDB id manually
- Added: WonderSwan and WonderSwan Color support added

## v1.6.3 (_12-04-2023_)

- Added: Support for multi file games: Now RomM can scan a folder with the game name and all of its files inside the folder. No need to match the folder with the files inside. Download feature can download a zip with the entire game and all of the files or just the desired ones.
- Added: Some UI tweaks

## v1.6.2 (_04-04-2023_)

- Added: Support for commodore64

- Fixed: Searching in IGDB for games in not supported platforms doesn't raise an error anymore

## v1.6.1 (_04-04-2023_)

- Added: Now sqlite database location needs to be binded to `/romm/database`. Check [docker-compose](examples/docker-compose.example.yml) example.
- Added: Now resources location (games cover) needs to be binded to `/romm/resources`. Check [docker-compose](examples/docker-compose.example.yml) example.
- Added: More platforms support. Check [platforms support](https://github.com/rommapp/romm#platforms-support)
- Added: Now RomM version appears in the bottom of the settings panel

- Fixed: Download feature is now fixed for RomM structucture 1

- Changed: Library path binding changed from `/library` to `/romm/library`. Check [docker-compose](examples/docker-compose.example.yml)

## v1.6 (_01-04-2023_)

- Added: Smart scan: now RomM will only scan the changes in the filesystem, making the scan process too much faster. Added an option to force a full scan.
- Added: Now game files can be renamed after the name matched in IGDB, keeping the tags.

## v1.5.1 (_31-03-2023_)

- Fixed: Delete game now works properly

## v1.5 (_30-03-2023_)

> [!WARNING]
> In order to make the new features to work, it is mandatory this time to drop all the database. This will only make you need to re-scan, but you won't lose the cover changes or file changes you made. I apologize for the inconveniences this may cause, as this is a new software, it may change a little bit the first weeks, at least until I can develop a proper way to migrate between versions. I hope you can understand these initial wipes in order to make a better tool.

- Added: Now RomM folder structure is more flexible to match two different patrons by priority. This change makes RomM **Emudeck** compatible at least with single file games platforms. Check [folder structure](readme.md#⚠️-folder-structure)
- Added: Added config file support to exclude folders and specific extension files to be scanned. Config file can be binded to `/romm/config.yml` .To reload config file RomM reload is needed. Check [config](readme.md#configuration).
- Added: Added tags support for region, revision/version and generic tags. Tags must have the right prefix to allow RomM scan them properly. Check [tags](readme.md#📑-tags-support).

## v1.4.1 (_29-03-2023_)

- Added: Now you can use your games tags (like (USA) or (rev-1)) to filter in the gallery

## v1.4 (_29-03-2023_)

- Added: Gamecube support [platforms support](https://github.com/rommapp/romm#platforms-support)
- Added: PC support added (only for single file games like zip, iso, etc) [platforms support](https://github.com/rommapp/romm#platforms-support)

- Changed: Now delete game only deletes it from RomM gallery. To delete it from the filesystem too you need to allow it with the checkbox.

## v1.3 (_29-03-2023_)

**`Breaking change`** - **This breaking change only applies for mariaDB users**:

Some users reported errors when scanning files with large names because file_names are limited to 100 characters in the database. As I want to give as much flexibility as possible I changed some database columns.

If you didn't make a lot of manual changes you can just get rid of the database and recreate it, scanning your library again. If you did some changes and don't want to lose the progress, you should do this changes manually from the mariadb container (or wherever you have your mariadb database) since there is not any kind of CLI for this migration.

I am so sorry for any inconvenience this can generate.

Columns to modify (examples in case that you set it with database name as romm, in other case just change the database name in the {db_name}.roms part):

```sql
 alter table romm.roms modify column file_name varchar(500);
 alter table romm.roms modify column file_name_no_ext varchar(500);
 alter table romm.roms modify column name varchar(500);
 alter table romm.roms modify column r_slug varchar(500);
 alter table romm.roms modify column p_slug varchar(500);
 alter table romm.roms modify column path_cover_l text;
 alter table romm.roms modify column path_cover_s text;
 alter table romm.platforms modify column slug varchar(500);
 alter table romm.platforms modify column name varchar(500);
 alter table romm.platforms modify column path_logo text;
```

## v1.2.2 (_28-03-2023_)

- Added: Notification added when downloading a game

- Changed: Database name when using mariadb now can be changed with the new variable DB_NAME. Check [docker-compos.example.yml](https://github.com/rommapp/romm/blob/master/examples/docker-compose.example.yml)

- Fixed: Potential password error when using mariadb if the password have special characters
- Fixed: Some other bugs

## v1.2 (_28-03-2023_)

- Added: SQLite support
- Added: Dreamcast support (<https://github.com/rommapp/romm#platforms-support>)

- Changed: SQLite is now the database by default if ROMM_DB_DRIVER is not set. Check [docker-compos.example.yml](https://github.com/rommapp/romm/blob/master/examples/docker-compose.example.yml)
- Changed: Platforms and games are now shown by alphabetical order

## v1.1 (_27-03-2023_)

- Added: Game names parentheses are now omitted when searching game in IGDB, allowing game names to have tags.

## v1.0 (_27-03-2023_)

- Birth of RomM
