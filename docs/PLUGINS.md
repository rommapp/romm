# Plugins

A plugin adds actions to RomM's game screen: one more button next to Play and Download, pointing at a URL of your choosing. That is enough to reach anything that speaks a URL, a desktop client on your own machine, a launcher, a companion app, a script behind a local web server.

Plugins are declarative. A manifest describes buttons, and nothing in a plugin folder runs on the server, so installing one cannot reach your library, your database or your credentials. The button opens a URL in the browser, and the browser hands a custom scheme to whatever handles it on that machine.

## Where plugins live

Plugins are read from `PLUGINS_BASE_PATH`, which defaults to `$ROMM_BASE_PATH/plugins` (`/romm/plugins` in the container). Each plugin is one folder holding a `plugin.json`:

```text
/romm/plugins/
  rommdeck/
    plugin.json
```

Mount the folder so it survives container updates:

```yaml
services:
  romm:
    volumes:
      - ./plugins:/romm/plugins
```

The shelf is read on every request, so a manifest dropped in shows up on the next page load. No restart, no scan, no migration. A manifest that fails validation is skipped and logged, and the rest of the shelf still loads.

## The manifest

```json
{
  "id": "rommdeck",
  "name": "RommDeck",
  "version": "1.0.0",
  "description": "Open a game on the device RommDeck manages.",
  "author": "s0liton",
  "homepage": "https://github.com/s0liton/RommDeck",
  "actions": [
    {
      "id": "open",
      "label": "Open in RommDeck",
      "icon": "mdi-monitor-dashboard",
      "url": "rommdeck://open?rom={rom_id}&platform={platform_slug}",
      "open": "new-tab"
    }
  ]
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | Lowercase slug, unique on the shelf. |
| `name` | yes | Shown as the plugin's name, 200 characters at most. |
| `version` | no | Free text, `0.0.0` when absent. |
| `description` | no | One line, not shown in the UI today. |
| `author` | no | Free text. |
| `homepage` | no | `http` or `https` only. |
| `actions` | yes | One to eight actions; a plugin without a usable action is skipped. |

### Actions

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | Lowercase slug, unique within the plugin. |
| `label` | yes | The button's tooltip and accessible name, 48 characters at most. Plugin labels are not translated. |
| `icon` | no | An `mdi-` icon name. Defaults to `mdi-puzzle-outline`. |
| `url` | yes | See placeholders below. |
| `open` | no | `new-tab` (default) or `same-tab`. |

### Placeholders

A URL may interpolate the game the button was pressed on. Values are URL-encoded, so a title with `&` or `#` cannot rewrite the query string.

| Placeholder | Value |
| --- | --- |
| `{rom_id}` | RomM's id for the game. |
| `{rom_name}` | The game's display name. |
| `{platform_slug}` | The platform's slug, e.g. `ngc`. |
| `{platform_name}` | The platform's display name. |
| `{file_name}` | The ROM file's name, empty when the game resolves to several files. |

Any other placeholder is refused, so a manifest cannot ask for values the UI does not offer.

## Schemes

`http` and `https` open like any link. Anything else is treated as a custom scheme and handed to the OS, which is how a desktop app gets launched. `javascript`, `data`, `file`, `blob`, `vbscript` and `about` are refused, and so is a URL with whitespace or control characters.

A custom scheme only resolves on machines that have registered a handler. Elsewhere the browser asks what to do with the link, which is the behaviour a user expects from an app link.

## Example: RommDeck

[RommDeck](https://github.com/s0liton/RommDeck) downloads and syncs your RomM library to a machine with the emulators, and keeps your saves in step. The manifest in `examples/plugins/rommdeck` adds an "Open in RommDeck" button that hands the game to a `rommdeck://` handler on the machine running RommDeck.
