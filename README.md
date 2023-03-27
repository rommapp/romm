<div align="center">
  <img src="romm.svg" height="128px" width="auto" alt="Gameyfin Logo">
  <h1 style="padding:20px;">RomM (Rom Manager)</h1>
  <br/><br/>
</div>

# Overview

Inspired by [Jellyfin](https://jellyfin.org/) and after found that the awesome [Gameyfin](https://github.com/grimsi/gameyfin) project is not supported for arm64 architectures (since my own homelab is only made by 3 rpis) and it is a general game library manager, I decided to develop my own game library solution, focused on retro gaming.

For now, it is only available as a docker [image](https://hub.docker.com/r/zurdi15/romm) (amd64/arm64)

## Features

* Scans your game library (all at once or by platform) and enriches it with IGDB metadata
* Access your library via your web-browser
* Possibility to select one of the matching IGDB results if the scan doesn't get the right one
* Download games directly from your web-browser
* Edit your game files directly from your web-browser
* Set a custom cover for each game [WIP]
* Upload games directly from your web-browser [WIP]
* Manage save files directly from your web-browser [WIP]
* Responsive design
* Light and dark theme

# Prerequisites

To allow RomM scan your retro games library, it should follow the following structure:

```
library/
├─ gbc/
│  ├─ roms/
│  │  ├─ rom_1.gbc
│  │  ├─ rom_2.gbc
|
├─ gba/
│  ├─ roms/
│  │  ├─ rom_1.gba
│  │  ├─ rom_2.gba
|
├─ gb/
│  ├─ roms/
│  │  ├─ rom_1.gb
│  │  ├─ rom_1.gb
```

# Preview

## Desktop

https://user-images.githubusercontent.com/34356590/227992371-33056130-c067-49c1-ae32-b3ba78db6798.mp4

## Mobile

https://user-images.githubusercontent.com/34356590/228007442-0a9cbf6b-4b62-4c1a-aad8-48b13e6337e8.mp4

# Docker image

Last version of the docker [image](https://hub.docker.com/r/zurdi15/romm/tags)

## Installation

Check the [docker-compose.yml](https://github.com/zurdi15/romm/blob/master/docker/docker-compose.example.yml) example

## Troubleshoot

After the first installation, sometimes the RomM container can have problems connecting with the database. Restarting the RomM container may solve the problem.
