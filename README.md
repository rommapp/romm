<div align="center">

  <img src=".github/resources/romm_complete.svg" height="220px" width="auto" alt="romm logo">
  
  <h3 style="font-size: 25px;">
    A beautiful, powerful, self-hosted rom manager.
  </h3>
  <br/>

[![license-badge]][license-badge-url]
[![release-badge]][release-badge-url]
[![docker-pulls-badge]][docker-pulls-badge-url]

[![discord-badge]][discord-badge-url]
[![unraid-badge]][unraid-badge-url]
[![wiki-badge]][wiki-url]

  </div>
</div>

# ⚠️ Breaking changes in version 3.0 ⚠️

Version 3.0 introduces exciting new fetures that require some changes to how RomM is setup and configured. **If you're currently running a 2.x version, please review the [migration guide](https://github.com/zurdi15/romm/wiki/Upgrading-to-3.0) before upgrading.**

# Overview

RomM (ROM Manager) allows you to scan, enrich, and browse your game collection with a clean and responsive interface. With support for multiple platforms, various naming schemes and custom tags, RomM is a must-have for anyone who plays on emulators.

## Features

- Scans your existing games library and enchances it with metadata from [IGDB][igdb]
- Supports a large number of **[platforms][platform-support]**
- Play games directly from the browser using [EmulatorJS][wiki-emulatorjs-url]
- Built-in [authentication][authentication] with multiple users and permissions
- Supports [MAME][mame-xml-update], [Nintendo Switch][switch-titledb-update] and PS2 naming schemes
- Detects and groups **multifile games** (e.g. PS1 games with multiple CDs)
- Can [parse tags][tag-support] in filenames (e.g. (E), (USA), (rev v1), etc.)
- View, upload, update, and delete games from any modern web browser

## Preview

|                              🖥 Desktop                              |                                                  📱 Mobile                                                   |
| :-----------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------: |
| <img src=".github/resources/screenshots/romm-desktop-slider.gif" /> | <img style="width: 325px; aspect-ratio: auto;" src=".github/resources/screenshots/romm-mobile-slider.gif" /> |

# Installation

Before running the [image][docker-tags], ensure that Docker is installed and running on your system.

1. Generate an API key for [IGDB][igdb] and set the `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` variables. This step is essential for running a library scan. Instructions for generating the ID and Secret can be found [here][igdb-api]. Note that IGDB requires a Twitch account with 2FA enabled to generate the ID and Secret.
2. Verify that your library folder structure matches one of the options listed in the [folder structure][folder-structure] section.
3. Create a docker-compose file. Refer to the example [docker-compose.yml][docker-compose-example] file for guidance. Customize it for your setup and include the `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` variables in the environment section of the file.
4. Launch the container(s) with `docker-compose up -d`

### Troubleshooting

If you are having issues with RomM, please review the [wiki page][wiki-troubleshooting-url] for troubleshooting steps and common issues.

# Configuration

## Folder Structure

As mentioned in the installation section, RomM requires a specific folder structure to work. The two supported structures are as follows:

<table border="0">
 <tr>
    <th style="text-align: center"><b>Structure A (recommended)</b></tthd>
    <th style="text-align: center"><b>Structure B </b></th>
 </tr>
 <tr>
  <td>
    <code>library/roms/gbc/rom_1.gbc</code>
  </td>
  <td>
    <code>library/gbc/roms/rom_1.gbc</code>
  </td>
 </tr>
 <tr>
    <td>
      <pre>
        library/
        ├─ roms/
        │  ├─ gbc/
        │  │  ├─ rom_1.gbc
        │  │  ├─ rom_2.gbc
        │  │
        │  ├─ gba/
        │  │  ├─ rom_1.gba
        │  │  ├─ rom_2.gba
        │  │
        │  ├─ ps/
        │     ├─ my_multifile_game/
        │     │   ├─ my_game_cd1.iso
        │     │   ├─ my_game_cd2.iso
        │     │
        │     ├─ rom_1.iso
      </pre>
    </td>
    <td>
      <pre>
        library/
        ├─ gbc/
        │  ├─ roms/
        │     ├─ rom_1.gbc
        │     ├─ rom_2.gbc
        │
        ├─ gba/
        │  ├─ roms/
        │     ├─ rom_1.gba
        │     ├─ rom_2.gba
        │
        ├─ ps/
        │  ├─ roms/
        │     ├─ my_multifile_game/
        │     │  ├─ my_game_cd1.iso
        │     │  ├─ my_game_cd2.iso
        │     │
        │     ├─ rom_1.iso
      </pre>
    </td>
 </tr>
</table>

For folder naming conventions, review the [Platform Support][platform-support] section. To override default system names in the folder structure (if your directories are named differently), see the [Configuration File][configuration-file] section.

## Configuration File

RomM can be configured with a `config.yaml` file. Anytime that file is change, **you must restart the container for changes to take effect.** Refer to the [config.example.yml][configuration-file-example] file and the [docker-compose.example.yml][docker-compose-example] for guidance on how to configure it.

## Authentication

If you want to enable authentication and the user management system, a redis container is required, and some environment variables needs to be set. Complete instructions are available in the [wiki][wiki-authentication-url].

## Scheduler

The scheduler allows to scheduled async tasks that run in the Redis container at regular intervals. Jobs can be run at a specific time in the future, after a time delta, or at recurring internals using cron notation.

Jobs can be toggled using these environment variables:

```
ENABLE_SCHEDULED_RESCAN: Whether to rescan on a schedule
SCHEDULED_RESCAN_CRON: Cron expression for scheduled rescan
ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB: Whether to update the switch title database on a schedule
SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: Cron expression for scheduled switch title database update
ENABLE_SCHEDULED_UPDATE_MAME_XML: Whether to update the MAME XML on a schedule
SCHEDULED_UPDATE_MAME_XML_CRON: Cron expression for scheduled MAME XML update
```

### Scheduled rescan

Users can opt to enable scheduled rescans, and set the interval using cron notation. Not that the scan will **not completely rescan** every file, only catch those which have been added/updated.

### Switch titleDB update

Support was added for Nintendo Switch ROMs with filenames using the [titleid/programid format][titleid-program-id-url] (e.g. 0100000000010000.xci). If a file under the `switch` folder matches the regex, the scanner will use the index to attempt to match it to a game. If a match is found, the IGDB handler will use the matched name as the search term.

The associated task updates the `/fixtures/switch_titledb.json` file at a regular interval to support new game releases.

### MAME XML update

Support was also added for MAME arcade games with shortcode names (e.g. `actionhw.zip` -> ACTION HOLLYWOOD), and works in the same way as the titleid matcher (without the regex).

The associated task updates the `/fixtures/mame.xml` file at a regular interval to support updates to the library.

## Watchdog

A watchdog was added which monitors the filesystem for events (files created/moved/deleted) and schedules a rescan of the platform (or entire library is a new platform was added).

Jobs can be toggled using these environment variables:

```
ENABLE_RESCAN_ON_FILESYSTEM_CHANGE: Whether to rescan when the filesystem changes
RESCAN_ON_FILESYSTEM_CHANGE_DELAY: Delay in minutes before rescanning on filesystem change
```

The watcher will monitor the `/library/roms` folder for changes to the filesystem, such as files being added, moved or deleted. It will ignore certain events (like modifying the file content or metadata), and will skip default OS files (like `.DS_Store` on mac).

When a change is detected, a scan will be scheduled for sometime in the future (default 5 minutes). If other events are triggered between now and the time at which the scan starts, more platforms will be added to the scan list (or the scan may switch to a full scan). This is done to reduce the number of tasks scheduled when many big changes happen to the library (mass upload, new mount, etc.)

# Naming Convention

## Platform Support

If you adhere to the [RomM folder structure][folder-structure], RomM supports all platforms listed on the [Supported Platforms][wiki-supported-platforms-url] page. **The folder is is case sensitive and must be used exactly how it appears in the list.** When scanning your library, RomM will use the folder name to determine the platform and fetch the appropriate game information, metadata, and cover art.

Additionally, some of these platforms have custom icons available ([learn more about platform icons in our wiki][wiki-platforms-icons-url]).

## Tag Support

Games can be tagged with region, revision, or other tags by using parentheses in the file name. Additionally, you can set the region and language by adding a prefix: (USA), [reg-J], (French), [De].

- Revision tags must be prefixed with **"rev "** or **"rev-"** (e.g. **(rev v1)** or **(rev-1)**)
- Other tags will also be imported, for example: **my_game [1.0001]\(HACK\)[!].gba**

Tags can be used to search for games in the search bar. For example, searching for **(USA)** will return all games with the USA tag.

# Community

Here are a few projects maintained by members of our community. As they are not regularly reviewed by the RomM team, **we recommend you closely review them before use**.

- CasaOS app via the [BigBear App Store][big-bear-casaos]
- [Helm Chart to deploy on Kubernetes][kubernetes-helm-chart] by @psych0d0g

Join us on discord, where you can ask questions, submit ideas, get help, showcase your collection, and discuss RomM with other users.

[![discord-invite]][discord-invite-url]

## Support

If you like this project, consider buying me a coffee!

[![coffee-donate]][coffee-donate-url]

## Our Friends

Here are a few projects that we think you might like:

- [EmualtorJS](https://emulatorjs.org/): An embeddable, browser-based emulator
- [RetroDECK](https://retrodeck.net/): Retro gaming on SteamOS and Linux
- [ES-DE Frontend](https://es-de.org/): Emulator frontend for Linux, macOS and Windows
- [Gaseous](https://github.com/gaseous-project/gaseous-server): Another self-hosted ROM manager

<!-- Sections -->

[folder-structure]: #-folder-structure
[platform-support]: #-platform-support
[authentication]: #-authentication
[tag-support]: #-tag-support
[switch-titledb-update]: #-switch-titledb-update
[mame-xml-update]: #-mame-xml-update
[configuration-file]: #%EF%B8%8F-configuration-file

<!-- Files -->

[docker-compose-example]: examples/docker-compose.example.yml
[configuration-file-example]: examples/config.example.yml

<!-- Wiki links -->

[wiki-url]: https://github.com/zurdi15/romm/wiki
[wiki-supported-platforms-url]: https://github.com/zurdi15/romm/wiki/Supported-Platforms
[wiki-authentication-url]: https://github.com/zurdi15/romm/wiki/Authentication
[wiki-platforms-icons-url]: https://github.com/zurdi15/romm/wiki/Custom-Platform-Icons
[wiki-troubleshooting-url]: https://github.com/zurdi15/romm/wiki/Troubleshooting
[wiki-emulatorjs-url]: https://github.com/zurdi15/romm/wiki/EmulatorJS-Player

<!-- Badges -->

[license-badge]: https://img.shields.io/github/license/zurdi15/romm?style=for-the-badge&color=a32d2a
[license-badge-url]: LICENSE
[release-badge]: https://img.shields.io/github/v/release/zurdi15/romm?style=for-the-badge
[release-badge-url]: https://github.com/zurdi15/romm/releases
[discord-badge]: https://img.shields.io/badge/discord-7289da?style=for-the-badge
[discord-badge-url]: https://discord.gg/P5HtHnhUDH
[unraid-badge]: https://img.shields.io/badge/Unraid-f57842?style=for-the-badge&labelColor=ee512b
[unraid-badge-url]: https://forums.unraid.net/topic/149738-support-eurotimmy-romm-rom-manager-by-zurdi15/
[wiki-badge]: https://img.shields.io/badge/Wiki-736e9b?style=for-the-badge
[docker-pulls-badge]: https://img.shields.io/docker/pulls/zurdi15/romm?style=for-the-badge&label=pulls
[docker-pulls-badge-url]: https://hub.docker.com/r/zurdi15/romm

<!-- Links -->

[discord-invite]: https://invidget.switchblade.xyz/P5HtHnhUDH
[discord-invite-url]: https://discord.gg/P5HtHnhUDH
[coffee-donate]: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
[coffee-donate-url]: https://www.buymeacoff.ee/zurdi15

<!-- External links -->

[docker-tags]: https://hub.docker.com/r/zurdi15/romm/tags
[igdb]: https://www.igdb.com/
[igdb-api]: https://api-docs.igdb.com/#getting-started
[titleid-program-id-url]: https://switchbrew.org/w/index.php?title=Title_list/Games&mobileaction=toggle_view_desktop
[igdb-platforms-list]: https://www.igdb.com/platforms
[big-bear-casaos]: https://github.com/bigbeartechworld/big-bear-casaos
[kubernetes-helm-chart]: https://artifacthub.io/packages/helm/crystalnet/romm
[pc-mac-icons]: https://www.flaticon.com/free-icons/keyboard-and-mouse
[flaticon]: https://www.flaticon.com
[user-default-icon]: https://icons8.com/icon/tZuAOUGm9AuS/user-default
[icons8]: https://icons8.com
