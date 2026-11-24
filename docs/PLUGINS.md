# Plugins

A plugin adds actions to RomM's game screen: one more button next to Play and Download, pointing at a URL of your choosing. That is enough to reach anything that speaks a URL, a desktop client on your own machine, a launcher, a companion app, a script behind a local web server.

Plugins are declarative. A manifest describes buttons, and nothing in a plugin folder runs on the server, so installing one cannot reach your library, your database or your credentials. The button opens a URL in the browser, and the browser hands a custom scheme to whatever handles it on that machine.

## Installing one

Two ways, and neither involves editing RomM:

- **Settings → Plugins → Add plugin.** Paste a URL to a `plugin.json` and the server fetches it, or paste the manifest body itself. The manifest is validated before it is written, so an install cannot store something the reader would then refuse, and a URL is only fetched over http(s) and only up to the manifest size limit.
- **Drop it on the shelf.** Copy the folder into the plugins directory. This is the option for a manifest kept beside the library, and for a server with no browser session to spare.

Removing one is the same page's Remove button, which deletes the plugin's folder. Only an administrator can install or remove: both routes need `users.write`, while reading the shelf needs only `roms.read`.

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

The shelf is read on every request and cached until a manifest changes, so a folder dropped in shows up on the next page load. No restart, no scan, no migration. A manifest that fails validation is skipped and logged, and the rest of the shelf still loads. A plugin folder is capped at 32 KiB, eight actions, 64 platform slugs and 64 plugins on the shelf, and a manifest that resolves outside the plugins folder (a symlink to somewhere else on disk) is refused.

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

| Field         | Required | Notes                                                                      |
| ------------- | -------- | -------------------------------------------------------------------------- |
| `id`          | yes      | Lowercase slug, unique on the shelf.                                       |
| `name`        | yes      | Shown as the plugin's name, 200 characters at most.                        |
| `version`     | no       | Free text, `0.0.0` when absent.                                            |
| `description` | no       | One line, not shown in the UI today.                                       |
| `author`      | no       | Free text.                                                                 |
| `homepage`    | no       | `http` or `https` only.                                                    |
| `actions`     | yes      | One to eight actions; a plugin without a usable action is skipped.         |
| `enabled`     | no       | `false` parks the plugin: its folder stays, and it adds nothing to the UI. |

### Actions

| Field       | Required | Notes                                                                                                                                                        |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`        | yes      | Lowercase slug, unique within the plugin.                                                                                                                    |
| `label`     | yes      | The button's tooltip and accessible name, 48 characters at most. Plugin labels are not translated.                                                           |
| `icon`      | no       | An `mdi-` icon name. Defaults to `mdi-puzzle-outline`.                                                                                                       |
| `image`     | no       | A logo URL (`http` or `https`) painted instead of the icon.                                                                                                  |
| `url`       | yes      | See placeholders below.                                                                                                                                      |
| `open`      | no       | `new-tab` (default) or `same-tab`.                                                                                                                           |
| `slot`      | no       | Where the action is drawn; `game.details` by default. See below.                                                                                             |
| `platforms` | no       | Platform slugs the action is offered on, e.g. `["ngc", "wii"]`. Omitted means every platform. A slug the game is also known by (`gc` for `ngc`) matches too. |

### Slots

A slot is one place in RomM that renders whatever plugins declare for it, so the same manifest can put a button on a game, an entry in the Play menu, or a link in Settings:

| Slot            | Where it lands                                                        |
| --------------- | --------------------------------------------------------------------- |
| `game.details`  | The action row on a game, beside Play and Download. The default.      |
| `game.play`     | A way to start the game, offered in the Play menu next to RomM's own. |
| `app.nav`       | An entry in the Settings navigation.                                  |
| `settings.page` | A row on Settings, Plugins.                                           |

A slot the UI does not render would be a button nobody can press, so an unknown one drops the action and logs it. `"play": true` from before slots existed still means `game.play`.

### Settings

A plugin may ask its user for values, and those values reach its URLs through
`{setting.<key>}`. The manifest describes the fields; the values live beside it,
in the plugin's own folder, and are checked against the manifest on every write.

```json
{
  "settings": [
    { "key": "address", "label": "Server address", "type": "url" },
    { "key": "token", "label": "API token", "type": "password" },
    {
      "key": "listed",
      "label": "Offer this action",
      "type": "boolean",
      "default": true
    }
  ]
}
```

| Field         | Required     | Notes                                                                                   |
| ------------- | ------------ | --------------------------------------------------------------------------------------- |
| `key`         | yes          | Lowercase slug, unique within the plugin.                                               |
| `label`       | yes          | The field's name in the form, 48 characters at most. Not translated.                    |
| `type`        | no           | `text` (default), `url`, `number`, `boolean`, `select`, `password`, `search`, `groups`. |
| `default`     | no           | Used until the user saves.                                                              |
| `help`        | no           | A line under the field.                                                                 |
| `placeholder` | no           | Hint text inside the field.                                                             |
| `required`    | no           | An empty value is refused when true.                                                    |
| `min`, `max`  | no           | Bounds for `number`.                                                                    |
| `options`     | for `select` | `[{ "value": "...", "label": "..." }]`, twelve at most.                                 |
| `source`      | for `search` | Where the choices come from; see below.                                                 |
| `fields`      | for `groups` | The fields one entry holds, eight at most.                                              |
| `max_items`   | no           | How many entries a `groups` field holds, eight at most; four when absent.               |

A `password` comes back blank to anyone who cannot manage plugins, and a value
saved by an older version is dropped when the manifest stops describing it.

#### Searchable lists

A `search` field holds an id from a list only the plugin's own source knows, so
RomM asks that source as the user types and shows what comes back. The list is
fetched on the server, through the same guard as everything else a manifest
names, and the address must be public.

```json
{
  "key": "handheld",
  "label": "Your handheld",
  "type": "search",
  "source": {
    "url": "https://www.emuready.com/api/mobile/trpc/devices.get",
    "query": { "input": "{\"json\":{\"search\":\"{query}\",\"limit\":20}}" },
    "items": "result.data.json.devices",
    "value": "id",
    "label": "{brandName} {modelName}",
    "limit": 20
  }
}
```

| Field   | Notes                                                                                                |
| ------- | ---------------------------------------------------------------------------------------------------- |
| `url`   | Must resolve to a public address.                                                                    |
| `query` | Parameters to send; `{query}` is replaced with what the user typed, escaped for the JSON it sits in. |
| `items` | Dotted path to the list in the reply.                                                                |
| `value` | Dotted path to what the field stores.                                                                |
| `label` | Dotted path to the text shown, or a template mixing several (`{brand.name} {modelName}`).            |
| `limit` | How many choices one search may offer, 50 at most.                                                   |

A source that cannot be reached empties the list and says why under the field;
the rest of the form still saves.

#### Lists of entries

A `groups` field is a list the user builds, one entry at a time. Each entry holds
the fields the manifest declares, and any of those fields may itself be a
`search`, which is how a machine's parts are each picked from their own list.

```json
{
  "key": "setups",
  "label": "Your PC setups",
  "type": "groups",
  "max_items": 4,
  "fields": [
    { "key": "name", "label": "Name" },
    {
      "key": "cpu",
      "label": "CPU",
      "type": "search",
      "source": { "...": "..." }
    },
    { "key": "memory", "label": "Memory (GB)", "type": "number", "min": 1 },
    {
      "key": "os",
      "label": "Operating system",
      "type": "select",
      "options": [{ "value": "WINDOWS", "label": "Windows" }]
    }
  ]
}
```

A list may not hold another list. Entries are stored as an array of objects in
the settings file, and an entry that loses every field the manifest still
declares is dropped rather than kept empty.

### Placeholders

A URL may interpolate the game the button was pressed on. Values are URL-encoded, so a title with `&` or `#` cannot rewrite the query string.

| Placeholder       | Value                                                               |
| ----------------- | ------------------------------------------------------------------- |
| `{rom_id}`        | RomM's id for the game.                                             |
| `{rom_name}`      | The game's display name.                                            |
| `{platform_slug}` | The platform's slug, e.g. `ngc`.                                    |
| `{platform_name}` | The platform's display name.                                        |
| `{file_name}`     | The ROM file's name, empty when the game resolves to several files. |

Any other placeholder is refused, so a manifest cannot ask for values the UI does not offer.

## Schemes

`http` and `https` open like any link. Anything else is treated as a custom scheme and handed to the OS, which is how a desktop app gets launched. `javascript`, `data`, `file`, `blob`, `vbscript` and `about` are refused, and so is a URL with whitespace or control characters.

A custom scheme only resolves on machines that have registered a handler. Elsewhere the browser asks what to do with the link, which is the behaviour a user expects from an app link.

The UI reads the shelf when a game page opens and keeps it for the session, so a plugin added while a tab is open appears on the next full page load.

## Example: RommDeck

[RommDeck](https://github.com/s0liton/RommDeck) downloads and syncs your RomM library to a machine with the emulators, and keeps your saves in step. Its plugin lives in its own repository, [rommdeck-plugin](https://github.com/jkoehler11/rommdeck-plugin), and adds a way to start a game from the Play chooser by handing it to a `rommdeck://` handler on the machine running RommDeck. A plugin is a manifest, so it is not part of RomM's source: install it from Settings, Plugins, or drop the folder on the shelf.
