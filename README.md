<!-- trunk-ignore-all(markdownlint/MD033) -->
<!-- trunk-ignore(markdownlint/MD041) -->
<div align="center">
  <img src=".github/resources/isotipo.png" height="180px" width="auto" alt="romm logo">

  <h3 style="font-size: 25px;">
    A beautiful, powerful, self-hosted ROM manager and player.
  </h3>
</div>

<div align="center">
  <div dir="auto">
    <a href="https://trendshift.io/repositories/14133?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-14133" target="_blank" rel="noopener noreferrer"><img src=".github/resources/trendshift-badge.svg" alt="Trendshift" width="250" height="58"/></a>
    <a href="https://news.ycombinator.com/item?id=44247964" target="_blank" rel="noopener noreferrer"><img src=".github/resources/hackernews-badge.svg" width="250px" alt="hackernews badge"></a>
    <br />
    <a href="https://selfh.st/survey/2025-results/" target="_blank" rel="noopener noreferrer"><img src=".github/resources/selfhst-badge.svg" width="250px" alt="selfh.st badge"></a>
    <a href="https://discord.gg/invite/romm" target="_blank" rel="noopener noreferrer"><img src=".github/resources/discord-badge.svg" alt="Discord" width="250" height="58"/></a>
  </div>
</div>

# Overview

RomM (ROM Manager) allows you to scan, enrich, browse and play your game collection with a clean and responsive interface. With support for multiple platforms, various naming schemes, and custom tags, RomM is a must-have for anyone who plays on emulators.

## Features

- Scan and enhance your game library with metadata from [IGDB][igdb-api], [Screenscraper][screenscraper-api] and [MobyGames][mobygames-api]
- Fetch custom artwork from [SteamGridDB][steamgriddb-api]
- Display your achievements from [Retroachievements][retroachievements-api]
- Metadata available for [400+ platforms][docs-supported-platforms]
- Play games directly from the browser using [EmulatorJS][docs-emulatorjs] and [RuffleRS][docs-rufflers]
- Share your library with friends with limited access and permissions
- Official apps for [Playnite][playnite-app], [Android][argosy-launcher] and [CFWs][grout]
- Supports multi-disk games, DLCs, mods, hacks, patches, and manuals
- Parse and filter by [tags][docs-tag-support] in filenames
- View, upload, update, and delete games from any modern web browser

## Preview

|                                       🖥 Desktop                                       |                                                           📱 Mobile                                                            |
| :------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------: |
| <img src=".github/resources/screenshots/preview-desktop.webp" alt="desktop preview" /> | <img style="width: 325px; aspect-ratio: auto;" src=".github/resources/screenshots/preview-mobile.webp" alt="mobile preview" /> |

## Installation

To start using RomM, check out the [Quick Start Guide][docs-quick-start-guide] in the docs. If you are having issues with RomM, please review the page for [troubleshooting steps][docs-troubleshooting].

## Contributing

To contribute to RomM, please check [Contribution Guide](./CONTRIBUTING.md).

## Official apps

Apps and integrations built and maintained by the RomM team.

- [Argosy][argosy-launcher] by [@tmgast](https://github.com/tmgast): Native Android client for installing and launching games.
- [Grout][grout] by [@BrandonKowalski](https://github.com/BrandonKowalski): Download and manage games from your RomM instance directly on your Linux based retro handheld. Supports: Allium, Batocera, Knulli, MinUI, muOS, NextUI, Onion, ROCKNIX, Spruce, TrimUI
- [Playnite plugin][playnite-app] by [@gantoine](https://github.com/gantoine): Library plugin for Playnite

## Community

Here are a few projects maintained by members of our community. Please note that the RomM team does not regularly review their source code.

### Mobile

- [romm-ios-app][romm-ios-app]: Native iOS app by [@ilyas-hallak](https://github.com/ilyas-hallak)

### Desktop

- [RommBrowser][romm-browser]: Electron client by [@smurflabs](https://github.com/smurflabs)
- [RetroArch Sync][romm-retroarch-sync]: Sync RetroArch library with RomM by [@Covin90](https://github.com/Covin90)
- [RomMate][rommate]: Desktop app for browsing your collection by [@brenoprata10](https://github.com/brenoprata10)
- [romm-client][romm-client]: Desktop client by [@chaun14](https://github.com/chaun14)
- [Freegosy][freegosy]: All-in-one game manager (download, launch, sync saves, and manage emulators) by [@abduznik](https://github.com/abduznik)

### Handhelds

- [DeckyRommSync][decky-romm-sync]: SteamOS downloader and syncer by [@danielcopper](https://github.com/danielcopper)
- [SwitchRomM][switch-romm]: Homebrew NRO for Switch by [@Shalasere](https://github.com/Shalasere)

### Other

- [romm-comm][romm-comm-discord-bot]: Discord bot by [@idio-sync](https://github.com/idio-sync)
- [GGRequestz][ggrequestz]: Game discovery and request tool by [@XTREEMMAK](https://github.com/XTREEMMAK)
- [Syncthing sync][syncthing-sync]: Small tool to push a Syncthing library to RomM by [@amn-96](https://github.com/amn-96)

Join us on Discord, where you can ask questions, submit ideas, get help, showcase your collection, and discuss RomM with other users.

[![discord-invite-img]][discord-invite]

## Technical Support

If you have any issues with RomM, please [open an issue](https://github.com/rommapp/romm/issues/new) in this repository.

## Financial Support

Consider supporting the development of this project on Open Collective. All funds will be used to cover the costs of hosting, development, and maintenance of RomM.

[![oc-donate-img]][oc-donate]

## Our Friends

Here are a few projects that we think you might like:

- [EmulatorJS](https://emulatorjs.org/): An embeddable, browser-based emulator
- [RetroDECK](https://retrodeck.net/): Retro gaming on SteamOS and Linux
- [ES-DE Frontend](https://es-de.org/): Emulator frontend for Linux, macOS and Windows
- [Gaseous](https://github.com/gaseous-project/gaseous-server): Another ROM manager with web-based emulator
- [Retrom](https://github.com/JMBeresford/retrom): A centralized game library/collection management service
- [Drop](https://droposs.org/): Steam-like experience for DRM-free games
- [LanCommander](https://lancommander.app/): Digital game platform for PC games
- [Steam ROM Manager](https://steamgriddb.github.io/steam-rom-manager/): An app for managing ROMs in Steam

<!-- docs links -->

[docs-quick-start-guide]: https://docs.romm.app/latest/Getting-Started/Quick-Start-Guide/
[docs-supported-platforms]: https://docs.romm.app/latest/Platforms-and-Players/Supported-Platforms/
[docs-emulatorjs]: https://docs.romm.app/latest/Platforms-and-Players/EmulatorJS-Player/
[docs-rufflers]: https://docs.romm.app/latest/Platforms-and-Players/RuffleRS-Player/
[docs-troubleshooting]: https://docs.romm.app/latest/Troubleshooting/Scanning-Issues/
[docs-tag-support]: https://docs.romm.app/latest/Getting-Started/Folder-Structure/#tag-support

<!-- Links -->

[discord-invite-img]: https://invidget.switchblade.xyz/P5HtHnhUDH
[discord-invite]: https://discord.gg/P5HtHnhUDH
[oc-donate-img]: https://opencollective.com/romm/donate/button.png?color=blue
[oc-donate]: https://opencollective.com/romm

<!-- External links -->

[igdb-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#igdb
[screenscraper-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#screenscraper
[mobygames-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#mobygames
[steamgriddb-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#steamgriddb
[retroachievements-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#retroachievements
[romm-comm-discord-bot]: https://github.com/idio-sync/romm-comm
[decky-romm-sync]: https://github.com/danielcopper/decky-romm-sync
[switch-romm]: https://github.com/Shalasere/SwitchRomM
[romm-browser]: https://github.com/smurflabs/RommBrowser/
[playnite-app]: https://github.com/rommapp/playnite-plugin
[ggrequestz]: https://github.com/XTREEMMAK/ggrequestz
[syncthing-sync]: https://github.com/amn-96/romm_syncthing_sync
[romm-client]: https://github.com/chaun14/romm-client
[romm-retroarch-sync]: https://github.com/Covin90/romm-retroarch-sync
[rommate]: https://github.com/brenoprata10/rommate
[freegosy]: https://github.com/abduznik/freegosy
[grout]: https://github.com/rommapp/grout
[romm-ios-app]: https://github.com/ilyas-hallak/romm-ios-app
[argosy-launcher]: https://github.com/rommapp/argosy-launcher
