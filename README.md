<!-- trunk-ignore-all(markdownlint/MD033) -->
<!-- trunk-ignore(markdownlint/MD041) -->
<div align="center">

  <img src=".github/resources/isotipo.png" height="180px" width="auto" alt="romm logo">
  <br />
  <img src=".github/resources/logotipo.png" height="45px" width="auto" alt="romm logotype">

  <h3 style="font-size: 25px;">
    A beautiful, powerful, self-hosted rom manager.
  </h3>
  <br/>

[![license-badge-img]][license-badge]
[![release-badge-img]][release-badge]
[![docker-pulls-badge-img]][docker-pulls-badge]

[![discord-badge-img]][discord-badge]
[![unraid-badge-img]][unraid-badge]
[![docs-badge-img]][docs]

  </div>
</div>

# Table of Contents

- [Table of Contents](#table-of-contents)
- [Overview](#overview)
  - [Features](#features)
  - [Preview](#preview)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Configuration File](#configuration-file)
  - [Scheduler](#scheduler)
- [Naming Convention](#naming-convention)
  - [Platform Support](#platform-support)
  - [Tag Support](#tag-support)
- [Community](#community)
  - [Support](#support)
  - [Our Friends](#our-friends)

# Overview

RomM (ROM Manager) allows you to scan, enrich, browse and play your game collection with a clean and responsive interface. With support for multiple platforms, various naming schemes, and custom tags, RomM is a must-have for anyone who plays on emulators.

## Features

- Scans and enhance your game library with metadata from [IGDB][igdb-api], [Screenscraper][screenscraper-api] and [MobyGames][mobygames-api]
- Metadata available for [400+ platforms][platform-support]
- Play games directly from the browser using [EmulatorJS][docs-emulatorjs]
- Share your library with friends with limited access and permissions
- Official apps for [Playnite][playnite-app] and [muOS][muos-app]
- Supports mutli-disk games, DCLs, mods, hacks, patches, and manuals
- Parse and [filter by tags][tag-support] in filenames
- View, upload, update, and delete games from any modern web browser

## Preview

|                                       🖥 Desktop                                       |                                                           📱 Mobile                                                            |
| :------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------: |
| <img src=".github/resources/screenshots/preview-desktop.webp" alt="desktop preview" /> | <img style="width: 325px; aspect-ratio: auto;" src=".github/resources/screenshots/preview-mobile.webp" alt="mobile preview" /> |

# Installation

To start using RomM, check out the [Quick Start Guide][docs-quick-start-guide] in the docs. If you are having issues with RomM, please review the page for [troubleshooting steps][docs-troubleshooting] and common issues, or join the [Discord][discord-invite] for support from the community.

# Configuration

## Configuration File

RomM's "understanding" of your library can be configured with a `config.yaml` file or through the `config` tab in the `Control Panel` under the `Settings` section. Refer to the [example config.yml][configuration-file-example] file for guidance on how to configure it and the [example docker-compose.yml][docker-compose-example] file on how to mount it into the container.

## Scheduler

The scheduler allows you to schedule async tasks that run in the Redis container at regular intervals. Jobs can be run at a specific time in the future, after a time delta, or at recurring internals using cron notation. The [docs page on the scheduler][docs-scheduled-tasks] has more information on which tasks are available and how to enable them.

# Naming Convention

## Platform Support

If you adhere to the [RomM folder structure][folder-structure], RomM supports all platforms listed on the [Supported Platforms][docs-supported-platforms] page. **The folder is case-sensitive and must be used exactly as it appears on the list.** When scanning your library, RomM will use the folder name to determine the platform and fetch the appropriate game information, metadata, and cover art.

## Tag Support

Games can be tagged with region, revision, or other tags by using parentheses in the file name. Additionally, you can set the region and language by adding a prefix: (USA), [reg-J], (French), [De].

- Revision tags must be prefixed with **"rev "** or **"rev-"** (e.g. **(rev v1)** or **(rev-1)**)
- Other tags will also be imported, for example: **my_game [1.0001]\(HACK\)[!].gba**

Tags can be used to search for games in the search bar. For example, searching for **(USA)** will return all games with the USA tag.

# Community

Here are a few projects maintained by members of our community. Please note that the RomM team does not regularly review their source code.

- [romm-comm][romm-comm-discord-bot]: Discord Bot by @idio-sync
- [DeckRommSync][deck-romm-sync]: SteamOS downloader and sync by @PeriBluGaming
- CasaOS app via the [BigBear App Store][big-bear-casaos]

Join us on Discord, where you can ask questions, submit ideas, get help, showcase your collection, and discuss RomM with other users.

[![discord-invite-img]][discord-invite]

## Support

Consider supporting the development of this project on Open Collective.

[![oc-donate-img]][oc-donate]

## Our Friends

Here are a few projects that we think you might like:

- [EmulatorJS](https://emulatorjs.org/): An embeddable, browser-based emulator
- [RetroDECK](https://retrodeck.net/): Retro gaming on SteamOS and Linux
- [ES-DE Frontend](https://es-de.org/): Emulator frontend for Linux, macOS and Windows
- [Gaseous](https://github.com/gaseous-project/gaseous-server): Another ROM manager with web-based emulator
- [Retrom](https://github.com/JMBeresford/retrom): A centralized game library/collection management service
- [Steam ROM Manager](https://steamgriddb.github.io/steam-rom-manager/): An app for managing ROMs in Steam

<!-- Sections -->

[folder-structure]: #folder-structure
[platform-support]: #platform-support
[tag-support]: #tag-support
[configuration-file]: #configuration-file

<!-- Files -->

[docker-compose-example]: examples/docker-compose.example.yml
[configuration-file-example]: examples/config.example.yml

<!-- docs links -->

[docs]: https://docs.romm.app/latest/
[docs-supported-platforms]: https://docs.romm.app/latest/Platforms-and-Players/Supported-Platforms/
[docs-troubleshooting]: https://docs.romm.app/latest/Troubleshooting/Scanning-Issues/
[docs-emulatorjs]: https://docs.romm.app/latest/Platforms-and-Players/EmulatorJS-Player/
[docs-scheduled-tasks]: https://docs.romm.app/latest/Maintenance/Scheduled-Tasks/
[docs-quick-start-guide]: https://docs.romm.app/latest/Getting-Started/Quick-Start-Guide/

<!-- Badges -->

[license-badge-img]: https://img.shields.io/github/license/rommapp/romm?style=for-the-badge&color=a32d2a
[license-badge]: LICENSE
[release-badge-img]: https://img.shields.io/github/v/release/rommapp/romm?style=for-the-badge
[release-badge]: https://github.com/rommapp/romm/releases
[discord-badge-img]: https://img.shields.io/badge/discord-7289da?style=for-the-badge
[discord-badge]: https://discord.gg/P5HtHnhUDH
[unraid-badge-img]: https://img.shields.io/badge/Unraid-f57842?style=for-the-badge&labelColor=ee512b
[unraid-badge]: https://forums.unraid.net/topic/149738-support-eurotimmy-romm-rom-manager-by-zurdi15/
[docs-badge-img]: https://img.shields.io/badge/docs-736e9b?style=for-the-badge
[docker-pulls-badge-img]: https://img.shields.io/docker/pulls/rommapp/romm?style=for-the-badge&label=pulls
[docker-pulls-badge]: https://hub.docker.com/r/rommapp/romm

<!-- Links -->

[discord-invite-img]: https://invidget.switchblade.xyz/P5HtHnhUDH
[discord-invite]: https://discord.gg/P5HtHnhUDH
[oc-donate-img]: https://opencollective.com/romm/donate/button.png?color=blue
[oc-donate]: https://opencollective.com/romm

<!-- External links -->

[igdb-api]: https://api-docs.igdb.com/#account-creation
[screenscraper-api]: https://www.screenscraper.fr/membreinscription.php
[mobygames-api]: https://www.mobygames.com/info/api/
[big-bear-casaos]: https://github.com/bigbeartechworld/big-bear-casaos
[romm-comm-discord-bot]: https://github.com/idio-sync/romm-comm
[deck-romm-sync]: https://github.com/PeriBluGaming/DeckRommSync-Standalone
[playnite-app]: https://github.com/rommapp/playnite-plugin
[muos-app]: https://github.com/rommapp/muos-app
