# RommDeck plugin

Adds an "Open in RommDeck" button to every game. The button opens a
`rommdeck://open?rom=<id>&platform=<slug>&name=<title>` URL, which a handler on
the machine running [RommDeck](https://github.com/s0liton/RommDeck) turns into
"open RommDeck".

## Install

Copy this folder into the plugins directory and mount that directory into the
container:

```yaml
volumes:
  - ./plugins:/romm/plugins
```

## Register the handler

The URL means nothing until the machine that runs RommDeck knows the scheme. On
Linux, a `.desktop` entry with `MimeType=x-scheme-handler/rommdeck` that runs
`rommdeck-open %u`, registered with `xdg-mime default`, is enough; the script
receives the URL on the command line and opens RommDeck.

## Offer it only where RommDeck can play

RommDeck launches whatever emulators that machine has mapped, so a button on a
platform it cannot run is a dead end. Name those platforms on the action and the
button appears only on their games:

```json
"platforms": ["ngc", "wii"]
```

Leave `platforms` out to offer the button on every game.
