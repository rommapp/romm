# Migrating emulator streaming to webstation

This is about the **emulator streaming broker protocol** (`config.yml`'s
`streaming.containers`), not the frontend's v1/v2 UI split. Unrelated "v1/v2"
naming, don't confuse the two.

## What's changing

Emulator streaming used to mean one container per emulator, each running its
own broker mod (`pcsx2-romm-integration`, `dolphin-romm-integration`,
`xemu-romm-integration`, `rpcs3-romm-integration`).
Going forward, streaming goes through a single [docker-webstation][webstation]
container running [romm-broker][romm-broker], which can serve every platform
RomM streams from one place instead of one container per emulator.

The per-emulator broker mods are **deprecated**. A `config.yml` container
without `protocol: webstation` still works today, logs a startup warning
telling you to migrate, and will stop being supported in a future release.
See the per-emulator repo's own README for a "Migrating to webstation"
section with details specific to that emulator.

## Why

- One container to run and update instead of N forks of the same broker
  pattern, each drifting slightly.
- One save-state and memory-card contract instead of five slightly different
  ones.
- A platform pool (`platforms:` on one container) claims whichever instance
  is free, instead of every platform being pinned to its own single
  container.

## Migrating your `config.yml`

Before, one container per platform:

```yaml
streaming:
  containers:
    - platform: ps2
      host: https://192.168.1.51:3001
      broker_host: http://192.168.1.51:8000
      label: PCSX2
      memory_card_sync: true
    - platform: ngc
      host: https://192.168.1.52:3001
      broker_host: http://192.168.1.52:8000
      label: Dolphin
```

After, one webstation container serving both:

```yaml
streaming:
  containers:
    - host: https://192.168.1.56:3010
      protocol: webstation
      subfolder: /streaming
      library_path: /romm
      label: Emulation station
      platforms:
        ps2:
          emulator: pcsx2
          label: PCSX2
          memory_card_sync: true
        ngc:
          emulator: dolphin
          label: Dolphin
```

The full field reference lives in [`examples/config.example.yml`][example-config].

## Migrating your containers

1. Stand up [docker-webstation][webstation] with [romm-broker][romm-broker]
   mounted at your ROM library path (use the same path your old per-emulator
   containers used, so save/state history keyed to it doesn't reset).
2. Point `library_path` in `config.yml` at that same mount.
3. Move each platform you were streaming into the new container's
   `platforms:` map (see the before/after above).
4. Confirm streaming works for each platform, then remove the old
   per-emulator containers.
5. Restart RomM. The startup warning about legacy containers disappears once
   no `config.yml` container is missing `protocol: webstation`.

## Per-emulator notes

Save data, memory cards, and BIOS/firmware requirements don't change, only
which container runs the emulator. See the "Migrating to webstation"
section in:

- [pcsx2-romm-integration][pcsx2]
- [dolphin-romm-integration][dolphin]
- [xemu-romm-integration][xemu]
- [rpcs3-romm-integration][rpcs3]

[webstation]: https://github.com/linuxserver/docker-webstation
[romm-broker]: https://github.com/romm-streaming/romm-broker
[example-config]: ../examples/config.example.yml
[pcsx2]: https://github.com/LoneAngelFayt/pcsx2-romm-integration
[dolphin]: https://github.com/LoneAngelFayt/dolphin-romm-integration
[xemu]: https://github.com/LoneAngelFayt/xemu-romm-integration
[rpcs3]: https://github.com/LoneAngelFayt/rpcs3-romm-integration
