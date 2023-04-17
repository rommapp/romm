<div align="center">
  <h1 style="padding:20px;"><img src="romm.svg" height="220px" width="auto" alt="RomM Logo"></h1>
  <img alt="GitHub" src="https://img.shields.io/github/license/zurdi15/romm?style=flat-square">
  <img alt="GitHub release (latest SemVer)" src="https://img.shields.io/github/v/release/zurdi15/romm?style=flat-square">
  <img alt="GitHub Workflow Status (with branch)" src="https://img.shields.io/github/actions/workflow/status/zurdi15/romm/image.yml?style=flat-square&branch=master">
  <a href="https://hub.docker.com/r/zurdi15/romm">
  <img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/zurdi15/romm?style=flat-square">
  <img alt="Docker Image Size (latest by date)" src="https://img.shields.io/docker/image-size/zurdi15/romm?style=flat-square">
</div>
<br>
<div align="center">
  <a href="https://www.buymeacoff.ee/zurdi15" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" target="_blank"></a>
</div>

# Overview

RomM (stands for Rom Manager) is a game library manager focused in retro gaming. Manage and organize all of your games from a web browser.

Inspired by [Jellyfin](https://jellyfin.org/) and after found that the awesome [Gameyfin](https://github.com/grimsi/gameyfin) project is not supported for arm64 architectures and it is a general game library manager, I decided to develop my own game library solution.

Available as a docker [image](https://hub.docker.com/r/zurdi15/romm) (amd64/arm64)

## ⚡ Features

* Scan your game library (all at once or by platform) and enriches it with IGDB metadata
* Access your library via your web-browser
* Possibility to select one of the matching IGDB results if the scan doesn't get the right one
* EmuDeck folder structure compatibility
* Multiple files games support
* Download games directly from your web-browser
* Edit your game files directly from your web-browser
* Region, revision/version and extra tags support
* Works with SQLite or MaridDB (SQLite by default)
* Responsive design
* Light and dark theme

## 🛠 Roadmap

* Upload games directly from your web-browser - [issue #54](https://github.com/zurdi15/romm/issues/54)
* Manage save files directly from your web-browser - [issue #55](https://github.com/zurdi15/romm/issues/55)
* Set a custom cover for each game - [issue #53](https://github.com/zurdi15/romm/issues/53)

# Preview

## 🖥 Desktop

<details><summary>Video preview</summary><p>https://user-images.githubusercontent.com/34356590/227992371-33056130-c067-49c1-ae32-b3ba78db6798.mp4</p></details>

## 📱 Mobile

<details><summary>Video preview</summary><p>https://user-images.githubusercontent.com/34356590/228007442-0a9cbf6b-4b62-4c1a-aad8-48b13e6337e8.mp4</p></details>

# Installation

## 🐳 Docker

Last version of the docker [image](https://hub.docker.com/r/zurdi15/romm/tags).

Check the [docker-compose.yml](https://github.com/zurdi15/romm/blob/master/docker/docker-compose.example.yml) example.

Get API key from [IGDB](https://api-docs.igdb.com/#about) for the CLIENT_ID and CLIENT_SECRET variables. 

# Configuration

## 📁 Folder structure

RomM accepts two different folder structure by priority.

RomM will try to find the structure 1 and if it doesn't exists, RomM will try to find structure 2.

  - Structure 1 (high priority) - roms folder at root of library folder:
  ```
  library/
  ├─ roms/
     ├─ gbc/
     │  ├─ rom_1.gbc
     │  ├─ rom_2.gbc
     │
     ├─ gba/
     │  ├─ rom_1.gba
     │  ├─ rom_2.gba
     │ 
     ├─ ps/
        ├─ my_multifile_game/
        │   ├─ my_game_cd1.iso
        │   ├─ my_game_cd2.iso
        │
        ├─ rom_1.iso
  ```
  - Structure 2 (low priority) - roms folder inside each platform folder
  ```
  library/
  ├─ gbc/
  │  ├─ roms/
  │     ├─ rom_1.gbc
  │     ├─ rom_2.gbc
  |
  ├─ gba/
  │  ├─ roms/
  │     ├─ rom_1.gba
  │     ├─ rom_2.gba
  |
  ├─ ps/
  │  ├─ roms/
  │     ├─ my_multifile_game/
  │     │  ├─ my_game_cd1.iso
  │     │  ├─ my_game_cd2.iso
  │     │
  │     ├─ rom_1.iso
  ```

## ⚙️ Config.yml file

RomM can be configured through a yml file. This is used to exclude platforms and/or roms to be scanned.

For a configuration change to take effect, RomM must be restarted.

Check the [config.yml](https://github.com/zurdi15/romm/blob/master/docker/config.example.yml) example.

Check the [docker-compose.yml](https://github.com/zurdi15/romm/blob/master/docker/docker-compose.example.yml) example to see how to bind it.

# Naming convention 

## 🎮 Platforms support

If the RomM [folder structure](#📁-folder-structure) is followed, any kind of platform/folder-name is supported for the core features. For having extra metadata as well as cover images and platforms icons, the following table shows how to name your platforms folders.
This will change over the time, adding games metadata for more platforms. Make sure that the platforms folder names are lowercase.

<br>
<details>
  <summary>Platforms support list</summary>
  <p>

| slug          | name                                | games metadata |
|---------------|-------------------------------------|     :----:     |
| 3ds             | Nintendo 3DS                        | ✅             |
| amiga           | Amiga                               | ✅             |
| arcade          | Arcade                              | ✅             |
| atari           | atari                               | ❌             |
| coleco          | coleco                              | ❌             |
| c64             | Commodore C64/128/MAX               | ✅             |
| cpc             | cpc                                 | ❌             |
| cps1            | cps1                                | ❌             |
| cps2            | cps2                                | ❌             |
| cps3            | cps3                                | ❌             |
| daphne          | daphne                              | ❌             |
| dc              | Dreamcast                           | ✅             |
| dos             | DOS                                 | ✅             |
| fairchild       | fairchild                           | ❌             |
| fba2012         | fba2012                             | ❌             |
| fbneo           | fbneo                               | ❌             |
| fds             | Family Computer Disk System         | ✅             |
| gb              | Game Boy                            | ✅             |
| gba             | Game Boy Advance                    | ✅             |
| gbc             | Game Boy Color                      | ✅             |
| gg              | gg                                  | ❌             |
| gw              | gw                                  | ❌             |
| intellivision   | Intellivision                       | ✅             |
| jaguar          | Atari Jaguar                        | ✅             |
| lynx            | Atari Lynx                          | ✅             |
| md              | md                                  | ❌             |
| megaduck        | megaduck                            | ❌             |
| ms              | ms                                  | ❌             |
| msx             | MSX                                 | ✅             |
| n64             | Nintendo 64                         | ✅             |
| nds             | Nintendo DS                         | ✅             |
| neocd           | neocd                               | ❌             |
| neogeo          | neogeo                              | ❌             |
| nes             | Nintendo Entertainment System       | ✅             |
| ngc             | Nintendo GameCube                   | ✅             |
| ngp             | ngp                                 | ❌             |
| odyssey         | odyssey                             | ❌             |
| pce             | pce                                 | ❌             |
| pcecd           | pcecd                               | ❌             |
| pico            | pico                                | ❌             |
| poke            | poke                                | ❌             |
| ps              | PlayStation                         | ✅             |
| ps2             | PlayStation 2                       | ✅             |
| ps3             | PlayStation 3                       | ✅             |
| ps4             | ps4                                 | ❌             |
| psp             | PlayStation Portable                | ✅             |
| psvita          | PlayStation Vita                    | ✅             |
| scummvm         | scummvm                             | ❌             |
| segacd          | Sega CD                             | ✅             |
| segasgone       | segasgone                           | ❌             |
| sgb             | sgb                                 | ❌             |
| sgfx            | sgfx                                | ❌             |
| snes            | Super Nintendo Entertainment System | ✅             |
| supervision     | supervision                         | ❌             |
| switch          | Nintendo Switch                     | ✅             |
| wii             | Wii                                 | ✅             |
| win             | PC (Microsoft Windows)              | ✅             |
| wiiu            | Wii U                               | ✅             |
| wonderswan      | WonderSwan                          | ✅             |
| wonderswan-color| WonderSwan Color                    | ✅             |
| xbox            | Xbox                                | ✅             |
| xbox360         | Xbox 360                            | ✅             |
| xboxone         | Xbox One                            | ✅             |

  </p>
</details>
<br>

## 📑 Tags support

Games can be tagged with region, revision or other tags using parenthesis in the file name. Region and revision tags must be built with the following reserved words:
  - Region tags must be prefixed with **"reg-"**: (reg-EUR) / (reg-USA) / (reg-Japan) / (reg-whatever)
  - Revision tags must be prefixed with **"rev-"**: (rev-1) / (rev-v2) / (rev-whatever)
  - Any other tag can have any structure
  - Example: **my_game (reg-EUR)(rev-1)(aditional_tag_1)(aditional_tag_2).gba**

Tags can be used with the search bar to help to filter your library.

# ⛏ Troubleshoot

* After the first installation, sometimes the RomM container can have problems connecting with the database. Restarting the RomM container may solve the problem.

# 🧾 References

* Complete [changelog](https://github.com/zurdi15/romm/blob/master/CHANGELOG.md)

# 🎖 Credits

* Pc icon support - <a href="https://www.flaticon.com/free-icons/keyboard-and-mouse" title="Keyboard and mouse icons">Keyboard and mouse icons created by Flat Icons - Flaticon</a>
