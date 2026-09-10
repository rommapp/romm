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

|                                       🖥 Desktop                                        |                                                           📱 Mobile                                                            |
| :------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------: |
| <img src=".github/resources/screenshots/preview-desktop.webp" alt="desktop preview" /> | <img style="width: 325px; aspect-ratio: auto;" src=".github/resources/screenshots/preview-mobile.webp" alt="mobile preview" /> |

## Installation

To start using RomM, check out the [Quick Start Guide][docs-quick-start-guide] in the docs. If you are having issues with RomM, please review the page for [troubleshooting steps][docs-troubleshooting].

### One-click deploys

Prefer a hosted deploy over wiring up the stack yourself? Each of these platforms has a 1-click RomM install, with a setup guide in our docs.

<table align="center">
  <tr valign="top">
    <td align="center">
      <p><br /><img src=".github/resources/hostinger-logo.svg" height="44" alt="Hostinger logo" /><br /><b>Hostinger</b></p>
      <p>Starting at <b>$6.49/mo</b><br /><a href="https://docs.romm.app/latest/install/hostinger/">Setup guide</a></p>
      <p><a href="https://www.hostg.xyz/aff_c?offer_id=815&amp;aff_id=243561&amp;url_id=6779" target="_blank" rel="noopener noreferrer"><img src=".github/resources/hostinger-badge.svg" alt="Deploy on Hostinger" width="250" height="58" /></a></p>
    </td>
    <td align="center">
      <p><br /><img src=".github/resources/cloudzy-logo.svg" height="44" alt="Cloudzy logo" /><br /><b>Cloudzy</b></p>
      <p>Starting at <b>$2.48/mo</b><br /><a href="https://docs.romm.app/latest/install/cloudzy/">Setup guide</a></p>
      <p><a href="https://cloudzy.com/marketplace/romm" target="_blank" rel="noopener noreferrer"><img src=".github/resources/cloudzy-badge.svg" alt="Deploy on Cloudzy" width="250" height="58" /></a></p>
    </td>
    <td align="center">
      <p><br /><img src=".github/resources/railway-logo.svg" height="44" alt="Railway logo" /><br /><b>Railway</b></p>
      <p>Starting at <b>$5/mo</b><br /><a href="https://docs.romm.app/latest/install/railway/">Setup guide</a></p>
      <p><a href="https://railway.com/deploy/romm" target="_blank" rel="noopener noreferrer"><img src=".github/resources/railway-badge.svg" alt="Deploy on Railway" width="250" height="58" /></a></p>
    </td>
  </tr>
</table>

<sub><i>Deployment and infrastructure support for these installs is handled by the platform, not our team. Prices are indicative and may not reflect current offerings. Signups through the Hostinger link send a share of the revenue back to RomM, which helps fund the project.</i></sub>

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

- [RetroArch Sync][romm-retroarch-sync]: Sync RetroArch library with RomM by [@Covin90](https://github.com/Covin90)
- [RomMate][rommate]: Desktop app for browsing your collection by [@brenoprata10](https://github.com/brenoprata10)
- [romm-client][romm-client]: Desktop client by [@chaun14](https://github.com/chaun14)
- [Freegosy][freegosy]: All-in-one game manager by [@abduznik](https://github.com/abduznik)

### Handhelds

- [DeckyRommSync][decky-romm-sync]: SteamOS downloader and syncer by [@danielcopper](https://github.com/danielcopper)
- [SwitchRomM][switch-romm]: Homebrew NRO for Switch by [@Shalasere](https://github.com/Shalasere)

### Other

- [romm-comm][romm-comm-discord-bot]: Discord bot by [@idio-sync](https://github.com/idio-sync)
- [GGRequestz][ggrequestz]: Game discovery and request tool by [@XTREEMMAK](https://github.com/XTREEMMAK)
- [Syncthing sync][syncthing-sync]: Small tool to push a Syncthing library to RomM by [@amn-96](https://github.com/amn-96)

## Support the project

Consider supporting the development of this project on Open Collective. All funds will be used to cover the costs of hosting, development, and maintenance of RomM.

<div align="center">
  <div dir="auto">
    <a href="https://opencollective.com/romm" target="_blank" rel="noopener noreferrer"><img src=".github/resources/opencollective-badge.svg" alt="Open Collective" width="250" height="58"/></a>
  </div>
</div>

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

## Supported By

These companies support us by providing their tools for free:

<div align="center">
  <div dir="auto">
    <a href="https://www.greptile.com/?utm_source=oss_badge&amp;utm_medium=readme&amp;utm_campaign=greptile_for_open_source" target="_blank" rel="noopener noreferrer"><img src=".github/resources/greptile-badge.svg" alt="Greptile" width="250" height="58"/></a>
    <a href="https://www.aikido.dev/" target="_blank" rel="noopener noreferrer"><img src=".github/resources/aikido-badge.svg" alt="Aikido" width="250" height="58"/></a>
  </div>
</div>

<!-- docs links -->

[docs-quick-start-guide]: https://docs.romm.app/latest/Getting-Started/Quick-Start-Guide/
[docs-supported-platforms]: https://docs.romm.app/latest/Platforms-and-Players/Supported-Platforms/
[docs-emulatorjs]: https://docs.romm.app/latest/Platforms-and-Players/EmulatorJS-Player/
[docs-rufflers]: https://docs.romm.app/latest/Platforms-and-Players/RuffleRS-Player/
[docs-troubleshooting]: https://docs.romm.app/latest/Troubleshooting/Scanning-Issues/
[docs-tag-support]: https://docs.romm.app/latest/Getting-Started/Folder-Structure/#tag-support

<!-- External links -->

[igdb-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#igdb
[screenscraper-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#screenscraper
[mobygames-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#mobygames
[steamgriddb-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#steamgriddb
[retroachievements-api]: https://docs.romm.app/latest/Getting-Started/Metadata-Providers/#retroachievements
[romm-comm-discord-bot]: https://github.com/idio-sync/romm-comm
[decky-romm-sync]: https://github.com/danielcopper/decky-romm-sync
[switch-romm]: https://github.com/Shalasere/SwitchRomM
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
