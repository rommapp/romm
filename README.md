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
[![docs-badge-img]][docs]

  </div>
</div>

# Table of Contents

- [Table of Contents](#table-of-contents)
- [Overview](#overview)
  - [Features](#features)
  - [Preview](#preview)
- [Installation](#installation)
- [Contributing](#contributing)
- [Community](#community)
- [Technical Support](#technical-support)
- [Project Support](#project-support)
- [Our Friends](#our-friends)

# Overview

RomM (ROM Manager) allows you to scan, enrich, browse and play your game collection with a clean and responsive interface. With support for multiple platforms, various naming schemes, and custom tags, RomM is a must-have for anyone who plays on emulators.

## Features

- Scans and enhance your game library with metadata from [IGDB][igdb-api], [Screenscraper][screenscraper-api] and [MobyGames][mobygames-api]
- Fetch custom arwork from [SteamGridDB][steamgriddb-api]
- Display your achievements from [Retroachievements][retroachievements-api]
- Metadata available for [400+ platforms][docs-supported-platforms]
- Play games directly from the browser using [EmulatorJS][docs-emulatorjs] and [RuffleRS][docs-rufflers]
- Share your library with friends with limited access and permissions
- Official apps for [Playnite][playnite-app] and [muOS][muos-app]
- Supports mutli-disk games, DCLs, mods, hacks, patches, and manuals
- Parse and filter by [tags][docs-tag-support] in filenames
- View, upload, update, and delete games from any modern web browser

## Preview

|                                       🖥 Desktop                                       |                                                           📱 Mobile                                                            |
| :------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------: |
| <img src=".github/resources/screenshots/preview-desktop.webp" alt="desktop preview" /> | <img style="width: 325px; aspect-ratio: auto;" src=".github/resources/screenshots/preview-mobile.webp" alt="mobile preview" /> |

# Installation

To start using RomM, check out the [Quick Start Guide][docs-quick-start-guide] in the docs. If you are having issues with RomM, please review the page for [troubleshooting steps][docs-troubleshooting].

# Contributing

To contribute to RomM, please check [Contribution Guide](./CONTRIBUTING.md).

# Community

Here are a few projects maintained by members of our community. Please note that the RomM team does not regularly review their source code.

- [romm-comm][romm-comm-discord-bot]: Discord Bot by @idio-sync
- [DeckRommSync][deck-romm-sync]: SteamOS downloader and sync by @PeriBluGaming
- CasaOS app via the [BigBear App Store][big-bear-casaos]

Join us on Discord, where you can ask questions, submit ideas, get help, showcase your collection, and discuss RomM with other users.

[![discord-invite-img]][discord-invite]

# Technical Support

If you have any issues with RomM, please [open an issue](https://github.com/rommapp/romm/issues/new) in this repository.

# Project Support

Consider supporting the development of this project on Open Collective.

[![oc-donate-img]][oc-donate]

# Our Friends

Here are a few projects that we think you might like:

- [EmulatorJS](https://emulatorjs.org/): An embeddable, browser-based emulator
- [RetroDECK](https://retrodeck.net/): Retro gaming on SteamOS and Linux
- [ES-DE Frontend](https://es-de.org/): Emulator frontend for Linux, macOS and Windows
- [Gaseous](https://github.com/gaseous-project/gaseous-server): Another ROM manager with web-based emulator
- [Retrom](https://github.com/JMBeresford/retrom): A centralized game library/collection management service
- [Steam ROM Manager](https://steamgriddb.github.io/steam-rom-manager/): An app for managing ROMs in Steam

<!-- docs links -->

[docs]: https://docs.romm.app/latest/
[docs-quick-start-guide]: https://docs.romm.app/latest/Getting-Started/Quick-Start-Guide/
[docs-supported-platforms]: https://docs.romm.app/latest/Platforms-and-Players/Supported-Platforms/
[docs-emulatorjs]: https://docs.romm.app/latest/Platforms-and-Players/EmulatorJS-Player/
[docs-rufflers]: https://docs.romm.app/latest/Platforms-and-Players/RuffleRS-Player/
[docs-troubleshooting]: https://docs.romm.app/latest/Troubleshooting/Scanning-Issues/
[docs-tag-support]: https://docs.romm.app/latest/Getting-Started/Folder-Structure/#tag-support

<!-- Badges -->

[license-badge-img]: https://img.shields.io/github/license/rommapp/romm?style=for-the-badge&color=a32d2a
[license-badge]: LICENSE
[release-badge-img]: https://img.shields.io/github/v/release/rommapp/romm?style=for-the-badge
[release-badge]: https://github.com/rommapp/romm/releases
[discord-badge-img]: https://img.shields.io/badge/discord-7289da?style=for-the-badge
[discord-badge]: https://discord.gg/P5HtHnhUDH
[docs-badge-img]: https://img.shields.io/badge/docs-736e9b?style=for-the-badge
[docker-pulls-badge-img]: https://img.shields.io/docker/pulls/rommapp/romm?style=for-the-badge&label=pulls
[docker-pulls-badge]: https://hub.docker.com/r/rommapp/romm

<!-- Links -->

[discord-invite-img]: https://invidget.switchblade.xyz/P5HtHnhUDH
[discord-invite]: https://discord.gg/P5HtHnhUDH
[oc-donate-img]: https://opencollective.com/romm/donate/button.png?color=blue
[oc-donate]: https://opencollective.com/romm

<!-- External links -->

[igdb-api]: https://docs.romm.app/latest/Getting-Started/Generate-API-Keys/#igdb
[screenscraper-api]: https://docs.romm.app/latest/Getting-Started/Generate-API-Keys/#screenscraper
[mobygames-api]: https://docs.romm.app/latest/Getting-Started/Generate-API-Keys/#mobygames
[steamgriddb-api]: https://docs.romm.app/latest/Getting-Started/Generate-API-Keys/#steamgriddb
[retroachievements-api]: https://docs.romm.app/latest/Getting-Started/Generate-API-Keys/#retroachievements
[big-bear-casaos]: https://github.com/bigbeartechworld/big-bear-casaos
[romm-comm-discord-bot]: https://github.com/idio-sync/romm-comm
[deck-romm-sync]: https://github.com/PeriBluGaming/DeckRommSync-Standalone
[playnite-app]: https://github.com/rommapp/playnite-plugin
[muos-app]: https://github.com/rommapp/muos-app
